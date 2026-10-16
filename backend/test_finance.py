"""Accounts receivable/payable self-check. Run from backend/:  python test_finance.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta
from decimal import Decimal

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app import clock, finance  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FinancialEntry  # noqa: E402

TODAY = date(2026, 10, 15)
clock.today_br = lambda: TODAY

# ---- pure rules ----
assert finance.installment_days("À vista") == [0]
assert finance.installment_days("30/60") == [30, 60]
assert finance.installment_days("30/60/90/120/150") == [30, 60, 90, 120, 150]
assert finance.installment_days("28/56") == [28, 56]
assert finance.installment_days("Quinzenal") == [15, 30, 45, 60, 75, 90, 105, 120, 135, 150]
assert finance.installment_days("combinar") == [0] and finance.installment_days(None) == [0]

assert finance.split_cents(10000, 3) == [3334, 3333, 3333]
assert finance.split_cents(5, 10) == [5] + [0] * 9  # callers drop the zero ones
assert sum(finance.split_cents(123457, 7)) == 123457

assert finance.add_months(date(2027, 1, 31), 0) == date(2027, 1, 31)
assert finance.add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)
assert finance.add_months(date(2027, 1, 31), 2) == date(2027, 3, 31)  # from the first date, no drift
assert finance.add_months(date(2027, 11, 30), 3) == date(2028, 2, 29)  # leap year
assert finance.add_months(date(2026, 12, 10), 1) == date(2027, 1, 10)

assert finance.to_cents(100.1) == 10010 and finance.to_cents(Decimal("33.34")) == 3334
assert finance.to_decimal(0.1 + 0.2) == Decimal("0.30")

e = FinancialEntry(due_date=TODAY, paid_at=None)
assert finance.entry_status(e, TODAY) == "open"
assert finance.entry_status(e, TODAY + timedelta(days=1)) == "overdue"
e.paid_at = TODAY
assert finance.entry_status(e, TODAY + timedelta(days=1)) == "paid"

def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def entries(oid):
    """Installments of an order, straight from the database."""
    with SessionLocal() as db:
        return (db.query(FinancialEntry).filter(FinancialEntry.order_id == oid)
                .order_by(FinancialEntry.paid_at.is_(None), FinancialEntry.installment).all())


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")
    c.post("/api/users", headers=admin, json={"name": "Ana", "email": "a@t.com", "password": "seller-pass-123",
                                             "role": "seller"})
    A = login(c, "a@t.com", "seller-pass-123")
    r = c.put("/api/settings", headers=admin, json={"allow_price_override": False, "max_discount_percent": 100,
                                                     "retail_markup_percent": 50, "monthly_goal": None})
    assert r.status_code == 200, r.text
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]
    product = c.post("/api/products", headers=admin, json={"reference": "R1", "description": "Blusão", "price": 100,
                                                           "color_ids": [color]}).json()["id"]
    cheap = c.post("/api/products", headers=admin, json={"reference": "R2", "description": "Botão", "price": 0.05,
                                                         "color_ids": [color]}).json()["id"]
    cust = c.post("/api/customers", headers=admin, json={"name": "Loja Bela", "document": "1"}).json()["id"]
    cust2 = c.post("/api/customers", headers=admin, json={"name": "Malharia Sul", "document": "2"}).json()["id"]

    def body(**kw):
        return {"customer_id": cust, "delivery_date": TODAY.isoformat(), "status": "confirmed",
                "payment_method": "Boleto", "payment_terms": "30/60/90", "discount": 0,
                "items": [{"product_id": product, "color_id": color, "size": "P", "quantity": 1}], **kw}

    def new_order(**kw):
        r = c.post("/api/orders", headers=admin, json=body(**kw))
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def set_status(oid, status):
        r = c.patch(f"/api/orders/{oid}/status", headers=admin, json={"status": status})
        assert r.status_code == 200, r.text

    # ---- order hooks ----
    o1 = new_order()  # R$ 100,00 in 30/60/90
    assert entries(o1) == []
    set_status(o1, "delivered")
    e = entries(o1)
    assert [(e_.amount, e_.due_date, e_.installment, e_.installments) for e_ in e] == [
        (Decimal("33.34"), TODAY + timedelta(days=30), 1, 3), (Decimal("33.33"), TODAY + timedelta(days=60), 2, 3),
        (Decimal("33.33"), TODAY + timedelta(days=90), 3, 3)], e
    assert e[0].description == f"Pedido {o1:05d} — parcela 1/3"
    assert (e[0].kind, e[0].payment_method, e[0].paid_at) == ("receivable", "Boleto", None)
    set_status(o1, "delivered")  # same status again: nothing new
    assert len(entries(o1)) == 3

    oq = new_order(status="delivered", payment_terms="Quinzenal",
                   items=[{"product_id": product, "color_id": color, "size": "P", "quantity": 10}])
    assert [x.due_date for x in entries(oq)] == [TODAY + timedelta(days=d) for d in range(15, 151, 15)]
    assert sum(x.amount for x in entries(oq)) == Decimal("1000.00")
    ov = new_order(status="delivered", payment_terms="À vista")
    assert [(x.amount, x.due_date) for x in entries(ov)] == [(Decimal("100.00"), TODAY)]
    oz = new_order(status="delivered", discount=100)  # nothing left to receive
    assert entries(oz) == []
    # Review Focus 1: R$ 0,05 over 10 installments → a single R$ 0,05 entry, never R$ 0,00 ones
    tiny = new_order(status="delivered", payment_terms="Quinzenal",
                     items=[{"product_id": cheap, "color_id": color, "size": "P", "quantity": 1}])
    assert [(x.amount, x.installment, x.installments) for x in entries(tiny)] == [(Decimal("0.05"), 1, 1)]

    # leaving "delivered" drops the open ones and keeps the paid; coming back generates only the balance
    with SessionLocal() as db:
        first = db.query(FinancialEntry).filter_by(order_id=o1, installment=1).one()
        first.paid_at, first.paid_amount = TODAY, first.amount
        db.commit()
    set_status(o1, "shipped")
    assert [(x.installment, x.paid_at) for x in entries(o1)] == [(1, TODAY)]
    set_status(o1, "delivered")
    open_ = [x for x in entries(o1) if x.paid_at is None]
    assert len(open_) == 3 and sum(x.amount for x in open_) == Decimal("66.66"), open_
    set_status(o1, "canceled")
    assert [x.paid_at for x in entries(o1)] == [TODAY]

    # the edit form also counts; editing while still delivered doesn't touch the installments
    oe = new_order()
    r = c.put(f"/api/orders/{oe}", headers=admin, json=body(status="delivered", payment_method="Pix", payment_terms="30/60"))
    assert r.status_code == 200, r.text
    assert [(x.amount, x.payment_method) for x in entries(oe)] == [(Decimal("50.00"), "Pix")] * 2
    r = c.put(f"/api/orders/{oe}", headers=admin, json=body(
        status="delivered", payment_method="Pix", payment_terms="30/60",
        items=[{"product_id": product, "color_id": color, "size": "P", "quantity": 2}]))
    assert r.status_code == 200, r.text
    assert [x.amount for x in entries(oe)] == [Decimal("50.00")] * 2
    assert "installments" not in r.json()  # order payloads (also read by sellers) never carry them

    # an order that still has entries can't be deleted (only quotes can, and a paid one stays)
    set_status(o1, "quote")
    r = c.delete(f"/api/orders/{o1}", headers=admin)
    assert r.status_code == 400 and "parcelas" in r.json()["detail"], r.text
    assert c.delete(f"/api/orders/{new_order(status='quote')}", headers=admin).status_code == 204

    # ---- /api/finance: admin only ----
    for path in ("/api/finance/entries", "/api/finance/summary?kind=payable"):
        assert c.get(path, headers=A).status_code == 403
    assert c.post("/api/finance/entries", headers=A, json={}).status_code == 403
    assert c.post(f"/api/finance/orders/{oe}/generate", headers=A).status_code == 403

    def post_entry(**kw):
        return c.post("/api/finance/entries", headers=admin, json={
            "kind": "payable", "description": "Aluguel", "amount": 1500, "due_date": "2027-01-31",
            "category": "Aluguel", **kw})

    # monthly repetition, from the first date (no drift)
    r = post_entry(repeat_months=12, supplier="Imobiliária")
    assert r.status_code == 201, r.text
    rent = r.json()
    assert len(rent) == 12 and [x["due_date"] for x in rent[:3]] == ["2027-01-31", "2027-02-28", "2027-03-31"]
    assert (rent[2]["description"], rent[2]["installment"], rent[2]["installments"]) == ("Aluguel (3/12)", 3, 12)
    assert post_entry(category="Viagem").status_code == 400
    assert post_entry(amount=0).status_code == 422
    assert post_entry(repeat_months=61).status_code == 422
    assert post_entry(kind="receivable", order_id=999999).status_code == 400

    bill = post_entry(description="Fio", amount=100, due_date=(TODAY - timedelta(days=1)).isoformat(),
                      category="Matéria-prima").json()[0]
    assert (bill["status"], bill["category"], bill["supplier"]) == ("overdue", "Matéria-prima", None)

    # pay / pay twice / can't change a paid amount / unpay
    def pay(eid, **kw):
        return c.post(f"/api/finance/entries/{eid}/pay", headers=admin, json=kw)

    r = pay(bill["id"], paid_amount=98.5)
    assert r.status_code == 200 and (r.json()["status"], r.json()["paid_at"], r.json()["paid_amount"]) == \
        ("paid", TODAY.isoformat(), 98.5), r.text
    assert pay(bill["id"]).status_code == 400
    upd = {"description": "Fio", "amount": 120, "due_date": bill["due_date"], "category": "Matéria-prima"}
    assert c.put(f"/api/finance/entries/{bill['id']}", headers=admin, json=upd).status_code == 400
    r = c.post(f"/api/finance/entries/{bill['id']}/unpay", headers=admin)
    assert (r.json()["paid_at"], r.json()["paid_amount"]) == (None, None)
    assert c.put(f"/api/finance/entries/{bill['id']}", headers=admin, json=upd).json()["amount"] == 120

    # split: total preserved, the original keeps its due date (Review Focus 5)
    split = f"/api/finance/entries/{bill['id']}/split"
    assert c.post(split, headers=admin, json={"amount": 120, "due_date": "2026-12-01"}).status_code == 400
    r = c.post(split, headers=admin, json={"amount": 20, "due_date": "2026-12-01"})
    assert r.status_code == 201, r.text
    part = r.json()
    assert part["description"] == "Fio (restante)"
    found = c.get("/api/finance/entries", headers=admin,
                  params={"kind": "payable", "status": "all", "search": "fio"}).json()
    assert sorted((x["amount"], x["due_date"]) for x in found) == [(20.0, "2026-12-01"), (100.0, bill["due_date"])]
    pay(part["id"])
    assert c.post(f"/api/finance/entries/{part['id']}/split", headers=admin,
                  json={"amount": 5, "due_date": "2026-12-01"}).status_code == 400

    # cards
    s = c.get("/api/finance/summary", headers=admin, params={"kind": "payable"}).json()
    assert s == {"overdue": {"total": 100.0, "count": 1}, "due_soon": {"total": 0.0, "count": 0},
                 "open": {"total": 18100.0, "count": 13}, "paid_this_month": {"total": 20.0, "count": 1}}, s
    assert [x["id"] for x in c.get("/api/finance/entries", headers=admin,
                                    params={"kind": "payable", "status": "overdue"}).json()] == [bill["id"]]
    assert c.get("/api/finance/entries", headers=admin, params={"kind": "payable", "category": "Aluguel",
                                                                "start": "2027-01-01", "end": "2027-02-28"}).json()[1]["due_date"] == "2027-02-28"

    # receivables show the order's *current* customer (Review Focus 2) and search is case-insensitive (3)
    rec = c.get("/api/finance/entries", headers=admin, params={"kind": "receivable", "order_id": oe}).json()
    assert [x["customer_name"] for x in rec] == ["Loja Bela"] * 2
    assert c.get("/api/finance/entries", headers=admin, params={"kind": "receivable", "status": "all",
                                                                "search": "bela"}).json()
    c.put(f"/api/orders/{oe}", headers=admin, json=body(status="delivered", payment_method="Pix", payment_terms="30/60",
                                                         customer_id=cust2))
    rec = c.get("/api/finance/entries", headers=admin, params={"kind": "receivable", "order_id": oe}).json()
    assert [x["customer_name"] for x in rec] == ["Malharia Sul"] * 2

    # "Gerar parcelas" for orders delivered before this feature
    old = new_order(status="delivered", payment_terms="30/60")
    gen = f"/api/finance/orders/{old}/generate"
    assert c.post(gen, headers=admin).status_code == 400  # already has open ones
    with SessionLocal() as db:
        db.query(FinancialEntry).filter(FinancialEntry.order_id == old).delete()
        db.commit()
    r = c.post(gen, headers=admin)
    assert r.status_code == 201 and len(r.json()) == 2, r.text
    assert c.post(f"/api/finance/orders/{new_order()}/generate", headers=admin).status_code == 400  # not delivered
    assert c.post(f"/api/finance/orders/{oz}/generate", headers=admin).status_code == 400  # nothing owed

    # a manual receivable linked to an order
    r = post_entry(kind="receivable", description="Acerto", amount=10, order_id=oe, category=None)
    assert r.status_code == 201 and (r.json()[0]["order_id"], r.json()[0]["category"]) == (oe, None), r.text

    assert c.delete(f"/api/finance/entries/{part['id']}", headers=admin).status_code == 204
    assert c.delete(f"/api/finance/entries/{part['id']}", headers=admin).status_code == 404

print("finance checks OK")
