from datetime import date, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session, contains_eager

from .. import clock, finance
from ..database import get_db
from ..models import PAYABLE_CATEGORIES, Customer, FinancialEntry, Order
from ..schemas import EntryIn, EntryUpdate, PayIn, SplitIn
from ..security import require_admin

router = APIRouter(prefix="/finance", tags=["finance"], dependencies=[Depends(require_admin)])


def _out(e: FinancialEntry, today: date) -> dict:
    return {
        "id": e.id, "kind": e.kind, "description": e.description, "amount": float(e.amount),
        "due_date": e.due_date, "paid_at": e.paid_at,
        "paid_amount": float(e.paid_amount) if e.paid_amount is not None else None,
        "payment_method": e.payment_method, "notes": e.notes, "order_id": e.order_id,
        "customer_name": e.order.customer.name if e.order else None,  # always the order's current customer
        "supplier": e.supplier, "category": e.category,
        "installment": e.installment, "installments": e.installments,
        "status": finance.entry_status(e, today),
    }


def _get(eid: int, db: Session) -> FinancialEntry:
    e = db.get(FinancialEntry, eid)
    if not e:
        raise HTTPException(404, "Lançamento não encontrado.")
    return e


def _check(db: Session, kind: str, category: str | None, order_id: int | None) -> None:
    if kind == "payable" and category not in PAYABLE_CATEGORIES:
        raise HTTPException(400, "Escolha uma categoria válida.")
    if order_id is not None and (kind != "receivable" or not db.get(Order, order_id)):
        raise HTTPException(400, "Pedido não encontrado.")


@router.get("/entries")
def list_entries(kind: str = "", status: str = "open", start: date | None = None, end: date | None = None,
                 search: str = "", category: str = "", order_id: int | None = None, db: Session = Depends(get_db)):
    today = clock.today_br()
    q = (db.query(FinancialEntry).outerjoin(FinancialEntry.order).outerjoin(Order.customer)
         .options(contains_eager(FinancialEntry.order).contains_eager(Order.customer)))
    if kind:
        q = q.filter(FinancialEntry.kind == kind)
    if status in ("open", "overdue"):
        q = q.filter(FinancialEntry.paid_at.is_(None))
    if status == "overdue":
        q = q.filter(FinancialEntry.due_date < today)
    if status == "paid":
        q = q.filter(FinancialEntry.paid_at.isnot(None))
    if start:
        q = q.filter(FinancialEntry.due_date >= start)
    if end:
        q = q.filter(FinancialEntry.due_date <= end)
    if category:
        q = q.filter(FinancialEntry.category == category)
    if order_id:
        q = q.filter(FinancialEntry.order_id == order_id)
    if search:
        t = f"%{search}%"  # ilike: Postgres LIKE is case-sensitive
        q = q.filter(or_(FinancialEntry.description.ilike(t), FinancialEntry.supplier.ilike(t), Customer.name.ilike(t)))
    return [_out(e, today) for e in q.order_by(FinancialEntry.due_date, FinancialEntry.id).all()]


@router.get("/summary")
def summary(kind: Literal["receivable", "payable"], db: Session = Depends(get_db)):
    today = clock.today_br()
    rows = (db.query(FinancialEntry)
            .filter(FinancialEntry.kind == kind,
                    or_(FinancialEntry.paid_at.is_(None), FinancialEntry.paid_at >= today.replace(day=1)))
            .all())

    def card(entries, field="amount"):
        return {"total": float(sum((getattr(e, field) for e in entries), Decimal(0))), "count": len(entries)}

    open_ = [e for e in rows if e.paid_at is None]
    paid = [e for e in rows if e.paid_at and (e.paid_at.year, e.paid_at.month) == (today.year, today.month)]
    return {
        "overdue": card([e for e in open_ if e.due_date < today]),
        "due_soon": card([e for e in open_ if today <= e.due_date <= today + timedelta(days=7)]),
        "open": card(open_),
        "paid_this_month": card(paid, "paid_amount"),
    }


@router.post("/entries", status_code=201)
def create_entry(data: EntryIn, db: Session = Depends(get_db)):
    _check(db, data.kind, data.category, data.order_id)
    n = data.repeat_months
    entries = [FinancialEntry(
        kind=data.kind, description=data.description if n == 1 else f"{data.description} ({i + 1}/{n})",
        amount=finance.to_decimal(data.amount), due_date=finance.add_months(data.due_date, i),
        payment_method=data.payment_method, notes=data.notes,
        order_id=data.order_id if data.kind == "receivable" else None,
        supplier=data.supplier if data.kind == "payable" else None,
        category=data.category if data.kind == "payable" else None,
        installment=i + 1 if n > 1 else None, installments=n if n > 1 else None,
    ) for i in range(n)]  # each month from the first date, so 31/01 → 28/02 → 31/03
    db.add_all(entries)
    db.commit()
    today = clock.today_br()
    return [_out(e, today) for e in entries]


@router.put("/entries/{eid}")
def update_entry(eid: int, data: EntryUpdate, db: Session = Depends(get_db)):
    e = _get(eid, db)
    _check(db, e.kind, data.category, None)
    amount = finance.to_decimal(data.amount)
    if e.paid_at and amount != e.amount:
        raise HTTPException(400, "Desfaça a baixa antes de mudar o valor.")
    e.description, e.amount, e.due_date = data.description, amount, data.due_date
    e.payment_method, e.notes = data.payment_method, data.notes
    if e.kind == "payable":
        e.supplier, e.category = data.supplier, data.category
    db.commit()
    return _out(e, clock.today_br())


@router.post("/entries/{eid}/pay")
def pay(eid: int, data: PayIn, db: Session = Depends(get_db)):
    e = _get(eid, db)
    if e.paid_at:
        raise HTTPException(400, "Este lançamento já está pago.")
    today = clock.today_br()
    e.paid_at = data.paid_at or today
    e.paid_amount = finance.to_decimal(data.paid_amount) if data.paid_amount else e.amount
    if data.payment_method:
        e.payment_method = data.payment_method
    db.commit()
    return _out(e, today)


@router.post("/entries/{eid}/unpay")
def unpay(eid: int, db: Session = Depends(get_db)):
    e = _get(eid, db)
    e.paid_at, e.paid_amount = None, None  # payment_method stays
    db.commit()
    return _out(e, clock.today_br())


@router.post("/entries/{eid}/split", status_code=201)
def split(eid: int, data: SplitIn, db: Session = Depends(get_db)):
    """The original keeps its due date and loses `amount`; a new entry gets it, due on `due_date`."""
    e = _get(eid, db)
    if e.paid_at:
        raise HTTPException(400, "Desfaça a baixa antes de desmembrar.")
    part = finance.to_decimal(data.amount)
    if not Decimal(0) < part < e.amount:
        raise HTTPException(400, "O valor desmembrado precisa ser menor que o valor do lançamento.")
    e.amount = e.amount - part
    new = FinancialEntry(kind=e.kind, description=f"{e.description} (restante)"[:200], amount=part,
                         due_date=data.due_date, payment_method=e.payment_method, notes=e.notes,
                         order_id=e.order_id, supplier=e.supplier, category=e.category,
                         installment=e.installment, installments=e.installments)
    db.add(new)
    db.commit()
    return _out(new, clock.today_br())


@router.delete("/entries/{eid}", status_code=204)
def delete_entry(eid: int, db: Session = Depends(get_db)):
    db.delete(_get(eid, db))
    db.commit()


@router.post("/orders/{order_id}/generate", status_code=201)
def generate(order_id: int, db: Session = Depends(get_db)):
    """For orders delivered before this feature, or paid in part and delivered again."""
    o = db.get(Order, order_id)
    if not o:
        raise HTTPException(404, "Pedido não encontrado.")
    if o.status != "delivered":
        raise HTTPException(400, "O pedido precisa estar Entregue.")
    if finance.open_installments(db, o.id).first():
        raise HTTPException(400, "O pedido já tem parcelas em aberto.")
    today = clock.today_br()
    entries = finance.create_order_installments(db, o, today)
    if not entries:
        raise HTTPException(400, "Não há saldo a receber neste pedido.")
    db.commit()
    return [_out(e, today) for e in entries]
