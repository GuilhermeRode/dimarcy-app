import subprocess
import sys
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import lead_import
from ..database import get_db
from ..models import AppSettings, User
from ..schemas import AppSettingsAdminOut, AppSettingsIn, AppSettingsOut
from ..security import get_current_user, require_admin
from ..settings_store import allowed_price_tables, get_app_settings

router = APIRouter(prefix="/settings", tags=["settings"])
BACKEND_DIR = Path(__file__).resolve().parents[2]
IMPORT_STALE = lead_import.IMPORT_STALE


def _spawn_import() -> None:
    """Detached importer; its own main() records started_at/error in the settings."""
    flags = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
             if sys.platform == "win32" else {"start_new_session": True})
    with open(BACKEND_DIR / "lead_import.log", "ab") as log:
        proc = subprocess.Popen([sys.executable, "-m", "app.lead_import", "--force"], cwd=BACKEND_DIR,
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log, **flags)
    threading.Thread(target=proc.wait, daemon=True).start()  # reap the child (no zombie)


@router.get("")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # The company goal is admin-only; sellers read this endpoint from the order form.
    schema = AppSettingsAdminOut if user.role == "admin" else AppSettingsOut
    # price_tables: which tables this user may sell with (read live, not from the cached login user)
    return {**schema.model_validate(get_app_settings(db)).model_dump(), "price_tables": allowed_price_tables(user)}


@router.put("", response_model=AppSettingsAdminOut, dependencies=[Depends(require_admin)])
def update_settings(data: AppSettingsIn, db: Session = Depends(get_db)):
    s = get_app_settings(db)
    s.allow_price_override = data.allow_price_override
    s.max_discount_percent = data.max_discount_percent
    s.retail_markup_percent = data.retail_markup_percent
    s.annual_goal = data.annual_goal
    if data.lead_cnaes is not None:
        s.lead_cnaes = data.lead_cnaes
    for field in ("lead_sizes", "lead_exclude_mei", "lead_head_office_only", "lead_require_contact", "lead_min_age_months",
                  "lead_states", "lead_area_codes", "lead_weekly_release"):
        value = getattr(data, field)
        if value is not None:
            setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s


CATALOG_DIR = BACKEND_DIR / "uploads" / "catalog"
CATALOG_MAX_BYTES = 40 * 1024 * 1024


def _delete_catalog(url: str | None) -> None:
    if url and url.startswith("/uploads/catalog/"):
        (CATALOG_DIR / Path(url).name).unlink(missing_ok=True)


@router.post("/catalog", response_model=AppSettingsAdminOut, dependencies=[Depends(require_admin)])
def upload_catalog(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = file.file.read(CATALOG_MAX_BYTES + 1)
    if len(content) > CATALOG_MAX_BYTES:
        raise HTTPException(400, "Arquivo grande demais (máximo 40 MB).")
    if not content.startswith(b"%PDF"):  # by content, not by name: only a PDF is served from /uploads
        raise HTTPException(400, "Envie o catálogo em PDF.")
    CATALOG_DIR.mkdir(parents=True, exist_ok=True)
    name = f"catalogo-dimarcy-{uuid.uuid4().hex[:8]}.pdf"  # new name per upload: no stale copy in caches
    (CATALOG_DIR / name).write_bytes(content)
    s = get_app_settings(db)
    old, s.catalog_url = s.catalog_url, f"/uploads/catalog/{name}"
    db.commit()
    db.refresh(s)
    _delete_catalog(old)
    return s


@router.delete("/catalog", response_model=AppSettingsAdminOut, dependencies=[Depends(require_admin)])
def delete_catalog(db: Session = Depends(get_db)):
    s = get_app_settings(db)
    old, s.catalog_url = s.catalog_url, None
    db.commit()
    db.refresh(s)
    _delete_catalog(old)
    return s


@router.post("/lead-import", status_code=202, dependencies=[Depends(require_admin)])
def start_lead_import(db: Session = Depends(get_db)):
    now = lead_import.utcnow()
    s = get_app_settings(db)
    free = [AppSettings.lead_import_started_at.is_(None), AppSettings.lead_import_started_at < now - IMPORT_STALE]
    if s.lead_import_pid is not None and not lead_import.pid_alive(s.lead_import_pid):
        free.append(AppSettings.lead_import_pid == s.lead_import_pid)  # its process died (e.g. server restart)
    # atomic claim: a second click gets 409 even before the child starts
    won = (db.query(AppSettings)
           .filter(AppSettings.id == s.id, or_(*free))
           .update({"lead_import_started_at": now, "lead_import_pid": None}, synchronize_session=False))
    db.commit()
    if not won:
        raise HTTPException(409, "Já existe uma importação em andamento.")
    try:
        _spawn_import()
    except Exception:
        db.query(AppSettings).filter(AppSettings.id == s.id).update(
            {"lead_import_started_at": None, "lead_import_pid": None}, synchronize_session=False)
        db.commit()
        raise HTTPException(500, "Não foi possível iniciar a importação.")
    return {"started": True}
