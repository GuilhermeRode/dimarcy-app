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
