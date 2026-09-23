from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..mailer import send_order_delivered_email
from ..models import ORDER_STATUSES, Customer, Order, OrderItem, Product, User
from ..schemas import OrderIn, StatusIn
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/orders", tags=["orders"])


def summary(o: Order) -> dict:
    return {
        "id": o.id, "date": o.date, "delivery_date": o.delivery_date, "status": o.status,
        "customer_id": o.customer_id, "customer_name": o.customer.name,
        "customer_city": o.customer.city, "customer_state": o.customer.state,
        "seller_name": o.seller.name, "seller_avatar_url": o.seller.avatar_url, "pieces": o.pieces,
        "gross": o.gross, "discount": float(o.discount or 0), "total": o.total,
    }


def full(o: Order) -> dict:
    d = summary(o)
    d["payment_method"] = o.payment_method
    d["payment_terms"] = o.payment_terms
    d["notes"] = o.notes
    d["items"] = [{
        "id": i.id, "product_id": i.product_id, "color_id": i.color_id, "size": i.size,
        "quantity": i.quantity, "unit_price": float(i.unit_price), "subtotal": i.subtotal,
        "product_reference": i.product.reference, "product_description": i.product.description,
        "color_name": i.color.name, "color_hex": i.color.hex,
    } for i in sorted(o.items, key=lambda x: (x.product.reference, x.color.name))]
    return d


def _build_items(data: OrderIn, db: Session, user: User) -> list[OrderItem]:
    if data.status not in ORDER_STATUSES:
        raise HTTPException(400, "Invalid status.")
    if not db.get(Customer, data.customer_id):
        raise HTTPException(400, "Customer not found.")
    items = []
    for it in data.items:
        prod = db.get(Product, it.product_id)
        if not prod:
            raise HTTPException(400, f"Product {it.product_id} not found.")
        if it.color_id not in {c.id for c in prod.colors}:
            raise HTTPException(400, f"The chosen color is not registered for {prod.reference}.")
        if it.size not in prod.sizes.split(","):
            raise HTTPException(400, f"Size {it.size} does not exist for {prod.reference}.")
        # Sellers cannot override the product's price — only admins can.
        if user.role == "admin" and it.unit_price is not None:
            price = it.unit_price
        else:
            price = float(prod.price)
        items.append(OrderItem(product_id=prod.id, color_id=it.color_id, size=it.size,
                                quantity=it.quantity, unit_price=price))
    return items


def _find(oid: int, db: Session) -> Order:
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found.")
    return o


@router.get("")
def list_all(status: str = "", customer_id: int | None = None, start: date | None = None,
             end: date | None = None, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    q = db.query(Order)
    if user.role != "admin":  # sellers only see their own orders
        q = q.filter(Order.seller_id == user.id)
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    if start:
        q = q.filter(Order.date >= start)
    if end:
        q = q.filter(Order.date <= end)
    return [summary(o) for o in q.order_by(Order.id.desc()).all()]


@router.get("/{oid}")
def get(oid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _find(oid, db)
    if user.role != "admin" and o.seller_id != user.id:
        raise HTTPException(404, "Order not found.")
    return full(o)


@router.post("", status_code=201)
def create(data: OrderIn, db: Session = Depends(get_db), u: User = Depends(get_current_user)):
    if u.role != "admin":
        customer = db.get(Customer, data.customer_id)
        if not customer or customer.owner_id != u.id:
            raise HTTPException(400, "Customer not found.")
    o = Order(customer_id=data.customer_id, seller_id=u.id, date=data.date or date.today(),
              delivery_date=data.delivery_date, status=data.status,
              payment_method=data.payment_method, payment_terms=data.payment_terms,
              discount=data.discount, notes=data.notes,
              items=_build_items(data, db, u))
    db.add(o)
    db.commit()
    db.refresh(o)
    return full(o)


@router.put("/{oid}", dependencies=[Depends(require_admin)])
def update(oid: int, data: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _find(oid, db)
    o.items = _build_items(data, db, user)
    became_delivered = data.status == "delivered" and o.status != "delivered"
    o.customer_id, o.status, o.discount, o.notes = data.customer_id, data.status, data.discount, data.notes
    o.payment_method, o.payment_terms = data.payment_method, data.payment_terms
    o.date = data.date or o.date
    o.delivery_date = data.delivery_date
    db.commit()
    db.refresh(o)
    if became_delivered:
        send_order_delivered_email(o)
    return full(o)


@router.patch("/{oid}/status", dependencies=[Depends(require_admin)])
def change_status(oid: int, data: StatusIn, db: Session = Depends(get_db)):
    if data.status not in ORDER_STATUSES:
        raise HTTPException(400, "Invalid status.")
    o = _find(oid, db)
    became_delivered = data.status == "delivered" and o.status != "delivered"
    o.status = data.status
    db.commit()
    db.refresh(o)
    if became_delivered:
        send_order_delivered_email(o)
    return full(o)


@router.delete("/{oid}", status_code=204, dependencies=[Depends(require_admin)])
def delete(oid: int, db: Session = Depends(get_db)):
    o = _find(oid, db)
    db.delete(o)
    db.commit()
