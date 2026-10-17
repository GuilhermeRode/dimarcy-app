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


def check_settings(ctx):
    c, admin = ctx["c"], ctx["admin"]
    base = {"allow_price_override": False, "max_discount_percent": 0, "retail_markup_percent": 50, "annual_goal": None}
    r = c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": "4781-4/00, 4642-7/01,4781400"})
    assert r.status_code == 200, r.text
    assert r.json()["lead_cnaes"] == "4781400,4642701"
    assert r.json()["last_lead_import_month"] is None
    assert c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": "123"}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": " , "}).status_code == 422
    r = c.put("/api/settings", headers=admin, json=base)  # omitted: unchanged
    assert r.json()["lead_cnaes"] == "4781400,4642701"
    assert "lead_cnaes" not in c.get("/api/settings", headers=ctx["a"]).json()  # sellers don't see it
    c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": "4781400"})


def check_regions(ctx):
    c, admin, a_id, b_id = ctx["c"], ctx["admin"], ctx["a_id"], ctx["b_id"]
    with SessionLocal() as db:  # leftovers from check_models
        db.query(SellerCity).delete()
        db.query(Lead).delete()
        db.commit()
    r = c.put(f"/api/users/{a_id}/cities", headers=admin, json=[
        {"city": "Jaraguá do Sul", "state": "sc"}, {"city": " jaragua  do sul ", "state": "SC"}])
    assert r.status_code == 200, r.text
    assert r.json() == [{"city": "Jaraguá do Sul", "state": "SC"}]  # same key twice -> once
    r = c.put(f"/api/users/{b_id}/cities", headers=admin, json=[{"city": "JARAGUA DO SUL", "state": "SC"}])
    assert r.status_code == 409 and r.json()["detail"] == "JARAGUA DO SUL já é da região de Ana.", r.text
    assert c.put(f"/api/users/{b_id}/cities", headers=admin, json=[{"city": "Corupá", "state": "SC"}]).status_code == 200
    assert c.get(f"/api/users/{b_id}/cities", headers=admin).json() == [{"city": "Corupá", "state": "SC"}]
    assert c.put("/api/users/9999/cities", headers=admin, json=[]).status_code == 404
    assert c.get(f"/api/users/{a_id}/cities", headers=ctx["a"]).status_code == 403  # admin only
    assert c.put(f"/api/users/{a_id}/cities", headers=admin, json=[{"city": "", "state": "SC"}]).status_code == 422

    # suggestions: Ana's customers' cities, marking the ones another seller has
    c.post("/api/customers", headers=ctx["a"], json={"name": "Loja Corupá", "document": "1", "city": "Corupa", "state": "SC"})
    c.post("/api/customers", headers=ctx["a"], json={"name": "Loja Guará", "document": "2", "city": "Guaramirim", "state": "SC"})
    sug = c.get(f"/api/users/{a_id}/cities/suggestions", headers=admin).json()
    assert {"city": "Corupa", "state": "SC", "taken_by": "Bruno"} in sug, sug
    assert {"city": "Guaramirim", "state": "SC", "taken_by": None} in sug, sug

    add_lead("11111111000111", "Lead Blumenau", city="Blumenau")
    opts = c.get("/api/users/cities/options", headers=admin).json()
    assert {"city": "Blumenau", "state": "SC"} in opts and {"city": "Guaramirim", "state": "SC"} in opts, opts
    with SessionLocal() as db:
        db.query(Lead).delete()
        db.commit()


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
    check_settings(ctx)
    check_regions(ctx)

print("test_leads OK")
