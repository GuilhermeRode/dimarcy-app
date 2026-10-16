from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from .models import AppSettings, User


def get_app_settings(db: Session) -> AppSettings:
    """Always returns the single settings row, creating it with defaults on first call."""
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def allowed_price_tables(user: User) -> list[str]:
    """Order price tables a user may sell with; the first one is their default."""
    if user.role == "admin":
        return ["wholesale", "retail"]
    return {"retail": ["retail"], "both": ["wholesale", "retail"]}.get(user.price_table, ["wholesale"])


def retail_price(price: float, markup_percent: float) -> float:
    # Decimal, half-up: matches the order form's integer-cents math (float round() would differ on half cents)
    cents = Decimal(str(price)) * 100 * (100 + Decimal(str(markup_percent))) / 100
    return float(cents.quantize(Decimal(1), ROUND_HALF_UP) / 100)
