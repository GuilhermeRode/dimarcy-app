"""Sales rules shared by the dashboard, the customers overview and the orders list, so a
number on the Painel always matches the list it links to.

Seller visibility (same rule as /orders): a seller counts only orders they sold
(seller_id) and sees only customers they own (owner_id). Admins see everything."""
from collections import Counter, defaultdict
from datetime import date, timedelta

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


def customers_by_city(db: Session, today: date, days: int, owner_id: int | None = None) -> list[dict]:
    """Per-city portfolio for the map (admin): registered customers, customers active in the last
    `days` days (at least one sale), revenue/orders/average ticket in that window, last sale ever.
    `owner_id` narrows to one seller's portfolio. Customers without a city are left out."""
    since = today - timedelta(days=days - 1)
    q = db.query(Customer).filter(Customer.city.isnot(None), Customer.city != "")
    if owner_id:
        q = q.filter(Customer.owner_id == owner_id)
    customers = q.all()
    # ponytail: all sales of the visible customers in Python; GROUP BY if this gets slow.
    sales = (db.query(Order).filter(Order.status.in_(SALE_STATUSES), Order.customer_id.in_([c.id for c in customers]))
             .all()) if customers else []
    by_customer: dict[int, list[Order]] = defaultdict(list)
    for o in sales:
        by_customer[o.customer_id].append(o)

    cities: dict[tuple[str, str], dict] = {}
    for c in customers:
        city, state = c.city.strip(), (c.state or "").strip().upper()
        g = cities.setdefault((city.lower(), state), {
            "city": city, "state": state, "lat": None, "lng": None, "registered": 0, "active": 0,
            "orders": 0, "revenue": 0.0, "last_order_date": None})
        g["registered"] += 1
        if g["lat"] is None and c.lat is not None:
            g["lat"], g["lng"] = c.lat, c.lng
        orders = by_customer.get(c.id, [])
        recent = [o for o in orders if o.date >= since]
        if recent:
            g["active"] += 1
        g["orders"] += len(recent)
        g["revenue"] += sum(o.total for o in recent)
        last = max((o.date for o in orders), default=None)
        if last and (g["last_order_date"] is None or last > g["last_order_date"]):
            g["last_order_date"] = last
    for g in cities.values():
        g["revenue"] = round(g["revenue"], 2)
        g["average_ticket"] = round(g["revenue"] / g["orders"], 2) if g["orders"] else None
    return list(cities.values())


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
