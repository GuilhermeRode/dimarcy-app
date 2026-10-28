"""Prospecting rules shared by the leads/contacts routers, the dashboard and the importer.

A lead's seller is never stored: it's the active seller whose region (seller_cities) has the
lead's city, so moving a city between sellers moves its leads with no migration.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md"""
import re
from collections import Counter
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session, contains_eager

from .br_format import format_phone
from .models import SALE_STATUSES, Contact, Customer, Lead, Order, SellerCity, User, customer_status
from .sales import _city_key
from .settings_store import get_app_settings

REGION_ROLES = ("seller", "admin")  # an admin may also keep a region and work leads like a seller
ADMIN_QUEUE = ("pending", "contacted")  # the admin's first contact, before releasing to the seller
QUEUE = (*ADMIN_QUEUE, "new")  # the statuses the Prospecção list shows (and that get a score)
NO_ANSWER = "Não respondeu"  # the note of a "Não respondeu" attempt: not a conversation with the store
ESTABLISHED_DAYS = 5 * 365  # opened within 5 years: past the first months, still choosing suppliers


def normalize_cnpj(value: str | None) -> str:
    """Letters and digits only, uppercase — CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def city_owners(db: Session) -> dict[tuple[str, str], User]:
    """(city_key, state) -> the ACTIVE seller whose region has that city."""
    rows = db.query(SellerCity).join(User, SellerCity.user_id == User.id).options(contains_eager(SellerCity.user)) \
             .filter(User.active.is_(True), User.role.in_(REGION_ROLES)).all()
    return {(r.city_key, r.state): r.user for r in rows}


def lead_owner(owners: dict[tuple[str, str], User], lead: Lead) -> User | None:
    return owners.get((lead.city_key, lead.state))


def customer_cnpjs(db: Session) -> set[str]:
    return {normalize_cnpj(d) for (d,) in db.query(Customer.document) if d}


def leads_open(db: Session, user: User) -> bool:
    """Prospecção may be admin-only for now (Configurações: leads_for_sellers off)."""
    return user.role == "admin" or get_app_settings(db).leads_for_sellers


def check_leads_open(db: Session, user: User) -> None:
    if not leads_open(db, user):
        raise HTTPException(403, "A Prospecção está desativada para vendedores.")


def visible_lead(db: Session, user: User, lead_id: int) -> Lead:
    """A seller only reaches leads of their region; an admin reaches every lead."""
    check_leads_open(db, user)
    lead = db.get(Lead, lead_id)
    if lead and user.role != "admin":
        if lead.status in ADMIN_QUEUE:  # awaiting admin release: invisible to sellers
            raise HTTPException(404, "Lead não encontrado.")
        owner = lead_owner(city_owners(db), lead)
        if not owner or owner.id != user.id:
            lead = None
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
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


def receita_phone(ddd: str, number: str) -> str | None:
    """A Receita phone (DDD and number in separate columns) as "(47) 99735-3510". Mobiles mostly come in the
    old 8-digit form: an 8-digit number starting with 6-9 gets the 9th digit every Brazilian mobile has had
    since 2016, or WhatsApp can't find it. Placeholders ("99999999", "00000000") are dropped; anything that
    isn't DDD + 8/9 digits is kept as "DDD number"."""
    d, n = re.sub(r"\D", "", ddd or "").lstrip("0"), re.sub(r"\D", "", number or "")
    if len(set(n)) <= 1 or len(n) < 7:  # "", "0", "99999999": no number at all
        return None
    if len(n) == 8 and n[0] in "6789":
        n = "9" + n
    if len(d) == 2 and len(n) in (8, 9):
        return format_phone(d + n)
    return f"{d} {n}".strip()


def is_mobile(phone: str | None) -> bool:
    """9 digits starting with 9 after the DDD — receita_phone adds the 9th digit to old 8-digit mobiles;
    8 starting with 6-9 still counts, for phones stored before that ("47 99735351")."""
    number = re.sub(r"\D", "", (phone or "").split(" ")[-1])
    return (len(number) == 9 and number[0] == "9") or (len(number) == 8 and number[0] in "6789")


SHARED_PHONE = 3  # the same phone on this many queued leads: most likely the accountant's, not the store's


def lead_score(lead: Lead, active_in_city: int, today: date, shared_phone: bool = False) -> int:
    """Points that order the queue; nothing here removes a lead (0-15):
    mobile phone 3 (landline 1; none or shared with other leads 0) · no federal debt 3 (not checked 1) ·
    capital ≥ R$ 50 mil 3, ≥ R$ 10 mil 2, ≥ R$ 1 mil 1 · opened within ESTABLISHED_DAYS 2 · e-mail 1 ·
    active Di Marcy customers in the city, up to 3."""
    capital = float(lead.capital or 0)
    phone = None if shared_phone else lead.phone
    return ((3 if is_mobile(phone) else 1 if phone else 0)
            + (3 if lead.in_debt is False else 1 if lead.in_debt is None else 0)
            + (3 if capital >= 50_000 else 2 if capital >= 10_000 else 1 if capital >= 1_000 else 0)
            + (2 if lead.opened_at and (today - lead.opened_at).days <= ESTABLISHED_DAYS else 0)
            + (1 if lead.email else 0)
            + min(active_in_city, 3))


def refresh_scores(db: Session, today: date) -> int:
    """Stores lead_score and the city's active-customer count on every queued lead, so the list ranks in
    SQL (ORDER BY ... LIMIT) instead of loading ~55k leads per request (that took ~5 s and ~200 MB).
    Runs on every daily import (lead_import.main) and whenever a queued lead has no score yet."""
    active = active_customers_by_city(db, today)
    rows = db.query(Lead.id, Lead.phone, Lead.email, Lead.capital, Lead.in_debt, Lead.opened_at,
                    Lead.city_key, Lead.state).filter(Lead.status.in_(QUEUE)).all()
    uses = Counter(r.phone for r in rows if r.phone)
    updates = []
    for r in rows:
        n = active[(r.city_key, r.state)]
        shared = uses[r.phone] >= SHARED_PHONE if r.phone else False
        updates.append({"id": r.id, "score": lead_score(r, n, today, shared), "city_active": n})
    if updates:
        db.execute(update(Lead), updates)  # ORM bulk UPDATE by primary key
    db.commit()
    return len(updates)


def ensure_scores(db: Session, today: date) -> None:
    """New leads (an import, the first run after the deploy) have no score until the next refresh."""
    if db.query(Lead.id).filter(Lead.status.in_(QUEUE), Lead.score.is_(None)).first():
        refresh_scores(db, today)


def _normalized_document():
    """Customer.document as digits/letters only, in SQL — matches Lead.cnpj (normalize_cnpj)."""
    d = Customer.document
    for ch in (".", "/", "-", " "):
        d = func.replace(d, ch, "")
    return func.upper(d)


def ranked_leads(db: Session, user: User, city: str = "", search: str = "",
                 seller_id: int | None = None, status: str = "new"):
    """Query of the leads the user may see, best first: stored score, then more active customers in the
    city, opened most recently, name. `seller_id` (admin) 0 = no seller. Callers .count() / .offset().limit()."""
    q = db.query(Lead).filter(Lead.status == status,
                              ~Lead.cnpj.in_(select(_normalized_document()).where(Customer.document.isnot(None))))
    # a lead's seller: the ACTIVE seller whose region has its city (see city_owners)
    owner = select(SellerCity.id).join(User, SellerCity.user_id == User.id).where(
        SellerCity.city_key == Lead.city_key, SellerCity.state == Lead.state, User.active.is_(True), User.role.in_(REGION_ROLES))
    if user.role != "admin":
        q = q.filter(owner.where(SellerCity.user_id == user.id).exists())
    elif seller_id == 0:
        q = q.filter(~owner.exists())
    elif seller_id is not None:
        q = q.filter(owner.where(SellerCity.user_id == seller_id).exists())
    if city.strip():  # typed in the Cidade pill: part of the name, accents ignored ("rio" -> Rio do Sul, Rio Negrinho)
        q = q.filter(Lead.city_key.contains(_city_key(city)))
    text = search.strip()
    if text:
        # name or city, accents ignored: the Receita sends names without accents ("florianópolis" finds FLORIANOPOLIS)
        plain = _city_key(text)
        conds = [Lead.name.ilike(f"%{text}%"), Lead.name.ilike(f"%{plain}%"), Lead.city_key.contains(plain)]
        cnpj = normalize_cnpj(text)
        if len(cnpj) >= 3:
            conds.append(Lead.cnpj.contains(cnpj))
        q = q.filter(or_(*conds))
    return q


def rank_order(q):
    # coalesce: SQLite and Postgres disagree on where NULLs go in DESC
    return q.order_by(func.coalesce(Lead.score, -1).desc(), func.coalesce(Lead.city_active, 0).desc(),
                      func.coalesce(Lead.opened_at, date(1900, 1, 1)).desc(), Lead.name, Lead.id)


def released_this_week(db: Session, seller_id: int) -> int:
    """Leads released (pending -> new) in the last 7 days in the seller's region: Prospecção suggests
    the admin release the rest of the weekly quota (Configurações), so nobody gets thousands at once."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=7)
    return db.query(Lead).join(SellerCity, and_(SellerCity.city_key == Lead.city_key, SellerCity.state == Lead.state)) \
             .filter(SellerCity.user_id == seller_id, Lead.released_at >= since).count()


def lead_out(lead: Lead, owner: User | None) -> dict:
    return {"id": lead.id, "cnpj": lead.cnpj, "name": lead.name, "phone": lead.phone, "email": lead.email,
            "address": lead.address, "city": lead.city, "state": lead.state, "opened_at": lead.opened_at, "size": lead.size,
            "capital": float(lead.capital) if lead.capital is not None else None, "in_debt": lead.in_debt,
            "score": getattr(lead, "score", None), "status": lead.status, "seller_id": owner.id if owner else None,
            "seller_name": owner.name if owner else None}


def due_follow_ups(db: Session, user: User, today: date) -> list[dict]:
    """The user's pending follow-ups: for each lead/customer, its LATEST contact, when its next_action_date
    is today or earlier and the follow-up is the user's: whoever registered the contact, except a lead's —
    every admin's while it's in the admin queue, its seller's once released (the admin's return passes on).
    Discarded/converted leads and anything the user can no longer see are left out."""
    latest: dict[tuple, Contact] = {}
    # ponytail: every contact in Python; a "latest per target" subquery if this grows past ~50k contacts
    for ct in db.query(Contact).order_by(Contact.id):
        latest[(ct.lead_id, ct.customer_id)] = ct
    due = [ct for ct in latest.values() if ct.next_action_date and ct.next_action_date <= today]
    if not due:
        return []
    owners = city_owners(db)
    names = dict(db.query(User.id, User.name))  # "vendedor X · feito por Y" without a query per row
    with_leads = leads_open(db, user)  # Prospecção off for sellers: their lead follow-ups wait too
    rows = []
    for ct in due:
        if ct.lead_id:
            if not with_leads:
                continue
            target, kind = ct.lead, "lead"
            if target is None or target.status not in QUEUE:
                continue
            seller = lead_owner(owners, target)
            if target.status in ADMIN_QUEUE:
                if user.role != "admin":
                    continue
            elif (seller.id if seller else ct.user_id) != user.id:
                continue
            seller_name = seller.name if seller else None
        else:
            target, kind = ct.customer, "customer"
            if target is None or ct.user_id != user.id:
                continue
            if user.role != "admin" and target.owner_id != user.id:
                continue
            seller_name = names.get(target.owner_id)
        rows.append({"contact_id": ct.id, "lead_id": ct.lead_id, "customer_id": ct.customer_id,
                     "name": target.name, "kind": kind, "phone": target.phone, "channel": ct.channel,
                     "seller_name": seller_name, "user_name": names.get(ct.user_id),
                     "notes": ct.notes, "next_action_date": ct.next_action_date, "last_contact_at": ct.created_at})
    return sorted(rows, key=lambda r: (r["next_action_date"], r["name"]))
