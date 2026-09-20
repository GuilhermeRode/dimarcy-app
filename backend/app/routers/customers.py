from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Order, User
from ..schemas import CustomerIn, CustomerOut
from ..security import get_current_user

router = APIRouter(prefix="/customers", tags=["customers"])


def _visible(cid: int, db: Session, user: User) -> Customer:
    """A seller only sees/edits the customers they registered; an admin sees everyone."""
    c = db.get(Customer, cid)
    if not c or (user.role != "admin" and c.owner_id != user.id):
        raise HTTPException(404, "Customer not found.")
    return c


@router.get("", response_model=list[CustomerOut])
def list_all(search: str = "", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Customer)
    if user.role != "admin":
        q = q.filter(Customer.owner_id == user.id)
    if search:
        t = f"%{search}%"
        q = q.filter(or_(Customer.name.ilike(t), Customer.city.ilike(t), Customer.document.ilike(t)))
    return q.order_by(Customer.name).all()


@router.get("/{cid}", response_model=CustomerOut)
def get(cid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _visible(cid, db, user)


@router.post("", response_model=CustomerOut, status_code=201)
def create(data: CustomerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    payload = data.model_dump(exclude={"owner_id"})
    # Sellers can only ever own the customers they register; only admins may assign a seller.
    owner_id = data.owner_id if user.role == "admin" else user.id
    c = Customer(**payload, owner_id=owner_id)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{cid}", response_model=CustomerOut)
def update(cid: int, data: CustomerIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _visible(cid, db, user)
    for k, v in data.model_dump(exclude={"owner_id"}).items():
        setattr(c, k, v)
    if user.role == "admin":
        c.owner_id = data.owner_id
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{cid}", status_code=204)
def delete(cid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _visible(cid, db, user)
    if db.query(Order).filter(Order.customer_id == cid).first():
        raise HTTPException(400, "This customer has orders and cannot be deleted.")
    db.delete(c)
    db.commit()
