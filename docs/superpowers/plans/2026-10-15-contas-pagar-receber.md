# Contas a pagar e a receber — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Admin-only accounts receivable (installments generated from delivered orders) and accounts payable (manual bills with monthly repetition), with manual settlement, inside the Faturamento screen.

**Architecture:** One table `financial_entries` (`kind` = receivable/payable). Pure rules in `backend/app/finance.py`; order status hooks in `routers/orders.py` call them inside the same transaction; CRUD/settlement in a new admin-only `routers/finance.py`. Frontend: one `Finance.jsx` page used by two tabs under `/revenue`, plus a "Parcelas" block in the order detail.

**Tech Stack:** FastAPI, SQLAlchemy 2 (SQLite dev / Postgres prod), Pydantic 2; React 18 + Vite + react-router-dom (hash data router), axios.

**Spec:** `docs/superpowers/specs/2026-10-15-contas-pagar-receber-design.md`

## Global Constraints

- Code (names, routes, tables, columns, comments, CSS classes) in English; all user-visible text in pt-BR (see `CLAUDE.md`).
- No migration tool: new tables come from `Base.metadata.create_all` (already called in `main.py` lifespan). This feature adds **no** columns to existing tables.
- "Today" is always `clock.today_br()` called through the module (`from .. import clock` / `from . import clock`), never `date.today()` or `func.current_date()` — tests patch `clock.today_br`.
- Money: never sum floats. Use `finance.to_cents` / `finance.to_decimal`; `Order.total` is a float.
- The whole `/api/finance` router is admin-only (`dependencies=[Depends(require_admin)]`). `GET /orders/{id}` (`full()`) never includes installments.
- Backend tests are plain scripts with `assert`, run from `backend/` as `python test_finance.py` (no pytest). They use a throwaway SQLite file.
- Frontend has no test runner; verify with `npx vite build` (from `frontend/`) plus the manual checks listed in Task 5.
- Session uses `autoflush=False` (`database.py`): flush explicitly when a query must see pending objects.

## Review Focus

1. **Balance smaller than the number of installments** (e.g. R$ 0,05 on "Quinzenal") → must create one R$ 0,05 entry, never R$ 0,00 entries. Test added in Task 2.
2. **Order's customer changed after delivery** → receivables list must show the new customer (customer comes through the order). Test added in Task 3.
3. **Case/accents in search** ("bela" finds "Loja Bela") → `ilike`, not `like` (Postgres `LIKE` is case-sensitive). Test added in Task 3.
4. **Month-end and leap years in repetition** (30/11 + 3 months → 29/02/2028; 31/01 → 28/02 → 31/03, no drift). Test in Task 1.
5. **Splitting with an amount ≥ the entry, or a paid entry** → 400, totals preserved. Test in Task 3.

---

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models.py` (modify) | `FinancialEntry` model, `ENTRY_KINDS`, `PAYABLE_CATEGORIES` |
| `backend/app/finance.py` (create) | Pure rules + order installment create/remove (no FastAPI) |
| `backend/app/routers/orders.py` (modify) | Call the rules on status transitions; block deleting orders with entries |
| `backend/app/schemas.py` (modify) | `EntryIn`, `EntryUpdate`, `PayIn`, `SplitIn` |
| `backend/app/routers/finance.py` (create) | `/api/finance` endpoints |
| `backend/app/main.py` (modify) | Register the finance router |
| `backend/test_finance.py` (create) | Self-check script for everything above |
| `frontend/src/components/RevenueTabs.jsx` (create) | Vendas / Contas a receber / Contas a pagar tabs |
| `frontend/src/pages/Finance.jsx` (create) | List, cards, filters, pay/edit/new modals; exports `EntryStatus`, `PayModal` |
| `frontend/src/pages/Revenue.jsx` (modify) | Show the tabs |
| `frontend/src/App.jsx` (modify) | Two admin routes |
| `frontend/src/styles.css` (modify) | Tab links, cards grid, date inputs in filter bar |
| `frontend/src/pages/OrderDetail.jsx` (modify) | "Parcelas" block + "Gerar parcelas" |

---

### Task 1: Model and pure rules

**Files:**
- Modify: `backend/app/models.py` (constants near the top; class at the end of the file)
- Create: `backend/app/finance.py`
- Create: `backend/test_finance.py`

**Interfaces:**
- Produces (in `app/models.py`): `ENTRY_KINDS = ["receivable", "payable"]`, `PAYABLE_CATEGORIES` (list[str]), class `FinancialEntry` with columns `id, kind, description, amount (Numeric→Decimal), due_date, paid_at, paid_amount, payment_method, notes, order_id, supplier, category, installment, installments, created_at` and relationship `order`.
- Produces (in `app/finance.py`): `installment_days(terms: str | None) -> list[int]`, `split_cents(total_cents: int, n: int) -> list[int]`, `add_months(d: date, n: int) -> date`, `to_cents(v) -> int`, `to_decimal(v) -> Decimal`, `entry_status(e: FinancialEntry, today: date) -> str` (`"paid" | "overdue" | "open"`).

- [ ] **Step 1: Write the failing test**

Create `backend/test_finance.py`:

```python
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

print("finance checks OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python test_finance.py`
Expected: FAIL — `ImportError: cannot import name 'finance' from 'app'` (or `FinancialEntry`).

- [ ] **Step 3: Add the model**

In `backend/app/models.py`, after the line `PRICE_TABLES = [...]` add:

```python
ENTRY_KINDS = ["receivable", "payable"]
# Business content, so in Portuguese; a payable's category must be one of these
PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"]
```

At the end of the file add:

```python
class FinancialEntry(Base):
    """A receivable installment or a payable bill — see finance.py for the rules."""
    __tablename__ = "financial_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), index=True)  # see ENTRY_KINDS
    description: Mapped[str] = mapped_column(String(200))
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    due_date: Mapped[_dt.date] = mapped_column(Date, index=True)
    paid_at: Mapped[_dt.date | None] = mapped_column(Date, nullable=True)  # NULL = still open
    paid_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(40))
    notes: Mapped[str | None] = mapped_column(Text)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), nullable=True, index=True)
    supplier: Mapped[str | None] = mapped_column(String(160))  # payables
    category: Mapped[str | None] = mapped_column(String(40))  # payables, see PAYABLE_CATEGORIES
    installment: Mapped[int | None] = mapped_column(Integer)  # "2" of "2/3"
    installments: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    order: Mapped["Order | None"] = relationship()
```

- [ ] **Step 4: Write the rules module**

Create `backend/app/finance.py`:

```python
"""Accounts receivable/payable rules. No FastAPI here, so they're easy to test."""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import FinancialEntry

QUINZENAL_DAYS = list(range(15, 151, 15))  # "Quinzenal" = 10 installments, every 15 days


def installment_days(terms: str | None) -> list[int]:
    """Days after delivery for each installment of an order's payment terms."""
    t = (terms or "").strip()
    if t.lower() == "quinzenal":
        return QUINZENAL_DAYS
    parts = [p.strip() for p in t.split("/")]
    if all(p.isdigit() for p in parts):
        return [int(p) for p in parts]
    return [0]  # "À vista" and anything unknown: one installment, due on delivery


def split_cents(total_cents: int, n: int) -> list[int]:
    """Equal split; the leftover cents go to the first installment."""
    base, rest = divmod(total_cents, n)
    return [base + rest] + [base] * (n - 1)


def add_months(d: date, n: int) -> date:
    """Same day n months later, capped at the month's last day (31/01 + 1 → 28/02)."""
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def to_decimal(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def to_cents(v) -> int:
    return int(to_decimal(v) * 100)


def entry_status(e: FinancialEntry, today: date) -> str:
    if e.paid_at:
        return "paid"
    return "overdue" if e.due_date < today else "open"
```

- [ ] **Step 5: Run test to verify it passes**

Run (from `backend/`): `python test_finance.py`
Expected: last line `finance checks OK`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models.py backend/app/finance.py backend/test_finance.py
git commit -m "Add financial entries model and installment rules"
```

---

### Task 2: Installments follow the order's status

**Files:**
- Modify: `backend/app/finance.py` (append functions)
- Modify: `backend/app/routers/orders.py` (imports, new helper after `_find`, `create`, `update`, `change_status`, `delete`)
- Test: `backend/test_finance.py`

**Interfaces:**
- Consumes: Task 1 (`FinancialEntry`, `installment_days`, `split_cents`, `to_cents`).
- Produces (in `app/finance.py`): `open_installments(db, order_id) -> Query`, `create_order_installments(db, order: Order, today: date) -> list[FinancialEntry]` (adds to session, no commit; `[]` when it has open installments or the balance ≤ 0), `remove_open_installments(db, order: Order) -> None` (no commit).

- [ ] **Step 1: Write the failing test**

In `backend/test_finance.py`, replace the last line `print("finance checks OK")` with:

```python
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

print("finance checks OK")
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python test_finance.py`
Expected: FAIL at `assert [(e_.amount, ...` (no entries are created yet: the list is `[]`).

- [ ] **Step 3: Add the order rules**

Append to `backend/app/finance.py` (and change its imports as shown):

```python
from datetime import date, timedelta  # replaces "from datetime import date"

from sqlalchemy.orm import Session  # new import

from .models import FinancialEntry, Order  # replaces "from .models import FinancialEntry"
```

```python
def open_installments(db: Session, order_id: int):
    return db.query(FinancialEntry).filter(FinancialEntry.order_id == order_id, FinancialEntry.paid_at.is_(None))


def create_order_installments(db: Session, order: Order, today: date) -> list[FinancialEntry]:
    """Receivables for what's still owed on a delivered order. Does nothing if it already has open
    installments or nothing is owed. Adds to the session; the caller commits."""
    if open_installments(db, order.id).first():
        return []
    paid = db.query(FinancialEntry).filter(FinancialEntry.order_id == order.id, FinancialEntry.paid_at.isnot(None))
    balance = to_cents(order.total) - sum(to_cents(e.amount) for e in paid)
    if balance <= 0:
        return []
    days = installment_days(order.payment_terms)
    parts = [(d, c) for d, c in zip(days, split_cents(balance, len(days))) if c > 0]
    n = len(parts)
    entries = [FinancialEntry(kind="receivable", description=f"Pedido {order.id:05d} — parcela {i}/{n}",
                              amount=Decimal(c) / 100, due_date=today + timedelta(days=d),
                              payment_method=order.payment_method, order_id=order.id,
                              installment=i, installments=n)
               for i, (d, c) in enumerate(parts, start=1)]
    db.add_all(entries)
    return entries


def remove_open_installments(db: Session, order: Order) -> None:
    """Paid installments stay; the caller commits."""
    open_installments(db, order.id).delete(synchronize_session=False)
```

- [ ] **Step 4: Hook it into the order routes**

In `backend/app/routers/orders.py`:

1. Change the imports:

```python
from .. import clock, finance
```
and add `FinancialEntry` to the `from ..models import ...` line.

2. Add right after `_find`:

```python
def _sync_installments(db: Session, o: Order, old_status: str | None) -> None:
    """Entering "delivered" creates the receivables; leaving it drops the unpaid ones.
    Runs after a flush and before the single commit, so the order and its installments save together."""
    if o.status == "delivered" and old_status != "delivered":
        finance.create_order_installments(db, o, clock.today_br())
    elif old_status == "delivered" and o.status != "delivered":
        finance.remove_open_installments(db, o)
```

3. In `create`, replace

```python
    db.add(o)
    db.commit()
```
with
```python
    db.add(o)
    db.flush()  # the installment descriptions need the order id
    _sync_installments(db, o, old_status=None)
    db.commit()
```

4. Replace the body of `update` from `o = _find(oid, db)` to the end with:

```python
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
```

5. Replace the body of `change_status` after the status validation with:

```python
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
```

6. In `delete`, after the quote check add:

```python
    if db.query(FinancialEntry).filter(FinancialEntry.order_id == oid).first():
        raise HTTPException(400, "Este pedido tem parcelas lançadas. Exclua as parcelas antes.")
```

- [ ] **Step 5: Run the tests**

Run (from `backend/`): `python test_finance.py` → `finance checks OK`.
Then the existing suite (they create orders through the same routes):
`for t in test_permissions test_dashboard test_performance test_security test_mailer test_price_tables test_cities test_import_catalog; do python $t.py 2>&1 | tail -1; done`
Expected: each prints its `... OK` line. If `test_performance` fails on a query count, check that `full()` was not changed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/finance.py backend/app/routers/orders.py backend/test_finance.py
git commit -m "Generate receivables when an order is delivered and drop open ones when it leaves"
```

---

### Task 3: `/api/finance` endpoints

**Files:**
- Modify: `backend/app/schemas.py` (new section at the end)
- Create: `backend/app/routers/finance.py`
- Modify: `backend/app/main.py` (router import + registration)
- Modify: `backend/app/finance.py` (nothing new; used as is)
- Test: `backend/test_finance.py`

**Interfaces:**
- Consumes: Tasks 1–2 (`FinancialEntry`, `PAYABLE_CATEGORIES`, `finance.*`).
- Produces (HTTP, all admin-only, JSON entry shape used by the frontend):
  `{id, kind, description, amount: float, due_date: "YYYY-MM-DD", paid_at, paid_amount: float|null, payment_method, notes, order_id, customer_name, supplier, category, installment, installments, status: "open"|"overdue"|"paid"}`
  - `GET /api/finance/entries?kind&status=open|overdue|paid|all&start&end&search&category&order_id` → `[entry]` (default status `open`)
  - `GET /api/finance/summary?kind=` → `{overdue, due_soon, open, paid_this_month}`, each `{total: float, count: int}`
  - `POST /api/finance/entries` (201) → `[entry]` (one per repeated month)
  - `PUT /api/finance/entries/{id}` → `entry`
  - `POST /api/finance/entries/{id}/pay` → `entry`; `POST /api/finance/entries/{id}/unpay` → `entry`
  - `POST /api/finance/entries/{id}/split` (201) → the new `entry`
  - `DELETE /api/finance/entries/{id}` (204)
  - `POST /api/finance/orders/{order_id}/generate` (201) → `[entry]`

- [ ] **Step 1: Write the failing test**

In `backend/test_finance.py`, insert this block **inside** the `with TestClient(app) as c:` block, right after the delete-order assertions (before the final unindented `print`):

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `python test_finance.py`
Expected: FAIL at the first `/api/finance` assertion (404 instead of 403).

- [ ] **Step 3: Add the schemas**

Append to `backend/app/schemas.py`:

```python
# ---------- Finance ----------
Money = Annotated[float, Field(gt=0, le=9_999_999_999, allow_inf_nan=False)]


class EntryUpdate(BaseModel):
    description: str = Field(min_length=1, max_length=200)
    amount: Money
    due_date: _dt.date
    payment_method: str | None = Field(default=None, max_length=40)
    notes: str | None = None
    supplier: str | None = Field(default=None, max_length=160)
    category: str | None = None


class EntryIn(EntryUpdate):
    kind: Literal["receivable", "payable"]
    order_id: int | None = None
    repeat_months: int = Field(default=1, ge=1, le=60)


class PayIn(BaseModel):
    paid_at: _dt.date | None = None  # default: today
    paid_amount: Money | None = None  # default: the entry's amount
    payment_method: str | None = Field(default=None, max_length=40)


class SplitIn(BaseModel):
    amount: Money
    due_date: _dt.date
```

- [ ] **Step 4: Add the router**

Create `backend/app/routers/finance.py`:

```python
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
```

- [ ] **Step 5: Register the router**

In `backend/app/main.py`:
- change `from .routers import auth, colors, customers, dashboard, orders, products, settings as settings_router, users`
  to `from .routers import auth, colors, customers, dashboard, finance, orders, products, settings as settings_router, users`
- change `for r in (auth, users, customers, colors, products, orders, dashboard, settings_router):`
  to `for r in (auth, users, customers, colors, products, orders, dashboard, finance, settings_router):`

- [ ] **Step 6: Run the tests**

Run (from `backend/`): `python test_finance.py` → `finance checks OK`.
Then the existing suite as in Task 2 Step 5 — all `OK`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/finance.py backend/app/main.py backend/test_finance.py
git commit -m "Add admin-only /api/finance endpoints for entries, settlement and summary"
```

---

### Task 4: Faturamento tabs and the Finance page

**Files:**
- Create: `frontend/src/components/RevenueTabs.jsx`
- Create: `frontend/src/pages/Finance.jsx`
- Modify: `frontend/src/pages/Revenue.jsx` (import + render tabs at the top of the page)
- Modify: `frontend/src/App.jsx` (import + two routes)
- Modify: `frontend/src/styles.css` (append)

**Interfaces:**
- Consumes: Task 3 HTTP API and entry shape.
- Produces (exports of `pages/Finance.jsx`, used by Task 5): `EntryStatus({ s })`, `PayModal({ entry, onClose, onDone })`, default `Finance({ kind })`.

- [ ] **Step 1: Tabs component**

Create `frontend/src/components/RevenueTabs.jsx`:

```jsx
import { NavLink } from "react-router-dom";

const TABS = [["/revenue", "Vendas"], ["/revenue/receivables", "Contas a receber"], ["/revenue/payables", "Contas a pagar"]];

export default function RevenueTabs() {
  return (
    <nav className="segmented revenue-tabs" aria-label="Seções do faturamento">
      {TABS.map(([to, label]) => <NavLink key={to} to={to} end>{label}</NavLink>)}
    </nav>
  );
}
```

- [ ] **Step 2: Finance page**

Create `frontend/src/pages/Finance.jsx`:

```jsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { addDays, dateBR, localDate, money, orderNumber } from "../format";
import { EmptyState, ErrorBox, Field, Modal, useConfirm } from "../components/ui";
import RevenueTabs from "../components/RevenueTabs";

// Same list as PAYABLE_CATEGORIES in backend/app/models.py
const PAYABLE_CATEGORIES = ["Matéria-prima", "Aluguel", "Salários", "Impostos", "Energia", "Manutenção", "Outros"];
const PAYMENT_METHODS = ["Boleto", "Pix", "Transferência", "Cheque", "Dinheiro", "Cartão"];
const STATUS_LABEL = { open: "Em aberto", overdue: "Vencida", paid: "Paga" };
const STATUS_FILTERS = [["open", "Em aberto"], ["overdue", "Vencidas"], ["paid", "Pagas"], ["all", "Todas"]];

export const EntryStatus = ({ s }) => <span className={`tag ${s === "overdue" ? "tag-warning" : ""}`}>{STATUS_LABEL[s]}</span>;

// Keeps a value that isn't in the list (e.g. a payment method typed on an old order) selectable
const withValue = (list, v) => (v && !list.includes(v) ? [...list, v] : list);

export function PayModal({ entry, onClose, onDone }) {
  const [f, setF] = useState({ paid_at: localDate(), paid_amount: entry.amount, payment_method: entry.payment_method || "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function save(e) {
    e.preventDefault();
    setError(""); setBusy(true);
    try {
      await api.post(`/finance/entries/${entry.id}/pay`, {
        paid_at: f.paid_at, paid_amount: Number(f.paid_amount), payment_method: f.payment_method || null,
      });
      onDone();
    } catch (err) { setError(errorMessage(err)); setBusy(false); }
  }

  return (
    <Modal title={`Dar baixa · ${entry.description}`} onClose={onClose}>
      <form onSubmit={save} className="form-grid">
        <Field label="Data do pagamento">
          <input type="date" required value={f.paid_at} onChange={(e) => setF({ ...f, paid_at: e.target.value })} />
        </Field>
        <Field label="Valor pago (R$)">
          <input type="number" step="0.01" min="0.01" required value={f.paid_amount}
            onChange={(e) => setF({ ...f, paid_amount: e.target.value })} />
        </Field>
        <Field label="Forma de pagamento" span={2}>
          <select value={f.payment_method} onChange={(e) => setF({ ...f, payment_method: e.target.value })}>
            <option value="">—</option>
            {withValue(PAYMENT_METHODS, entry.payment_method).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2"><button className="btn btn-primary" disabled={busy}>Confirmar baixa</button></div>
      </form>
    </Modal>
  );
}

const EMPTY = { description: "", amount: "", due_date: localDate(), payment_method: "", notes: "", supplier: "",
  category: "Outros", order_number: "", repeat_months: 1 };

function EntryModal({ kind, entry, onClose, onDone }) {
  const [confirmDialog, ask] = useConfirm();
  const isNew = !entry;
  const payable = kind === "payable";
  const paid = Boolean(entry?.paid_at);
  const [f, setF] = useState(() => (entry ? { ...EMPTY, ...entry, supplier: entry.supplier || "", notes: entry.notes || "",
    payment_method: entry.payment_method || "", category: entry.category || "Outros" } : EMPTY));
  const [split, setSplit] = useState(null); // { amount, due_date } while splitting
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const input = (k) => ({ value: f[k] ?? "", onChange: (e) => setF({ ...f, [k]: e.target.value }) });

  async function run(request) {
    setError(""); setBusy(true);
    try { await request(); onDone(); } catch (err) { setError(errorMessage(err)); setBusy(false); }
  }

  function save(e) {
    e.preventDefault();
    const body = {
      description: f.description, amount: Number(f.amount), due_date: f.due_date,
      payment_method: f.payment_method || null, notes: f.notes || null,
      supplier: payable ? f.supplier || null : null, category: payable ? f.category : null,
    };
    run(() => (isNew
      ? api.post("/finance/entries", { ...body, kind, repeat_months: Number(f.repeat_months) || 1,
          order_id: !payable && f.order_number ? Number(f.order_number) : null })
      : api.put(`/finance/entries/${entry.id}`, body)));
  }

  async function remove() {
    if (!(await ask({ title: "Excluir este lançamento?", message: entry.description, confirmLabel: "Excluir", danger: true }))) return;
    run(() => api.delete(`/finance/entries/${entry.id}`));
  }

  const title = isNew ? (payable ? "Lançar conta a pagar" : "Lançar conta a receber") : entry.description;
  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={save} className="form-grid">
        <Field label="Descrição" span={2}><input required maxLength={200} {...input("description")} /></Field>
        {payable ? (
          <>
            <Field label="Fornecedor / favorecido"><input maxLength={160} {...input("supplier")} /></Field>
            <Field label="Categoria">
              <select {...input("category")}>{PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}</select>
            </Field>
          </>
        ) : isNew && (
          <Field label="Nº do pedido (opcional)" span={2}>
            <input inputMode="numeric" {...input("order_number")} onChange={(e) => setF({ ...f, order_number: e.target.value.replace(/\D/g, "") })} />
          </Field>
        )}
        <Field label="Valor (R$)">
          <input type="number" step="0.01" min="0.01" required disabled={paid} {...input("amount")} />
        </Field>
        <Field label={isNew ? "1º vencimento" : "Vencimento"}><input type="date" required {...input("due_date")} /></Field>
        <Field label="Forma de pagamento">
          <select {...input("payment_method")}>
            <option value="">—</option>
            {withValue(PAYMENT_METHODS, entry?.payment_method).map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </Field>
        {isNew && (
          <Field label="Repetir mensalmente por (meses)">
            <input type="number" min="1" max="60" required {...input("repeat_months")} />
          </Field>
        )}
        <Field label="Observações" span={2}><textarea rows={2} {...input("notes")} /></Field>
        {paid && <p className="muted span-2">Paga em {dateBR(entry.paid_at)} · {money(entry.paid_amount)}. Para mudar o valor, desfaça a baixa.</p>}

        {split && (
          <div className="span-2 form-grid">
            <Field label="Valor a separar (R$)">
              <input type="number" step="0.01" min="0.01" value={split.amount} onChange={(e) => setSplit({ ...split, amount: e.target.value })} />
            </Field>
            <Field label="Vencimento da nova parcela">
              <input type="date" value={split.due_date} onChange={(e) => setSplit({ ...split, due_date: e.target.value })} />
            </Field>
            <div className="actions span-2">
              <button type="button" className="btn" onClick={() => setSplit(null)}>Cancelar</button>
              <button type="button" className="btn btn-primary" disabled={busy || !split.amount}
                onClick={() => run(() => api.post(`/finance/entries/${entry.id}/split`, { amount: Number(split.amount), due_date: split.due_date }))}>
                Confirmar desmembramento
              </button>
            </div>
          </div>
        )}

        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2">
          {!isNew && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
          {!isNew && !paid && !split && (
            <button type="button" className="btn" onClick={() => setSplit({ amount: "", due_date: addDays(entry.due_date, 30) })}>Desmembrar</button>
          )}
          {paid && <button type="button" className="btn" disabled={busy} onClick={() => run(() => api.post(`/finance/entries/${entry.id}/unpay`))}>Desfazer baixa</button>}
          <button className="btn btn-primary" disabled={busy}>{isNew ? "Lançar" : "Salvar"}</button>
        </div>
      </form>
      {confirmDialog}
    </Modal>
  );
}

function Card({ label, card, onClick }) {
  return (
    <div className="kpi kpi-clickable" role="button" tabIndex={0} onClick={onClick}
      onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } }}>
      <span>{label}</span>
      <strong>{money(card.total)}</strong>
      <small>{card.count} {card.count === 1 ? "lançamento" : "lançamentos"}</small>
    </div>
  );
}

export default function Finance({ kind }) {
  const receivable = kind === "receivable";
  const [filters, setFilters] = useState({ status: "open", start: "", end: "", search: "", category: "" });
  const [list, setList] = useState([]);
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");
  const [paying, setPaying] = useState(null);
  const [editing, setEditing] = useState(null); // entry, or "new"

  function load() {
    const { status, start, end, search, category } = filters;
    api.get("/finance/entries", { params: { kind, status, search, category, start: start || undefined, end: end || undefined } })
      .then((r) => setList(r.data)).catch((e) => setError(errorMessage(e)));
    api.get("/finance/summary", { params: { kind } })
      .then((r) => setSummary(r.data)).catch((e) => setError(errorMessage(e)));
  }
  useEffect(() => { const t = setTimeout(load, filters.search ? 250 : 0); return () => clearTimeout(t); }, [kind, filters]);

  const setFilter = (k) => (e) => setFilters({ ...filters, [k]: e.target.value });
  const show = (next) => setFilters({ ...filters, start: "", end: "", ...next });
  const today = localDate();
  const done = () => { setPaying(null); setEditing(null); load(); };

  return (
    <div className="page">
      <RevenueTabs />
      <header className="page-header">
        <h1>{receivable ? "Contas a receber" : "Contas a pagar"}</h1>
        <button className="btn btn-primary" onClick={() => setEditing("new")}>Lançar conta</button>
      </header>
      <ErrorBox msg={error} />

      {summary && (
        <div className="finance-cards">
          <Card label="Vencido" card={summary.overdue} onClick={() => show({ status: "overdue" })} />
          <Card label="Vence em 7 dias" card={summary.due_soon} onClick={() => show({ status: "open", start: today, end: addDays(today, 7) })} />
          <Card label="Em aberto" card={summary.open} onClick={() => show({ status: "open" })} />
          <Card label={receivable ? "Recebido no mês" : "Pago no mês"} card={summary.paid_this_month} onClick={() => show({ status: "paid" })} />
        </div>
      )}

      <section className="panel">
        <div className="filter-bar">
          <input placeholder={receivable ? "Buscar por cliente ou descrição" : "Buscar por fornecedor ou descrição"}
            value={filters.search} onChange={setFilter("search")} />
          <select value={filters.status} onChange={setFilter("status")} aria-label="Situação">
            {STATUS_FILTERS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          {!receivable && (
            <select value={filters.category} onChange={setFilter("category")} aria-label="Categoria">
              <option value="">Todas as categorias</option>
              {PAYABLE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
            </select>
          )}
          <label className="muted">Vencimento de <input type="date" value={filters.start} onChange={setFilter("start")} /></label>
          <label className="muted">até <input type="date" value={filters.end} onChange={setFilter("end")} /></label>
        </div>

        {!list.length ? <EmptyState text="Nenhum lançamento encontrado." /> : (
          <table className="table">
            <thead>
              <tr>
                <th>Vencimento</th><th>{receivable ? "Cliente" : "Fornecedor"}</th><th>{receivable ? "Pedido" : "Categoria"}</th>
                <th>Descrição</th><th>Parcela</th><th className="num">Valor</th><th>Situação</th><th></th>
              </tr>
            </thead>
            <tbody>
              {list.map((x) => (
                <tr key={x.id} className="clickable" onClick={() => setEditing(x)}>
                  <td>{dateBR(x.due_date)}</td>
                  <td>{(receivable ? x.customer_name : x.supplier) || "—"}</td>
                  <td>{receivable
                    ? (x.order_id ? <Link to={`/orders/${x.order_id}`} onClick={(e) => e.stopPropagation()}>{orderNumber(x.order_id)}</Link> : "—")
                    : x.category}</td>
                  <td>{x.description}</td>
                  <td>{x.installments ? `${x.installment}/${x.installments}` : "—"}</td>
                  <td className="num">{money(x.amount)}</td>
                  <td><EntryStatus s={x.status} /></td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {x.paid_at
                      ? <span className="muted">pago em {dateBR(x.paid_at)}</span>
                      : <button className="btn btn-light" onClick={() => setPaying(x)}>Dar baixa</button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {paying && <PayModal entry={paying} onClose={() => setPaying(null)} onDone={done} />}
      {editing && <EntryModal kind={kind} entry={editing === "new" ? null : editing} onClose={() => setEditing(null)} onDone={done} />}
    </div>
  );
}
```

- [ ] **Step 3: Wire the tabs and routes**

In `frontend/src/pages/Revenue.jsx`: add `import RevenueTabs from "../components/RevenueTabs";` and render `<RevenueTabs />` as the first child of `<div className="page">` (before `<header className="dashboard-header">`).

In `frontend/src/App.jsx`: add `import Finance from "./pages/Finance";` next to `import Revenue ...`, and right after the `revenue` route add:

```jsx
      {/* key: both routes render Finance, so switching tabs must start fresh state */}
      <Route path="revenue/receivables" element={<Protected admin><Finance key="receivable" kind="receivable" /></Protected>} />
      <Route path="revenue/payables" element={<Protected admin><Finance key="payable" kind="payable" /></Protected>} />
```

(The side-menu "Faturamento" link has no `end`, so it stays highlighted on the sub-routes.)

- [ ] **Step 4: Styles**

Append to `frontend/src/styles.css`:

```css
/* Faturamento tabs (NavLinks styled like .segmented buttons) */
.revenue-tabs { margin-bottom: 16px; }
.segmented a { padding: 8px 14px; font-size: 14px; color: inherit; text-decoration: none; background: var(--surface); }
.segmented a + a { border-left: 1px solid var(--line); }
.segmented a.active { background: #0c2140; color: #fff; }

/* Contas a pagar / receber */
.finance-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
@media (max-width: 800px) { .finance-cards { grid-template-columns: repeat(2, 1fr); } }
.filter-bar input[type="date"] { min-width: 0; flex: 0 0 auto; margin-left: 4px; }
```

- [ ] **Step 5: Build**

Run (from `frontend/`): `npx vite build`
Expected: `✓ built in ...` with no errors (the existing >500 kB chunk warning is fine).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/RevenueTabs.jsx frontend/src/pages/Finance.jsx frontend/src/pages/Revenue.jsx frontend/src/App.jsx frontend/src/styles.css
git commit -m "Add Contas a receber / Contas a pagar tabs to Faturamento"
```

---

### Task 5: Installments on the order detail + end-to-end check

**Files:**
- Modify: `frontend/src/pages/OrderDetail.jsx`

**Interfaces:**
- Consumes: `EntryStatus`, `PayModal` from `pages/Finance.jsx` (Task 4); `GET /api/finance/entries?order_id=&status=all`, `POST /api/finance/orders/{id}/generate` (Task 3).

- [ ] **Step 1: Add state, loading and actions**

In `frontend/src/pages/OrderDetail.jsx`:

1. Add the import: `import { EntryStatus, PayModal } from "./Finance";`
2. After `const [error, setError] = useState("");` add (hooks must stay above the early `if (!o) return`):

```jsx
  const [installments, setInstallments] = useState([]);
  const [paying, setPaying] = useState(null);
  const [generating, setGenerating] = useState(false);

  // Admin only: sellers can open this screen too and must not see the order's receivables.
  function loadInstallments() {
    if (!isAdmin) return;
    api.get("/finance/entries", { params: { order_id: id, status: "all" } })
      .then((r) => setInstallments(r.data)).catch((e) => setError(errorMessage(e)));
  }
  useEffect(loadInstallments, [id]);

  async function generate() {
    setGenerating(true);
    try { await api.post(`/finance/orders/${id}/generate`); loadInstallments(); }
    catch (e) { setError(errorMessage(e)); } finally { setGenerating(false); }
  }
```

3. In `changeStatus`, reload installments after a status change (delivering creates them, leaving removes the open ones):

```jsx
  async function changeStatus(status) {
    try { setO((await api.patch(`/orders/${id}/status`, { status })).data); loadInstallments(); }
    catch (e) { setError(errorMessage(e)); }
  }
```

- [ ] **Step 2: Render the block**

After the `if (!o) return ...` line add:

```jsx
  const paidTotal = installments.filter((x) => x.paid_at).reduce((s, x) => s + x.amount, 0);
  const canGenerate = o.status === "delivered" && !installments.some((x) => !x.paid_at) && o.total - paidTotal > 0.005;
```

And insert this section right before `<section className="panel order-summary">`:

```jsx
      {isAdmin && (installments.length > 0 || canGenerate) && (
        <section className="panel">
          <div className="panel-header">
            <h3>Parcelas</h3>
            {canGenerate && <button className="btn btn-primary" disabled={generating} onClick={generate}>Gerar parcelas</button>}
          </div>
          {installments.length > 0 && (
            <table className="table table-compact">
              <thead><tr><th>Parcela</th><th>Vencimento</th><th className="num">Valor</th><th>Situação</th><th></th></tr></thead>
              <tbody>
                {installments.map((x) => (
                  <tr key={x.id}>
                    <td>{x.installments ? `${x.installment}/${x.installments}` : x.description}</td>
                    <td>{dateBR(x.due_date)}</td>
                    <td className="num">{money(x.amount)}</td>
                    <td><EntryStatus s={x.status} /></td>
                    <td>{x.paid_at
                      ? <span className="muted">pago em {dateBR(x.paid_at)}</span>
                      : <button className="btn btn-light" onClick={() => setPaying(x)}>Dar baixa</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
```

And next to `{confirmDialog}` at the end:

```jsx
      {paying && <PayModal entry={paying} onClose={() => setPaying(null)} onDone={() => { setPaying(null); loadInstallments(); }} />}
```

- [ ] **Step 3: Build and run all backend checks**

Run (from `frontend/`): `npx vite build` → `✓ built`.
Run (from `backend/`): `for t in test_finance test_permissions test_dashboard test_performance test_security test_mailer test_price_tables test_cities test_import_catalog; do python $t.py 2>&1 | tail -1; done` → all `OK`.

- [ ] **Step 4: Manual check in the browser**

Start the backend (`uvicorn app.main:app --reload` from `backend/`) and the frontend (`npm run dev` from `frontend/`), log in as admin, then:
1. Open an order, set Situação to **Entregue** → "Parcelas" appears with the right count, values and due dates.
2. Faturamento → **Contas a receber**: the installments are listed with the customer; "Dar baixa" on one → it moves out of "Em aberto"; the "Recebido no mês" card goes up.
3. **Contas a pagar** → "Lançar conta" with "Repetir mensalmente por 3" → three entries; click one → edit, "Desmembrar", "Excluir" work.
4. Set the order back to **Enviado** → open installments disappear, the paid one stays; back to **Entregue** → "Gerar parcelas" is not needed (they come back automatically for the balance).
5. Log in as a seller → no "Parcelas" block on their order, and `#/revenue/receivables` redirects to the dashboard.
6. Phone width (DevTools ~380px): the cards wrap to 2 columns and the page has no horizontal scroll except the table.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/OrderDetail.jsx
git commit -m "Show and settle an order's installments on the order detail"
```
