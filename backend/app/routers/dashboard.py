from collections import defaultdict
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SALE_STATUSES, Order, User
from ..security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _top(d: dict, n=8):
    return sorted(d.values(), key=lambda x: x["value"], reverse=True)[:n]


@router.get("")
def dashboard(start: date | None = None, end: date | None = None, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    today = date.today()
    start = start or date(today.year, 1, 1)
    end = end or today

    q = db.query(Order).filter(Order.date >= start, Order.date <= end)
    if user.role != "admin":  # sellers only see their own orders
        q = q.filter(Order.seller_id == user.id)
    orders = q.all()
    sales = [o for o in orders if o.status in SALE_STATUSES]

    revenue = sum(o.total for o in sales)
    pieces = sum(o.pieces for o in sales)

    by_status = defaultdict(lambda: {"count": 0, "value": 0.0})
    for o in orders:
        by_status[o.status]["count"] += 1
        by_status[o.status]["value"] += o.total

    products, customers, colors, sellers, sizes = {}, {}, {}, {}, defaultdict(int)
    for o in sales:
        c = customers.setdefault(o.customer_id, {"name": o.customer.name, "orders": 0, "pieces": 0, "value": 0.0})
        c["orders"] += 1
        c["pieces"] += o.pieces
        c["value"] += o.total
        s = sellers.setdefault(o.seller_id, {"name": o.seller.name, "orders": 0, "pieces": 0, "value": 0.0})
        s["orders"] += 1
        s["pieces"] += o.pieces
        s["value"] += o.total
        for i in o.items:
            pr = products.setdefault(i.product_id, {"reference": i.product.reference,
                                                     "description": i.product.description, "pieces": 0, "value": 0.0})
            pr["pieces"] += i.quantity
            pr["value"] += i.subtotal
            co = colors.setdefault(i.color_id, {"name": i.color.name, "hex": i.color.hex, "pieces": 0, "value": 0.0})
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
    start12 = date(*months[0], 1)
    series = {k: {"value": 0.0, "pieces": 0} for k in months}
    for o in db.query(Order).filter(Order.date >= start12, Order.status.in_(SALE_STATUSES)).all():
        k = (o.date.year, o.date.month)
        if k in series:
            series[k]["value"] += o.total
            series[k]["pieces"] += o.pieces

    size_order = ["U", "PP", "P", "M", "G", "GG", "XG"]
    return {
        "period": {"start": start, "end": end},
        "kpis": {
            "revenue": round(revenue, 2),
            "orders": len(sales),
            "average_ticket": round(revenue / len(sales), 2) if sales else 0,
            "pieces": pieces,
        },
        "monthly_sales": [{"month": f"{m:02d}/{str(y)[2:]}", **series[(y, m)]} for y, m in months],
        "by_status": [{"status": s, **v} for s, v in by_status.items()],
        "top_products": _top(products),
        "top_customers": _top(customers),
        "by_seller": _top(sellers, 50),
        "by_color": _top(colors, 10),
        "by_size": sorted(
            [{"size": t, "pieces": q} for t, q in sizes.items()],
            key=lambda x: size_order.index(x["size"]) if x["size"] in size_order else 99,
        ),
    }
