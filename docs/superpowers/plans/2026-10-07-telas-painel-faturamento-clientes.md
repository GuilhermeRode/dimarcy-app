# Painel, Faturamento e Clientes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the Painel, Faturamento and Clientes screens after the prototype, backed by real data: goals, alerts, previous-period comparison and a per-customer overview.

**Architecture:** The backend computes every business rule (customer status, late orders, period goal, previous-period KPIs) in one module (`backend/app/sales.py`) plus constants in `models.py`; `/api/dashboard` grows new fields and `/api/customers/overview` is new. The frontend only draws: shared components (`PeriodPicker`, `usePeriodData`, `Delta`, `RevenueHero`, `AlertStrip`, `TeamRanking`) are composed by thin pages.

**Tech Stack:** FastAPI + SQLAlchemy 2 (SQLite dev / Postgres-ready), Pydantic v2; React 18 + react-router-dom 7 (HashRouter) + Recharts 2; Vite; Electron; Capacitor.

**Spec:** `docs/superpowers/specs/2026-10-07-telas-painel-faturamento-clientes-design.md`

## Global Constraints

- Code (names, comments, CSS classes, API fields) in English; every user-visible string in pt-BR (`CLAUDE.md`).
- No new dependencies (backend or frontend).
- "Hoje" on the server = `clock.today_br()` (UTC−3 fixed). Frontend dates = `localDate()` from `format.js`; never `toISOString()` for a calendar date.
- Sales = `SALE_STATUSES` (`confirmed`, `in_production`, `shipped`, `delivered`).
- Seller visibility: orders with `seller_id == user.id`; customers with `owner_id == user.id`. Admin sees everything.
- Customer status keys: `active` (≤ 60 days) · `at_risk` (61–150) · `inactive` (> 150) · `never_ordered` (no sale).
- Late order: `delivery_date < today` and status in `LATE_STATUSES = ["confirmed", "in_production"]`.
- Period goal = `monthly_goal × days ÷ 30.4`; `NULL` or `0` goal → `null` (UI hides goal widgets).
- Max dashboard period: 731 days; `start > end` → 400 "Período inválido."
- Company goal is never sent to a seller (not in `/dashboard`, not in `GET /settings`).
- WhatsApp link only through `whatsappUrl()` (10–11 digits after stripping a leading 55), `rel="noopener noreferrer"`.
- Clientes page size: 20.
- Run backend tests from `backend/` with the project's Python env: `python test_security.py` and `python test_dashboard.py`. Frontend: `npm run build` and `node scripts/check-format.mjs` from `frontend/`.

## Review Focus

1. Phone typed as `+55 (47) 99123-4567` or `047 9912-3456` → WhatsApp still opens the right number; junk like `abc` disables the button (Task 4 check script).
2. Browser clock at 23:30 local → "7 dias"/"Este mês" and new-order date use today, not tomorrow (Task 4 check script: `localDate`).
3. Search typed without accents/case ("itaiopolis", "adriana muller") or a CNPJ without punctuation still finds the customer (Task 4 check script: `normalize`; Task 5 uses it).
4. Fresh database with no orders → Painel, Faturamento and Clientes render with empty states, no crash (Task 2 test: dashboard on empty DB).
5. Seller with no sales in the period still appears in Faturamento with R$ 0,00; a deactivated seller appears only if they sold (Task 2 test).

---

## File Structure

**Backend**
- Create `backend/app/clock.py` — `today_br()`.
- Create `backend/app/sales.py` — visible orders/customers, `customer_overview()`, `late_filter()`.
- Modify `backend/app/models.py` — constants, `customer_status()`, `monthly_goal` columns.
- Modify `backend/app/main.py` — `_ensure_columns()` migration helper.
- Modify `backend/app/schemas.py` — goal fields; `AppSettingsOut` / `AppSettingsAdminOut`.
- Modify `backend/app/routers/settings.py`, `users.py`, `customers.py`, `orders.py`, `dashboard.py`.
- Create `backend/test_dashboard.py`.

**Frontend**
- Modify `frontend/src/format.js` — date helpers, `CUSTOMER_STATUS`, `normalize`, `whatsappUrl`, `initials`, `plural`, `compactMoney`.
- Create `frontend/scripts/check-format.mjs`.
- Create `frontend/src/components/PeriodPicker.jsx`, `usePeriodData.js`, `Delta.jsx`, `RevenueHero.jsx`, `AlertStrip.jsx`, `TeamRanking.jsx`, `CustomerPanel.jsx`, `CustomerFormModal.jsx`.
- Rewrite `frontend/src/pages/Dashboard.jsx`, `Revenue.jsx`, `Customers.jsx`.
- Modify `frontend/src/pages/OrderForm.jsx`, `Orders.jsx`, `Settings.jsx`, `Users.jsx`, `frontend/src/styles.css`, `frontend/electron/main.cjs`.

---

### Task 1: Business rules, goal columns and goal settings

**Files:**
- Create: `backend/app/clock.py`
- Modify: `backend/app/models.py` (constants after line 11; `User` and `AppSettings` columns)
- Modify: `backend/app/main.py:21-34` (migration)
- Modify: `backend/app/schemas.py` (`UserBase`, app settings schemas)
- Modify: `backend/app/routers/settings.py`, `backend/app/routers/users.py`
- Test: `backend/test_dashboard.py` (new)

**Interfaces:**
- Produces: `clock.today_br() -> date`; `models.ACTIVE_DAYS`, `AT_RISK_DAYS`, `LATE_STATUSES`, `customer_status(last_sale: date | None, today: date) -> str`; `User.monthly_goal`, `AppSettings.monthly_goal` (`Numeric(12,2)`, nullable); schemas `Goal`, `AppSettingsOut`, `AppSettingsAdminOut`.
- Callers must call `clock.today_br()` through the module (`from .. import clock`), so tests can patch `clock.today_br`.

- [ ] **Step 1: Write the failing test** — create `backend/test_dashboard.py`:

```python
"""Dashboard / customers-overview self-check. Run from backend/:  python test_dashboard.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app import clock  # noqa: E402
from app.main import app  # noqa: E402
from app.models import customer_status  # noqa: E402

TODAY = date(2026, 10, 7)
clock.today_br = lambda: TODAY

# ---- customer_status boundaries ----
assert customer_status(None, TODAY) == "never_ordered"
assert customer_status(TODAY, TODAY) == "active"
assert customer_status(TODAY - timedelta(days=60), TODAY) == "active"
assert customer_status(TODAY - timedelta(days=61), TODAY) == "at_risk"
assert customer_status(TODAY - timedelta(days=150), TODAY) == "at_risk"
assert customer_status(TODAY - timedelta(days=151), TODAY) == "inactive"


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")

    # ---- goals: company goal is admin-only, validated ----
    r = c.put("/api/settings", headers=admin, json={
        "allow_price_override": False, "max_discount_percent": 10, "monthly_goal": 60800})
    assert r.status_code == 200 and r.json()["monthly_goal"] == 60800, r.text
    assert c.put("/api/settings", headers=admin, json={
        "allow_price_override": False, "max_discount_percent": 10, "monthly_goal": -1}).status_code == 422

    def new_user(name, email, goal=None, active=True):
        r = c.post("/api/users", headers=admin, json={
            "name": name, "email": email, "password": "seller-pass-123", "role": "seller",
            "active": active, "monthly_goal": goal})
        assert r.status_code == 201, r.text
        return r.json()

    a = new_user("Ana Vendas", "a@test.com", goal=30400)
    assert a["monthly_goal"] == 30400
    b = new_user("Bruno Vendas", "b@test.com")
    assert b["monthly_goal"] is None
    seller_a = login(c, "a@test.com", "seller-pass-123")
    seller_b = login(c, "b@test.com", "seller-pass-123")

    s = c.get("/api/settings", headers=seller_a).json()
    assert "monthly_goal" not in s, s  # sellers never see the company goal
    assert c.get("/api/settings", headers=admin).json()["monthly_goal"] == 60800

    # PUT keeps the goal when the client sends it, clears it with null
    r = c.put(f"/api/users/{b['id']}", headers=admin, json={**b, "password": None, "monthly_goal": 1000})
    assert r.json()["monthly_goal"] == 1000
    r = c.put(f"/api/users/{b['id']}", headers=admin, json={**b, "password": None, "monthly_goal": None})
    assert r.json()["monthly_goal"] is None

    # TASK2_TESTS

print("dashboard checks OK")
```

- [ ] **Step 2: Run it to verify it fails**

Run (from `backend/`): `python test_dashboard.py`
Expected: FAIL — `ImportError: cannot import name 'clock' from 'app'`.

- [ ] **Step 3: Create `backend/app/clock.py`**

```python
from datetime import date, datetime, timedelta, timezone

# Brazil dropped daylight saving time in 2019, so a fixed UTC-3 offset is exact and
# needs no tz database (Windows has none without the tzdata package).
BRT = timezone(timedelta(hours=-3))


def today_br() -> date:
    """'Today' for business rules (late orders, customer status, default periods)."""
    return datetime.now(BRT).date()
```

- [ ] **Step 4: Add rules and columns in `backend/app/models.py`**

After the `SALE_STATUSES` line add:

```python
LATE_STATUSES = ["confirmed", "in_production"]  # past delivery_date in these = late

# Customer status by days since the last sale (see customer_status)
ACTIVE_DAYS = 60
AT_RISK_DAYS = 150


def customer_status(last_sale: date | None, today: date) -> str:
    if last_sale is None:
        return "never_ordered"
    days = (today - last_sale).days
    if days <= ACTIVE_DAYS:
        return "active"
    if days <= AT_RISK_DAYS:
        return "at_risk"
    return "inactive"
```

In `class User`, after `theme`:

```python
    monthly_goal: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)  # NULL/0 = no goal
```

In `class AppSettings`, after `max_discount_percent`:

```python
    monthly_goal: Mapped[float | None] = mapped_column(Numeric(12, 2), default=0)  # company goal; NULL/0 = none
```

- [ ] **Step 5: Generalize the migration in `backend/app/main.py`**

Replace `_ensure_user_columns` and its call:

```python
def _ensure_columns(table: str, columns: dict[str, str]):
    """create_all only creates missing TABLES, not missing columns on an existing one —
    there's no migration tool in this repo, so new columns get added here instead.
    `table` and the DDL are code constants, never user input."""
    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
```

In `lifespan`, replace `_ensure_user_columns()` with:

```python
    _ensure_columns("users", {"reset_token_hash": "VARCHAR(64)", "reset_token_expires_at": "TIMESTAMP",
                              "monthly_goal": "NUMERIC(12,2)"})
    _ensure_columns("app_settings", {"monthly_goal": "NUMERIC(12,2) DEFAULT 0"})
```

- [ ] **Step 6: Schemas in `backend/app/schemas.py`**

Near the top (after `class ORM`):

```python
# Monthly goal in R$: optional, non-negative, finite, fits NUMERIC(12,2).
Goal = Annotated[float | None, Field(ge=0, le=9_999_999_999, allow_inf_nan=False)]
```

Add `from typing import Annotated` to the imports. In `UserBase` add `monthly_goal: Goal = None`.

Replace the app-settings block with:

```python
# ---------- App settings ----------
class AppSettingsIn(BaseModel):
    allow_price_override: bool
    max_discount_percent: float = Field(ge=0, le=100)
    monthly_goal: Goal = None


class AppSettingsOut(ORM):
    """What every logged-in user may read (the order form needs these rules)."""
    allow_price_override: bool
    max_discount_percent: float


class AppSettingsAdminOut(AppSettingsOut):
    monthly_goal: float | None = None
```

- [ ] **Step 7: Settings router — `backend/app/routers/settings.py`**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import AppSettingsAdminOut, AppSettingsIn, AppSettingsOut
from ..security import get_current_user, require_admin
from ..settings_store import get_app_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # The company goal is admin-only; sellers read this endpoint from the order form.
    schema = AppSettingsAdminOut if user.role == "admin" else AppSettingsOut
    return schema.model_validate(get_app_settings(db))


@router.put("", response_model=AppSettingsAdminOut, dependencies=[Depends(require_admin)])
def update_settings(data: AppSettingsIn, db: Session = Depends(get_db)):
    s = get_app_settings(db)
    s.allow_price_override = data.allow_price_override
    s.max_discount_percent = data.max_discount_percent
    s.monthly_goal = data.monthly_goal
    db.commit()
    db.refresh(s)
    return s
```

- [ ] **Step 8: Users router — `backend/app/routers/users.py`**

In `create`, add `monthly_goal=data.monthly_goal` to the `User(...)` call. In `update`, after the line assigning `u.name, u.email, u.role, u.active`, add:

```python
    u.monthly_goal = data.monthly_goal
```

- [ ] **Step 9: Run tests**

Run: `python test_dashboard.py` → `dashboard checks OK`
Run: `python test_security.py` → `security checks OK`

- [ ] **Step 10: Commit**

```bash
git add backend/app/clock.py backend/app/models.py backend/app/main.py backend/app/schemas.py backend/app/routers/settings.py backend/app/routers/users.py backend/test_dashboard.py
git commit -m "Add customer status rules, monthly goals and admin-only company goal"
```

---

### Task 2: Sales module, customers overview, late filter and dashboard fields

**Files:**
- Create: `backend/app/sales.py`
- Modify: `backend/app/routers/customers.py` (new route before `get("/{cid}")`)
- Modify: `backend/app/routers/orders.py` (`list_all` gets `late`; default order date)
- Rewrite: `backend/app/routers/dashboard.py`
- Test: `backend/test_dashboard.py` (replace the `# TASK2_TESTS` line)

**Interfaces:**
- Consumes: Task 1 (`clock.today_br`, `customer_status`, `LATE_STATUSES`, `monthly_goal`).
- Produces:
  - `sales.late_filter(today: date)` → SQLAlchemy condition.
  - `sales.customer_overview(db, user, today) -> list[dict]` with keys `id, name, city, state, phone, document, owner_id, owner_name, created_at, total, orders, last_order_date, status, colors (all, by pieces desc), recent_orders (≤3: id, date, pieces, total)`.
  - `GET /api/customers/overview` → that list.
  - `GET /api/orders?late=1`.
  - `GET /api/dashboard` adds `previous_kpis`, `sales_series [{label, start, value}]`, `goal`, `by_seller[].{id, avatar_url, goal}`, `alerts {customers_at_risk, customers_never_ordered, late_orders, oldest_late_days}`; 400 on invalid period.

- [ ] **Step 1: Write the failing tests** — in `backend/test_dashboard.py`, replace the line `    # TASK2_TESTS` with:

```python
    # ---- empty database renders ----
    r = c.get("/api/dashboard", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["alerts"] == {"customers_at_risk": 0, "customers_never_ordered": 0,
                                  "late_orders": 0, "oldest_late_days": None}
    assert c.get("/api/customers/overview", headers=admin).json() == []

    # ---- catalog ----
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()
    product = c.post("/api/products", headers=admin, json={
        "reference": "R1", "description": "Blusão", "price": 100, "color_ids": [color["id"]]}).json()

    def customer(headers, name):
        r = c.post("/api/customers", headers=headers, json={"name": name, "document": "123"})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def order(headers, cid, days_ago, status="delivered", delivery_days_ago=None):
        d = TODAY - timedelta(days=days_ago)
        dd = TODAY - timedelta(days=days_ago if delivery_days_ago is None else delivery_days_ago)
        r = c.post("/api/orders", headers=headers, json={
            "customer_id": cid, "date": d.isoformat(), "delivery_date": dd.isoformat(), "status": status,
            "payment_method": "PIX", "payment_terms": "À vista",
            "items": [{"product_id": product["id"], "color_id": color["id"], "size": "P", "quantity": 1}]})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    c_active = customer(seller_a, "Ácida Modas")
    c60, c61 = customer(seller_a, "Cliente 60"), customer(seller_a, "Cliente 61")
    c150, c151 = customer(seller_a, "Cliente 150"), customer(seller_a, "Cliente 151")
    c_quote = customer(seller_a, "Só Orçamento")
    customer(seller_a, "Nunca Comprou")
    c_reassigned = customer(seller_a, "Atendido Pelo Admin")
    c_b = customer(seller_b, "Cliente do Bruno")

    order(seller_a, c_active, 0)
    for cid, days in ((c60, 60), (c61, 61), (c150, 150), (c151, 151)):
        order(seller_a, cid, days)
    order(seller_a, c_quote, 5, status="quote")
    late1 = order(seller_a, c_active, 10, status="confirmed", delivery_days_ago=1)
    late2 = order(seller_a, c_active, 10, status="in_production", delivery_days_ago=3)
    order(seller_a, c_active, 10, status="shipped", delivery_days_ago=5)      # shipped: not late
    order(seller_a, c_active, 10, status="confirmed", delivery_days_ago=0)    # due today: not late
    order(seller_a, c_active, 10, status="canceled", delivery_days_ago=9)     # canceled: not late
    admin_order = order(admin, c_reassigned, 2)  # admin sold to Ana's customer
    order(seller_b, c_b, 1)

    # ---- overview: statuses, seller scoping ----
    ov_a = {r["name"]: r for r in c.get("/api/customers/overview", headers=seller_a).json()}
    assert {n: r["status"] for n, r in ov_a.items()} == {
        "Ácida Modas": "active", "Cliente 60": "active", "Cliente 61": "at_risk", "Cliente 150": "at_risk",
        "Cliente 151": "inactive", "Só Orçamento": "never_ordered", "Nunca Comprou": "never_ordered",
        "Atendido Pelo Admin": "never_ordered"}, ov_a
    assert ov_a["Atendido Pelo Admin"]["recent_orders"] == []  # admin's sale is not Ana's
    acida = ov_a["Ácida Modas"]
    assert acida["orders"] == 5 and acida["total"] == 500.0  # delivered + confirmed x2 + in_production + shipped
    assert len(acida["recent_orders"]) == 3 and acida["colors"] == ["Preto"]
    assert acida["last_order_date"] == TODAY.isoformat()
    ov_b = c.get("/api/customers/overview", headers=seller_b).json()
    assert [r["name"] for r in ov_b] == ["Cliente do Bruno"]
    ov_admin = {r["name"]: r for r in c.get("/api/customers/overview", headers=admin).json()}
    assert ov_admin["Atendido Pelo Admin"]["recent_orders"][0]["id"] == admin_order

    # ---- late filter ----
    late_ids = {o["id"] for o in c.get("/api/orders", headers=seller_a, params={"late": 1}).json()}
    assert late_ids == {late1, late2}, late_ids
    assert c.get("/api/orders", headers=seller_b, params={"late": 1}).json() == []

    # ---- dashboard alerts agree with the overview ----
    d = c.get("/api/dashboard", headers=seller_a).json()
    assert d["alerts"] == {"customers_at_risk": 2, "customers_never_ordered": 3,
                           "late_orders": 2, "oldest_late_days": 3}, d["alerts"]
    da = c.get("/api/dashboard", headers=admin).json()
    assert da["alerts"]["customers_at_risk"] == sum(r["status"] == "at_risk" for r in ov_admin.values())

    # ---- period validation ----
    assert c.get("/api/dashboard", headers=admin, params={"start": "2026-10-07", "end": "2026-10-01"}).status_code == 400
    assert c.get("/api/dashboard", headers=admin, params={"start": "2020-01-01", "end": "2026-10-07"}).status_code == 400

    # ---- sales_series: daily up to 31 days, weekly beyond, clipped ----
    week = {"start": (TODAY - timedelta(days=6)).isoformat(), "end": TODAY.isoformat()}
    s7 = c.get("/api/dashboard", headers=admin, params=week).json()
    assert len(s7["sales_series"]) == 7 and s7["sales_series"][0]["start"] == week["start"]
    year = c.get("/api/dashboard", headers=admin, params={"start": "2026-01-01", "end": TODAY.isoformat()}).json()
    starts = [p["start"] for p in year["sales_series"]]
    assert starts[0] == "2026-01-01" and starts[1] == "2026-01-05"  # Thu 1st, then Monday the 5th
    assert round(sum(p["value"] for p in year["sales_series"]), 2) == year["kpis"]["revenue"]

    # ---- previous period of the same length ----
    day60 = (TODAY - timedelta(days=60)).isoformat()
    p = c.get("/api/dashboard", headers=admin, params={"start": day60, "end": day60}).json()
    assert p["kpis"]["revenue"] == 100 and p["previous_kpis"]["revenue"] == 100  # day 60 vs day 61

    # ---- goals: prorated, admin-only company goal, sellers with zero sales listed ----
    assert s7["goal"] == 14000.0  # 60800 * 7 / 30.4
    sellers = {s["name"]: s for s in s7["by_seller"]}
    assert sellers["Ana Vendas"]["goal"] == 7000.0  # 30400 * 7 / 30.4
    assert sellers["Bruno Vendas"]["goal"] is None
    new_user("Carla Nova", "carla@test.com")
    new_user("Davi Inativo", "davi@test.com", active=False)
    names = {s["name"] for s in c.get("/api/dashboard", headers=admin, params=week).json()["by_seller"]}
    assert "Carla Nova" in names and "Davi Inativo" not in names, names
    sa7 = c.get("/api/dashboard", headers=seller_a, params=week).json()
    assert sa7["goal"] == 7000.0  # the seller gets their own goal, never the company's
    assert [s["name"] for s in sa7["by_seller"]] == ["Ana Vendas"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python test_dashboard.py`
Expected: FAIL — `KeyError: 'alerts'` (or 404 on `/api/customers/overview`).

- [ ] **Step 3: Create `backend/app/sales.py`**

```python
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
```

- [ ] **Step 4: Customers route** — in `backend/app/routers/customers.py` add imports and a route **between** `list_all` and `get`:

```python
from .. import clock
from ..sales import customer_overview
```

```python
@router.get("/overview")
def overview(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Every visible customer with sales aggregates and status, for the Clientes screen."""
    return customer_overview(db, user, clock.today_br())
```

- [ ] **Step 5: Orders route** — in `backend/app/routers/orders.py`:

Add imports:

```python
from .. import clock
from ..sales import late_filter
```

Change the `list_all` signature to include `late: bool = False` (after `end`), and before `return` add:

```python
    if late:
        q = q.filter(late_filter(clock.today_br()))
```

In `create`, replace `date=data.date or date.today()` with `date=data.date or clock.today_br()`.

- [ ] **Step 6: Rewrite `backend/app/routers/dashboard.py`**

```python
from collections import Counter, defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..models import SALE_STATUSES, Order, User
from ..sales import customer_overview, late_filter, visible_orders
from ..security import get_current_user
from ..settings_store import get_app_settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

MAX_PERIOD_DAYS = 731
DAYS_PER_MONTH = 30.4
SIZE_ORDER = ["U", "PP", "P", "M", "G", "GG", "XG"]


def _top(d: dict, n=8):
    return sorted(d.values(), key=lambda x: x["value"], reverse=True)[:n]


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


def _period_goal(monthly, days: int) -> float | None:
    monthly = float(monthly or 0)  # Numeric columns load as Decimal
    return round(monthly * days / DAYS_PER_MONTH, 2) if monthly > 0 else None


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


def _seller_row(u: User, days: int) -> dict:
    return {"id": u.id, "name": u.name, "avatar_url": u.avatar_url, "goal": _period_goal(u.monthly_goal, days),
            "orders": 0, "pieces": 0, "value": 0.0}


@router.get("")
def dashboard(start: date | None = None, end: date | None = None, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    today = clock.today_br()
    start = start or date(today.year, 1, 1)
    end = end or today
    if start > end or (end - start).days >= MAX_PERIOD_DAYS:
        raise HTTPException(400, "Período inválido.")
    days = (end - start).days + 1
    is_admin = user.role == "admin"

    orders = visible_orders(db, user).filter(Order.date >= start, Order.date <= end).all()
    sales = [o for o in orders if o.status in SALE_STATUSES]
    prev_end = start - timedelta(days=1)
    prev_sales = _sales_between(db, user, prev_end - timedelta(days=days - 1), prev_end)

    by_status = defaultdict(lambda: {"count": 0, "value": 0.0})
    for o in orders:
        by_status[o.status]["count"] += 1
        by_status[o.status]["value"] += o.total

    sellers: dict[int, dict] = {}
    if is_admin:  # active sellers with no sales still show up, with zeros
        for u in db.query(User).filter(User.active.is_(True), User.role == "seller"):
            sellers[u.id] = _seller_row(u, days)
    else:
        sellers[user.id] = _seller_row(user, days)

    products, customers, colors, cities, sizes = {}, {}, {}, {}, defaultdict(int)
    for o in sales:
        c = customers.setdefault(o.customer_id, {"name": o.customer.name, "orders": 0, "pieces": 0, "value": 0.0})
        c["orders"] += 1
        c["pieces"] += o.pieces
        c["value"] += o.total
        s = sellers.setdefault(o.seller_id, _seller_row(o.seller, days))
        s["orders"] += 1
        s["pieces"] += o.pieces
        s["value"] += o.total
        city_key = f"{o.customer.city or 'Não informado'}/{o.customer.state or ''}".rstrip("/")
        ci = cities.setdefault(city_key, {"name": city_key, "orders": 0, "pieces": 0, "value": 0.0})
        ci["orders"] += 1
        ci["pieces"] += o.pieces
        ci["value"] += o.total
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
    series = {k: {"value": 0.0, "pieces": 0} for k in months}
    for o in _sales_between(db, user, date(*months[0], 1), today):
        k = (o.date.year, o.date.month)
        if k in series:
            series[k]["value"] += o.total
            series[k]["pieces"] += o.pieces

    statuses = Counter(r["status"] for r in customer_overview(db, user, today))
    late = visible_orders(db, user).filter(late_filter(today)).all()

    company_goal = get_app_settings(db).monthly_goal if is_admin else user.monthly_goal
    return {
        "period": {"start": start, "end": end},
        "kpis": _kpis(sales),
        "previous_kpis": _kpis(prev_sales),
        "sales_series": _sales_series(sales, start, end),
        "goal": _period_goal(company_goal, days),
        "monthly_sales": [{"month": f"{m:02d}/{str(y)[2:]}", **series[(y, m)]} for y, m in months],
        "by_status": [{"status": s, **v} for s, v in by_status.items()],
        "top_products": _top(products),
        "top_customers": _top(customers),
        "by_seller": _top(sellers, 50),
        "by_city": _top(cities, 50),
        "by_color": _top(colors, 10),
        "by_size": sorted(
            [{"size": t, "pieces": q} for t, q in sizes.items()],
            key=lambda x: SIZE_ORDER.index(x["size"]) if x["size"] in SIZE_ORDER else 99,
        ),
        "alerts": {
            "customers_at_risk": statuses["at_risk"],
            "customers_never_ordered": statuses["never_ordered"],
            "late_orders": len(late),
            "oldest_late_days": max(((today - o.delivery_date).days for o in late), default=None),
        },
    }
```

- [ ] **Step 7: Run tests**

Run: `python test_dashboard.py` → `dashboard checks OK`
Run: `python test_security.py` → `security checks OK`

- [ ] **Step 8: Commit**

```bash
git add backend/app/sales.py backend/app/routers/customers.py backend/app/routers/orders.py backend/app/routers/dashboard.py backend/test_dashboard.py
git commit -m "Add customers overview, late-order filter and dashboard goals, alerts and series"
```

---

### Task 3: Goal fields in Configurações and Usuários

**Files:**
- Modify: `frontend/src/pages/Settings.jsx` (PUT body; new field)
- Modify: `frontend/src/pages/Users.jsx` (save body; new field)

**Interfaces:**
- Consumes: `PUT /api/settings` accepts `monthly_goal: number | null`; `GET /api/settings` returns it for admin. `POST/PUT /api/users` accept `monthly_goal`.

- [ ] **Step 1: Settings.jsx** — in `save`, add `monthly_goal` to the PUT body:

```jsx
      const { data } = await api.put("/settings", {
        allow_price_override: form.allow_price_override,
        max_discount_percent: Number(form.max_discount_percent) || 0,
        monthly_goal: form.monthly_goal === "" || form.monthly_goal == null ? null : Number(form.monthly_goal),
      });
```

Change the header paragraph text to `Regras de preço, desconto e meta de vendas.` and add, after the discount `<Field>`:

```jsx
            <Field label="Meta mensal da empresa (R$)" span={2}>
              <input type="number" min="0" step="0.01" placeholder="Sem meta"
                value={form.monthly_goal ?? ""}
                onChange={(e) => setForm({ ...form, monthly_goal: e.target.value })} />
            </Field>
            <p className="muted span-2" style={{ marginTop: -8 }}>
              Usada no Painel e no Faturamento, proporcional ao período escolhido. Deixe em branco para não usar meta.
            </p>
```

- [ ] **Step 2: Users.jsx** — replace `save` with:

```jsx
  async function save(e) {
    e.preventDefault();
    const goal = form.monthly_goal;
    const body = { ...form, monthly_goal: goal === "" || goal == null ? null : Number(goal) };
    try {
      form.id ? await api.put(`/users/${form.id}`, body) : await api.post("/users", body);
      setForm(null);
      load();
    } catch (err) { setError(errorMessage(err)); }
  }
```

Add `monthly_goal: ""` to the object created by the "Cadastrar usuário" button, and in the form, after the "Perfil" field:

```jsx
            <Field label="Meta mensal (R$)">
              <input type="number" min="0" step="0.01" placeholder="Sem meta" {...f("monthly_goal")} />
            </Field>
```

- [ ] **Step 3: Build**

Run (from `frontend/`): `npm run build` → `✓ built`.

- [ ] **Step 4: Manual check** — with the backend running, as admin: save a company goal in Configurações, reload, value persists; save "Meta mensal" on a user, reload, persists; clear it, persists as empty.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Settings.jsx frontend/src/pages/Users.jsx
git commit -m "Add company and per-user monthly goal fields"
```

---

### Task 4: Frontend helpers and shared period components

**Files:**
- Modify: `frontend/src/format.js`
- Create: `frontend/scripts/check-format.mjs`
- Create: `frontend/src/components/PeriodPicker.jsx`, `frontend/src/components/usePeriodData.js`, `frontend/src/components/Delta.jsx`

**Interfaces:**
- Produces (format.js): `localDate(d?: Date) -> "YYYY-MM-DD"`, `addDays(iso, n) -> iso`, `compactMoney(v) -> "R$ 18,2 mil"`, `plural(n, one, many) -> "3 pedidos"`, `initials(name) -> "AM"`, `normalize(s) -> string`, `whatsappUrl(phone) -> string | null`, `CUSTOMER_STATUS = { [key]: { label, tone } }`.
- Produces (components): `<PeriodPicker value={{start,end}} onChange={fn} />`, `defaultPeriod() -> {start,end}`, `usePeriodData({start,end}) -> {data, error}`, `<Delta cur prev />`.

- [ ] **Step 1: Write the failing check** — create `frontend/scripts/check-format.mjs`:

```js
// Self-check for pure helpers in src/format.js. Run from frontend/:  node scripts/check-format.mjs
import assert from "node:assert/strict";
import { addDays, compactMoney, initials, localDate, normalize, plural, whatsappUrl } from "../src/format.js";

// late-night local time must still be "today", not UTC tomorrow
assert.equal(localDate(new Date(2026, 9, 7, 23, 30)), "2026-10-07");
assert.equal(addDays("2026-10-07", -6), "2026-10-01");
assert.equal(addDays("2026-02-28", 1), "2026-03-01");

assert.equal(whatsappUrl("(47) 99123-4567"), "https://wa.me/5547991234567");
assert.equal(whatsappUrl("+55 (47) 99123-4567"), "https://wa.me/5547991234567");
assert.equal(whatsappUrl("47 3521-1234"), "https://wa.me/554735211234");
assert.equal(whatsappUrl("abc"), null);
assert.equal(whatsappUrl("123"), null);
assert.equal(whatsappUrl(null), null);

assert.equal(normalize("Itaiópolis"), "itaiopolis");
assert.ok(normalize("Adriana Müller").includes(normalize("adriana muller")));

assert.equal(initials("Adriana Muller de Souza"), "AM");
assert.equal(initials("Bella"), "BE");
assert.equal(plural(1, "pedido", "pedidos"), "1 pedido");
assert.equal(plural(3, "pedido", "pedidos"), "3 pedidos");
assert.equal(compactMoney(18240), "R$ 18,2 mil");
assert.equal(compactMoney(1250000), "R$ 1,25 mi");

console.log("format checks OK");
```

- [ ] **Step 2: Run to verify it fails**

Run (from `frontend/`): `node scripts/check-format.mjs`
Expected: FAIL — `SyntaxError: The requested module '../src/format.js' does not provide an export named 'addDays'`.

- [ ] **Step 3: Add helpers to `frontend/src/format.js`** (append):

```js
// Calendar dates in the user's local timezone. Never toISOString() — that's UTC and
// returns tomorrow's date after 21:00 in Brazil.
export const localDate = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

export const addDays = (iso, days) => {
  const d = new Date(`${iso}T00:00:00`);
  d.setDate(d.getDate() + days);
  return localDate(d);
};

export const compactMoney = (v) => {
  const n = Number(v || 0);
  if (n >= 1e6) return `R$ ${(n / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 2 })} mi`;
  if (n >= 1e3) return `R$ ${(n / 1e3).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} mil`;
  return money(n);
};

export const plural = (n, one, many) => `${n.toLocaleString("pt-BR")} ${n === 1 ? one : many}`;

export function initials(name) {
  const words = (name || "?").trim().split(/\s+/);
  return words.length > 1 ? (words[0][0] + words[1][0]).toUpperCase() : words[0].slice(0, 2).toUpperCase();
}

// Lowercase without accents, for search ("Itaiópolis" matches "itaiopolis").
export const normalize = (s) => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

// Only digits ever reach the URL. Brazilian numbers: 10-11 digits after an optional leading 55.
export function whatsappUrl(phone) {
  let digits = (phone || "").replace(/\D/g, "");
  if ((digits.length === 12 || digits.length === 13) && digits.startsWith("55")) digits = digits.slice(2);
  return digits.length === 10 || digits.length === 11 ? `https://wa.me/55${digits}` : null;
}

// Keys match the backend's customer_status(); tone picks the CSS color (.cstatus-<tone>).
export const CUSTOMER_STATUS = {
  active: { label: "Ativo", tone: "active" },
  at_risk: { label: "Em risco", tone: "risk" },
  inactive: { label: "Inativo", tone: "inactive" },
  never_ordered: { label: "Nunca comprou", tone: "never" },
};
```

- [ ] **Step 4: Run the check**

Run: `node scripts/check-format.mjs` → `format checks OK`

- [ ] **Step 5: Create `frontend/src/components/Delta.jsx`** (moved from `Dashboard.jsx`):

```jsx
// Change vs. the previous period. Hidden when there's nothing to compare against.
export default function Delta({ cur, prev }) {
  if (!prev) return null;
  const pct = ((cur - prev) / prev) * 100;
  if (!isFinite(pct) || Math.abs(pct) < 0.5) return <span className="kpi-delta neutral">= período anterior</span>;
  const pos = pct >= 0;
  return (
    <span className={`kpi-delta ${pos ? "pos" : "neg"}`}>
      {pos ? "▲" : "▼"} {Math.abs(pct).toFixed(0)}%
    </span>
  );
}
```

- [ ] **Step 6: Create `frontend/src/components/PeriodPicker.jsx`**

```jsx
import { useState } from "react";
import { addDays, localDate } from "../format";

const PRESETS = [
  { key: "7d", label: "7 dias", start: () => addDays(localDate(), -6) },
  { key: "month", label: "Este mês", start: () => `${localDate().slice(0, 8)}01` },
  { key: "year", label: "Este ano", start: () => `${new Date().getFullYear()}-01-01` },
];

export const defaultPeriod = () => ({ start: PRESETS[2].start(), end: localDate() });

export default function PeriodPicker({ value, onChange }) {
  const [preset, setPreset] = useState("year");
  return (
    <div className="period-block">
      <div className="period-chips" role="group" aria-label="Período">
        {PRESETS.map((p) => (
          <button key={p.key} type="button" className={`period-chip ${preset === p.key ? "on" : ""}`}
            onClick={() => { setPreset(p.key); onChange({ start: p.start(), end: localDate() }); }}>
            {p.label}
          </button>
        ))}
        <button type="button" className={`period-chip ${preset === "custom" ? "on" : ""}`}
          onClick={() => setPreset("custom")}>Personalizado</button>
      </div>
      {preset === "custom" && (
        <div className="period-filter">
          <input type="date" value={value.start} max={value.end} aria-label="Início"
            onChange={(e) => e.target.value && onChange({ ...value, start: e.target.value })} />
          <span>até</span>
          <input type="date" value={value.end} min={value.start} aria-label="Fim"
            onChange={(e) => e.target.value && onChange({ ...value, end: e.target.value })} />
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 7: Create `frontend/src/components/usePeriodData.js`**

```js
import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";

// Fetches /dashboard for a period; ignores responses that arrive after the period changed.
export default function usePeriodData({ start, end }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let current = true;
    api.get("/dashboard", { params: { start, end } })
      .then((r) => { if (current) { setData(r.data); setError(""); } })
      .catch((e) => { if (current) setError(errorMessage(e)); });
    return () => { current = false; };
  }, [start, end]);
  return { data, error };
}
```

- [ ] **Step 8: Build** — `npm run build` → `✓ built` (new files aren't imported yet; this catches syntax errors only in `format.js`).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/format.js frontend/scripts/check-format.mjs frontend/src/components/Delta.jsx frontend/src/components/PeriodPicker.jsx frontend/src/components/usePeriodData.js
git commit -m "Add local-date, search and WhatsApp helpers and shared period components"
```

---

### Task 5: Clientes screen, order prefill, late-orders filter and Electron links

**Files:**
- Rewrite: `frontend/src/pages/Customers.jsx`
- Create: `frontend/src/components/CustomerPanel.jsx`, `frontend/src/components/CustomerFormModal.jsx`
- Modify: `frontend/src/pages/OrderForm.jsx:1-2,195-209,227-228`
- Modify: `frontend/src/pages/Orders.jsx` (`late` param)
- Modify: `frontend/electron/main.cjs`
- Modify: `frontend/src/styles.css` (append Clientes block)

**Interfaces:**
- Consumes: `GET /api/customers/overview` (Task 2), `GET /api/orders?late=1`, format helpers (Task 4).
- Produces: route params `#/customers?q&status&state&city&seller&color&sort&page`, `#/orders/new?customer=<id>`, `#/orders?late=1`.

- [ ] **Step 1: Create `frontend/src/components/CustomerFormModal.jsx`** (form moved out of `Customers.jsx`, unchanged behavior):

```jsx
import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import { Field, ErrorBox, Modal } from "./ui";

export const EMPTY_CUSTOMER = { name: "", document: "", phone: "", email: "", city: "", state: "", address: "", notes: "", owner_id: "" };

export default function CustomerFormModal({ initial, isAdmin, onClose, onSaved }) {
  const [form, setForm] = useState({ ...initial, owner_id: initial.owner_id || "" });
  const [sellers, setSellers] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => { if (isAdmin) api.get("/users").then((r) => setSellers(r.data)); }, [isAdmin]);

  async function save(e) {
    e.preventDefault();
    setError("");
    const body = { ...form, state: form.state ? form.state.toUpperCase() : null, owner_id: form.owner_id ? Number(form.owner_id) : null };
    try {
      form.id ? await api.put(`/customers/${form.id}`, body) : await api.post("/customers", body);
      onSaved();
    } catch (err) { setError(errorMessage(err)); }
  }

  async function remove() {
    if (!confirm(`Excluir ${form.name}?`)) return;
    try { await api.delete(`/customers/${form.id}`); onSaved(); }
    catch (err) { setError(errorMessage(err)); }
  }

  const f = (k) => ({ value: form[k] || "", onChange: (e) => setForm({ ...form, [k]: e.target.value }) });

  return (
    <Modal title={form.id ? "Editar cliente" : "Cadastrar cliente"} onClose={onClose} wide>
      <form onSubmit={save} className="form-grid">
        <Field label="Nome / razão social" span={2}><input required {...f("name")} /></Field>
        <Field label="CPF/CNPJ" span={2}><input required {...f("document")} /></Field>
        {isAdmin && (
          <Field label="Vendedor responsável" span={2}>
            <select required {...f("owner_id")}>
              <option value="">Selecione o vendedor</option>
              {sellers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </Field>
        )}
        <Field label="Telefone"><input {...f("phone")} /></Field>
        <Field label="E-mail"><input type="email" {...f("email")} /></Field>
        <Field label="Cidade / UF" span={2}>
          <div className="city-row">
            <input placeholder="Cidade" {...f("city")} />
            <input placeholder="UF" maxLength={2} className="uf-input" {...f("state")} />
          </div>
        </Field>
        <Field label="Endereço" span={2}><input {...f("address")} /></Field>
        <Field label="Observações" span={2}><textarea rows={3} {...f("notes")} /></Field>
        <div className="span-2"><ErrorBox msg={error} /></div>
        <div className="actions span-2">
          {form.id && <button type="button" className="btn danger" onClick={remove}>Excluir</button>}
          <button className="btn btn-primary">Salvar cliente</button>
        </div>
      </form>
    </Modal>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/CustomerPanel.jsx`**

```jsx
import { useNavigate } from "react-router-dom";
import { CUSTOMER_STATUS, compactMoney, dateBR, initials, money, orderNumber, whatsappUrl } from "../format";

export default function CustomerPanel({ customer: c, isAdmin, onClose, onEdit }) {
  const nav = useNavigate();
  const st = CUSTOMER_STATUS[c.status];
  const wa = whatsappUrl(c.phone);
  const since = c.created_at
    ? new Date(c.created_at).toLocaleDateString("pt-BR", { month: "short", year: "numeric" }) : "—";
  const stats = [
    ["Total comprado", c.total ? money(c.total) : "—"],
    ["Pedidos", String(c.orders)],
    ["Ticket médio", c.orders ? compactMoney(c.total / c.orders) : "—"],
    ["Cliente desde", since],
  ];
  return (
    <aside className="customer-panel" aria-label={`Cliente ${c.name}`}>
      <button type="button" className="customer-panel-close" onClick={onClose} aria-label="Fechar">×</button>
      <div className="customer-panel-head">
        <span className="customer-avatar lg">{initials(c.name)}</span>
        <div>
          <strong>{c.name}</strong>
          <span className="muted">{[c.city && `${c.city}${c.state ? `/${c.state}` : ""}`, c.phone].filter(Boolean).join(" · ")}</span>
          <span className={`cstatus cstatus-${st.tone}`}>{st.label}</span>
        </div>
      </div>
      <div className="customer-panel-actions">
        <button type="button" className="btn btn-primary" onClick={() => nav(`/orders/new?customer=${c.id}`)}>Novo pedido</button>
        {wa
          ? <a className="btn" href={wa} target="_blank" rel="noopener noreferrer">WhatsApp</a>
          : <button type="button" className="btn" disabled title="Telefone não cadastrado ou inválido">WhatsApp</button>}
        <button type="button" className="btn" onClick={onEdit}>Editar</button>
      </div>
      <div className="customer-panel-stats">
        {stats.map(([l, v]) => <div key={l}><span>{l}</span><strong>{v}</strong></div>)}
      </div>
      <dl className="customer-panel-info">
        {isAdmin && <><dt>Vendedor</dt><dd>{c.owner_name || "Sem vendedor"}</dd></>}
        <dt>Cores mais compradas</dt><dd>{c.colors.slice(0, 3).join(", ") || "—"}</dd>
      </dl>
      <div>
        <h3>Últimos pedidos</h3>
        {c.recent_orders.length ? c.recent_orders.map((o) => (
          <button type="button" key={o.id} className="customer-panel-order" onClick={() => nav(`/orders/${o.id}`)}>
            <span><strong>#{orderNumber(o.id)}</strong><small>{dateBR(o.date)} · {o.pieces} peças</small></span>
            <strong>{money(o.total)}</strong>
          </button>
        )) : <p className="customer-panel-empty">Ainda sem compras. Bom momento para um primeiro contato.</p>}
      </div>
    </aside>
  );
}
```

- [ ] **Step 3: Rewrite `frontend/src/pages/Customers.jsx`**

```jsx
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useAuth } from "../auth";
import { CUSTOMER_STATUS, compactMoney, initials, normalize } from "../format";
import { ErrorBox } from "../components/ui";
import CustomerPanel from "../components/CustomerPanel";
import CustomerFormModal, { EMPTY_CUSTOMER } from "../components/CustomerFormModal";

const PAGE_SIZE = 20;
const SORTS = {
  total: { label: "Total comprado", fn: (a, b) => b.total - a.total },
  orders: { label: "Nº de pedidos", fn: (a, b) => b.orders - a.orders },
  recent: { label: "Compra mais recente", fn: (a, b) => (b.last_order_date || "").localeCompare(a.last_order_date || "") },
  name: { label: "Nome A–Z", fn: (a, b) => a.name.localeCompare(b.name, "pt-BR") },
};
const uniqSorted = (list) => [...new Set(list.filter(Boolean))].sort((a, b) => a.localeCompare(b, "pt-BR"));

export default function Customers() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [form, setForm] = useState(null);
  const [params, setParams] = useSearchParams();

  const load = () => api.get("/customers/overview")
    .then((r) => { setRows(r.data); setError(""); })
    .catch((e) => setError(errorMessage(e)));
  useEffect(() => { load(); }, []);

  const options = useMemo(() => {
    const sellers = new Map(rows.filter((r) => r.owner_id).map((r) => [String(r.owner_id), r.owner_name]));
    return {
      states: uniqSorted(rows.map((r) => r.state)),
      sellers: [...sellers.entries()].sort((a, b) => a[1].localeCompare(b[1], "pt-BR")),
      colors: uniqSorted(rows.flatMap((r) => r.colors)),
    };
  }, [rows]);

  // URL values are untrusted: anything outside the known lists is ignored.
  const f = useMemo(() => {
    const get = (k) => params.get(k) || "";
    const seller = get("seller");
    return {
      q: get("q"),
      status: get("status") in CUSTOMER_STATUS ? get("status") : "",
      state: get("state"),
      city: get("city"),
      seller: isAdmin && (seller === "none" || options.sellers.some(([id]) => id === seller)) ? seller : "",
      color: get("color"),
      sort: get("sort") in SORTS ? get("sort") : "total",
      page: Math.max(1, parseInt(get("page"), 10) || 1),
    };
  }, [params, isAdmin, options]);

  function setFilter(key, value) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value); else next.delete(key);
    if (key === "state") next.delete("city");
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  }

  const cities = useMemo(() => uniqSorted(rows.filter((r) => !f.state || r.state === f.state).map((r) => r.city)), [rows, f.state]);

  const visible = useMemo(() => {
    const text = normalize(f.q.trim());
    const digits = f.q.replace(/\D/g, "");
    return rows.filter((r) =>
      (!f.status || r.status === f.status)
      && (!f.state || r.state === f.state)
      && (!f.city || r.city === f.city)
      && (!f.seller || (f.seller === "none" ? !r.owner_id : String(r.owner_id) === f.seller))
      && (!f.color || r.colors.includes(f.color))
      && (!text || normalize(`${r.name} ${r.city || ""}`).includes(text)
        || (digits.length >= 3 && (r.document || "").replace(/\D/g, "").includes(digits)))
    ).sort(SORTS[f.sort].fn);
  }, [rows, f]);

  const pages = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const page = Math.min(f.page, pages);
  const pageRows = visible.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const selected = rows.find((r) => r.id === selectedId);

  const chips = [
    f.q && ["q", `Busca: ${f.q}`],
    f.status && ["status", `Status: ${CUSTOMER_STATUS[f.status].label}`],
    f.state && ["state", `Estado: ${f.state}`],
    f.city && ["city", `Cidade: ${f.city}`],
    f.seller && ["seller", `Vendedor: ${f.seller === "none" ? "Sem vendedor" : options.sellers.find(([id]) => id === f.seller)[1]}`],
    f.color && ["color", `Cor: ${f.color}`],
  ].filter(Boolean);

  async function openEdit(id) {
    try { setForm((await api.get(`/customers/${id}`)).data); }
    catch (e) { setError(errorMessage(e)); }
  }

  const select = (label, key, value, opts) => (
    <label className={`filter ${value ? "on" : ""}`}>
      <span>{label}</span>
      <select value={value} onChange={(e) => setFilter(key, e.target.value)}>{opts}</select>
    </label>
  );

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Clientes</h1>
          <p className="muted">Acompanhe a carteira e encontre oportunidades de venda.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setForm(EMPTY_CUSTOMER)}>+ Cadastrar cliente</button>
      </header>

      <section className="filters-bar">
        <div className="filters-row">
          <input className="filters-search" placeholder="Buscar por nome, cidade ou CPF/CNPJ"
            value={f.q} onChange={(e) => setFilter("q", e.target.value)} />
          {select("Status", "status", f.status, <>
            <option value="">Todos</option>
            {Object.entries(CUSTOMER_STATUS).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
          </>)}
          {select("Estado", "state", f.state, <>
            <option value="">Todos</option>{options.states.map((s) => <option key={s}>{s}</option>)}
          </>)}
          {select("Cidade", "city", f.city, <>
            <option value="">Todas</option>{cities.map((c) => <option key={c}>{c}</option>)}
          </>)}
          {isAdmin && select("Vendedor", "seller", f.seller, <>
            <option value="">Todos</option><option value="none">Sem vendedor</option>
            {options.sellers.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </>)}
          {select("Cor comprada", "color", f.color, <>
            <option value="">Todas</option>{options.colors.map((c) => <option key={c}>{c}</option>)}
          </>)}
          {select("Ordenar", "sort", f.sort === "total" ? "" : f.sort,
            Object.entries(SORTS).map(([k, s]) => <option key={k} value={k === "total" ? "" : k}>{s.label}</option>))}
        </div>
        {chips.length > 0 && (
          <div className="filters-chips">
            <span className="muted">Filtros ativos</span>
            {chips.map(([key, label]) => (
              <button type="button" key={key} className="chip" onClick={() => setFilter(key, "")}>{label} ×</button>
            ))}
            <button type="button" className="link-btn" onClick={() => setParams({}, { replace: true })}>Limpar tudo</button>
          </div>
        )}
      </section>

      <ErrorBox msg={error} />

      <div className={`customers-layout ${selected ? "with-panel" : ""}`}>
        <section className="customers-table">
          <div className={`customers-row head ${isAdmin ? "admin" : ""}`}>
            <span>Cliente</span>{isAdmin && <span>Vendedor</span>}<span className="num">Total</span><span className="num">Pedidos</span><span>Status</span>
          </div>
          {pageRows.map((r) => (
            <button type="button" key={r.id} onClick={() => setSelectedId(r.id)}
              className={`customers-row ${isAdmin ? "admin" : ""} ${r.id === selectedId ? "on" : ""}`}>
              <span className="customers-cell-main">
                <span className="customer-avatar">{initials(r.name)}</span>
                <span><strong>{r.name}</strong><small>{r.city ? `${r.city}${r.state ? `/${r.state}` : ""}` : "—"}</small></span>
              </span>
              {isAdmin && <span>{r.owner_name?.split(" ")[0] || "—"}</span>}
              <span className="num">{r.total ? compactMoney(r.total) : "—"}</span>
              <span className="num">{r.orders}</span>
              <span><span className={`cstatus cstatus-${CUSTOMER_STATUS[r.status].tone}`}>{CUSTOMER_STATUS[r.status].label}</span></span>
            </button>
          ))}
          {!pageRows.length && <p className="customers-empty">Nenhum cliente com esses filtros.</p>}
          <footer className="customers-footer">
            <span className="muted">
              Mostrando {visible.length ? `${(page - 1) * PAGE_SIZE + 1}–${Math.min(visible.length, page * PAGE_SIZE)}` : "0"} de {visible.length}
            </span>
            <div className="pager">
              <button type="button" className="btn" disabled={page === 1} onClick={() => setFilter("page", String(page - 1))}>‹ Anterior</button>
              <span>{page} / {pages}</span>
              <button type="button" className="btn" disabled={page === pages} onClick={() => setFilter("page", String(page + 1))}>Próxima ›</button>
            </div>
          </footer>
        </section>

        {selected && (
          <CustomerPanel customer={selected} isAdmin={isAdmin}
            onClose={() => setSelectedId(null)} onEdit={() => openEdit(selected.id)} />
        )}
      </div>

      {form && (
        <CustomerFormModal initial={form} isAdmin={isAdmin} onClose={() => setForm(null)}
          onSaved={() => { setForm(null); setSelectedId(null); load(); }} />
      )}
    </div>
  );
}
```

- [ ] **Step 4: OrderForm prefill and local date** — in `frontend/src/pages/OrderForm.jsx`:

Change the router import to `import { useNavigate, useParams, useSearchParams } from "react-router-dom";` and add `localDate` to the `../format` import.

After `const { id } = useParams();` add:

```jsx
  const [searchParams] = useSearchParams();
  // ?customer=<id> from the Clientes screen; only for new orders, only a number.
  const presetCustomer = id ? null : Number(searchParams.get("customer")) || null;
```

In the initial `header` state replace `date: new Date().toISOString().slice(0, 10)` with `date: localDate()`.

Replace the `hasUnsavedChanges` line with:

```jsx
  // A customer preselected from the Clientes screen alone isn't "unsaved work".
  const customerChanged = Boolean(header.customer_id) && Number(header.customer_id) !== presetCustomer;
  const hasUnsavedChanges = !saved && (customerChanged || items.length > 0);
```

Replace `api.get("/customers").then((r) => setCustomers(r.data));` with:

```jsx
    api.get("/customers").then((r) => {
      setCustomers(r.data);
      // Accept the preset only if it's in the list this user may see (the server checks again on save).
      if (presetCustomer && r.data.some((c) => c.id === presetCustomer)) {
        setHeader((h) => ({ ...h, customer_id: presetCustomer }));
        setCustomerKey((k) => k + 1);
      }
    });
```

- [ ] **Step 5: Orders late filter** — in `frontend/src/pages/Orders.jsx`:

Change the router import to `import { useNavigate, useSearchParams } from "react-router-dom";`. After `const isAdmin = ...` add:

```jsx
  const [params, setParams] = useSearchParams();
  const late = params.get("late") === "1";
```

Replace the fetch effect with:

```jsx
  useEffect(() => {
    api.get("/orders", { params: late ? { late: 1 } : {} })
      .then((r) => { setOrders(r.data); setError(""); })
      .catch((e) => setError(errorMessage(e)))
      .finally(() => setLoaded(true));
  }, [late]);
```

Right after the `<header className="page-header">…</header>` block add:

```jsx
      {late && (
        <div className="filters-chips">
          <span className="muted">Mostrando só pedidos atrasados</span>
          <button type="button" className="chip" onClick={() => setParams({}, { replace: true })}>Atrasados ×</button>
        </div>
      )}
```

- [ ] **Step 6: Electron external links** — in `frontend/electron/main.cjs` replace the `setWindowOpenHandler` line with:

```js
  // Only https links leave the app (WhatsApp, maps); everything else is ignored.
  const openExternal = (url) => { if (url.startsWith("https://")) shell.openExternal(url); };
  win.webContents.setWindowOpenHandler(({ url }) => { openExternal(url); return { action: "deny" }; });
  win.webContents.on("will-navigate", (e, url) => {
    if (new URL(url).origin === new URL(win.webContents.getURL()).origin) return;
    e.preventDefault(); // the app window never navigates away from the app
    openExternal(url);
  });
```

- [ ] **Step 7: Styles** — append to `frontend/src/styles.css`:

```css
/* ---------- clientes ---------- */
.filters-bar { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.filters-row { display: flex; gap: 10px; flex-wrap: wrap; align-items: stretch; }
.filters-search { flex: 1 1 240px; min-width: 200px; background: var(--surface-2); }
.filter { display: flex; flex-direction: column; justify-content: center; gap: 1px; background: var(--surface-2); border: 1px solid var(--line); border-radius: 10px; padding: 4px 8px 4px 12px; min-width: 140px; }
.filter.on { background: var(--accent-light); border-color: #bcd2fb; }
.filter span { font-size: 10px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.filter select { border: 0; background: transparent; padding: 0; font-size: 14px; font-weight: 600; }
.filters-chips { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; padding-top: 12px; border-top: 1px solid var(--line); }
.chip { border: 0; background: var(--accent-light); color: var(--accent-strong); border-radius: 999px; padding: 4px 10px; font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
.link-btn { margin-left: auto; border: 0; background: none; color: var(--accent); font: inherit; font-weight: 600; cursor: pointer; }
.customers-layout { display: grid; grid-template-columns: minmax(0, 1fr); gap: 16px; align-items: start; }
.customers-layout.with-panel { grid-template-columns: minmax(0, 1fr) 340px; }
.customers-table { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
.customers-row { display: grid; grid-template-columns: minmax(220px, 2.6fr) 110px 70px 120px; gap: 14px; align-items: center; width: 100%; padding: 12px 18px; border: 0; border-bottom: 1px solid var(--line); background: var(--surface); text-align: left; font: inherit; color: inherit; cursor: pointer; }
.customers-row.admin { grid-template-columns: minmax(220px, 2.6fr) minmax(90px, 1fr) 110px 70px 120px; }
.customers-row:hover { background: var(--surface-2); }
.customers-row.on { background: var(--accent-light); box-shadow: inset 3px 0 0 var(--accent); }
.customers-row.head { cursor: default; padding: 10px 18px; background: var(--surface-2); font-size: 11px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--muted); }
.customers-row .num { text-align: right; font-variant-numeric: tabular-nums; }
.customers-cell-main { display: flex; align-items: center; gap: 12px; min-width: 0; }
.customers-cell-main > span:last-child { display: flex; flex-direction: column; min-width: 0; }
.customers-cell-main strong { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 600; }
.customers-cell-main small { color: var(--muted); }
.customer-avatar { width: 34px; height: 34px; border-radius: 50%; display: grid; place-items: center; flex-shrink: 0; background: var(--accent-light); color: var(--accent-strong); font-size: 12px; font-weight: 700; }
.customer-avatar.lg { width: 48px; height: 48px; font-size: 16px; }
.cstatus { display: inline-block; font-size: 12px; font-weight: 600; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }
.cstatus-active { background: #e3f5ec; color: #0f7a4a; }
.cstatus-risk { background: #fdf1dc; color: #9a5b00; }
.cstatus-inactive { background: var(--danger-light); color: var(--danger); }
.cstatus-never { background: var(--slate-light); color: var(--muted); }
.customers-empty { padding: 48px 20px; text-align: center; color: var(--muted); margin: 0; }
.customers-footer { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 18px; flex-wrap: wrap; }
.pager { display: flex; gap: 8px; align-items: center; }
.customer-panel { position: sticky; top: 20px; background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 20px; display: flex; flex-direction: column; gap: 18px; }
.customer-panel-close { position: absolute; top: 10px; right: 12px; border: 0; background: none; font-size: 22px; color: var(--muted); cursor: pointer; }
.customer-panel-head { display: flex; gap: 12px; align-items: flex-start; padding-right: 20px; }
.customer-panel-head > div { display: flex; flex-direction: column; gap: 3px; min-width: 0; }
.customer-panel-head .cstatus { align-self: flex-start; margin-top: 4px; }
.customer-panel-actions { display: flex; gap: 8px; }
.customer-panel-actions .btn { flex: 1; text-align: center; text-decoration: none; }
.customer-panel-stats { display: grid; grid-template-columns: 1fr 1fr; gap: 1px; background: var(--line); border: 1px solid var(--line); border-radius: 10px; overflow: hidden; }
.customer-panel-stats div { background: var(--surface); padding: 12px; display: flex; flex-direction: column; gap: 2px; }
.customer-panel-stats span { font-size: 11px; color: var(--muted); }
.customer-panel-info { display: grid; grid-template-columns: auto 1fr; gap: 8px 12px; margin: 0; font-size: 13px; }
.customer-panel-info dt { color: var(--muted); }
.customer-panel-info dd { margin: 0; font-weight: 600; text-align: right; }
.customer-panel-order { display: flex; justify-content: space-between; gap: 10px; width: 100%; padding: 8px 0; border: 0; border-top: 1px solid var(--line); background: none; font: inherit; color: inherit; text-align: left; cursor: pointer; }
.customer-panel-order span { display: flex; flex-direction: column; }
.customer-panel-order small { color: var(--muted); }
.customer-panel-empty { font-size: 13px; color: var(--muted); padding: 10px 12px; background: var(--surface-2); border-radius: 8px; margin: 0; }
@media (max-width: 860px) {
  .customers-layout.with-panel { grid-template-columns: minmax(0, 1fr); }
  .customer-panel { position: fixed; inset: 0; z-index: 50; border-radius: 0; overflow-y: auto; }
  .customers-row, .customers-row.admin { grid-template-columns: minmax(0, 1fr) auto; }
  .customers-row.head { display: none; }
  .customers-row > span:not(.customers-cell-main):not(:last-child) { display: none; }
}
```

- [ ] **Step 8: Build and check**

Run (from `frontend/`): `npm run build` → `✓ built`; `node scripts/check-format.mjs` → `format checks OK`.

- [ ] **Step 9: Manual check** (backend + `npm run dev`):
  - As admin: filters, chips, "Limpar tudo", pagination, URL `#/customers?status=at_risk&sort=xyz` shows at-risk sorted by total; `?page=999` shows the last page.
  - Click a row → panel; Novo pedido opens the form with the customer chosen and going back without items asks nothing; WhatsApp disabled without phone; Editar → save → list reloads.
  - As seller: no Vendedor column/filter; only own customers.
  - `#/orders?late=1` shows the chip and only late orders.
  - Narrow window (< 860px): cards and full-screen panel with ×.

- [ ] **Step 10: Commit**

```bash
git add frontend/src/pages/Customers.jsx frontend/src/components/CustomerPanel.jsx frontend/src/components/CustomerFormModal.jsx frontend/src/pages/OrderForm.jsx frontend/src/pages/Orders.jsx frontend/electron/main.cjs frontend/src/styles.css
git commit -m "Redesign Clientes with filters, status and side panel; prefill new order; late-orders filter"
```

---

### Task 6: Painel

**Files:**
- Create: `frontend/src/components/RevenueHero.jsx`, `frontend/src/components/AlertStrip.jsx`, `frontend/src/components/TeamRanking.jsx`
- Rewrite: `frontend/src/pages/Dashboard.jsx`
- Modify: `frontend/src/styles.css` (append Painel block)

**Interfaces:**
- Consumes: `/dashboard` fields (Task 2); `PeriodPicker`, `defaultPeriod`, `usePeriodData`, `Delta` (Task 4).
- Produces: `<RevenueHero title revenue prevRevenue series goal onClick />`; `<AlertStrip alerts isAdmin />`; `<TeamRanking title sellers showGoalGap />` and `SELLER_COLORS` (used by Task 7).

- [ ] **Step 1: Create `frontend/src/components/RevenueHero.jsx`**

```jsx
import { useState } from "react";
import { money } from "../format";
import Delta from "./Delta";

export default function RevenueHero({ title, revenue, prevRevenue, series, goal, onClick }) {
  const [hover, setHover] = useState(null);
  const max = Math.max(...series.map((p) => p.value), 1);
  const active = hover ?? series.length - 1;
  const point = series[active];
  const pct = goal ? Math.round((revenue / goal) * 100) : null;
  return (
    <div className={`hero ${onClick ? "hero-clickable" : ""}`} onClick={onClick}>
      <div className="hero-main">
        <span className="hero-label">{title}</span>
        <strong className="hero-value">{money(revenue)}</strong>
        {prevRevenue > 0 && <span className="hero-delta"><Delta cur={revenue} prev={prevRevenue} /> vs. período anterior</span>}
        {point && <span className="hero-point">{point.label}: {money(point.value)}</span>}
        <div className="spark" onMouseLeave={() => setHover(null)}>
          {series.map((p, i) => (
            <span key={p.start} className={i === active ? "on" : ""} title={`${p.label}: ${money(p.value)}`}
              style={{ height: `${Math.max(4, (p.value / max) * 100)}%` }} onMouseEnter={() => setHover(i)} />
          ))}
        </div>
      </div>
      {pct != null && (
        <div className="hero-goal">
          <div className="goal-ring" style={{ "--pct": Math.min(pct, 100) }}>
            <div><strong>{pct}%</strong><span>da meta</span></div>
          </div>
          <span>Meta do período · {money(goal)}</span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Create `frontend/src/components/AlertStrip.jsx`**

```jsx
import { useNavigate } from "react-router-dom";
import { plural } from "../format";

export default function AlertStrip({ alerts }) {
  const nav = useNavigate();
  const items = [
    alerts.customers_at_risk > 0 && {
      tone: "warn", to: "/customers?status=at_risk", cta: "Ver lista",
      title: `${plural(alerts.customers_at_risk, "cliente", "clientes")} em risco`,
      text: "Compravam e estão entre 61 e 150 dias sem comprar.",
    },
    alerts.late_orders > 0 && {
      tone: "danger", to: "/orders?late=1", cta: "Ver pedidos",
      title: plural(alerts.late_orders, "pedido atrasado", "pedidos atrasados"),
      text: `O mais antigo está ${plural(alerts.oldest_late_days, "dia", "dias")} além da data de entrega.`,
    },
    alerts.customers_never_ordered > 0 && {
      tone: "info", to: "/customers?status=never_ordered", cta: "Ver cadastros",
      title: plural(alerts.customers_never_ordered, "cadastro sem compra", "cadastros sem compra"),
      text: "Oportunidade de primeira venda para a equipe comercial.",
    },
  ].filter(Boolean);
  if (!items.length) return null;
  return (
    <section className="alerts">
      {items.map((a) => (
        <div key={a.to} className={`alert alert-${a.tone}`}>
          <span className="alert-dot" aria-hidden="true" />
          <div>
            <strong>{a.title}</strong>
            <p>{a.text}</p>
            <button type="button" className="link-btn" onClick={() => nav(a.to)}>{a.cta} →</button>
          </div>
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 3: Create `frontend/src/components/TeamRanking.jsx`**

```jsx
import { useState } from "react";
import { money, plural } from "../format";
import { Avatar } from "./ui";

// Index i always gets the same color, so a seller keeps their color across components.
export const SELLER_COLORS = ["#5aa2ff", "#86efac", "#fcd34d", "#c4b5fd", "#f9a8d4", "#67e8f9", "#fdba74", "#a5b4fc"];

const METRICS = {
  value: { label: "Faturamento", fmt: money },
  orders: { label: "Pedidos", fmt: (n) => plural(n, "pedido", "pedidos") },
  pieces: { label: "Peças", fmt: (n) => plural(n, "peça", "peças") },
  goal: { label: "% da meta" },
};

// `sellers` = dashboard by_seller (already sorted by revenue).
export default function TeamRanking({ title, sellers, showGoalGap = false }) {
  const [metric, setMetric] = useState("value");
  const hasGoal = sellers.some((s) => s.goal);
  const m = metric === "goal" && !hasGoal ? "value" : metric;
  if (!sellers.length) return null;

  const score = (s) => (m === "goal" ? (s.goal ? (s.value / s.goal) * 100 : -1) : s[m]);
  const rows = sellers.map((s, i) => ({ ...s, color: SELLER_COLORS[i % SELLER_COLORS.length] }))
    .sort((a, b) => score(b) - score(a));
  const best = Math.max(score(rows[0]), 1);
  const teamTotal = sellers.reduce((t, s) => t + s[m === "goal" ? "value" : m], 0);
  const lead = score(rows[0]) > 0
    ? `${rows[0].name.split(" ")[0]} lidera em ${METRICS[m].label.toLowerCase()}`
    : "Sem vendas no período";

  return (
    <section className="team">
      <div className="team-head">
        <div><span>{title}</span><strong>{lead}</strong></div>
        <div className="team-tabs" role="tablist">
          {Object.entries(METRICS).filter(([k]) => k !== "goal" || hasGoal).map(([k, def]) => (
            <button key={k} type="button" role="tab" aria-selected={m === k} className={m === k ? "on" : ""}
              onClick={() => setMetric(k)}>{def.label}</button>
          ))}
        </div>
      </div>
      <div className="team-grid">
        {rows.map((s, i) => (
          <div key={s.id} className="team-card">
            <div className="team-card-head">
              <Avatar url={s.avatar_url} name={s.name} />
              <div><strong>{s.name}</strong><span>{i + 1}º lugar</span></div>
            </div>
            <strong className="team-value">
              {m === "goal" ? (s.goal ? `${Math.round(score(s))}%` : "Sem meta") : METRICS[m].fmt(s[m])}
            </strong>
            <div className="team-bar"><span style={{ width: `${Math.max(0, score(s)) / best * 100}%`, background: s.color }} /></div>
            <span className="team-sub">
              {m === "goal"
                ? (s.goal ? `Meta ${money(s.goal)}` : "Defina em Usuários")
                : `${teamTotal ? Math.round((s[m] / teamTotal) * 100) : 0}% do total da equipe`}
            </span>
            {showGoalGap && s.goal > 0 && (
              <span className="team-sub">
                {s.value >= s.goal ? "Meta do período batida" : `Faltam ${money(s.goal - s.value)} para a meta`}
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
```

- [ ] **Step 4: Rewrite `frontend/src/pages/Dashboard.jsx`**

```jsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useAuth } from "../auth";
import { compactMoney, initials, money, plural, STATUS } from "../format";
import { ErrorBox } from "../components/ui";
import AlertStrip from "../components/AlertStrip";
import Delta from "../components/Delta";
import PeriodPicker, { defaultPeriod } from "../components/PeriodPicker";
import RevenueHero from "../components/RevenueHero";
import TeamRanking from "../components/TeamRanking";
import usePeriodData from "../components/usePeriodData";

const EXCLUDE_MAP = import.meta.env.VITE_EXCLUDE_MAP === "1";

const STATUS_COLORS = {
  quote: "#8b96b3", confirmed: "#2f6fed", in_production: "#b8862f",
  shipped: "#0d95ac", delivered: "#0c2140", canceled: "#c0392b",
};

function greeting(h = new Date().getHours()) {
  if (h < 5) return "Boa noite"; // after midnight it's still night, not morning
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
}

function todayLabel() {
  const s = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  return s.charAt(0).toUpperCase() + s.slice(1);
}

const Empty = () => <p className="muted">Sem vendas no período.</p>;

function StatusDonut({ items }) {
  const [active, setActive] = useState(null);
  const total = items.reduce((t, s) => t + s.count, 0);
  const sel = active == null ? null : items[active];
  if (!total) return <p className="muted">Sem pedidos no período.</p>;
  return (
    <div className="donut-row" onMouseLeave={() => setActive(null)}>
      <div className="donut">
        <ResponsiveContainer width={184} height={184}>
          <PieChart>
            <Pie data={items} dataKey="count" nameKey="status" innerRadius={62} outerRadius={90} paddingAngle={2}
              onMouseEnter={(_, i) => setActive(i)} isAnimationActive={false}>
              {items.map((s, i) => (
                <Cell key={s.status} fill={STATUS_COLORS[s.status] || "#8b96b3"} opacity={active == null || active === i ? 1 : 0.25} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        <div className="donut-center">
          <strong>{sel ? sel.count : total}</strong>
          <span>{sel ? STATUS[sel.status] : "pedidos no período"}</span>
          {sel && <small>{Math.round((sel.count / total) * 100)}% do total</small>}
        </div>
      </div>
      <ul className="donut-legend">
        {items.map((s, i) => (
          <li key={s.status} className={active === i ? "on" : ""} onMouseEnter={() => setActive(i)}>
            <span className="legend-dot" style={{ background: STATUS_COLORS[s.status] || "#8b96b3" }} />
            <span className="legend-name">{STATUS[s.status] || s.status}</span>
            <span className="legend-qty">{s.count}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Bars({ items, label, value, detail }) {
  if (!items.length) return <Empty />;
  const max = Math.max(...items.map(value), 1);
  return (
    <ul className="hbars">
      {items.map((i, k) => (
        <li key={k}>
          <div><span>{label(i)}</span><strong>{detail(i)}</strong></div>
          <span className="hbar"><span style={{ width: `${(value(i) / max) * 100}%` }} /></span>
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const { user } = useAuth();
  const nav = useNavigate();
  const isAdmin = user?.role === "admin";
  const [period, setPeriod] = useState(defaultPeriod);
  const { data: d, error } = usePeriodData(period);
  const [topCities, setTopCities] = useState([]);

  useEffect(() => {
    if (!isAdmin || EXCLUDE_MAP) return;
    api.get("/customers").then((r) => {
      const counts = new Map();
      for (const c of r.data) {
        if (!c.city) continue;
        const key = `${c.city.trim()}/${(c.state || "").trim().toUpperCase()}`;
        counts.set(key, (counts.get(key) || 0) + 1);
      }
      setTopCities([...counts.entries()].map(([name, count]) => ({ name, count }))
        .sort((a, b) => b.count - a.count).slice(0, 5));
    });
  }, [isAdmin]);

  const colorTotal = d ? d.by_color.reduce((t, c) => t + c.pieces, 0) : 0;
  const sizeMax = d ? Math.max(...d.by_size.map((s) => s.pieces), 1) : 1;
  const kpis = d && [
    ["Pedidos fechados", d.kpis.orders, d.previous_kpis.orders, (v) => v.toLocaleString("pt-BR")],
    ["Peças vendidas", d.kpis.pieces, d.previous_kpis.pieces, (v) => v.toLocaleString("pt-BR")],
    ["Ticket médio", d.kpis.average_ticket, d.previous_kpis.average_ticket, money],
  ];

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <p className="dashboard-date muted">{todayLabel()}</p>
          <h1>{greeting()}, {user?.name?.split(" ")[0] || "vendedor"}</h1>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </header>
      <ErrorBox msg={error} />
      {d && (
        <>
          <section className="hero-row">
            <RevenueHero title="Faturamento no período" revenue={d.kpis.revenue} prevRevenue={d.previous_kpis.revenue}
              series={d.sales_series} goal={d.goal} onClick={isAdmin ? () => nav("/revenue") : undefined} />
            <div className="kpi-stack">
              {kpis.map(([label, cur, prev, fmt]) => (
                <div key={label}>
                  <span>{label}</span><strong>{fmt(cur)}</strong><Delta cur={cur} prev={prev} />
                </div>
              ))}
            </div>
          </section>

          <AlertStrip alerts={d.alerts} />

          <section className="dash-row">
            <div className="panel dash-wide">
              <h3>Faturamento nos últimos 12 meses</h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={d.monthly_sales} margin={{ left: 10, right: 10 }}>
                  <CartesianGrid vertical={false} stroke="#eef1f5" />
                  <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis tickLine={false} axisLine={false} fontSize={12} tickFormatter={(v) => (v ? compactMoney(v) : "0")} width={84} />
                  <Tooltip formatter={(v) => [money(v), "Faturamento"]} />
                  <Area type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2} fill="rgba(37,99,235,.08)" dot={{ r: 4, fill: "#fff", strokeWidth: 2 }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Situação dos pedidos</h3></div>
              <StatusDonut items={d.by_status} />
            </div>
          </section>

          {isAdmin && <TeamRanking title="Equipe comercial no período" sellers={d.by_seller} />}

          <section className="dash-grid-3">
            <div className="panel">
              <h3>Cores mais vendidas</h3>
              {d.by_color.length ? (
                <>
                  <div className="color-strip">
                    {d.by_color.map((c) => <span key={c.name} title={c.name} style={{ flex: c.pieces, background: c.hex }} />)}
                  </div>
                  <ul className="color-legend">
                    {d.by_color.slice(0, 6).map((c) => (
                      <li key={c.name}><span className="swatch" style={{ background: c.hex, width: 12, height: 12 }} />
                        <span>{c.name}</span><strong>{Math.round((c.pieces / colorTotal) * 100)}%</strong></li>
                    ))}
                  </ul>
                </>
              ) : <Empty />}
            </div>
            <div className="panel">
              <div className="panel-header"><h3>Peças por tamanho</h3><span className="muted">{plural(d.kpis.pieces, "peça", "peças")}</span></div>
              {d.by_size.length ? (
                <div className="vbars">
                  {d.by_size.map((s) => (
                    <div key={s.size}>
                      <small>{Math.round((s.pieces / Math.max(d.kpis.pieces, 1)) * 100)}%</small>
                      <span className={s.pieces === sizeMax ? "top" : ""} style={{ height: `${(s.pieces / sizeMax) * 78}%` }} />
                      <strong>{s.size}</strong>
                    </div>
                  ))}
                </div>
              ) : <Empty />}
            </div>
            <div className="panel">
              <h3>Produtos mais vendidos</h3>
              <Bars items={d.top_products.slice(0, 5)} label={(i) => `${i.reference} · ${i.description}`}
                value={(i) => i.pieces} detail={(i) => `${i.pieces} pç`} />
            </div>
          </section>

          <section className="dash-grid-2">
            <div className="panel">
              <div className="panel-header">
                <h3>Melhores clientes</h3>
                <button type="button" className="link-btn" onClick={() => nav("/customers?sort=total")}>Ver todos →</button>
              </div>
              {d.top_customers.length ? (
                <ol className="top-customers">
                  {d.top_customers.slice(0, 5).map((c, i) => (
                    <li key={c.name}>
                      <span className="rank">{i + 1}</span>
                      <span className="customer-avatar">{initials(c.name)}</span>
                      <span className="grow"><strong>{c.name}</strong><small>{plural(c.orders, "pedido", "pedidos")}</small></span>
                      <strong>{compactMoney(c.value)}</strong>
                    </li>
                  ))}
                </ol>
              ) : <Empty />}
            </div>
            {!EXCLUDE_MAP && isAdmin && topCities.length > 0 && (
              <div className="panel">
                <div className="panel-header">
                  <h3>Clientes por cidade</h3>
                  <button type="button" className="link-btn" onClick={() => nav("/customers-by-city")}>Ver mapa →</button>
                </div>
                <Bars items={topCities} label={(i) => i.name} value={(i) => i.count} detail={(i) => i.count} />
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Styles** — append to `frontend/src/styles.css`:

```css
/* ---------- painel / faturamento ---------- */
.hero-row { display: grid; grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr); gap: 16px; }
.hero { background: #0c2140; color: #fff; border-radius: 16px; padding: 24px 26px; display: flex; flex-wrap: wrap; gap: 24px; }
.hero-clickable { cursor: pointer; }
.hero-main { display: flex; flex-direction: column; gap: 6px; min-width: 0; flex: 1 1 280px; }
.hero-label, .hero-point, .hero-delta, .hero-goal > span { font-size: 13px; color: #9fb2d1; }
.hero-value { font-size: clamp(30px, 3.2vw, 44px); font-weight: 700; letter-spacing: -.02em; line-height: 1.05; overflow-wrap: anywhere; }
.hero-delta { display: flex; gap: 8px; align-items: center; }
.hero .kpi-delta.pos { background: rgba(74,222,128,.14); color: #86efac; }
.hero .kpi-delta.neg { background: rgba(248,113,113,.16); color: #fca5a5; }
.hero-point { margin-top: auto; padding-top: 14px; }
.spark { display: flex; align-items: flex-end; gap: 3px; height: 64px; }
.spark span { flex: 1; min-width: 2px; background: rgba(255,255,255,.22); border-radius: 2px 2px 0 0; cursor: crosshair; }
.spark span.on { background: #5aa2ff; }
.hero-goal { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding-left: 22px; border-left: 1px solid rgba(255,255,255,.1); }
.goal-ring { width: 124px; height: 124px; border-radius: 50%; display: grid; place-items: center; background: conic-gradient(#5aa2ff calc(var(--pct) * 1%), rgba(255,255,255,.12) 0); }
.goal-ring > div { width: 100px; height: 100px; border-radius: 50%; background: #0c2140; display: flex; flex-direction: column; align-items: center; justify-content: center; }
.goal-ring strong { font-size: 26px; }
.goal-ring span { font-size: 11px; color: #9fb2d1; }
.kpi-stack { background: var(--surface); border: 1px solid var(--line); border-radius: 16px; display: flex; flex-direction: column; }
.kpi-stack > div { flex: 1; display: grid; grid-template-columns: 1fr auto; grid-template-rows: auto auto; align-items: center; gap: 2px 12px; padding: 16px 18px 16px 22px; }
.kpi-stack > div + div { border-top: 1px solid var(--line); }
.kpi-stack span:first-child { grid-column: 1; font-size: 13px; color: var(--muted); }
.kpi-stack strong { grid-column: 1; font-size: 24px; font-variant-numeric: tabular-nums; }
.kpi-stack .kpi-delta { grid-column: 2; grid-row: 1 / 3; }
.alerts { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 16px; }
.alert { background: var(--surface); border: 1px solid var(--line); border-radius: 14px; padding: 16px 18px; display: flex; gap: 14px; align-items: flex-start; }
.alert p { margin: 4px 0; font-size: 13px; color: var(--muted); }
.alert .link-btn { margin: 0; padding: 0; }
.alert-dot { width: 10px; height: 10px; border-radius: 50%; margin-top: 6px; flex-shrink: 0; }
.alert-warn .alert-dot { background: #e0a32e; }
.alert-danger .alert-dot { background: var(--danger); }
.alert-info .alert-dot { background: var(--accent); }
.dash-row { display: flex; flex-wrap: wrap; gap: 16px; }
.dash-row > .panel { flex: 1 1 300px; min-width: 0; }
.dash-row > .dash-wide { flex: 1.7 1 460px; }
.dash-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.dash-grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; }
.donut { position: relative; width: 184px; height: 184px; flex-shrink: 0; }
.donut-center { position: absolute; inset: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; pointer-events: none; padding: 0 40px; }
.donut-center strong { font-size: 30px; line-height: 1; }
.donut-center span, .donut-center small { font-size: 12px; color: var(--muted); }
.donut-legend li.on { background: var(--surface-2); border-radius: 8px; }
.team { background: #0c2140; color: #fff; border-radius: 16px; padding: 24px 26px; display: flex; flex-direction: column; gap: 20px; }
.team-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; }
.team-head > div:first-child { display: flex; flex-direction: column; gap: 4px; }
.team-head span { font-size: 13px; color: #9fb2d1; }
.team-head strong { font-size: 22px; }
.team-tabs { display: flex; background: rgba(255,255,255,.08); border-radius: 10px; padding: 3px; gap: 2px; flex-wrap: wrap; }
.team-tabs button { border: 0; background: transparent; color: #c9d4e6; padding: 7px 14px; border-radius: 7px; font: inherit; font-size: 13px; font-weight: 600; cursor: pointer; }
.team-tabs button.on { background: #fff; color: #0c2140; }
.team-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; }
.team-card { background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.08); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
.team-card-head { display: flex; align-items: center; gap: 10px; }
.team-card-head > div { display: flex; flex-direction: column; }
.team-card-head span, .team-sub { font-size: 12px; color: #9fb2d1; }
.team-value { font-size: 24px; }
.team-bar { height: 6px; background: rgba(255,255,255,.1); border-radius: 3px; overflow: hidden; }
.team-bar span { display: block; height: 100%; border-radius: 3px; }
.color-strip { display: flex; height: 40px; border-radius: 8px; overflow: hidden; gap: 2px; margin-bottom: 14px; }
.color-legend { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 10px 16px; font-size: 13px; }
.color-legend li { display: flex; align-items: center; gap: 8px; }
.color-legend li span:nth-child(2) { flex: 1; }
.vbars { display: flex; gap: 10px; height: 150px; align-items: flex-end; }
.vbars > div { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; gap: 6px; font-size: 12px; }
.vbars > div > span { width: 100%; background: #cfe0fb; border-radius: 6px 6px 2px 2px; }
.vbars > div > span.top { background: #0c2140; }
.hbars { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 12px; }
.hbars li > div { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; }
.hbar { display: block; height: 4px; background: var(--surface-2); border-radius: 2px; margin-top: 5px; }
.hbar span { display: block; height: 100%; background: var(--accent); border-radius: 2px; }
.top-customers { list-style: none; margin: 0; padding: 0; }
.top-customers li { display: flex; align-items: center; gap: 12px; padding: 8px 0; border-top: 1px solid var(--line); font-size: 13px; }
.top-customers .rank { width: 18px; color: var(--muted); font-weight: 700; }
.top-customers .grow { flex: 1; min-width: 0; display: flex; flex-direction: column; }
.top-customers .grow strong { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.top-customers small { color: var(--muted); }
@media (max-width: 860px) {
  .hero-row { grid-template-columns: minmax(0, 1fr); }
  .hero-goal { padding-left: 0; border-left: 0; }
}
```

- [ ] **Step 6: Build and check** — `npm run build` → `✓ built`; `node scripts/check-format.mjs` → OK.

- [ ] **Step 7: Manual check** (backend + `npm run dev`):
  - Admin: hero with delta, sparkline hover, goal ring only when a company goal is set; alerts link to filtered Clientes and `#/orders?late=1`; donut hover; team tabs (no "% da meta" tab without goals); empty database shows "Sem vendas no período." everywhere.
  - Seller: no team block, no clickable hero, goal ring uses own goal.
  - "Personalizado" opens dates; 7 dias / Este mês / Este ano reload data.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/RevenueHero.jsx frontend/src/components/AlertStrip.jsx frontend/src/components/TeamRanking.jsx frontend/src/pages/Dashboard.jsx frontend/src/styles.css
git commit -m "Redesign Painel with revenue hero, goal ring, alerts and team ranking"
```

---

### Task 7: Faturamento

**Files:**
- Rewrite: `frontend/src/pages/Revenue.jsx`
- Modify: `frontend/src/styles.css` (append small block)

**Interfaces:**
- Consumes: `PeriodPicker`, `defaultPeriod`, `usePeriodData`, `Delta` (Task 4); `TeamRanking`, `SELLER_COLORS` (Task 6); `/dashboard` fields (Task 2).

- [ ] **Step 1: Rewrite `frontend/src/pages/Revenue.jsx`**

```jsx
import { useState } from "react";
import { compactMoney, money } from "../format";
import { ErrorBox } from "../components/ui";
import Delta from "../components/Delta";
import PeriodPicker, { defaultPeriod } from "../components/PeriodPicker";
import TeamRanking, { SELLER_COLORS } from "../components/TeamRanking";
import usePeriodData from "../components/usePeriodData";

function topCities(cities, n = 5) {
  const top = cities.slice(0, n);
  const rest = cities.slice(n).reduce((t, c) => t + c.value, 0);
  return rest > 0 ? [...top, { name: "Outras", value: rest }] : top;
}

export default function Revenue() {
  const [period, setPeriod] = useState(defaultPeriod);
  const { data: d, error } = usePeriodData(period);
  const sellers = d?.by_seller || [];
  const withSales = sellers.map((s, i) => ({ ...s, color: SELLER_COLORS[i % SELLER_COLORS.length] })).filter((s) => s.value > 0);
  const cities = topCities(d?.by_city || []);
  const cityMax = Math.max(...cities.map((c) => c.value), 1);

  return (
    <div className="page">
      <header className="dashboard-header">
        <div>
          <h1>Faturamento</h1>
          <p className="dashboard-greeting muted">Desempenho de vendas no período.</p>
        </div>
        <PeriodPicker value={period} onChange={setPeriod} />
      </header>
      <ErrorBox msg={error} />
      {d && (
        <>
          <section className="hero revenue-hero">
            <div className="revenue-hero-top">
              <div className="hero-main">
                <span className="hero-label">Faturamento total</span>
                <strong className="hero-value">{money(d.kpis.revenue)}</strong>
                {d.previous_kpis.revenue > 0 && (
                  <span className="hero-delta"><Delta cur={d.kpis.revenue} prev={d.previous_kpis.revenue} /> vs. período anterior</span>
                )}
              </div>
              <div className="revenue-hero-kpis">
                <div><span>Pedidos</span><strong>{d.kpis.orders.toLocaleString("pt-BR")}</strong></div>
                <div><span>Peças</span><strong>{d.kpis.pieces.toLocaleString("pt-BR")}</strong></div>
                <div><span>Ticket médio</span><strong>{money(d.kpis.average_ticket)}</strong></div>
              </div>
            </div>
            {withSales.length > 0 && (
              <div className="share">
                <div className="share-bar">
                  {withSales.map((s) => <span key={s.id} title={s.name} style={{ flex: s.value, background: s.color }} />)}
                </div>
                <div className="share-legend">
                  {withSales.map((s) => (
                    <span key={s.id}><i style={{ background: s.color }} />
                      {s.name.split(" ")[0]} {Math.round((s.value / d.kpis.revenue) * 100)}%</span>
                  ))}
                </div>
              </div>
            )}
          </section>

          <TeamRanking title="Por vendedor" sellers={sellers} showGoalGap />

          <section className="panel">
            <h3>Por cidade</h3>
            {cities.length ? (
              <ul className="hbars">
                {cities.map((c) => (
                  <li key={c.name}>
                    <div><span>{c.name}</span><strong>{compactMoney(c.value)}</strong></div>
                    <span className="hbar"><span style={{ width: `${(c.value / cityMax) * 100}%` }} /></span>
                  </li>
                ))}
              </ul>
            ) : <p className="muted">Sem vendas no período.</p>}
          </section>
        </>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Styles** — append to `frontend/src/styles.css`:

```css
.revenue-hero { flex-direction: column; gap: 22px; }
.revenue-hero-top { display: flex; justify-content: space-between; align-items: flex-end; gap: 24px; flex-wrap: wrap; }
.revenue-hero-kpis { display: flex; gap: 32px; flex-wrap: wrap; }
.revenue-hero-kpis div { display: flex; flex-direction: column; gap: 2px; }
.revenue-hero-kpis span { font-size: 13px; color: #9fb2d1; }
.revenue-hero-kpis strong { font-size: 22px; }
.share { display: flex; flex-direction: column; gap: 10px; }
.share-bar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; gap: 2px; }
.share-legend { display: flex; gap: 20px; flex-wrap: wrap; font-size: 13px; color: #c9d4e6; }
.share-legend span { display: flex; align-items: center; gap: 7px; }
.share-legend i { width: 10px; height: 10px; border-radius: 3px; }
```

- [ ] **Step 3: Build and check** — `npm run build` → `✓ built`.

- [ ] **Step 4: Manual check** — admin: total + delta; share bar colors match the TeamRanking card colors; "% da meta" tab and "Faltam R$ …" only for sellers with goal; seller with no sales shows R$ 0,00; cities top 5 + Outras.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Revenue.jsx frontend/src/styles.css
git commit -m "Redesign Faturamento with seller share bar, team ranking and goal gap"
```

---

### Task 8: Final verification

- [ ] **Step 1:** From `backend/`: `python test_security.py` and `python test_dashboard.py` → both OK.
- [ ] **Step 2:** From `frontend/`: `node scripts/check-format.mjs` and `npm run build` → OK, no new warnings besides the existing chunk-size one.
- [ ] **Step 3:** Grep for leftovers: `grep -rn "toISOString().slice(0, 10)" frontend/src` → no results in Dashboard/Revenue/OrderForm; `grep -rn "previousPeriod" frontend/src` → none.
- [ ] **Step 4:** Run the app against a copy of the real database (never the original): copy `dimarcy.db` to the scratch dir, start the backend with `DATABASE_URL=sqlite:///<copy>`, confirm the startup migration adds `monthly_goal` to `users` and `app_settings`, and walk the three screens as admin and as a seller at desktop and phone width.
- [ ] **Step 5:** Commit any fixes found, one commit per fix.
