from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text

from .config import settings
from .database import Base, SessionLocal, engine
from .br_format import extract_state_registration, format_document, format_phone, format_state_registration
from . import clock
from .lead_import import clear_interrupted
from .leads import refresh_scores
from .models import Contact, Customer, Lead, Product, User, size_key
from .routers.leads import NO_ANSWER
from .routers import auth, colors, contacts, customers, dashboard, finance, leads, orders, products, settings as settings_router, users
from .security import hash_password
from .settings_store import get_app_settings
from .uploads import backfill_thumbs

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


def _ensure_columns(table: str, columns: dict[str, str]):
    """create_all only creates missing TABLES, not missing columns on an existing one —
    there's no migration tool in this repo, so new columns get added here instead.
    `table` and the DDL are code constants, never user input."""
    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    with engine.begin() as conn:
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))


def _monthly_to_annual_goal(table: str):
    """Goals used to be monthly (monthly_goal); now they're annual. Once, when annual_goal is added to a
    database that still has monthly_goal, carry the old value over as 12 months' worth."""
    existing = {c["name"] for c in inspect(engine).get_columns(table)}
    if "annual_goal" in existing or "monthly_goal" not in existing:
        return
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN annual_goal NUMERIC(12,2)"))
        conn.execute(text(f"UPDATE {table} SET annual_goal = monthly_goal * 12"))


def _tidy_customers():
    """Customers imported/registered before the masks existed have bare digits ("12345678000190"), and the
    IE (inscrição estadual) used to be typed into the notes. Format the first and move the second into
    state_registration. Idempotent: rows already tidy are left alone."""
    with SessionLocal() as db:
        for c in db.query(Customer).all():
            c.document, c.phone = format_document(c.document), format_phone(c.phone)
            if not c.state_registration:
                ie, notes = extract_state_registration(c.notes)
                if ie:
                    c.state_registration, c.notes = ie, notes
            c.state_registration = format_state_registration(c.state_registration, c.state)
        db.commit()  # only the rows that actually changed are written


def _drop_lead_phones():
    """Lead phones came from the Receita and were mostly wrong (the accountant's, outdated); the import no
    longer brings them. Clear the old ones, keeping what an admin typed in (edited), then re-rank. Idempotent."""
    with SessionLocal() as db:
        changed = db.query(Lead).filter(Lead.phone.isnot(None), Lead.edited.is_(False))                     .update({"phone": None}, synchronize_session=False)
        db.commit()
        if changed:
            refresh_scores(db, clock.today_br())


def _contacted_leads():
    """Pending leads the admin already talked to (a contact other than "Não respondeu") go to Primeiro contato
    (contacted), the only status that can be released. Idempotent."""
    with SessionLocal() as db:
        talked = select(Contact.lead_id).where(Contact.lead_id.isnot(None), Contact.notes.is_distinct_from(NO_ANSWER))
        db.query(Lead).filter(Lead.status == "pending", Lead.id.in_(talked))           .update({"status": "contacted"}, synchronize_session=False)
        db.commit()


def _sort_product_sizes():
    """Sizes used to be saved in the order they were ticked ("GG,P,M"); store them in SIZE_ORDER ("P,M,GG").
    Idempotent: products already in order are left alone."""
    with SessionLocal() as db:
        for p in db.query(Product).all():
            p.sizes = ",".join(sorted((t for t in (p.sizes or "").split(",") if t), key=size_key))
        db.commit()  # only the rows that actually changed are written


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    _monthly_to_annual_goal("users")
    _monthly_to_annual_goal("app_settings")
    _ensure_columns("users", {"reset_token_hash": "VARCHAR(64)", "reset_token_expires_at": "TIMESTAMP",
                              "annual_goal": "NUMERIC(12,2)", "price_table": "VARCHAR(10) DEFAULT 'wholesale'",
                              "quick_quantity": "BOOLEAN DEFAULT TRUE"})
    _ensure_columns("colors", {"hex2": "VARCHAR(7)"})
    _ensure_columns("customers", {"state_registration": "VARCHAR(30)"})
    _tidy_customers()
    _sort_product_sizes()
    _ensure_columns("orders", {"price_table": "VARCHAR(10) DEFAULT 'wholesale'",
                               "notify_customer": "BOOLEAN DEFAULT TRUE"})
    _ensure_columns("app_settings", {"annual_goal": "NUMERIC(12,2) DEFAULT 0",
                                     "retail_markup_percent": "NUMERIC(6,2) DEFAULT 50",
                                     "lead_cnaes": "VARCHAR(200) DEFAULT '4781400'",
                                     "last_lead_import_month": "VARCHAR(7)",
                                     "last_lead_import_scope": "VARCHAR(500)",
                                     "last_lead_import_at": "TIMESTAMP",
                                     "lead_sizes": "VARCHAR(20) DEFAULT '01,03'",
                                     "lead_exclude_mei": "BOOLEAN DEFAULT TRUE",
                                     "lead_head_office_only": "BOOLEAN DEFAULT TRUE",
                                     "lead_require_contact": "BOOLEAN DEFAULT TRUE",
                                     "lead_min_age_months": "INTEGER DEFAULT 6",
                                     "lead_states": "VARCHAR(30) DEFAULT 'PR,RS,SC'",
                                     "lead_area_codes": "VARCHAR(60) DEFAULT ''",
                                     "lead_weekly_release": "INTEGER DEFAULT 20",
                                     "leads_for_sellers": "BOOLEAN DEFAULT FALSE",
                                     "lead_import_started_at": "TIMESTAMP",
                                     "lead_import_pid": "INTEGER",
                                     "lead_import_error": "VARCHAR(300)",
                                     "catalog_url": "VARCHAR(200)"})
    if engine.dialect.name == "postgresql":  # the scope column was created as VARCHAR(300)
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE app_settings ALTER COLUMN last_lead_import_scope TYPE VARCHAR(500)"))
    _ensure_columns("leads", {"size": "VARCHAR(5) DEFAULT ''", "capital": "NUMERIC(14,2)", "in_debt": "BOOLEAN",
                              "released_at": "TIMESTAMP", "score": "INTEGER", "city_active": "INTEGER",
                              "edited": "BOOLEAN DEFAULT FALSE"})
    _drop_lead_phones()
    _contacted_leads()
    with SessionLocal() as db:
        if not db.query(User).first():  # first run: create the administrator
            db.add(User(name="Administrador", email=settings.admin_email,
                        password_hash=hash_password(settings.admin_password), role="admin"))
            db.commit()
        clear_interrupted(db)  # an import killed by the last restart
        get_app_settings(db)  # first run: create the single settings row with its defaults
    backfill_thumbs(products.UPLOAD_DIR)  # photos uploaded before thumbnails existed
    yield


docs = {} if settings.enable_docs else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Di Marcy — Pedidos", lifespan=lifespan, **docs)

MAX_BODY_BYTES = 6 * 1024 * 1024  # largest legit request is a 5 MB image upload...
LARGE_BODY_PATHS = {"/api/settings/catalog": 41 * 1024 * 1024}  # ...except the catalog PDF (40 MB)


class BodySizeLimit:
    """Rejects request bodies over MAX_BODY_BYTES with 413, counting bytes as they
    arrive — so it also catches chunked uploads that send no Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        received, too_large = 0, False
        limit = LARGE_BODY_PATHS.get(scope["path"], MAX_BODY_BYTES)

        async def limited_receive():
            nonlocal received, too_large
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                too_large = True
                raise RuntimeError("request body too large")
            return message

        async def guarded_send(message):
            if not too_large:  # drop whatever error response the app built; we answer 413 below
                await send(message)

        try:
            await self.app(scope, limited_receive, guarded_send)
        except RuntimeError:
            if not too_large:
                raise
        if too_large:
            await JSONResponse({"detail": "Requisição grande demais."}, 413)(scope, receive, send)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"  # browsers never run an upload as HTML/JS
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


app.add_middleware(BodySizeLimit)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

for r in (auth, users, customers, colors, products, orders, dashboard, finance, leads, contacts, settings_router):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
