from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from .. import clock, lead_import
from ..database import get_db
from ..leads import (NO_ANSWER, QUEUE, REGION_ROLES, SHARED_PHONE, active_customers_by_city, check_leads_open, lead_score, city_owners, customer_cnpjs, ensure_scores, lead_out, lead_owner, normalize_cnpj, rank_order,
                     ranked_leads, released_this_week, visible_lead)
from ..models import Contact, Lead, SellerCity, User
from ..sales import _city_key
from ..br_format import format_phone
from ..schemas import BulkDiscardIn, CustomerOut, DiscardIn, LeadCreateIn, LeadEditIn, ReleaseToIn
from ..security import get_current_user, require_admin
from ..settings_store import get_app_settings
from .customers import add_customer, geocode_later, new_customer_in


def _leads_open(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    check_leads_open(db, user)


router = APIRouter(prefix="/leads", tags=["leads"], dependencies=[Depends(_leads_open)])
ALREADY_HANDLED = "Este lead já foi tratado."


@router.get("")
def list_leads(city: str = "", search: str = "", seller_id: int | None = None,
               status: Literal["pending", "contacted", "new"] = "new",
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    admin = user.role == "admin"  # only the admin may list pending leads
    ensure_scores(db, clock.today_br())
    q = ranked_leads(db, user, city, search, seller_id if admin else None, status if admin else "new")
    owners = city_owners(db)
    page = [(lead, lead_owner(owners, lead, user)) for lead in rank_order(q).offset(offset).limit(limit)]
    latest: dict[int, Contact] = {}  # the list shows where the seller left off
    for ct in db.query(Contact).filter(Contact.lead_id.in_([lead.id for lead, _ in page])).order_by(Contact.id):
        latest[ct.lead_id] = ct
    items = [{**lead_out(lead, owner), "seller_name": ", ".join(s.name for s in owners.get((lead.city_key, lead.state), [])) or None,
              "last_contact_at": getattr(latest.get(lead.id), "created_at", None),
              "next_action_date": getattr(latest.get(lead.id), "next_action_date", None)} for lead, owner in page]
    out = {"items": items, "total": q.count(),
           "cities": sorted(c for (c,) in q.with_entities(Lead.city).distinct())}  # for the screen's city filter
    if admin and status == "contacted" and seller_id:  # the weekly suggestion for that seller
        out["week"] = {"released": released_this_week(db, seller_id), "quota": get_app_settings(db).lead_weekly_release}
    return out


@router.post("/release", dependencies=[Depends(require_admin)])
def release(data: ReleaseToIn, db: Session = Depends(get_db)):
    """Contacted -> new (only after the admin's first contact) for leads whose city has an active seller. With `seller_id`, a lead whose city has
    NO active seller gets that city added to the seller's region (so the city's other leads follow);
    a city that already belongs to another active seller stays theirs (a city has one seller)."""
    seller = None
    if data.seller_id is not None:
        seller = db.get(User, data.seller_id)
        if not seller or seller.role not in REGION_ROLES or not seller.active:
            raise HTTPException(400, "Vendedor inválido ou inativo.")
    owners = city_owners(db)
    leads = db.query(Lead).filter(Lead.id.in_(data.ids), Lead.status == "contacted").all()
    ok, other, added = [], {}, []
    for lead in leads:
        owner = lead_owner(owners, lead, seller)
        if owner is None and seller:
            # the row may exist for an inactive seller: hand it over
            sc = db.query(SellerCity).filter_by(city_key=lead.city_key, state=lead.state).first()
            if sc:
                sc.user_id = seller.id
            else:
                db.add(SellerCity(user_id=seller.id, city=lead.city, state=lead.state, city_key=lead.city_key))
            owner = seller
            owners[(lead.city_key, lead.state)] = [seller]
            added.append(f"{lead.city}/{lead.state}")
        if owner is None:
            continue
        if seller and owner.id != seller.id:
            other[owner.name] = other.get(owner.name, 0) + 1
            continue
        ok.append(lead.id)
    if ok:
        db.query(Lead).filter(Lead.id.in_(ok), Lead.status == "contacted").update(
            {"status": "new", "released_at": lead_import.utcnow()}, synchronize_session=False)
    db.commit()
    skipped_other = sum(other.values())
    return {"released": len(ok), "skipped_no_seller": len(leads) - len(ok) - skipped_other,
            "skipped_other_seller": other, "cities_added": sorted(set(added))}


@router.post("/discard", dependencies=[Depends(require_admin)])
def discard_many(data: BulkDiscardIn, db: Session = Depends(get_db)):
    """The admin takes leads out of the queue ("Não recomendar"); the import never brings them back."""
    done = db.query(Lead).filter(Lead.id.in_(data.ids), Lead.status.in_(QUEUE)) \
             .update({"status": "discarded", "discard_reason": data.reason}, synchronize_session=False)
    db.commit()
    return {"discarded": done}


@router.get("/my-cities")
def my_cities(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The user's region: where a seller may type in a lead of their own."""
    return [{"city": r.city, "state": r.state}
            for r in db.query(SellerCity).filter(SellerCity.user_id == user.id).order_by(SellerCity.city)]


@router.get("/{lid}")
def get_lead(lid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = visible_lead(db, user, lid)
    return lead_out(lead, lead_owner(city_owners(db), lead))


def _typed_fields(data: LeadEditIn) -> dict:
    fields = {k: (v or "").strip() or None for k, v in data.model_dump().items()}
    if not fields["name"]:
        raise HTTPException(422, "Informe o nome da loja.")
    fields["phone"] = format_phone(fields["phone"])
    return fields


def _checked_cnpj(db: Session, value: str | None) -> str | None:
    cnpj = normalize_cnpj(value) or None  # blank: "a confirmar", the order asks for it
    if cnpj:
        if len(cnpj) != 14:
            raise HTTPException(422, "CNPJ inválido.")
        if db.query(Lead.id).filter(Lead.cnpj == cnpj).first():
            raise HTTPException(409, "Esse CNPJ já está na Prospecção.")
        if cnpj in customer_cnpjs(db):
            raise HTTPException(409, "Esse CNPJ já é cliente.")
    return cnpj


@router.post("", status_code=201)
def create_lead(data: LeadCreateIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """A lead typed in by hand; edited=True: the import neither overwrites nor drops it. The admin's starts
    pending and is released the usual way; a seller's must be in their region and is already theirs (new)."""
    fields = _typed_fields(data)
    fields["cnpj"] = _checked_cnpj(db, fields["cnpj"])
    fields["state"] = fields["state"].upper()
    city_key = _city_key(fields["city"])
    status = "pending"
    if user.role != "admin":
        if not db.query(SellerCity.id).filter_by(user_id=user.id, city_key=city_key, state=fields["state"]).first():
            raise HTTPException(422, "Essa cidade não está na sua região.")
        status = "new"  # no released_at: it doesn't use up the weekly release quota (released_this_week)
    today = clock.today_br()
    # scored now: a lead without a score makes the next list load re-score the whole queue (ensure_scores)
    n = active_customers_by_city(db, today)[(city_key, fields["state"])]
    shared = bool(fields["phone"]) and db.query(Lead.id).filter(
        Lead.phone == fields["phone"], Lead.status.in_(QUEUE)).count() + 1 >= SHARED_PHONE
    lead = Lead(**fields, city_key=city_key, status=status, edited=True, seen_at=today, city_active=n)
    lead.score = lead_score(lead, n, today, shared)
    db.add(lead)
    db.commit()
    return lead_out(lead, lead_owner(city_owners(db), lead))


@router.put("/{lid}", dependencies=[Depends(require_admin)])
def edit_lead(lid: int, data: LeadEditIn, db: Session = Depends(get_db)):
    lead = db.get(Lead, lid)
    if not lead:
        raise HTTPException(404, "Lead não encontrado.")
    fields = _typed_fields(data)
    cnpj = fields.pop("cnpj")
    if not lead.cnpj:
        lead.cnpj = _checked_cnpj(db, cnpj)
    for k, v in fields.items():
        setattr(lead, k, v)
    lead.edited = True
    db.commit()
    return lead_out(lead, lead_owner(city_owners(db), lead))


@router.post("/{lid}/convert", response_model=CustomerOut, status_code=201)
def convert(lid: int, background_tasks: BackgroundTasks, body: dict = Body(...),
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lead -> customer in one transaction; the lead's contacts move to the customer."""
    lead = visible_lead(db, user, lid)
    data = new_customer_in(body, user)
    if user.role == "admin":
        owner = lead_owner(city_owners(db), lead)
        owner_id = data.owner_id or (owner.id if owner else None)
    else:
        owner_id = user.id
    c = add_customer(db, data, owner_id)
    db.flush()
    # conditional UPDATE: a double click converts once, the second request gets 409
    done = db.query(Lead).filter(Lead.id == lid, Lead.status.in_(QUEUE)) \
             .update({"status": "converted", "customer_id": c.id}, synchronize_session=False)
    if not done:
        db.rollback()
        raise HTTPException(409, ALREADY_HANDLED)
    db.query(Contact).filter(Contact.lead_id == lid) \
      .update({"customer_id": c.id, "lead_id": None}, synchronize_session=False)
    db.commit()
    db.refresh(c)
    geocode_later(c, background_tasks)
    return c


NO_ANSWER_RETRY_DAYS, NO_ANSWER_LIMIT = 7, 3


@router.post("/{lid}/no-answer")
def no_answer(lid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Logs a WhatsApp attempt with no reply and a retry in 7 days; the 3rd one discards the lead."""
    if visible_lead(db, user, lid).status not in QUEUE:
        raise HTTPException(409, ALREADY_HANDLED)
    retry = clock.today_br() + timedelta(days=NO_ANSWER_RETRY_DAYS)
    db.add(Contact(lead_id=lid, user_id=user.id, channel="whatsapp", notes=NO_ANSWER, next_action_date=retry))
    db.flush()
    tries = db.query(Contact).filter(Contact.lead_id == lid, Contact.notes == NO_ANSWER).count()
    discarded = tries >= NO_ANSWER_LIMIT
    if discarded:
        db.query(Lead).filter(Lead.id == lid).update({"status": "discarded", "discard_reason": "no_answer"},
                                                     synchronize_session=False)
    db.commit()
    return {"tries": tries, "discarded": discarded, "retry_on": None if discarded else retry}


@router.post("/{lid}/first-contact", status_code=204, dependencies=[Depends(require_admin)])
def move_to_first_contact(lid: int, db: Session = Depends(get_db)):
    """Pendentes -> Primeiro contato by hand: no contact is logged, the admin only sorts the queue."""
    if not db.query(Lead).filter(Lead.id == lid, Lead.status == "pending").update({"status": "contacted"}, synchronize_session=False):
        raise HTTPException(409, ALREADY_HANDLED)
    db.commit()
    return Response(status_code=204)


@router.post("/{lid}/discard", status_code=204)
def discard(lid: int, data: DiscardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    visible_lead(db, user, lid)
    done = db.query(Lead).filter(Lead.id == lid, Lead.status.in_(QUEUE)) \
             .update({"status": "discarded", "discard_reason": data.reason}, synchronize_session=False)
    if not done:
        raise HTTPException(409, ALREADY_HANDLED)
    db.commit()
    return Response(status_code=204)
