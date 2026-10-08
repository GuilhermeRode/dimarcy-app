from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from .routers import auth, colors, customers, dashboard, orders, products, settings as settings_router, users
from .security import hash_password
from .settings_store import get_app_settings

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    _ensure_columns("users", {"reset_token_hash": "VARCHAR(64)", "reset_token_expires_at": "TIMESTAMP",
                              "monthly_goal": "NUMERIC(12,2)"})
    _ensure_columns("app_settings", {"monthly_goal": "NUMERIC(12,2) DEFAULT 0"})
    with SessionLocal() as db:
        if not db.query(User).first():  # first run: create the administrator
            db.add(User(name="Administrador", email=settings.admin_email,
                        password_hash=hash_password(settings.admin_password), role="admin"))
            db.commit()
        get_app_settings(db)  # first run: create the single settings row with its defaults
    yield


docs = {} if settings.enable_docs else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="Di Marcy — Pedidos", lifespan=lifespan, **docs)

MAX_BODY_BYTES = 6 * 1024 * 1024  # largest legit request is a 5 MB image upload


class BodySizeLimit:
    """Rejects request bodies over MAX_BODY_BYTES with 413, counting bytes as they
    arrive — so it also catches chunked uploads that send no Content-Length."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        received, too_large = 0, False

        async def limited_receive():
            nonlocal received, too_large
            message = await receive()
            received += len(message.get("body", b""))
            if received > MAX_BODY_BYTES:
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

for r in (auth, users, customers, colors, products, orders, dashboard, settings_router):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}
