from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from .. import clock, lead_import
from ..database import get_db
from ..leads import city_owners, lead_out, lead_owner, ranked_leads, visible_lead
from ..models import Contact, Lead, User
from ..schemas import CustomerIn, CustomerOut, DiscardIn, ReleaseIn
from ..security import get_current_user, require_admin
from .customers import add_customer, geocode_later

router = APIRouter(prefix="/leads", tags=["leads"])
ALREADY_HANDLED = "Este lead já foi tratado."


@router.get("")
def list_leads(city: str = "", search: str = "", seller_id: int | None = None,
               status: Literal["pending", "new"] = "new",
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    admin = user.role == "admin"  # only the admin may list pending leads
    rows = ranked_leads(db, user, clock.today_br(), city, search, seller_id if admin else None,
                        status if admin else "new")
    return {"items": [lead_out(lead, owner) for lead, owner in rows[offset:offset + limit]], "total": len(rows),
            "cities": sorted({lead.city for lead, _ in rows})}  # for the screen's city filter


@router.post("/release", dependencies=[Depends(require_admin)])
def release(data: ReleaseIn, db: Session = Depends(get_db)):
    """Pending -> new, only for leads whose city has an active seller."""
    owners = city_owners(db)
    leads = db.query(Lead).filter(Lead.id.in_(data.ids), Lead.status == "pending").all()
    ok = [lead.id for lead in leads if lead_owner(owners, lead)]
    if ok:
        db.query(Lead).filter(Lead.id.in_(ok), Lead.status == "pending").update(
            {"status": "new", "released_at": lead_import.utcnow()}, synchronize_session=False)
        db.commit()
    return {"released": len(ok), "skipped_no_seller": len(leads) - len(ok)}


@router.get("/{lid}")
def get_lead(lid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = visible_lead(db, user, lid)
    return lead_out(lead, lead_owner(city_owners(db), lead))


@router.post("/{lid}/convert", response_model=CustomerOut, status_code=201)
def convert(lid: int, data: CustomerIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lead -> customer in one transaction; the lead's contacts move to the customer."""
    lead = visible_lead(db, user, lid)
    if user.role == "admin":
        owner = lead_owner(city_owners(db), lead)
        owner_id = data.owner_id or (owner.id if owner else None)
    else:
        owner_id = user.id
    c = add_customer(db, data, owner_id)
    db.flush()
    # conditional UPDATE: a double click converts once, the second request gets 409
    done = db.query(Lead).filter(Lead.id == lid, Lead.status.in_(("pending", "new"))) \
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


@router.post("/{lid}/discard", status_code=204)
def discard(lid: int, data: DiscardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    visible_lead(db, user, lid)
    done = db.query(Lead).filter(Lead.id == lid, Lead.status.in_(("pending", "new"))) \
             .update({"status": "discarded", "discard_reason": data.reason}, synchronize_session=False)
    if not done:
        raise HTTPException(409, ALREADY_HANDLED)
    db.commit()
    return Response(status_code=204)
