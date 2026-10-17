from datetime import date, datetime, timedelta, timezone

# Brazil dropped daylight saving time in 2019, so a fixed UTC-3 offset is exact and
# needs no tz database (Windows has none without the tzdata package).
BRT = timezone(timedelta(hours=-3))


def today_br() -> date:
    """'Today' for business rules (late orders, customer status, default periods)."""
    return datetime.now(BRT).date()


GOAL_YEAR_START_MONTH = 10  # goals run October -> September: the 2027 goal covers 2026-10-01 .. 2027-09-30


def goal_year_start(today: date) -> date:
    """First day of the goal year `today` falls in."""
    year = today.year if today.month >= GOAL_YEAR_START_MONTH else today.year - 1
    return date(year, GOAL_YEAR_START_MONTH, 1)
