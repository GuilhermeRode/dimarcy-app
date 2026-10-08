from datetime import date, datetime, timedelta, timezone

# Brazil dropped daylight saving time in 2019, so a fixed UTC-3 offset is exact and
# needs no tz database (Windows has none without the tzdata package).
BRT = timezone(timedelta(hours=-3))


def today_br() -> date:
    """'Today' for business rules (late orders, customer status, default periods)."""
    return datetime.now(BRT).date()
