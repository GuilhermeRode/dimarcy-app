"""Dashboard / customers-overview self-check. Run from backend/:  python test_dashboard.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app import clock  # noqa: E402
from app.main import app  # noqa: E402
from app.models import customer_status  # noqa: E402

TODAY = date(2026, 10, 7)
clock.today_br = lambda: TODAY

# ---- customer_status boundaries ----
assert customer_status(None, TODAY) == "never_ordered"
assert customer_status(TODAY, TODAY) == "active"
assert customer_status(TODAY - timedelta(days=60), TODAY) == "active"
assert customer_status(TODAY - timedelta(days=61), TODAY) == "at_risk"
assert customer_status(TODAY - timedelta(days=150), TODAY) == "at_risk"
assert customer_status(TODAY - timedelta(days=151), TODAY) == "inactive"


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")

    # ---- goals: company goal is admin-only, validated ----
    r = c.put("/api/settings", headers=admin, json={
        "allow_price_override": False, "max_discount_percent": 10, "monthly_goal": 60800})
    assert r.status_code == 200 and r.json()["monthly_goal"] == 60800, r.text
    assert c.put("/api/settings", headers=admin, json={
        "allow_price_override": False, "max_discount_percent": 10, "monthly_goal": -1}).status_code == 422

    def new_user(name, email, goal=None, active=True):
        r = c.post("/api/users", headers=admin, json={
            "name": name, "email": email, "password": "seller-pass-123", "role": "seller",
            "active": active, "monthly_goal": goal})
        assert r.status_code == 201, r.text
        return r.json()

    a = new_user("Ana Vendas", "a@test.com", goal=30400)
    assert a["monthly_goal"] == 30400
    b = new_user("Bruno Vendas", "b@test.com")
    assert b["monthly_goal"] is None
    seller_a = login(c, "a@test.com", "seller-pass-123")
    seller_b = login(c, "b@test.com", "seller-pass-123")

    s = c.get("/api/settings", headers=seller_a).json()
    assert "monthly_goal" not in s, s  # sellers never see the company goal
    assert c.get("/api/settings", headers=admin).json()["monthly_goal"] == 60800

    # PUT keeps the goal when the client sends it, clears it with null
    r = c.put(f"/api/users/{b['id']}", headers=admin, json={**b, "password": None, "monthly_goal": 1000})
    assert r.json()["monthly_goal"] == 1000
    r = c.put(f"/api/users/{b['id']}", headers=admin, json={**b, "password": None, "monthly_goal": None})
    assert r.json()["monthly_goal"] is None

    # TASK2_TESTS

print("dashboard checks OK")
