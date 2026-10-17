from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..geocoding import geocode_and_cache_background, lookup_cached_city
from ..models import Contact, Customer, Lead, Order, User
from ..schemas import CustomerIn, CustomerOut
from ..sales import customer_overview, customers_by_city
from ..security import get_current_user, require_admin

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


@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every visible customer with sales aggregates and status, for the Clientes screen."""
    return customer_overview(db, user, clock.today_br())


@router.get("/by-city", dependencies=[Depends(require_admin)])
def by_city(days: int = Query(365, ge=1, le=731), owner_id: int | None = None, db: Session = Depends(get_db)):
    """Map data: registered/active customers, revenue and average ticket per city."""
    return customers_by_city(db, clock.today_br(), days, owner_id)


@router.get("/{cid}", response_model=CustomerOut)
def get(cid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _visible(cid, db, user)


def add_customer(db: Session, data: CustomerIn, owner_id: int | None) -> Customer:
    """Adds (doesn't commit) a new customer, with cached coordinates when the city is known.
    Callers commit, then call geocode_later."""
    c = Customer(**data.model_dump(exclude={"owner_id"}), owner_id=owner_id)
    if c.city:
        cached = lookup_cached_city(db, c.city, c.state)
        if cached:
            c.lat, c.lng = cached
    db.add(c)
    return c


def geocode_later(c: Customer, background_tasks: BackgroundTasks):
    if c.city and c.lat is None:  # not cached — resolve it in the background, doesn't block the response
        background_tasks.add_task(geocode_and_cache_background, c.id, c.city, c.state)


@router.post("", response_model=CustomerOut, status_code=201)
def create(data: CustomerIn, background_tasks: BackgroundTasks,
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Sellers can only ever own the customers they register; only admins may assign a seller.
    c = add_customer(db, data, data.owner_id if user.role == "admin" else user.id)
    db.commit()
    db.refresh(c)
    geocode_later(c, background_tasks)
    return c


@router.put("/{cid}", response_model=CustomerOut)
def update(cid: int, data: CustomerIn, background_tasks: BackgroundTasks,
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _visible(cid, db, user)
    city_changed = data.city != c.city or data.state != c.state
    for k, v in data.model_dump(exclude={"owner_id"}).items():
        setattr(c, k, v)
    if user.role == "admin":
        c.owner_id = data.owner_id
    if c.city and (city_changed or c.lat is None):
        cached = lookup_cached_city(db, c.city, c.state)
        c.lat, c.lng = cached if cached else (None, None)  # clear stale coords until re-geocoded
    db.commit()
    db.refresh(c)
    if c.city and c.lat is None:
        background_tasks.add_task(geocode_and_cache_background, c.id, c.city, c.state)
    return c


@router.delete("/{cid}", status_code=204)
def delete(cid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _visible(cid, db, user)
    if db.query(Order).filter(Order.customer_id == cid).first():
        raise HTTPException(400, "This customer has orders and cannot be deleted.")
    # no FK cascades on SQLite here: clean up dependents by hand
    db.query(Contact).filter(Contact.customer_id == cid).delete(synchronize_session=False)
    db.query(Lead).filter(Lead.customer_id == cid).update({"customer_id": None}, synchronize_session=False)
    db.delete(c)
    db.commit()
