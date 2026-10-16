"""Accounts receivable/payable rules. No FastAPI here, so they're easy to test."""
import calendar
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .models import FinancialEntry

QUINZENAL_DAYS = list(range(15, 151, 15))  # "Quinzenal" = 10 installments, every 15 days


def installment_days(terms: str | None) -> list[int]:
    """Days after delivery for each installment of an order's payment terms."""
    t = (terms or "").strip()
    if t.lower() == "quinzenal":
        return QUINZENAL_DAYS
    parts = [p.strip() for p in t.split("/")]
    if all(p.isdigit() for p in parts):
        return [int(p) for p in parts]
    return [0]  # "À vista" and anything unknown: one installment, due on delivery


def split_cents(total_cents: int, n: int) -> list[int]:
    """Equal split; the leftover cents go to the first installment."""
    base, rest = divmod(total_cents, n)
    return [base + rest] + [base] * (n - 1)


def add_months(d: date, n: int) -> date:
    """Same day n months later, capped at the month's last day (31/01 + 1 → 28/02)."""
    m = d.month - 1 + n
    year, month = d.year + m // 12, m % 12 + 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def to_decimal(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), ROUND_HALF_UP)


def to_cents(v) -> int:
    return int(to_decimal(v) * 100)


def entry_status(e: FinancialEntry, today: date) -> str:
    if e.paid_at:
        return "paid"
    return "overdue" if e.due_date < today else "open"
