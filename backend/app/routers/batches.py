"""Batches (lotes) on the Produção board: a named group of orders that moves between columns together."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..mailer import send_order_delivered_email
from ..models import ORDER_STATUSES, Batch, Order
from ..schemas import BatchIn, BatchPatch
from ..security import require_admin
from .orders import set_status

router = APIRouter(prefix="/batches", tags=["batches"], dependencies=[Depends(require_admin)])


def _out(b: Batch) -> dict:
    return {"id": b.id, "name": b.name, "status": b.status}


def _find(bid: int, db: Session) -> Batch:
    b = db.get(Batch, bid)
    if not b:
        raise HTTPException(404, "Lote não encontrado.")
    return b


@router.get("")
def list_all(db: Session = Depends(get_db)):
    return [_out(b) for b in db.query(Batch).order_by(Batch.id).all()]


@router.post("", status_code=201)
def create(data: BatchIn, db: Session = Depends(get_db)):
    if data.status not in ORDER_STATUSES:
        raise HTTPException(400, "Invalid status.")
    b = Batch(name=data.name.strip(), status=data.status)
    db.add(b)
    db.commit()
    return _out(b)


@router.patch("/{bid}")
def update(bid: int, data: BatchPatch, db: Session = Depends(get_db)):
    """Renames and/or moves the batch; moving takes every order in it to the same status."""
    b = _find(bid, db)
    if data.name is not None:
        b.name = data.name.strip()
    delivered = []
    if data.status is not None:
        if data.status not in ORDER_STATUSES:
            raise HTTPException(400, "Invalid status.")
        b.status = data.status
        for o in db.query(Order).filter(Order.batch_id == b.id).all():
            if set_status(db, o, data.status):
                delivered.append(o)
    db.commit()
    for o in delivered:
        send_order_delivered_email(o)
    return _out(b)


@router.delete("/{bid}", status_code=204)
def delete(bid: int, db: Session = Depends(get_db)):
    """Undoes the grouping only: the orders stay in the column they're in."""
    b = _find(bid, db)
    db.query(Order).filter(Order.batch_id == b.id).update({"batch_id": None}, synchronize_session=False)
    db.delete(b)
    db.commit()
