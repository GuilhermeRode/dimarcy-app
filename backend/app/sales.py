"""Sales rules shared by the dashboard, the customers overview and the orders list, so a
number on the Painel always matches the list it links to.

Seller visibility (same rule as /orders): a seller counts only orders they sold
(seller_id) and sees only customers they own (owner_id). Admins see everything."""
from collections import Counter, defaultdict
from datetime import date

from sqlalchemy import and_
from sqlalchemy.orm import Session, joinedload

from .models import LATE_STATUSES, SALE_STATUSES, Customer, Order, User, customer_status


def late_filter(today: date):
    return and_(Order.status.in_(LATE_STATUSES), Order.delivery_date < today)


def visible_orders(db: Session, user: User):
    q = db.query(Order)
    if user.role != "admin":
        q = q.filter(Order.seller_id == user.id)
    return q


def visible_customers(db: Session, user: User) -> list[Customer]:
    q = db.query(Customer).options(joinedload(Customer.owner))
    if user.role != "admin":
        q = q.filter(Customer.owner_id == user.id)
    return q.order_by(Customer.name).all()


def customer_overview(db: Session, user: User, today: date) -> list[dict]:
    # ponytail: loads every visible sale order (items come in one selectin query); fine for a few
    # thousand orders — switch to GROUP BY aggregates if this endpoint gets slow.
    sales = (visible_orders(db, user).filter(Order.status.in_(SALE_STATUSES))
             .order_by(Order.date.desc(), Order.id.desc()).all())
    by_customer: dict[int, list[Order]] = defaultdict(list)
    for o in sales:
        by_customer[o.customer_id].append(o)

    rows = []
    for c in visible_customers(db, user):
        orders = by_customer.get(c.id, [])  # newest first
        colors: Counter[str] = Counter()
        for o in orders:
            for i in o.items:
                colors[i.color.name] += i.quantity
        last = orders[0].date if orders else None
        rows.append({
            "id": c.id, "name": c.name, "city": c.city, "state": c.state, "phone": c.phone,
            "document": c.document, "owner_id": c.owner_id, "owner_name": c.owner_name,
            "created_at": c.created_at,
            "total": round(sum(o.total for o in orders), 2), "orders": len(orders),
            "last_order_date": last, "status": customer_status(last, today),
            "colors": [name for name, _ in colors.most_common()],
            "recent_orders": [{"id": o.id, "date": o.date, "pieces": o.pieces, "total": o.total}
                              for o in orders[:3]],
        })
    return rows
