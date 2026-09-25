from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import Base, SessionLocal, engine
from .models import User
from .routers import auth, colors, customers, dashboard, orders, products, settings as settings_router, users
from .security import hash_password
from .settings_store import get_app_settings

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if not db.query(User).first():  # first run: create the administrator
            db.add(User(name="Administrador", email=settings.admin_email,
                        password_hash=hash_password(settings.admin_password), role="admin"))
            db.commit()
        get_app_settings(db)  # first run: create the single settings row with its defaults
    yield


app = FastAPI(title="Di Marcy — Pedidos", lifespan=lifespan)
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
