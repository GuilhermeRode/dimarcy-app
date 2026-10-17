"""Prospecting rules shared by the leads/contacts routers, the dashboard and the importer.

A lead's seller is never stored: it's the active seller whose region (seller_cities) has the
lead's city, so moving a city between sellers moves its leads with no migration.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md"""
import re
from collections import Counter
from datetime import date

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from .models import SALE_STATUSES, Contact, Customer, Lead, Order, SellerCity, User, customer_status
from .sales import _city_key

NEW_STORE_DAYS = 730  # "abriu recentemente": a new store is still choosing its suppliers


def normalize_cnpj(value: str | None) -> str:
    """Letters and digits only, uppercase — CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def city_owners(db: Session) -> dict[tuple[str, str], User]:
    """(city_key, state) -> the ACTIVE seller whose region has that city."""
    rows = db.query(SellerCity).join(User, SellerCity.user_id == User.id).filter(User.active.is_(True), User.role == "seller").all()
    return {(r.city_key, r.state): r.user for r in rows}


def lead_owner(owners: dict[tuple[str, str], User], lead: Lead) -> User | None:
    return owners.get((lead.city_key, lead.state))


def customer_cnpjs(db: Session) -> set[str]:
    return {normalize_cnpj(d) for (d,) in db.query(Customer.document) if d}


def visible_lead(db: Session, user: User, lead_id: int) -> Lead:
    """A seller only reaches leads of their region; an admin reaches every lead."""
    lead = db.get(Lead, lead_id)
    if lead and user.role != "admin":
        owner = lead_owner(city_owners(db), lead)
        if not owner or owner.id != user.id:
            lead = None
    if not lead:
        raise HTTPException(404, "Lead not found.")
    return lead


def active_customers_by_city(db: Session, today: date) -> Counter:
    """Company-wide count of 'active' customers per (city_key, state) — not scoped to a seller."""
    last = dict(db.query(Order.customer_id, func.max(Order.date))
                .filter(Order.status.in_(SALE_STATUSES)).group_by(Order.customer_id).all())
    counts: Counter = Counter()
    for cid, city, state in db.query(Customer.id, Customer.city, Customer.state).filter(Customer.city.isnot(None)):
        if customer_status(last.get(cid), today) == "active":
            counts[(_city_key(city), (state or "").strip().upper())] += 1
    return counts


def ranked_leads(db: Session, user: User, today: date, city: str = "", search: str = "",
                 seller_id: int | None = None) -> list[tuple[Lead, User | None]]:
    """New leads the user may see, best first: has phone/e-mail, opened within NEW_STORE_DAYS,
    more active customers in the city, opened most recently, name. `seller_id` (admin) 0 = no seller."""
    q = db.query(Lead).filter(Lead.status == "new")
    if user.role != "admin":
        q = q.join(SellerCity, and_(SellerCity.city_key == Lead.city_key, SellerCity.state == Lead.state)) \
             .filter(SellerCity.user_id == user.id)
    if city.strip():
        q = q.filter(Lead.city_key == _city_key(city))
    text = search.strip()
    if text:
        cnpj = normalize_cnpj(text)
        cond = Lead.name.ilike(f"%{text}%")
        q = q.filter(or_(cond, Lead.cnpj.contains(cnpj)) if len(cnpj) >= 3 else cond)
    known, owners, active = customer_cnpjs(db), city_owners(db), active_customers_by_city(db, today)

    rows = []
    # ponytail: ranks in Python (~60k new leads per state for the admin); SQL window function if slow
    for lead in q.all():
        if lead.cnpj in known:
            continue
        owner = lead_owner(owners, lead)
        if seller_id is not None and (owner.id if owner else 0) != seller_id:
            continue
        rows.append((lead, owner))

    def rank(row):
        lead = row[0]
        recent = lead.opened_at is not None and (today - lead.opened_at).days <= NEW_STORE_DAYS
        return (not (lead.phone or lead.email), not recent, -active[(lead.city_key, lead.state)],
                -(lead.opened_at.toordinal() if lead.opened_at else 0), lead.name)
    return sorted(rows, key=rank)


def lead_out(lead: Lead, owner: User | None) -> dict:
    return {"id": lead.id, "cnpj": lead.cnpj, "name": lead.name, "phone": lead.phone, "email": lead.email,
            "address": lead.address, "city": lead.city, "state": lead.state, "opened_at": lead.opened_at,
            "status": lead.status, "seller_id": owner.id if owner else None,
            "seller_name": owner.name if owner else None}


def due_follow_ups(db: Session, user: User, today: date) -> list[dict]:
    """The user's pending follow-ups: for each lead/customer, its LATEST contact, when that contact
    was registered by this user and its next_action_date is today or earlier. Discarded/converted
    leads and anything the user can no longer see are left out."""
    latest: dict[tuple, Contact] = {}
    # ponytail: every contact in Python; a "latest per target" subquery if this grows past ~50k contacts
    for ct in db.query(Contact).order_by(Contact.id):
        latest[(ct.lead_id, ct.customer_id)] = ct
    owners = city_owners(db) if user.role != "admin" else {}
    rows = []
    for ct in latest.values():
        if ct.user_id != user.id or ct.next_action_date is None or ct.next_action_date > today:
            continue
        if ct.lead_id:
            target, kind = ct.lead, "lead"
            if target.status != "new":
                continue
            if user.role != "admin" and getattr(lead_owner(owners, target), "id", None) != user.id:
                continue
        else:
            target, kind = ct.customer, "customer"
            if user.role != "admin" and target.owner_id != user.id:
                continue
        rows.append({"contact_id": ct.id, "lead_id": ct.lead_id, "customer_id": ct.customer_id,
                     "name": target.name, "kind": kind, "phone": target.phone, "channel": ct.channel,
                     "notes": ct.notes, "next_action_date": ct.next_action_date, "last_contact_at": ct.created_at})
    return sorted(rows, key=lambda r: (r["next_action_date"], r["name"]))
