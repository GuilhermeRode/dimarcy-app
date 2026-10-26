# Prospecção + mini-CRM — Plano 1 de 3: backend (região, leads, contatos)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tables, rules and API for seller regions, leads (listing, ranking, convert, discard) and contacts (history, follow-ups due), so the frontend (Plano 3) and the importer (Plano 2) can build on them.

**Architecture:** One rules module `backend/app/leads.py` (like `sales.py` / `finance.py`) holds visibility, ranking and follow-up rules; thin routers `routers/leads.py` and `routers/contacts.py` expose them; region endpoints go in the existing admin-only `routers/users.py`. A lead's seller is never stored — it's computed from `seller_cities`.

**Tech Stack:** FastAPI + SQLAlchemy 2 (SQLite), Pydantic v2. Tests are assert scripts run with `python test_leads.py` from `backend/`.

**Spec:** `docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md`

**Order:** Plano 1 → Plano 2 (`2026-10-16-prospeccao-2-importacao.md`) → Plano 3 (`2026-10-16-prospeccao-3-frontend.md`). Plano 2 and 3 only depend on this one.

**Before starting:** the working tree carries uncommitted changes from `feature/period-picker-revenue-header` (clock.py, dashboard.py, settings.py, users.py, schemas.py, tests…). Ask the user to commit or stash them before Task 1, so this branch's commits contain only this feature.

## Global Constraints

- Code (names, comments, routes, columns) in English; every user-visible string in pt-BR (`CLAUDE.md`). Error `detail` messages follow each file's existing language (routers use English details, e.g. `"Customer not found."`); new user-facing 409 texts listed in the spec are pt-BR.
- No new dependencies.
- "Today" = `clock.today_br()` (call it through the module, `clock.today_br()`, so tests can patch it).
- No migration tool: new tables via `Base.metadata.create_all`; new columns on existing tables via `_ensure_columns` in `main.py`.
- SQLite here has no `PRAGMA foreign_keys`: never rely on DB cascades; delete/adjust dependents in code.
- CNPJ normalization everywhere = `leads.normalize_cnpj` (letters+digits, uppercase).
- City matching everywhere = `sales._city_key(city)` + uppercase `state`.
- Region visibility: seller sees only leads whose `(city_key, state)` is in their `seller_cities`; admin sees all. Lead not visible → 404.

## Review Focus

- A seller hitting `/leads/{id}`, `/leads/{id}/convert`, `/leads/{id}/discard`, `/contacts?lead_id=` or `POST /contacts` for a lead outside their region must get 404 — not 200, not 409.
- Two clicks on "Virar cliente" (double submit) must create exactly one customer.
- A customer typed by hand with a formatted CNPJ (`12.345.678/0001-90`) must hide the matching lead at once.
- Deleting a customer that has contacts (or a converted lead pointing at it) must work and leave no orphans.
- A seller deactivated by the admin: their cities' leads show as "sem vendedor" for the admin; their reminders vanish with them.

---

### Task 1: Models, settings columns and the `leads` rules module skeleton

**Files:**
- Modify: `backend/app/models.py` (imports; new constants; `AppSettings` fields; new classes `SellerCity`, `Lead`, `Contact` at the end)
- Modify: `backend/app/main.py` (`_ensure_columns("app_settings", …)`)
- Create: `backend/app/leads.py`
- Create: `backend/test_leads.py`

**Interfaces:**
- Produces: `models.SellerCity`, `models.Lead`, `models.Contact`, constants `LEAD_STATUSES`, `DISCARD_REASONS`, `CONTACT_CHANNELS`; `AppSettings.lead_cnaes / last_lead_import_month / last_lead_import_scope / last_lead_import_at`; `leads.normalize_cnpj(value: str | None) -> str`; `test_leads.py` with helpers `login(c, email, password)`, `add_lead(cnpj, name, city=..., state=..., **extra) -> int` and a `ctx` dict (`c`, `admin`, `a`, `b`, `a_id`, `b_id`).

- [ ] **Step 1: Write the failing test** — create `backend/test_leads.py`:

```python
"""Prospecting + mini-CRM self-check: regions, leads, contacts. Run from backend/:  python test_leads.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app import clock  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.leads import normalize_cnpj  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppSettings, Contact, Customer, Lead, SellerCity, User  # noqa: E402
from app.sales import _city_key  # noqa: E402

TODAY = date(2026, 10, 16)
clock.today_br = lambda: TODAY


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def add_lead(cnpj, name, city="Jaraguá do Sul", state="SC", **extra):
    with SessionLocal() as db:
        lead = Lead(cnpj=cnpj, name=name, city=city, state=state, city_key=_city_key(city),
                    seen_at=TODAY, **extra)
        db.add(lead)
        db.commit()
        return lead.id


def check_models(ctx):
    assert normalize_cnpj("12.ABC.345/0001-99") == "12ABC345000199"
    assert normalize_cnpj(None) == ""
    with SessionLocal() as db:
        uid = ctx["a_id"]
        db.add(SellerCity(user_id=uid, city="Corupá", state="SC", city_key=_city_key("Corupá")))
        db.add(SellerCity(user_id=uid, city="corupa", state="SC", city_key=_city_key("corupa")))
        try:
            db.commit()
            raise AssertionError("same city twice must be refused")
        except IntegrityError:
            db.rollback()
        db.add(Contact(user_id=uid, channel="call"))  # neither lead nor customer
        try:
            db.commit()
            raise AssertionError("a contact needs exactly one target")
        except IntegrityError:
            db.rollback()
        lid = Lead(cnpj="00000000000191", name="X", city="Corupá", state="SC", city_key="corupa", seen_at=TODAY)
        db.add(lid)
        db.flush()
        db.add(Contact(user_id=uid, channel="call", lead_id=lid.id, customer_id=1))  # both
        try:
            db.commit()
            raise AssertionError("a contact needs exactly one target")
        except IntegrityError:
            db.rollback()
        assert db.query(AppSettings).first().lead_cnaes == "4781400"


# ---- run ----
with TestClient(app) as c:
    ctx = {"c": c, "admin": login(c, "admin@test.com", "admin-pass-123")}
    for key, name in (("a", "Ana"), ("b", "Bruno")):
        r = c.post("/api/users", headers=ctx["admin"], json={
            "name": name, "email": f"{key}@t.com", "password": "seller-pass-123", "role": "seller"})
        assert r.status_code == 201, r.text
        ctx[key + "_id"] = r.json()["id"]
        ctx[key] = login(c, f"{key}@t.com", "seller-pass-123")
    check_models(ctx)

print("test_leads OK")
```

Later tasks add a `check_*` function above `# ---- run ----` and a call at the end of the `with` block.

- [ ] **Step 2: Run it to verify it fails**

Run (from `backend/`): `python test_leads.py`
Expected: `ModuleNotFoundError: No module named 'app.leads'`

- [ ] **Step 3: Add the models** — in `backend/app/models.py`:

Change the sqlalchemy import to:

```python
from sqlalchemy import (Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey, Index, Integer, Numeric,
                        String, Table, Text, UniqueConstraint, func)
```

Below `PAYABLE_CATEGORIES`, add:

```python
LEAD_STATUSES = ["new", "converted", "discarded"]
DISCARD_REASONS = ["closed", "not_target", "competitor", "other"]
CONTACT_CHANNELS = ["whatsapp", "call", "visit", "email"]
```

In `class AppSettings`, before `updated_at`, add:

```python
    lead_cnaes: Mapped[str] = mapped_column(String(200), default="4781400", server_default="4781400")  # CNAE codes, comma-separated
    last_lead_import_month: Mapped[str | None] = mapped_column(String(7))  # e.g. "2026-10"
    last_lead_import_scope: Mapped[str | None] = mapped_column(String(300))  # e.g. "PR,SC|4781400"
    last_lead_import_at: Mapped[datetime | None] = mapped_column(DateTime)
```

At the end of the file, add:

```python
class SellerCity(Base):
    """A city in a seller's region. A city belongs to at most one seller (see leads.py)."""
    __tablename__ = "seller_cities"
    __table_args__ = (UniqueConstraint("city_key", "state", name="uq_seller_cities_city"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    city_key: Mapped[str] = mapped_column(String(100))  # sales._city_key(city)
    user: Mapped[User] = relationship()


class Lead(Base):
    """A store from the Receita's open CNPJ data that isn't a customer yet. Its seller is never
    stored: it's whoever has the lead's city in seller_cities (see leads.city_owners)."""
    __tablename__ = "leads"
    __table_args__ = (Index("ix_leads_area", "state", "city_key", "status"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    cnpj: Mapped[str] = mapped_column(String(14), unique=True)  # leads.normalize_cnpj
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(160))
    address: Mapped[str | None] = mapped_column(String(250))
    city: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(2))
    city_key: Mapped[str] = mapped_column(String(100))
    opened_at: Mapped[_dt.date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="new", server_default="new")  # see LEAD_STATUSES
    discard_reason: Mapped[str | None] = mapped_column(String(30))  # see DISCARD_REASONS
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"))
    seen_at: Mapped[_dt.date] = mapped_column(Date)  # last import that listed this CNPJ


class Contact(Base):
    """One touch with a lead or a customer (exactly one of them). The latest contact's
    next_action_date is the pending follow-up — see leads.due_follow_ups."""
    __tablename__ = "contacts"
    __table_args__ = (CheckConstraint("(lead_id IS NULL) <> (customer_id IS NULL)", name="ck_contacts_one_target"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    lead_id: Mapped[int | None] = mapped_column(ForeignKey("leads.id"), index=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), index=True)
    channel: Mapped[str] = mapped_column(String(10))  # see CONTACT_CHANNELS
    notes: Mapped[str | None] = mapped_column(Text)
    next_action_date: Mapped[_dt.date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    user: Mapped[User] = relationship()
    lead: Mapped[Lead | None] = relationship()
    customer: Mapped[Customer | None] = relationship()
```

- [ ] **Step 4: Add the columns for existing databases** — in `backend/app/main.py`, replace the `app_settings` `_ensure_columns` call with:

```python
    _ensure_columns("app_settings", {"annual_goal": "NUMERIC(12,2) DEFAULT 0",
                                     "retail_markup_percent": "NUMERIC(6,2) DEFAULT 50",
                                     "lead_cnaes": "VARCHAR(200) DEFAULT '4781400'",
                                     "last_lead_import_month": "VARCHAR(7)",
                                     "last_lead_import_scope": "VARCHAR(300)",
                                     "last_lead_import_at": "TIMESTAMP"})
```

- [ ] **Step 5: Create `backend/app/leads.py`**

```python
"""Prospecting rules shared by the leads/contacts routers, the dashboard and the importer.

A lead's seller is never stored: it's the active seller whose region (seller_cities) has the
lead's city, so moving a city between sellers moves its leads with no migration.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md"""
import re


def normalize_cnpj(value: str | None) -> str:
    """Letters and digits only, uppercase — CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()
```

- [ ] **Step 6: Run the test**

Run: `python test_leads.py`
Expected: `test_leads OK`

- [ ] **Step 7: Run the existing suites (nothing else may break)**

Run: `python test_permissions.py && python test_dashboard.py && python test_finance.py && python test_price_tables.py`
Expected: each prints its OK line.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models.py backend/app/main.py backend/app/leads.py backend/test_leads.py
git commit -m "Add seller cities, leads and contacts tables"
```

---

### Task 2: `lead_cnaes` in Configurações (API)

**Files:**
- Modify: `backend/app/schemas.py` (`import re`; `AppSettingsIn`; `AppSettingsAdminOut`)
- Modify: `backend/app/routers/settings.py` (`update_settings`)
- Test: `backend/test_leads.py`

**Interfaces:**
- Produces: `PUT /api/settings` accepts optional `lead_cnaes: str` (normalized to `"4781400,4642701"`; invalid → 422; omitted → unchanged). `GET /api/settings` (admin) returns `lead_cnaes`, `last_lead_import_month`, `last_lead_import_at`.

- [ ] **Step 1: Write the failing test** — add above `# ---- run ----`:

```python
def check_settings(ctx):
    c, admin = ctx["c"], ctx["admin"]
    base = {"allow_price_override": False, "max_discount_percent": 0, "retail_markup_percent": 50, "annual_goal": None}
    r = c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": "4781-4/00, 4642-7/01,4781400"})
    assert r.status_code == 200, r.text
    assert r.json()["lead_cnaes"] == "4781400,4642701"
    assert r.json()["last_lead_import_month"] is None
    assert c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": "123"}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": " , "}).status_code == 422
    r = c.put("/api/settings", headers=admin, json=base)  # omitted: unchanged
    assert r.json()["lead_cnaes"] == "4781400,4642701"
    assert "lead_cnaes" not in c.get("/api/settings", headers=ctx["a"]).json()  # sellers don't see it
    c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": "4781400"})
```

and at the end of the `with` block: `    check_settings(ctx)`

- [ ] **Step 2: Run to verify it fails**

Run: `python test_leads.py`
Expected: `KeyError: 'lead_cnaes'` (or AssertionError on the first status).

- [ ] **Step 3: Implement** — in `backend/app/schemas.py`, add `import re` at the top (after `import datetime as _dt`). Replace `AppSettingsIn` and `AppSettingsAdminOut` with:

```python
class AppSettingsIn(BaseModel):
    allow_price_override: bool
    max_discount_percent: float = Field(ge=0, le=100)
    retail_markup_percent: float = Field(default=50, ge=0, le=1000)
    annual_goal: Goal = None
    lead_cnaes: str | None = None  # None = keep the current list

    @field_validator("lead_cnaes")
    @classmethod
    def _cnaes(cls, v: str | None) -> str | None:
        if v is None:
            return v
        codes = [re.sub(r"\D", "", part) for part in v.split(",") if part.strip()]
        if not codes or any(len(code) != 7 for code in codes):
            raise ValueError("Informe códigos CNAE de 7 dígitos, separados por vírgula.")
        return ",".join(dict.fromkeys(codes))  # dedup, keep order
```

```python
class AppSettingsAdminOut(AppSettingsOut):
    annual_goal: float | None = None
    lead_cnaes: str
    last_lead_import_month: str | None = None
    last_lead_import_at: datetime | None = None
```

In `backend/app/routers/settings.py` `update_settings`, after `s.annual_goal = data.annual_goal`:

```python
    if data.lead_cnaes is not None:
        s.lead_cnaes = data.lead_cnaes
```

- [ ] **Step 4: Run the test**

Run: `python test_leads.py`
Expected: `test_leads OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/routers/settings.py backend/test_leads.py
git commit -m "Settings: editable CNAE list for prospecting"
```

---

### Task 3: Seller regions (`/api/users/.../cities`)

**Files:**
- Modify: `backend/app/routers/users.py`
- Modify: `backend/app/schemas.py` (new `CityIn`, `CityOut`)
- Test: `backend/test_leads.py`

**Interfaces:**
- Consumes: `SellerCity`, `Lead`, `Customer`, `sales._city_key`.
- Produces (all admin-only, router already has `require_admin`):
  - `GET /api/users/{uid}/cities` → `[{city, state}]` sorted by city
  - `PUT /api/users/{uid}/cities` body `[{city, state}]` → same shape; 404 unknown user; 409 `"{city} já é da região de {name}."`
  - `GET /api/users/{uid}/cities/suggestions` → `[{city, state, taken_by: str | None}]` from that seller's customers
  - `GET /api/users/cities/options` → `[{city, state}]` distinct from customers + leads (customer spelling wins)

- [ ] **Step 1: Write the failing test** — add above `# ---- run ----`:

```python
def check_regions(ctx):
    c, admin, a_id, b_id = ctx["c"], ctx["admin"], ctx["a_id"], ctx["b_id"]
    with SessionLocal() as db:  # leftovers from check_models
        db.query(SellerCity).delete()
        db.query(Lead).delete()
        db.commit()
    r = c.put(f"/api/users/{a_id}/cities", headers=admin, json=[
        {"city": "Jaraguá do Sul", "state": "sc"}, {"city": " jaragua  do sul ", "state": "SC"}])
    assert r.status_code == 200, r.text
    assert r.json() == [{"city": "Jaraguá do Sul", "state": "SC"}]  # same key twice -> once
    r = c.put(f"/api/users/{b_id}/cities", headers=admin, json=[{"city": "JARAGUA DO SUL", "state": "SC"}])
    assert r.status_code == 409 and r.json()["detail"] == "JARAGUA DO SUL já é da região de Ana.", r.text
    assert c.put(f"/api/users/{b_id}/cities", headers=admin, json=[{"city": "Corupá", "state": "SC"}]).status_code == 200
    assert c.get(f"/api/users/{b_id}/cities", headers=admin).json() == [{"city": "Corupá", "state": "SC"}]
    assert c.put("/api/users/9999/cities", headers=admin, json=[]).status_code == 404
    assert c.get(f"/api/users/{a_id}/cities", headers=ctx["a"]).status_code == 403  # admin only
    assert c.put(f"/api/users/{a_id}/cities", headers=admin, json=[{"city": "", "state": "SC"}]).status_code == 422

    # suggestions: Ana's customers' cities, marking the ones another seller has
    c.post("/api/customers", headers=ctx["a"], json={"name": "Loja Corupá", "document": "1", "city": "Corupa", "state": "SC"})
    c.post("/api/customers", headers=ctx["a"], json={"name": "Loja Guará", "document": "2", "city": "Guaramirim", "state": "SC"})
    sug = c.get(f"/api/users/{a_id}/cities/suggestions", headers=admin).json()
    assert {"city": "Corupa", "state": "SC", "taken_by": "Bruno"} in sug, sug
    assert {"city": "Guaramirim", "state": "SC", "taken_by": None} in sug, sug

    add_lead("11111111000111", "Lead Blumenau", city="Blumenau")
    opts = c.get("/api/users/cities/options", headers=admin).json()
    assert {"city": "Blumenau", "state": "SC"} in opts and {"city": "Guaramirim", "state": "SC"} in opts, opts
    with SessionLocal() as db:
        db.query(Lead).delete()
        db.commit()
```

and at the end of the `with` block: `    check_regions(ctx)`

- [ ] **Step 2: Run to verify it fails**

Run: `python test_leads.py`
Expected: AssertionError on the first `PUT` (404/405).

- [ ] **Step 3: Implement** — in `backend/app/schemas.py`, after `UserOut`:

```python
class CityIn(BaseModel):
    city: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=2, max_length=2)


class CityOut(ORM):
    city: str
    state: str
```

Replace the imports of `backend/app/routers/users.py` and add the routes at the end:

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Customer, Lead, SellerCity, User
from ..sales import _city_key
from ..schemas import CityIn, CityOut, UserIn, UserOut
from ..security import MIN_PASSWORD_LENGTH, hash_password, require_admin
```

```python
def _clean_city(city: str, state: str) -> tuple[str, str]:
    return " ".join(city.split()), state.strip().upper()


@router.get("/cities/options", response_model=list[CityOut])
def city_options(db: Session = Depends(get_db)):
    """Cities to pick from when building a region: customers' spelling first, then the leads'."""
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    rows = db.query(Customer.city, Customer.state).filter(Customer.city.isnot(None)).distinct().all()
    rows += db.query(Lead.city, Lead.state).distinct().all()
    for city, state in rows:
        city, state = _clean_city(city or "", state or "")
        if city:
            seen.setdefault((_city_key(city), state), (city, state))
    return sorted(({"city": c, "state": s} for c, s in seen.values()), key=lambda x: (x["city"], x["state"]))


@router.get("/{uid}/cities", response_model=list[CityOut])
def get_cities(uid: int, db: Session = Depends(get_db)):
    return db.query(SellerCity).filter(SellerCity.user_id == uid).order_by(SellerCity.city).all()


@router.put("/{uid}/cities", response_model=list[CityOut])
def set_cities(uid: int, data: list[CityIn], db: Session = Depends(get_db)):
    """Replaces the seller's region. A city already in another seller's region -> 409."""
    if not db.get(User, uid):
        raise HTTPException(404, "User not found.")
    others = {(sc.city_key, sc.state): sc for sc in db.query(SellerCity).filter(SellerCity.user_id != uid)}
    wanted: dict[tuple[str, str], str] = {}
    for item in data:
        city, state = _clean_city(item.city, item.state)
        if not city:
            raise HTTPException(422, "Informe o nome da cidade.")
        key = (_city_key(city), state)
        if key in others:
            raise HTTPException(409, f"{city} já é da região de {others[key].user.name}.")
        wanted.setdefault(key, city)
    db.query(SellerCity).filter(SellerCity.user_id == uid).delete()
    for (key, state), city in wanted.items():
        db.add(SellerCity(user_id=uid, city=city, state=state, city_key=key))
    try:
        db.commit()
    except IntegrityError:  # another admin saved the same city at the same moment
        db.rollback()
        raise HTTPException(409, "Uma das cidades acabou de ser incluída na região de outro vendedor.")
    return get_cities(uid, db)


@router.get("/{uid}/cities/suggestions")
def city_suggestions(uid: int, db: Session = Depends(get_db)):
    """The seller's customers' cities, each with the name of the other seller who already has it."""
    others = {(sc.city_key, sc.state): sc.user.name
              for sc in db.query(SellerCity).filter(SellerCity.user_id != uid)}
    seen: dict[tuple[str, str], dict] = {}
    for city, state in db.query(Customer.city, Customer.state).filter(
            Customer.owner_id == uid, Customer.city.isnot(None)).distinct():
        city, state = _clean_city(city or "", state or "")
        key = (_city_key(city), state)
        if city and key not in seen:
            seen[key] = {"city": city, "state": state, "taken_by": others.get(key)}
    return sorted(seen.values(), key=lambda x: x["city"])
```

Note: `/cities/options` must be declared before any `/{uid}` GET route with one segment (there is none today; keep it first anyway).

- [ ] **Step 4: Run the test**

Run: `python test_leads.py`
Expected: `test_leads OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/users.py backend/app/schemas.py backend/test_leads.py
git commit -m "Users: seller regions (cities) with one seller per city"
```

---

### Task 4: Lead listing, ranking and detail (`GET /api/leads`, `GET /api/leads/{id}`)

**Files:**
- Modify: `backend/app/leads.py`
- Create: `backend/app/routers/leads.py`
- Modify: `backend/app/main.py` (import + include router)
- Test: `backend/test_leads.py`

**Interfaces:**
- Consumes: `normalize_cnpj`, `SellerCity`, `Lead`, `Customer`, `Order`, `customer_status`, `SALE_STATUSES`, `sales._city_key`.
- Produces in `leads.py`:
  - `NEW_STORE_DAYS = 730`
  - `city_owners(db) -> dict[tuple[str, str], User]` keyed `(city_key, state)`, active users only
  - `lead_owner(owners, lead) -> User | None`
  - `customer_cnpjs(db) -> set[str]`
  - `visible_lead(db, user, lead_id) -> Lead` (404 `"Lead not found."`)
  - `active_customers_by_city(db, today) -> Counter[tuple[str, str]]`
  - `ranked_leads(db, user, today, city="", search="", seller_id=None) -> list[tuple[Lead, User | None]]`
  - `lead_out(lead, owner) -> dict` with keys `id, cnpj, name, phone, email, address, city, state, opened_at, status, seller_id, seller_name`
- Produces routes: `GET /api/leads?city=&search=&seller_id=&limit=50&offset=0` → `{"items": [lead_out…], "total": int, "cities": [str]}` (`cities` = distinct `city` of the filtered rows, sorted); `GET /api/leads/{id}` → `lead_out`.

- [ ] **Step 1: Write the failing test** — add above `# ---- run ----`:

```python
def check_listing(ctx):
    c, admin = ctx["c"], ctx["admin"]
    old, recent = TODAY - timedelta(days=2000), TODAY - timedelta(days=100)
    ids = {
        "j_phone_recent": add_lead("10000000000101", "Jota Moda", phone="47 3333-0001", opened_at=recent),
        "j_no_contact": add_lead("10000000000102", "Jaraguá Sem Fone", opened_at=recent),
        "j_phone_old": add_lead("10000000000103", "Antiga Modas", phone="47 3333-0003", opened_at=old),
        "corupa": add_lead("10000000000104", "Corupá Store", city="Corupá", phone="1", opened_at=recent),
        "blumenau": add_lead("10000000000105", "Blu Fashion", city="Blumenau", phone="1", opened_at=recent),
        "gone": add_lead("10000000000106", "Descartada", status="discarded"),
    }
    names = lambda r: [x["name"] for x in r.json()["items"]]  # noqa: E731

    r = c.get("/api/leads", headers=ctx["a"])
    assert r.status_code == 200, r.text
    assert names(r) == ["Jota Moda", "Antiga Modas", "Jaraguá Sem Fone"], names(r)  # contact, then new store
    assert r.json()["total"] == 3 and r.json()["cities"] == ["Jaraguá do Sul"]
    assert names(c.get("/api/leads", headers=ctx["b"])) == ["Corupá Store"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"limit": 1, "offset": 1})) == ["Antiga Modas"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"search": "antiga"})) == ["Antiga Modas"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"search": "0000000000103"})) == ["Antiga Modas"]

    r = c.get("/api/leads", headers=admin)
    assert r.json()["total"] == 5  # every new lead, discarded left out
    blu = next(x for x in r.json()["items"] if x["name"] == "Blu Fashion")
    assert blu["seller_id"] is None and blu["seller_name"] is None
    assert names(c.get("/api/leads", headers=admin, params={"seller_id": 0})) == ["Blu Fashion"]
    assert names(c.get("/api/leads", headers=admin, params={"seller_id": ctx["b_id"], "city": "corupa"})) == ["Corupá Store"]

    # detail: visible to the region's seller and the admin only
    assert c.get(f"/api/leads/{ids['corupa']}", headers=ctx["b"]).json()["seller_name"] == "Bruno"
    assert c.get(f"/api/leads/{ids['corupa']}", headers=ctx["a"]).status_code == 404
    assert c.get(f"/api/leads/{ids['blumenau']}", headers=ctx["a"]).status_code == 404
    assert c.get(f"/api/leads/{ids['blumenau']}", headers=admin).status_code == 200

    # a customer typed by hand with the lead's CNPJ (formatted) hides the lead at once
    c.post("/api/customers", headers=ctx["a"], json={"name": "Antiga", "document": "10.000.000/0001-03"})
    assert names(c.get("/api/leads", headers=ctx["a"])) == ["Jota Moda", "Jaraguá Sem Fone"]

    # moving Corupá to Ana moves its leads; a deactivated seller's cities show as "sem vendedor"
    c.put(f"/api/users/{ctx['b_id']}/cities", headers=admin, json=[])
    c.put(f"/api/users/{ctx['a_id']}/cities", headers=admin, json=[
        {"city": "Jaraguá do Sul", "state": "SC"}, {"city": "Corupá", "state": "SC"}])
    assert "Corupá Store" in names(c.get("/api/leads", headers=ctx["a"]))
    assert names(c.get("/api/leads", headers=ctx["b"])) == []
    c.put(f"/api/users/{ctx['a_id']}", headers=admin, json={"name": "Ana", "email": "a@t.com", "role": "seller", "active": False})
    assert sorted(names(c.get("/api/leads", headers=admin, params={"seller_id": 0}))) == \
        ["Blu Fashion", "Corupá Store", "Jaraguá Sem Fone", "Jota Moda"]
    c.put(f"/api/users/{ctx['a_id']}", headers=admin, json={"name": "Ana", "email": "a@t.com", "role": "seller", "active": True})
    c.put(f"/api/users/{ctx['a_id']}/cities", headers=admin, json=[{"city": "Jaraguá do Sul", "state": "SC"}])
    c.put(f"/api/users/{ctx['b_id']}/cities", headers=admin, json=[{"city": "Corupá", "state": "SC"}])
    ctx["leads"] = ids


def check_ranking_by_active_customers(ctx):
    """Same contact/new-store tier: the city with more active Di Marcy customers comes first."""
    c, admin = ctx["c"], ctx["admin"]
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]
    product = c.post("/api/products", headers=admin, json={"reference": "R1", "description": "Blusão", "price": 100,
                                                           "color_ids": [color]}).json()["id"]
    cust = c.post("/api/customers", headers=admin, json={"name": "Cliente Blu", "document": "77", "city": "Blumenau",
                                                         "state": "SC", "owner_id": None}).json()["id"]
    r = c.post("/api/orders", headers=admin, json={
        "customer_id": cust, "date": TODAY.isoformat(), "delivery_date": TODAY.isoformat(), "status": "delivered", "payment_method": "PIX",
        "payment_terms": "À vista", "items": [{"product_id": product, "color_id": color, "size": "P", "quantity": 1}]})
    assert r.status_code == 201, r.text
    top = [x["name"] for x in c.get("/api/leads", headers=admin).json()["items"]][:3]
    assert top[0] == "Blu Fashion", top
```

and at the end of the `with` block:

```python
    check_listing(ctx)
    check_ranking_by_active_customers(ctx)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python test_leads.py`
Expected: AssertionError on `r.status_code == 200` (404 — route missing).

- [ ] **Step 3: Implement the rules** — replace `backend/app/leads.py` with:

```python
"""Prospecting rules shared by the leads/contacts routers, the dashboard and the importer.

A lead's seller is never stored: it's the active seller whose region (seller_cities) has the
lead's city, so moving a city between sellers moves its leads with no migration.
Spec: docs/superpowers/specs/2026-10-16-prospeccao-crm-design.md"""
import re
from collections import Counter
from datetime import date

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from .models import SALE_STATUSES, Customer, Lead, Order, SellerCity, User, customer_status
from .sales import _city_key

NEW_STORE_DAYS = 730  # "abriu recentemente": a new store is still choosing its suppliers


def normalize_cnpj(value: str | None) -> str:
    """Letters and digits only, uppercase — CNPJs may be alphanumeric since July 2026."""
    return re.sub(r"[^0-9A-Za-z]", "", value or "").upper()


def city_owners(db: Session) -> dict[tuple[str, str], User]:
    """(city_key, state) -> the ACTIVE seller whose region has that city."""
    rows = db.query(SellerCity).join(User, SellerCity.user_id == User.id).filter(User.active.is_(True)).all()
    return {(r.city_key, r.state): r.user for r in rows}


def lead_owner(owners: dict[tuple[str, str], User], lead: Lead) -> User | None:
    return owners.get((lead.city_key, lead.state))


def customer_cnpjs(db: Session) -> set[str]:
    return {normalize_cnpj(d) for (d,) in db.query(Customer.document) if d}


def visible_lead(db: Session, user: User, lead_id: int) -> Lead:
    """A seller only reaches leads of their region; an admin reaches every lead."""
    lead = db.get(Lead, lead_id)
    if lead and user.role != "admin":
        owner = lead_owner(city_owners(db), lead)
        if not owner or owner.id != user.id:
            lead = None
    if not lead:
        raise HTTPException(404, "Lead not found.")
    return lead


def active_customers_by_city(db: Session, today: date) -> Counter:
    """Company-wide count of 'active' customers per (city_key, state) — not scoped to a seller."""
    last = dict(db.query(Order.customer_id, func.max(Order.date))
                .filter(Order.status.in_(SALE_STATUSES)).group_by(Order.customer_id).all())
    counts: Counter = Counter()
    for cid, city, state in db.query(Customer.id, Customer.city, Customer.state).filter(Customer.city.isnot(None)):
        if customer_status(last.get(cid), today) == "active":
            counts[(_city_key(city), (state or "").strip().upper())] += 1
    return counts


def ranked_leads(db: Session, user: User, today: date, city: str = "", search: str = "",
                 seller_id: int | None = None) -> list[tuple[Lead, User | None]]:
    """New leads the user may see, best first: has phone/e-mail, opened within NEW_STORE_DAYS,
    more active customers in the city, opened most recently, name. `seller_id` (admin) 0 = no seller."""
    q = db.query(Lead).filter(Lead.status == "new")
    if user.role != "admin":
        q = q.join(SellerCity, and_(SellerCity.city_key == Lead.city_key, SellerCity.state == Lead.state)) \
             .filter(SellerCity.user_id == user.id)
    if city.strip():
        q = q.filter(Lead.city_key == _city_key(city))
    text = search.strip()
    if text:
        cnpj = normalize_cnpj(text)
        cond = Lead.name.ilike(f"%{text}%")
        q = q.filter(or_(cond, Lead.cnpj.contains(cnpj)) if len(cnpj) >= 3 else cond)
    known, owners, active = customer_cnpjs(db), city_owners(db), active_customers_by_city(db, today)

    rows = []
    # ponytail: ranks in Python (~60k new leads per state for the admin); SQL window function if slow
    for lead in q.all():
        if lead.cnpj in known:
            continue
        owner = lead_owner(owners, lead)
        if seller_id is not None and (owner.id if owner else 0) != seller_id:
            continue
        rows.append((lead, owner))

    def rank(row):
        lead = row[0]
        recent = lead.opened_at is not None and (today - lead.opened_at).days <= NEW_STORE_DAYS
        return (not (lead.phone or lead.email), not recent, -active[(lead.city_key, lead.state)],
                -(lead.opened_at.toordinal() if lead.opened_at else 0), lead.name)
    return sorted(rows, key=rank)


def lead_out(lead: Lead, owner: User | None) -> dict:
    return {"id": lead.id, "cnpj": lead.cnpj, "name": lead.name, "phone": lead.phone, "email": lead.email,
            "address": lead.address, "city": lead.city, "state": lead.state, "opened_at": lead.opened_at,
            "status": lead.status, "seller_id": owner.id if owner else None,
            "seller_name": owner.name if owner else None}
```

- [ ] **Step 4: Create `backend/app/routers/leads.py`**

```python
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..leads import city_owners, lead_out, lead_owner, ranked_leads, visible_lead
from ..models import User
from ..security import get_current_user

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("")
def list_leads(city: str = "", search: str = "", seller_id: int | None = None,
               limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = ranked_leads(db, user, clock.today_br(), city, search,
                        seller_id if user.role == "admin" else None)
    return {"items": [lead_out(lead, owner) for lead, owner in rows[offset:offset + limit]], "total": len(rows),
            "cities": sorted({lead.city for lead, _ in rows})}  # for the screen's city filter


@router.get("/{lid}")
def get_lead(lid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lead = visible_lead(db, user, lid)
    return lead_out(lead, lead_owner(city_owners(db), lead))
```

In `backend/app/main.py`, add `leads` to the routers import and to the `for r in (...)` tuple:

```python
from .routers import auth, colors, customers, dashboard, finance, leads, orders, products, settings as settings_router, users
```

```python
for r in (auth, users, customers, colors, products, orders, dashboard, finance, leads, settings_router):
```

- [ ] **Step 5: Run the test**

Run: `python test_leads.py`
Expected: `test_leads OK`

- [ ] **Step 6: Commit**

```bash
git add backend/app/leads.py backend/app/routers/leads.py backend/app/main.py backend/test_leads.py
git commit -m "Leads: ranked, region-scoped listing and detail"
```

---

### Task 5: Convert and discard a lead

**Files:**
- Modify: `backend/app/routers/customers.py` (extract `add_customer` + `geocode_later`; `create` uses them)
- Modify: `backend/app/routers/leads.py` (convert, discard)
- Modify: `backend/app/schemas.py` (`DiscardIn`)
- Test: `backend/test_leads.py`

**Interfaces:**
- Produces in `routers/customers.py`: `add_customer(db, data: CustomerIn, owner_id: int | None) -> Customer` (adds, not commits) and `geocode_later(c: Customer, background_tasks) -> None`.
- Produces routes: `POST /api/leads/{id}/convert` body `CustomerIn` → 201 `CustomerOut`; 409 `"Este lead já foi tratado."`. `POST /api/leads/{id}/discard` body `{"reason": "closed"|"not_target"|"competitor"|"other"}` → 204; 409 same text.
- Note for Task 6: convert moves the lead's contacts to the customer — Task 6 adds `Contact` rows; this task already writes the `UPDATE contacts …` line (it's a no-op until contacts exist).

- [ ] **Step 1: Write the failing test** — add above `# ---- run ----`:

```python
def check_convert(ctx):
    c, admin, ids = ctx["c"], ctx["admin"], ctx["leads"]
    body = {"name": "Jota Moda Ltda", "document": "10000000000101", "city": "Jaraguá do Sul", "state": "SC",
            "owner_id": ctx["b_id"]}  # a seller can't pick the owner: ignored
    assert c.post(f"/api/leads/{ids['corupa']}/convert", headers=ctx["a"], json=body).status_code == 404
    r = c.post(f"/api/leads/{ids['j_phone_recent']}/convert", headers=ctx["a"], json=body)
    assert r.status_code == 201, r.text
    assert r.json()["owner_id"] == ctx["a_id"]
    assert c.post(f"/api/leads/{ids['j_phone_recent']}/convert", headers=ctx["a"], json=body).status_code == 409
    with SessionLocal() as db:
        lead = db.get(Lead, ids["j_phone_recent"])
        assert lead.status == "converted" and lead.customer_id == r.json()["id"]
        assert db.query(Customer).filter_by(name="Jota Moda Ltda").count() == 1

    # admin without owner_id -> the region's seller; with owner_id -> that one
    r = c.post(f"/api/leads/{ids['corupa']}/convert", headers=admin, json={**body, "name": "Corupá", "owner_id": None})
    assert r.status_code == 201 and r.json()["owner_id"] == ctx["b_id"], r.text
    r = c.post(f"/api/leads/{ids['blumenau']}/convert", headers=admin, json={**body, "name": "Blu", "owner_id": ctx["a_id"]})
    assert r.status_code == 201 and r.json()["owner_id"] == ctx["a_id"], r.text

    # discard
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["b"], json={"reason": "closed"}).status_code == 404
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["a"], json={"reason": "x"}).status_code == 422
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["a"], json={"reason": "competitor"}).status_code == 204
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["a"], json={"reason": "closed"}).status_code == 409
    with SessionLocal() as db:
        assert db.get(Lead, ids["j_no_contact"]).discard_reason == "competitor"
    assert [x["name"] for x in c.get("/api/leads", headers=ctx["a"]).json()["items"]] == []
```

and at the end of the `with` block: `    check_convert(ctx)`

- [ ] **Step 2: Run to verify it fails**

Run: `python test_leads.py`
Expected: AssertionError (405 instead of 404/201).

- [ ] **Step 3: Extract the customer-creation helper** — in `backend/app/routers/customers.py`, replace `create` with:

```python
def add_customer(db: Session, data: CustomerIn, owner_id: int | None) -> Customer:
    """Adds (doesn't commit) a new customer, with cached coordinates when the city is known.
    Callers commit, then call geocode_later."""
    c = Customer(**data.model_dump(exclude={"owner_id"}), owner_id=owner_id)
    if c.city:
        cached = lookup_cached_city(db, c.city, c.state)
        if cached:
            c.lat, c.lng = cached
    db.add(c)
    return c


def geocode_later(c: Customer, background_tasks: BackgroundTasks):
    if c.city and c.lat is None:  # not cached — resolve it in the background, doesn't block the response
        background_tasks.add_task(geocode_and_cache_background, c.id, c.city, c.state)


@router.post("", response_model=CustomerOut, status_code=201)
def create(data: CustomerIn, background_tasks: BackgroundTasks,
           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Sellers can only ever own the customers they register; only admins may assign a seller.
    c = add_customer(db, data, data.owner_id if user.role == "admin" else user.id)
    db.commit()
    db.refresh(c)
    geocode_later(c, background_tasks)
    return c
```

- [ ] **Step 4: Add `DiscardIn`** — in `backend/app/schemas.py`, after `CustomerOut`:

```python
class DiscardIn(BaseModel):
    reason: Literal["closed", "not_target", "competitor", "other"]  # models.DISCARD_REASONS
```

- [ ] **Step 5: Add the routes** — in `backend/app/routers/leads.py`, replace the imports with:

```python
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..leads import city_owners, lead_out, lead_owner, ranked_leads, visible_lead
from ..models import Contact, Lead, User
from ..schemas import CustomerIn, CustomerOut, DiscardIn
from ..security import get_current_user
from .customers import add_customer, geocode_later

ALREADY_HANDLED = "Este lead já foi tratado."
```

and add at the end:

```python
@router.post("/{lid}/convert", response_model=CustomerOut, status_code=201)
def convert(lid: int, data: CustomerIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Lead -> customer in one transaction; the lead's contacts move to the customer."""
    lead = visible_lead(db, user, lid)
    if user.role == "admin":
        owner = lead_owner(city_owners(db), lead)
        owner_id = data.owner_id or (owner.id if owner else None)
    else:
        owner_id = user.id
    c = add_customer(db, data, owner_id)
    db.flush()
    # conditional UPDATE: a double click converts once, the second request gets 409
    done = db.query(Lead).filter(Lead.id == lid, Lead.status == "new") \
             .update({"status": "converted", "customer_id": c.id}, synchronize_session=False)
    if not done:
        db.rollback()
        raise HTTPException(409, ALREADY_HANDLED)
    db.query(Contact).filter(Contact.lead_id == lid) \
      .update({"customer_id": c.id, "lead_id": None}, synchronize_session=False)
    db.commit()
    db.refresh(c)
    geocode_later(c, background_tasks)
    return c


@router.post("/{lid}/discard", status_code=204)
def discard(lid: int, data: DiscardIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    visible_lead(db, user, lid)
    done = db.query(Lead).filter(Lead.id == lid, Lead.status == "new") \
             .update({"status": "discarded", "discard_reason": data.reason}, synchronize_session=False)
    if not done:
        raise HTTPException(409, ALREADY_HANDLED)
    db.commit()
    return Response(status_code=204)
```

- [ ] **Step 6: Run the tests**

Run: `python test_leads.py && python test_permissions.py`
Expected: `test_leads OK` and the permissions OK line (customer creation still behaves the same).

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/customers.py backend/app/routers/leads.py backend/app/schemas.py backend/test_leads.py
git commit -m "Leads: convert to customer and discard"
```

---

### Task 6: Contacts, follow-ups due, Painel alert and customer delete cleanup

**Files:**
- Modify: `backend/app/leads.py` (`due_follow_ups`)
- Create: `backend/app/routers/contacts.py`
- Modify: `backend/app/schemas.py` (`ContactIn`)
- Modify: `backend/app/main.py` (include `contacts`)
- Modify: `backend/app/routers/dashboard.py` (`alerts.follow_ups_due`)
- Modify: `backend/app/routers/customers.py` (`delete`)
- Test: `backend/test_leads.py`

**Interfaces:**
- Consumes: `visible_lead`, `city_owners`, `lead_owner`, customers `_visible`.
- Produces:
  - `leads.due_follow_ups(db, user, today) -> list[dict]` with keys `contact_id, lead_id, customer_id, name, kind ("lead"|"customer"), phone, channel, notes, next_action_date, last_contact_at`, sorted by `next_action_date`, then name.
  - `GET /api/contacts?lead_id=` or `?customer_id=` → `[{id, user_name, channel, notes, next_action_date, created_at}]` newest first (exactly one param, else 422).
  - `POST /api/contacts` body `{lead_id?, customer_id?, channel, notes?, next_action_date?}` → 201 same item shape.
  - `GET /api/contacts/due` → `due_follow_ups(...)`.
  - Dashboard `alerts.follow_ups_due: int`.

- [ ] **Step 1: Write the failing test** — add above `# ---- run ----`:

```python
def check_contacts(ctx):
    c, admin = ctx["c"], ctx["admin"]
    jl = add_lead("20000000000101", "Loja Contato", phone="47 99999-0000")
    yesterday, tomorrow = (TODAY - timedelta(days=1)).isoformat(), (TODAY + timedelta(days=1)).isoformat()

    def contact(h, **body):
        return c.post("/api/contacts", headers=h, json={"channel": "call", **body})

    assert contact(ctx["a"], lead_id=jl, customer_id=1).status_code == 422  # exactly one target
    assert contact(ctx["a"]).status_code == 422
    assert contact(ctx["a"], lead_id=jl, channel="fax").status_code == 422
    assert contact(ctx["b"], lead_id=jl).status_code == 404  # not Bruno's region
    r = contact(ctx["a"], lead_id=jl, notes="Pediu catálogo", next_action_date=yesterday)
    assert r.status_code == 201 and r.json()["user_name"] == "Ana", r.text

    due = c.get("/api/contacts/due", headers=ctx["a"]).json()
    assert [(d["name"], d["kind"], d["notes"]) for d in due] == [("Loja Contato", "lead", "Pediu catálogo")], due
    assert c.get("/api/contacts/due", headers=admin).json() == []  # reminders belong to who set them
    assert c.get("/api/dashboard", headers=ctx["a"]).json()["alerts"]["follow_ups_due"] == 1

    # the latest contact replaces the reminder: future date -> not due; no date -> no reminder
    contact(ctx["a"], lead_id=jl, next_action_date=tomorrow)
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []
    contact(ctx["a"], lead_id=jl, next_action_date=yesterday)
    assert len(c.get("/api/contacts/due", headers=ctx["a"]).json()) == 1
    contact(ctx["a"], lead_id=jl)
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []

    # history: newest first, visible to whoever sees the lead (admin too), not to Bruno
    hist = c.get("/api/contacts", headers=admin, params={"lead_id": jl}).json()
    assert len(hist) == 4 and hist[0]["next_action_date"] is None
    assert c.get("/api/contacts", headers=ctx["b"], params={"lead_id": jl}).status_code == 404
    assert c.get("/api/contacts", headers=ctx["a"]).status_code == 422

    # discarded lead leaves the due list
    contact(ctx["a"], lead_id=jl, next_action_date=yesterday)
    c.post(f"/api/leads/{jl}/discard", headers=ctx["a"], json={"reason": "other"})
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []

    # converting moves the history to the customer; customer contacts work the same way
    jl2 = add_lead("20000000000102", "Loja Converte")
    contact(ctx["a"], lead_id=jl2, next_action_date=yesterday)
    cust = c.post(f"/api/leads/{jl2}/convert", headers=ctx["a"], json={"name": "Loja Converte", "document": "20000000000102"}).json()
    hist = c.get("/api/contacts", headers=ctx["a"], params={"customer_id": cust["id"]}).json()
    assert len(hist) == 1
    due = c.get("/api/contacts/due", headers=ctx["a"]).json()
    assert [(d["name"], d["kind"]) for d in due] == [("Loja Converte", "customer")], due
    assert c.get("/api/contacts", headers=ctx["b"], params={"customer_id": cust["id"]}).status_code == 404

    # deleting the customer removes its contacts and unlinks the converted lead
    assert c.delete(f"/api/customers/{cust['id']}", headers=ctx["a"]).status_code == 204
    with SessionLocal() as db:
        assert db.query(Contact).filter(Contact.customer_id == cust["id"]).count() == 0
        assert db.get(Lead, jl2).customer_id is None
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []
```

and at the end of the `with` block: `    check_contacts(ctx)`

- [ ] **Step 2: Run to verify it fails**

Run: `python test_leads.py`
Expected: AssertionError (404/405 from `/api/contacts`).

- [ ] **Step 3: Add `due_follow_ups`** — append to `backend/app/leads.py` (add `Contact` to the models import):

```python
def due_follow_ups(db: Session, user: User, today: date) -> list[dict]:
    """The user's pending follow-ups: for each lead/customer, its LATEST contact, when that contact
    was registered by this user and its next_action_date is today or earlier. Discarded/converted
    leads and anything the user can no longer see are left out."""
    latest: dict[tuple, Contact] = {}
    # ponytail: every contact in Python; a "latest per target" subquery if this grows past ~50k contacts
    for ct in db.query(Contact).order_by(Contact.id):
        latest[(ct.lead_id, ct.customer_id)] = ct
    owners = city_owners(db) if user.role != "admin" else {}
    rows = []
    for ct in latest.values():
        if ct.user_id != user.id or ct.next_action_date is None or ct.next_action_date > today:
            continue
        if ct.lead_id:
            target, kind = ct.lead, "lead"
            if target.status != "new":
                continue
            if user.role != "admin" and getattr(lead_owner(owners, target), "id", None) != user.id:
                continue
        else:
            target, kind = ct.customer, "customer"
            if user.role != "admin" and target.owner_id != user.id:
                continue
        rows.append({"contact_id": ct.id, "lead_id": ct.lead_id, "customer_id": ct.customer_id,
                     "name": target.name, "kind": kind, "phone": target.phone, "channel": ct.channel,
                     "notes": ct.notes, "next_action_date": ct.next_action_date, "last_contact_at": ct.created_at})
    return sorted(rows, key=lambda r: (r["next_action_date"], r["name"]))
```

Models import line in `leads.py` becomes:

```python
from .models import SALE_STATUSES, Contact, Customer, Lead, Order, SellerCity, User, customer_status
```

- [ ] **Step 4: Add `ContactIn`** — in `backend/app/schemas.py`, after `DiscardIn` (add `model_validator` to the pydantic import):

```python
class ContactIn(BaseModel):
    lead_id: int | None = None
    customer_id: int | None = None
    channel: Literal["whatsapp", "call", "visit", "email"]  # models.CONTACT_CHANNELS
    notes: str | None = Field(default=None, max_length=2000)
    next_action_date: _dt.date | None = None

    @model_validator(mode="after")
    def _one_target(self):
        if (self.lead_id is None) == (self.customer_id is None):
            raise ValueError("Informe o lead ou o cliente do contato.")
        return self
```

pydantic import line becomes:

```python
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator
```

- [ ] **Step 5: Create `backend/app/routers/contacts.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import clock
from ..database import get_db
from ..leads import due_follow_ups, visible_lead
from ..models import Contact, User
from ..schemas import ContactIn
from ..security import get_current_user
from .customers import _visible as visible_customer

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _out(ct: Contact) -> dict:
    return {"id": ct.id, "user_name": ct.user.name, "channel": ct.channel, "notes": ct.notes,
            "next_action_date": ct.next_action_date, "created_at": ct.created_at}


def _check_target(db: Session, user: User, lead_id: int | None, customer_id: int | None):
    """Whoever sees the lead/customer sees and adds to its whole history."""
    if (lead_id is None) == (customer_id is None):
        raise HTTPException(422, "Informe o lead ou o cliente do contato.")
    if lead_id is not None:
        visible_lead(db, user, lead_id)
    else:
        visible_customer(customer_id, db, user)


@router.get("/due")
def due(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return due_follow_ups(db, user, clock.today_br())


@router.get("")
def history(lead_id: int | None = None, customer_id: int | None = None,
            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_target(db, user, lead_id, customer_id)
    q = db.query(Contact).filter(Contact.lead_id == lead_id if lead_id is not None else Contact.customer_id == customer_id)
    return [_out(ct) for ct in q.order_by(Contact.id.desc())]


@router.post("", status_code=201)
def create(data: ContactIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _check_target(db, user, data.lead_id, data.customer_id)
    ct = Contact(user_id=user.id, **data.model_dump())
    db.add(ct)
    db.commit()
    db.refresh(ct)
    return _out(ct)
```

In `backend/app/main.py`, add `contacts` to the routers import and to the `for r in (...)` tuple (after `leads`).

- [ ] **Step 6: Painel alert** — in `backend/app/routers/dashboard.py`, add `from ..leads import due_follow_ups` to the imports, and in the `"alerts"` dict add:

```python
            "follow_ups_due": len(due_follow_ups(db, user, today)),
```

- [ ] **Step 7: Customer delete cleanup** — in `backend/app/routers/customers.py`, change the models import to include `Contact, Lead`, and replace `delete` with:

```python
@router.delete("/{cid}", status_code=204)
def delete(cid: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = _visible(cid, db, user)
    if db.query(Order).filter(Order.customer_id == cid).first():
        raise HTTPException(400, "This customer has orders and cannot be deleted.")
    # no FK cascades on SQLite here: clean up dependents by hand
    db.query(Contact).filter(Contact.customer_id == cid).delete(synchronize_session=False)
    db.query(Lead).filter(Lead.customer_id == cid).update({"customer_id": None}, synchronize_session=False)
    db.delete(c)
    db.commit()
```

- [ ] **Step 8: Run all backend suites**

Run: `python test_leads.py && python test_dashboard.py && python test_permissions.py && python test_finance.py && python test_price_tables.py && python test_security.py`
Expected: every script prints its OK line. If `test_dashboard.py` compares the whole `alerts` dict, add `"follow_ups_due": 0` to its expected value.

- [ ] **Step 9: Commit**

```bash
git add backend/app/leads.py backend/app/routers/contacts.py backend/app/schemas.py backend/app/main.py \
        backend/app/routers/dashboard.py backend/app/routers/customers.py backend/test_leads.py backend/test_dashboard.py
git commit -m "Mini-CRM: contacts, follow-ups due and Painel alert"
```
