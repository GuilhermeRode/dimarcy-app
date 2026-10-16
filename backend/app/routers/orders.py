from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock, finance
from ..database import get_db
from ..mailer import send_order_created_emails, send_order_delivered_email
from ..models import ORDER_STATUSES, AppSettings, Customer, FinancialEntry, Order, OrderItem, Product, User
from ..schemas import OrderIn, StatusIn
from ..sales import late_filter, visible_orders
from ..security import get_current_user, require_admin
from ..settings_store import allowed_price_tables, get_app_settings, retail_price

router = APIRouter(prefix="/orders", tags=["orders"])


def _format_brl(v: float) -> str:
    return f"R$ {v:,.2f}".translate(str.maketrans(",.", ".,"))


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
    d["price_table"] = o.price_table
    d["notes"] = o.notes
    d["items"] = [{
        "id": i.id, "product_id": i.product_id, "color_id": i.color_id, "size": i.size,
        "quantity": i.quantity, "unit_price": float(i.unit_price), "subtotal": i.subtotal,
        "product_reference": i.product.reference, "product_description": i.product.description,
        "color_name": i.color.name, "color_hex": i.color.hex, "color_hex2": i.color.hex2,
    } for i in sorted(o.items, key=lambda x: (x.product.reference, x.color.name))]
    return d


def _build_items(data: OrderIn, db: Session, user: User, app_settings: AppSettings,
                  existing_order: Order | None, price_table: str) -> list[OrderItem]:
    if data.status not in ORDER_STATUSES:
        raise HTTPException(400, "Invalid status.")
    if not db.get(Customer, data.customer_id):
        raise HTTPException(400, "Customer not found.")
    # Editing an order keeps each existing line's recorded price — only a brand-new
    # product line falls back to the product's current price (see also the override case).
    price_on_record = {i.product_id: float(i.unit_price) for i in existing_order.items} if existing_order else {}
    items = []
    for it in data.items:
        prod = db.get(Product, it.product_id)
        if not prod or (user.role != "admin" and prod.sellers and user not in prod.sellers):
            raise HTTPException(400, f"Product {it.product_id} not found.")
        if it.color_id not in {c.id for c in prod.colors}:
            raise HTTPException(400, f"The chosen color is not registered for {prod.reference}.")
        if it.size not in prod.sizes.split(","):
            raise HTTPException(400, f"Size {it.size} does not exist for {prod.reference}.")
        if app_settings.allow_price_override and user.role == "admin" and it.unit_price is not None:
            price = it.unit_price
        elif prod.id in price_on_record:
            price = price_on_record[prod.id]
        elif price_table == "retail":
            price = retail_price(prod.price, app_settings.retail_markup_percent)
        else:
            price = float(prod.price)
        items.append(OrderItem(product_id=prod.id, color_id=it.color_id, size=it.size,
                                quantity=it.quantity, unit_price=price))
    return items


def _check_discount(discount: float, items: list[OrderItem], app_settings: AppSettings) -> None:
    gross = sum(i.subtotal for i in items)
    max_discount = round(gross * float(app_settings.max_discount_percent) / 100, 2)
    if discount > max_discount + 0.005:
        pct = app_settings.max_discount_percent
        pct_text = f"{pct:.2f}".rstrip("0").rstrip(".") if pct % 1 else f"{pct:.0f}"
        raise HTTPException(400, f"O desconto máximo é de {pct_text}% ({_format_brl(max_discount)}). "
                                  f"Peça ao administrador para alterar o limite.")


def _find(oid: int, db: Session) -> Order:
    o = db.get(Order, oid)
    if not o:
        raise HTTPException(404, "Order not found.")
    return o


def _sync_installments(db: Session, o: Order, old_status: str | None) -> None:
    """Entering "delivered" creates the receivables; leaving it drops the unpaid ones.
    Runs after a flush and before the single commit, so the order and its installments save together."""
    if o.status == "delivered" and old_status != "delivered":
        finance.create_order_installments(db, o, clock.today_br())
    elif old_status == "delivered" and o.status != "delivered":
        finance.remove_open_installments(db, o)


@router.get("")
def list_all(status: str = "", customer_id: int | None = None, start: date | None = None,
             end: date | None = None, late: bool = False, db: Session = Depends(get_db),
             user: User = Depends(get_current_user)):
    q = visible_orders(db, user)  # sellers only see their own orders
    if status:
        q = q.filter(Order.status == status)
    if customer_id:
        q = q.filter(Order.customer_id == customer_id)
    if start:
        q = q.filter(Order.date >= start)
    if end:
        q = q.filter(Order.date <= end)
    if late:
        q = q.filter(late_filter(clock.today_br()))
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
    tables = allowed_price_tables(u)
    price_table = data.price_table or tables[0]
    if price_table not in tables:
        raise HTTPException(400, "Tabela de preço não permitida para este vendedor.")
    app_settings = get_app_settings(db)
    items = _build_items(data, db, u, app_settings, existing_order=None, price_table=price_table)
    _check_discount(data.discount, items, app_settings)
    o = Order(customer_id=data.customer_id, seller_id=u.id, date=data.date or clock.today_br(),
              delivery_date=data.delivery_date, status=data.status,
              payment_method=data.payment_method, payment_terms=data.payment_terms, price_table=price_table,
              discount=data.discount, notes=data.notes, items=items)
    db.add(o)
    db.flush()  # the installment descriptions need the order id
    _sync_installments(db, o, old_status=None)
    db.commit()
    db.refresh(o)
    send_order_created_emails(o)
    return full(o)


@router.put("/{oid}", dependencies=[Depends(require_admin)])
def update(oid: int, data: OrderIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    o = _find(oid, db)
    old_status = o.status
    app_settings = get_app_settings(db)
    # The table is fixed when the order is created; editing keeps it.
    items = _build_items(data, db, user, app_settings, existing_order=o, price_table=o.price_table)
    _check_discount(data.discount, items, app_settings)
    o.items = items
    o.customer_id, o.status, o.discount, o.notes = data.customer_id, data.status, data.discount, data.notes
    o.payment_method, o.payment_terms = data.payment_method, data.payment_terms
    o.date = data.date or o.date
    o.delivery_date = data.delivery_date
    db.flush()
    _sync_installments(db, o, old_status)
    db.commit()
    db.refresh(o)
    if o.status == "delivered" and old_status != "delivered":
        send_order_delivered_email(o)
    return full(o)


@router.patch("/{oid}/status", dependencies=[Depends(require_admin)])
def change_status(oid: int, data: StatusIn, db: Session = Depends(get_db)):
    if data.status not in ORDER_STATUSES:
        raise HTTPException(400, "Invalid status.")
    o = _find(oid, db)
    old_status = o.status
    o.status = data.status
    db.flush()
    _sync_installments(db, o, old_status)
    db.commit()
    db.refresh(o)
    if o.status == "delivered" and old_status != "delivered":
        send_order_delivered_email(o)
    return full(o)


@router.delete("/{oid}", status_code=204, dependencies=[Depends(require_admin)])
def delete(oid: int, db: Session = Depends(get_db)):
    o = _find(oid, db)
    if o.status != "quote":
        raise HTTPException(400, "Só orçamentos podem ser excluídos. Para os demais, use Cancelar.")
    if db.query(FinancialEntry).filter(FinancialEntry.order_id == oid).first():
        raise HTTPException(400, "Este pedido tem parcelas lançadas. Exclua as parcelas antes.")
    db.delete(o)
    db.commit()
