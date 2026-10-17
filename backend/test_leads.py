"""Prospecting + mini-CRM self-check: regions, leads, contacts. Run from backend/:  python test_leads.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app import clock  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.leads import normalize_cnpj  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppSettings, Contact, Customer, Lead, SellerCity, User  # noqa: E402
from app.sales import _city_key  # noqa: E402

TODAY = date(2026, 10, 16)
clock.today_br = lambda: TODAY


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def add_lead(cnpj, name, city="Jaraguá do Sul", state="SC", **extra):
    with SessionLocal() as db:
        lead = Lead(cnpj=cnpj, name=name, city=city, state=state, city_key=_city_key(city),
                    seen_at=TODAY, **extra)
        db.add(lead)
        db.commit()
        return lead.id


def check_models(ctx):
    assert normalize_cnpj("12.ABC.345/0001-99") == "12ABC345000199"
    assert normalize_cnpj(None) == ""
    with SessionLocal() as db:
        uid = ctx["a_id"]
        db.add(SellerCity(user_id=uid, city="Corupá", state="SC", city_key=_city_key("Corupá")))
        db.add(SellerCity(user_id=uid, city="corupa", state="SC", city_key=_city_key("corupa")))
        try:
            db.commit()
            raise AssertionError("same city twice must be refused")
        except IntegrityError:
            db.rollback()
        db.add(Contact(user_id=uid, channel="call"))  # neither lead nor customer
        try:
            db.commit()
            raise AssertionError("a contact needs exactly one target")
        except IntegrityError:
            db.rollback()
        lid = Lead(cnpj="00000000000191", name="X", city="Corupá", state="SC", city_key="corupa", seen_at=TODAY)
        db.add(lid)
        db.flush()
        db.add(Contact(user_id=uid, channel="call", lead_id=lid.id, customer_id=1))  # both
        try:
            db.commit()
            raise AssertionError("a contact needs exactly one target")
        except IntegrityError:
            db.rollback()
        assert db.query(AppSettings).first().lead_cnaes == "4781400"


# ---- run ----
with TestClient(app) as c:
    ctx = {"c": c, "admin": login(c, "admin@test.com", "admin-pass-123")}
    for key, name in (("a", "Ana"), ("b", "Bruno")):
        r = c.post("/api/users", headers=ctx["admin"], json={
            "name": name, "email": f"{key}@t.com", "password": "seller-pass-123", "role": "seller"})
        assert r.status_code == 201, r.text
        ctx[key + "_id"] = r.json()["id"]
        ctx[key] = login(c, f"{key}@t.com", "seller-pass-123")
    check_models(ctx)

print("test_leads OK")
