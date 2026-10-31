from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..leads import due_follow_ups, ranked_leads
from ..models import SALE_STATUSES, Order, User, size_key
from ..sales import late_filter, visible_orders
from ..security import get_current_user
from ..settings_store import get_app_settings
from ..uploads import thumb_name

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

MAX_PERIOD_DAYS = 731


def _top(d: dict, n=8, by="value"):
    return sorted(d.values(), key=lambda x: x[by], reverse=True)[:n]


def _sales_between(db: Session, user: User, start: date, end: date) -> list[Order]:
    return (visible_orders(db, user)
            .filter(Order.date >= start, Order.date <= end, Order.status.in_(SALE_STATUSES)).all())


def _kpis(sales: list[Order]) -> dict:
    revenue = sum(o.total for o in sales)
    return {
        "revenue": round(revenue, 2),
        "orders": len(sales),
        "average_ticket": round(revenue / len(sales), 2) if sales else 0,
        "pieces": sum(o.pieces for o in sales),
    }


def _goal(annual) -> float | None:
    """The full annual goal, whatever the chosen period: it's measured against the goal year's sales."""
    annual = float(annual or 0)  # Numeric columns load as Decimal
    return annual if annual > 0 else None


def _sales_series(sales: list[Order], start: date, end: date) -> list[dict]:
    """One point per day up to 31 days, else one per Monday-to-Sunday week, clipped to the period."""
    weekly = (end - start).days + 1 > 31
    buckets: dict[date, float] = {}
    d = start
    while d <= end:
        buckets[d] = 0.0
        d += timedelta(days=7 - d.weekday()) if weekly else timedelta(days=1)
    for o in sales:
        key = max(start, o.date - timedelta(days=o.date.weekday())) if weekly else o.date
        buckets[key] += o.total
    return [{"label": k.strftime("%d/%m"), "start": k, "value": round(v, 2)} for k, v in buckets.items()]


def _seller_row(u: User, year_sales: dict[int, float]) -> dict:
    return {"id": u.id, "name": u.name, "avatar_url": u.avatar_url, "goal": _goal(u.annual_goal),
            "goal_value": round(year_sales.get(u.id, 0.0), 2), "orders": 0, "pieces": 0, "value": 0.0}


@router.get("")
def dashboard(start: date | None = None, end: date | None = None, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    today = clock.today_br()
    start = start or clock.goal_year_start(today)
    end = end or today
    if start > end or (end - start).days >= MAX_PERIOD_DAYS:
        raise HTTPException(400, "Período inválido.")
    days = (end - start).days + 1
    is_admin = user.role == "admin"

    orders = visible_orders(db, user).filter(Order.date >= start, Order.date <= end).all()
    sales = [o for o in orders if o.status in SALE_STATUSES]
    prev_end = start - timedelta(days=1)
    prev_sales = _sales_between(db, user, prev_end - timedelta(days=days - 1), prev_end)
    year_sales: dict[int, float] = defaultdict(float)  # goal-year sales per seller, independent of the period
    for o in _sales_between(db, user, clock.goal_year_start(today), today):
        year_sales[o.seller_id] += o.total

    by_status = defaultdict(lambda: {"count": 0, "value": 0.0})
    for o in orders:
        by_status[o.status]["count"] += 1
        by_status[o.status]["value"] += o.total

    sellers: dict[int, dict] = {}
    if is_admin:  # active sellers with no sales still show up, with zeros
        for u in db.query(User).filter(User.active.is_(True), User.role == "seller"):
            sellers[u.id] = _seller_row(u, year_sales)
    else:
        sellers[user.id] = _seller_row(user, year_sales)

    products, customers, colors, cities, sizes = {}, {}, {}, {}, defaultdict(int)
    for o in sales:
        c = customers.setdefault(o.customer_id, {"id": o.customer_id, "name": o.customer.name, "orders": 0, "pieces": 0, "value": 0.0})
        c["orders"] += 1
        c["pieces"] += o.pieces
        c["value"] += o.total
        s = sellers.setdefault(o.seller_id, _seller_row(o.seller, year_sales))
        s["orders"] += 1
        s["pieces"] += o.pieces
        s["value"] += o.total
        city_key = f"{o.customer.city or 'Não informado'}/{o.customer.state or ''}".rstrip("/")
        ci = cities.setdefault(city_key, {"name": city_key, "orders": 0, "pieces": 0, "value": 0.0})
        ci["orders"] += 1
        ci["pieces"] += o.pieces
        ci["value"] += o.total
        in_order = set()  # products already counted in this order's "orders"
        for i in o.items:
            img = i.product.image_url
            pr = products.setdefault(i.product_id, {"reference": i.product.reference, "description": i.product.description,
                                                     "thumb_url": f"/uploads/products/{thumb_name(img)}" if img else None,
                                                     "orders": 0, "pieces": 0, "value": 0.0, "colors": {}})
            if i.product_id not in in_order:
                in_order.add(i.product_id)
                pr["orders"] += 1
            pr["pieces"] += i.quantity
            pr["value"] += i.subtotal
            pc = pr["colors"].setdefault(i.color_id, {"name": i.color.name, "hex": i.color.hex, "hex2": i.color.hex2, "pieces": 0})
            pc["pieces"] += i.quantity
            co = colors.setdefault(i.color_id, {"name": i.color.name, "hex": i.color.hex, "hex2": i.color.hex2,
                                                 "pieces": 0, "value": 0.0})
            co["pieces"] += i.quantity
            co["value"] += i.subtotal
            sizes[i.size] += i.quantity

    # Last 12 months (independent of the filter) for the trend chart
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    months.reverse()
    series = {k: {"value": 0.0, "pieces": 0, "orders": 0} for k in months}
    for o in _sales_between(db, user, date(*months[0], 1), today):
        k = (o.date.year, o.date.month)
        if k in series:
            series[k]["value"] += o.total
            series[k]["pieces"] += o.pieces
            series[k]["orders"] += 1

    late = visible_orders(db, user).filter(late_filter(today)).all()

    follow_ups = due_follow_ups(db, user, today, everyone=is_admin, until=today + timedelta(days=7))
    company_goal = get_app_settings(db).annual_goal if is_admin else user.annual_goal
    return {
        "period": {"start": start, "end": end},
        "kpis": _kpis(sales),
        "previous_kpis": _kpis(prev_sales),
        "sales_series": _sales_series(sales, start, end),
        "goal": _goal(company_goal),
        "goal_value": round(sum(year_sales.values()), 2),
        "monthly_sales": [{"month": f"{m:02d}/{str(y)[2:]}", **series[(y, m)]} for y, m in months],
        "by_status": [{"status": s, **v} for s, v in by_status.items()],
        # every product sold, ranked by pieces: the Painel shows the top 3, "Referências mais vendidas" all of them
        "top_products": [{**p, "colors": _top(p["colors"], len(p["colors"]), by="pieces")}
                         for p in _top(products, len(products), by="pieces")],
        "top_customers": _top(customers),
        "by_seller": _top(sellers, 50),
        "by_city": _top(cities, len(cities)),  # all of them: Faturamento sums the tail into "Outras"
        "by_color": _top(colors, len(colors), by="pieces"),  # all colors: the Painel pools the tail into "Outras cores"
        "by_size": sorted(
            [{"size": t, "pieces": q} for t, q in sizes.items()],
            key=lambda x: size_key(x["size"]),
        ),
        "alerts": {
            "late_orders": len(late),
            "oldest_late_days": max(((today - o.delivery_date).days for o in late), default=None),
            "follow_ups_due": sum(f["next_action_date"] <= today for f in follow_ups),  # same as Retornos
        },
        # the Painel's "Retornos pendentes" card: leads to call back, late / today / coming week (customers come from the overview)
        "lead_follow_ups": {
            "overdue": sum(f["kind"] == "lead" and f["next_action_date"] < today for f in follow_ups),
            "today": sum(f["kind"] == "lead" and f["next_action_date"] == today for f in follow_ups),
            "week": sum(f["kind"] == "lead" and f["next_action_date"] > today for f in follow_ups),
        },
        # admin only: same counts as the Prospecção tabs Primeiro contato / Liberados (Pendentes is just the raw import)
        "first_contact": {s: ranked_leads(db, user, status=s).count() for s in ("contacted", "new")} if is_admin else None,
    }
