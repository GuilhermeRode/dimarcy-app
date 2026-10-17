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


def check_listing(ctx):
    c, admin = ctx["c"], ctx["admin"]
    old, recent = TODAY - timedelta(days=2000), TODAY - timedelta(days=100)
    ids = {
        "j_phone_recent": add_lead("10000000000101", "Jota Moda", phone="47 3333-0001", opened_at=recent),
        "j_no_contact": add_lead("10000000000102", "Jaraguá Sem Fone", opened_at=recent),
        "j_phone_old": add_lead("10000000000103", "Antiga Modas", phone="47 3333-0003", opened_at=old),
        "corupa": add_lead("10000000000104", "Corupá Store", city="Corupá", phone="1", opened_at=recent),
        "blumenau": add_lead("10000000000105", "Blu Fashion", city="Blumenau", phone="1", opened_at=recent),
        "gone": add_lead("10000000000106", "Descartada", status="discarded"),
    }
    names = lambda r: [x["name"] for x in r.json()["items"]]  # noqa: E731

    r = c.get("/api/leads", headers=ctx["a"])
    assert r.status_code == 200, r.text
    assert names(r) == ["Jota Moda", "Antiga Modas", "Jaraguá Sem Fone"], names(r)  # contact, then new store
    assert r.json()["total"] == 3 and r.json()["cities"] == ["Jaraguá do Sul"]
    assert names(c.get("/api/leads", headers=ctx["b"])) == ["Corupá Store"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"limit": 1, "offset": 1})) == ["Antiga Modas"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"search": "antiga"})) == ["Antiga Modas"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"search": "0000000000103"})) == ["Antiga Modas"]

    r = c.get("/api/leads", headers=admin)
    assert r.json()["total"] == 5  # every new lead, discarded left out
    blu = next(x for x in r.json()["items"] if x["name"] == "Blu Fashion")
    assert blu["seller_id"] is None and blu["seller_name"] is None
    assert names(c.get("/api/leads", headers=admin, params={"seller_id": 0})) == ["Blu Fashion"]
    assert names(c.get("/api/leads", headers=admin, params={"seller_id": ctx["b_id"], "city": "corupa"})) == ["Corupá Store"]

    # detail: visible to the region's seller and the admin only
    assert c.get(f"/api/leads/{ids['corupa']}", headers=ctx["b"]).json()["seller_name"] == "Bruno"
    assert c.get(f"/api/leads/{ids['corupa']}", headers=ctx["a"]).status_code == 404
    assert c.get(f"/api/leads/{ids['blumenau']}", headers=ctx["a"]).status_code == 404
    assert c.get(f"/api/leads/{ids['blumenau']}", headers=admin).status_code == 200

    # a customer typed by hand with the lead's CNPJ (formatted) hides the lead at once
    c.post("/api/customers", headers=ctx["a"], json={"name": "Antiga", "document": "10.000.000/0001-03"})
    assert names(c.get("/api/leads", headers=ctx["a"])) == ["Jota Moda", "Jaraguá Sem Fone"]

    # moving Corupá to Ana moves its leads; a deactivated seller's cities show as "sem vendedor"
    c.put(f"/api/users/{ctx['b_id']}/cities", headers=admin, json=[])
    c.put(f"/api/users/{ctx['a_id']}/cities", headers=admin, json=[
        {"city": "Jaraguá do Sul", "state": "SC"}, {"city": "Corupá", "state": "SC"}])
    assert "Corupá Store" in names(c.get("/api/leads", headers=ctx["a"]))
    assert names(c.get("/api/leads", headers=ctx["b"])) == []
    c.put(f"/api/users/{ctx['a_id']}", headers=admin, json={"name": "Ana", "email": "a@t.com", "role": "seller", "active": False})
    assert sorted(names(c.get("/api/leads", headers=admin, params={"seller_id": 0}))) == \
        ["Blu Fashion", "Corupá Store", "Jaraguá Sem Fone", "Jota Moda"]
    c.put(f"/api/users/{ctx['a_id']}", headers=admin, json={"name": "Ana", "email": "a@t.com", "role": "seller", "active": True})
    c.put(f"/api/users/{ctx['a_id']}/cities", headers=admin, json=[{"city": "Jaraguá do Sul", "state": "SC"}])
    c.put(f"/api/users/{ctx['b_id']}/cities", headers=admin, json=[{"city": "Corupá", "state": "SC"}])
    ctx["leads"] = ids


def check_ranking_by_active_customers(ctx):
    """Same contact/new-store tier: the city with more active Di Marcy customers comes first."""
    c, admin = ctx["c"], ctx["admin"]
    # sorts after Corupá and Jota by name, so only the active-customers criterion can put it second
    add_lead("10000000000107", "Zz Blumenau", city="Blumenau", phone="1", opened_at=TODAY - timedelta(days=100))
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]
    product = c.post("/api/products", headers=admin, json={"reference": "R1", "description": "Blusão", "price": 100,
                                                           "color_ids": [color]}).json()["id"]
    cust = c.post("/api/customers", headers=admin, json={"name": "Cliente Blu", "document": "77", "city": "Blumenau",
                                                         "state": "SC", "owner_id": None}).json()["id"]
    r = c.post("/api/orders", headers=admin, json={
        "customer_id": cust, "date": TODAY.isoformat(), "delivery_date": TODAY.isoformat(), "status": "delivered", "payment_method": "PIX",
        "payment_terms": "À vista", "items": [{"product_id": product, "color_id": color, "size": "P", "quantity": 1}]})
    assert r.status_code == 201, r.text
    top = [x["name"] for x in c.get("/api/leads", headers=admin).json()["items"]][:3]
    assert top[:2] == ["Blu Fashion", "Zz Blumenau"], top


def check_convert(ctx):
    c, admin, ids = ctx["c"], ctx["admin"], ctx["leads"]
    body = {"name": "Jota Moda Ltda", "document": "10000000000101", "city": "Jaraguá do Sul", "state": "SC",
            "owner_id": ctx["b_id"]}  # a seller can't pick the owner: ignored
    assert c.post(f"/api/leads/{ids['corupa']}/convert", headers=ctx["a"], json=body).status_code == 404
    r = c.post(f"/api/leads/{ids['j_phone_recent']}/convert", headers=ctx["a"], json=body)
    assert r.status_code == 201, r.text
    assert r.json()["owner_id"] == ctx["a_id"]
    assert c.post(f"/api/leads/{ids['j_phone_recent']}/convert", headers=ctx["a"], json=body).status_code == 409
    with SessionLocal() as db:
        lead = db.get(Lead, ids["j_phone_recent"])
        assert lead.status == "converted" and lead.customer_id == r.json()["id"]
        assert db.query(Customer).filter_by(name="Jota Moda Ltda").count() == 1

    # admin without owner_id -> the region's seller; with owner_id -> that one
    r = c.post(f"/api/leads/{ids['corupa']}/convert", headers=admin, json={**body, "name": "Corupá", "owner_id": None})
    assert r.status_code == 201 and r.json()["owner_id"] == ctx["b_id"], r.text
    r = c.post(f"/api/leads/{ids['blumenau']}/convert", headers=admin, json={**body, "name": "Blu", "owner_id": ctx["a_id"]})
    assert r.status_code == 201 and r.json()["owner_id"] == ctx["a_id"], r.text

    # discard
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["b"], json={"reason": "closed"}).status_code == 404
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["a"], json={"reason": "x"}).status_code == 422
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["a"], json={"reason": "competitor"}).status_code == 204
    assert c.post(f"/api/leads/{ids['j_no_contact']}/discard", headers=ctx["a"], json={"reason": "closed"}).status_code == 409
    with SessionLocal() as db:
        assert db.get(Lead, ids["j_no_contact"]).discard_reason == "competitor"
    assert [x["name"] for x in c.get("/api/leads", headers=ctx["a"]).json()["items"]] == []


def check_contacts(ctx):
    c, admin = ctx["c"], ctx["admin"]
    jl = add_lead("20000000000101", "Loja Contato", phone="47 99999-0000")
    yesterday, tomorrow = (TODAY - timedelta(days=1)).isoformat(), (TODAY + timedelta(days=1)).isoformat()

    def contact(h, **body):
        return c.post("/api/contacts", headers=h, json={"channel": "call", **body})

    assert contact(ctx["a"], lead_id=jl, customer_id=1).status_code == 422  # exactly one target
    assert contact(ctx["a"]).status_code == 422
    assert contact(ctx["a"], lead_id=jl, channel="fax").status_code == 422
    assert contact(ctx["b"], lead_id=jl).status_code == 404  # not Bruno's region
    r = contact(ctx["a"], lead_id=jl, notes="Pediu catálogo", next_action_date=yesterday)
    assert r.status_code == 201 and r.json()["user_name"] == "Ana", r.text

    due = c.get("/api/contacts/due", headers=ctx["a"]).json()
    assert [(d["name"], d["kind"], d["notes"]) for d in due] == [("Loja Contato", "lead", "Pediu catálogo")], due
    assert c.get("/api/contacts/due", headers=admin).json() == []  # reminders belong to who set them
    assert c.get("/api/dashboard", headers=ctx["a"]).json()["alerts"]["follow_ups_due"] == 1

    # the latest contact replaces the reminder: future date -> not due; no date -> no reminder
    contact(ctx["a"], lead_id=jl, next_action_date=tomorrow)
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []
    contact(ctx["a"], lead_id=jl, next_action_date=yesterday)
    assert len(c.get("/api/contacts/due", headers=ctx["a"]).json()) == 1
    contact(ctx["a"], lead_id=jl)
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []

    # history: newest first, visible to whoever sees the lead (admin too), not to Bruno
    hist = c.get("/api/contacts", headers=admin, params={"lead_id": jl}).json()
    assert len(hist) == 4 and hist[0]["next_action_date"] is None
    assert c.get("/api/contacts", headers=ctx["b"], params={"lead_id": jl}).status_code == 404
    assert c.get("/api/contacts", headers=ctx["a"]).status_code == 422

    # discarded lead leaves the due list
    contact(ctx["a"], lead_id=jl, next_action_date=yesterday)
    c.post(f"/api/leads/{jl}/discard", headers=ctx["a"], json={"reason": "other"})
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []

    # converting moves the history to the customer; customer contacts work the same way
    jl2 = add_lead("20000000000102", "Loja Converte")
    contact(ctx["a"], lead_id=jl2, next_action_date=yesterday)
    cust = c.post(f"/api/leads/{jl2}/convert", headers=ctx["a"], json={"name": "Loja Converte", "document": "20000000000102"}).json()
    hist = c.get("/api/contacts", headers=ctx["a"], params={"customer_id": cust["id"]}).json()
    assert len(hist) == 1
    due = c.get("/api/contacts/due", headers=ctx["a"]).json()
    assert [(d["name"], d["kind"]) for d in due] == [("Loja Converte", "customer")], due
    assert c.get("/api/contacts", headers=ctx["b"], params={"customer_id": cust["id"]}).status_code == 404

    # deleting the customer removes its contacts and unlinks the converted lead
    assert c.delete(f"/api/customers/{cust['id']}", headers=ctx["a"]).status_code == 204
    with SessionLocal() as db:
        assert db.query(Contact).filter(Contact.customer_id == cust["id"]).count() == 0
        assert db.get(Lead, jl2).customer_id is None
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []


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
    check_listing(ctx)
    check_ranking_by_active_customers(ctx)
    check_convert(ctx)
    check_contacts(ctx)

print("test_leads OK")
