from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import AppSettingsIn, AppSettingsOut
from ..security import get_current_user, require_admin
from ..settings_store import get_app_settings

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=AppSettingsOut, dependencies=[Depends(get_current_user)])
def get_settings(db: Session = Depends(get_db)):
    return get_app_settings(db)


@router.put("", response_model=AppSettingsOut, dependencies=[Depends(require_admin)])
def update_settings(data: AppSettingsIn, db: Session = Depends(get_db)):
    s = get_app_settings(db)
    s.allow_price_override = data.allow_price_override
    s.max_discount_percent = data.max_discount_percent
    db.commit()
    db.refresh(s)
    return s
