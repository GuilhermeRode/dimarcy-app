from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..leads import due_follow_ups, visible_lead
from ..models import Contact, User
from ..schemas import ContactIn
from ..security import get_current_user
from .customers import _visible as visible_customer

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _out(ct: Contact) -> dict:
    return {"id": ct.id, "user_name": ct.user.name, "channel": ct.channel, "notes": ct.notes,
            "next_action_date": ct.next_action_date, "created_at": ct.created_at}


def _check_target(db: Session, user: User, lead_id: int | None, customer_id: int | None, writing: bool = False):
    """Whoever sees the lead/customer sees and adds to its whole history."""
    if (lead_id is None) == (customer_id is None):
        raise HTTPException(422, "Informe o lead ou o cliente do contato.")
    if lead_id is not None:
        if visible_lead(db, user, lead_id).status not in ("pending", "new") and writing:  # history of handled leads stays readable
            raise HTTPException(409, "Este lead já foi tratado.")
    else:
        visible_customer(customer_id, db, user)


@router.get("/due")
def due(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return due_follow_ups(db, user, clock.today_br())


@router.get("")
def history(lead_id: int | None = None, customer_id: int | None = None,
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_target(db, user, lead_id, customer_id)
    q = db.query(Contact).filter(Contact.lead_id == lead_id if lead_id is not None else Contact.customer_id == customer_id)
    return [_out(ct) for ct in q.order_by(Contact.id.desc())]


@router.post("", status_code=201)
def create(data: ContactIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_target(db, user, data.lead_id, data.customer_id, writing=True)
    ct = Contact(user_id=user.id, **data.model_dump())
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return _out(ct)
