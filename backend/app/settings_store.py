from sqlalchemy.orm import Session

from .models import AppSettings


def get_app_settings(db: Session) -> AppSettings:
    """Always returns the single settings row, creating it with defaults on first call."""
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s
