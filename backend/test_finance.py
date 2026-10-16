"""Accounts receivable/payable self-check. Run from backend/:  python test_finance.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta
from decimal import Decimal

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app import clock, finance  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import FinancialEntry  # noqa: E402

TODAY = date(2026, 10, 15)
clock.today_br = lambda: TODAY

# ---- pure rules ----
assert finance.installment_days("À vista") == [0]
assert finance.installment_days("30/60") == [30, 60]
assert finance.installment_days("30/60/90/120/150") == [30, 60, 90, 120, 150]
assert finance.installment_days("28/56") == [28, 56]
assert finance.installment_days("Quinzenal") == [15, 30, 45, 60, 75, 90, 105, 120, 135, 150]
assert finance.installment_days("combinar") == [0] and finance.installment_days(None) == [0]

assert finance.split_cents(10000, 3) == [3334, 3333, 3333]
assert finance.split_cents(5, 10) == [5] + [0] * 9  # callers drop the zero ones
assert sum(finance.split_cents(123457, 7)) == 123457

assert finance.add_months(date(2027, 1, 31), 0) == date(2027, 1, 31)
assert finance.add_months(date(2027, 1, 31), 1) == date(2027, 2, 28)
assert finance.add_months(date(2027, 1, 31), 2) == date(2027, 3, 31)  # from the first date, no drift
assert finance.add_months(date(2027, 11, 30), 3) == date(2028, 2, 29)  # leap year
assert finance.add_months(date(2026, 12, 10), 1) == date(2027, 1, 10)

assert finance.to_cents(100.1) == 10010 and finance.to_cents(Decimal("33.34")) == 3334
assert finance.to_decimal(0.1 + 0.2) == Decimal("0.30")

e = FinancialEntry(due_date=TODAY, paid_at=None)
assert finance.entry_status(e, TODAY) == "open"
assert finance.entry_status(e, TODAY + timedelta(days=1)) == "overdue"
e.paid_at = TODAY
assert finance.entry_status(e, TODAY + timedelta(days=1)) == "paid"

print("finance checks OK")
