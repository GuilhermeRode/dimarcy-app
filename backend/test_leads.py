"""Prospecting + mini-CRM self-check: regions, leads, contacts. Run from backend/:  python test_leads.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, datetime, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="", CHECK_EMAIL_DNS="false")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app import clock  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.leads import is_mobile, lead_score, normalize_cnpj, receita_phone  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AppSettings, Contact, Customer, Lead, SellerCity, User  # noqa: E402
from app.sales import _city_key  # noqa: E402

TODAY = date(2026, 10, 16)
# every field a customer needs since registration became complete; tests override what they check
REQ = {"phone": "(47) 99999-8888", "email": "loja@gmail.com", "city": "Caxias do Sul", "state": "RS",
       "address": "Rua A, 1", "state_registration": "ISENTO"}
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
    too_many = ",".join(f"{4000000 + i}" for i in range(26))  # 26 * 8 - 1 = 207 chars > 200
    assert c.put("/api/settings", headers=admin, json={**base, "lead_cnaes": too_many}).status_code == 422
    r = c.put("/api/settings", headers=admin, json=base)  # omitted: unchanged
    assert r.json()["lead_cnaes"] == "4781400,4642701"
    assert "lead_cnaes" not in c.get("/api/settings", headers=ctx["a"]).json()  # sellers don't see it
    r = c.get("/api/settings", headers=admin).json()
    assert (r["lead_sizes"], r["lead_exclude_mei"], r["lead_head_office_only"], r["lead_require_contact"],
            r["lead_min_age_months"]) == ("01,03", True, True, True, 6), r
    assert r["lead_import_started_at"] is None and r["lead_import_error"] is None
    r = c.put("/api/settings", headers=admin, json={**base, "lead_sizes": "03, 01,05", "lead_exclude_mei": False,
                                                    "lead_head_office_only": False, "lead_require_contact": False,
                                                    "lead_min_age_months": 0})
    assert r.status_code == 200, r.text
    assert (r.json()["lead_sizes"], r.json()["lead_min_age_months"]) == ("01,03,05", 0)
    assert c.put("/api/settings", headers=admin, json={**base, "lead_sizes": "02"}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_sizes": ""}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_min_age_months": 121}).status_code == 422
    r = c.put("/api/settings", headers=admin, json={**base, "lead_states": "sc, pr ,SC", "lead_weekly_release": 30})
    assert (r.json()["lead_states"], r.json()["lead_weekly_release"]) == ("PR,SC", 30), r.text
    assert c.put("/api/settings", headers=admin, json={**base, "lead_states": "XX"}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_weekly_release": -1}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_area_codes": "49, 47,47"}).json()["lead_area_codes"] == "47,49"
    assert c.put("/api/settings", headers=admin, json={**base, "lead_area_codes": "4"}).status_code == 422
    assert c.put("/api/settings", headers=admin, json={**base, "lead_area_codes": ""}).json()["lead_area_codes"] == ""

    # catalog PDF: admin uploads, everyone reads the link, only a real PDF
    pdf = {"file": ("x.pdf", b"%PDF-1.4 catalog", "application/pdf")}
    assert c.post("/api/settings/catalog", headers=ctx["a"], files=pdf).status_code == 403
    assert c.post("/api/settings/catalog", headers=admin, files={"file": ("x.pdf", b"<html>", "application/pdf")}).status_code == 400
    url = c.post("/api/settings/catalog", headers=admin, files=pdf).json()["catalog_url"]
    assert url.startswith("/uploads/catalog/catalogo-dimarcy-") and c.get(url).content == b"%PDF-1.4 catalog"
    assert c.get("/api/settings", headers=ctx["a"]).json()["catalog_url"] == url
    assert c.delete("/api/settings/catalog", headers=admin).json()["catalog_url"] is None
    assert c.get(url).status_code == 404  # the old file is removed
    c.put("/api/settings", headers=admin, json={**base, "lead_states": "PR,RS,SC", "lead_weekly_release": 20})
    r = c.put("/api/settings", headers=admin, json=base)  # omitted: unchanged
    assert r.json()["lead_sizes"] == "01,03,05" and r.json()["lead_exclude_mei"] is False
    assert "lead_sizes" not in c.get("/api/settings", headers=ctx["a"]).json()
    c.put("/api/settings", headers=admin, json={**base, "lead_sizes": "01,03", "lead_exclude_mei": True,
                                                "lead_head_office_only": True, "lead_require_contact": True,
                                                "lead_min_age_months": 6})
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
    with SessionLocal() as db:
        admin_id = db.query(User).filter(User.email == "admin@test.com").one().id
    assert c.put(f"/api/users/{admin_id}/cities", headers=admin, json=[]).status_code == 200  # an admin may have a region too
    ctx["admin_id"] = admin_id
    assert c.get(f"/api/users/{a_id}/cities", headers=ctx["a"]).status_code == 403  # admin only
    assert c.put(f"/api/users/{a_id}/cities", headers=admin, json=[{"city": "", "state": "SC"}]).status_code == 422

    # suggestions: Ana's customers' cities, marking the ones another seller has
    c.post("/api/customers", headers=ctx["a"], json={**REQ, "name": "Loja Corupá", "document": "1", "city": "Corupa", "state": "SC"})
    c.post("/api/customers", headers=ctx["a"], json={**REQ, "name": "Loja Guará", "document": "2", "city": "Guaramirim", "state": "SC"})
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
    # lead_score: landline + opened within 5 years 4 (+1 debt not checked), 5-year store alone 3, landline alone 2
    assert names(r) == ["Jota Moda", "Jaraguá Sem Fone", "Antiga Modas"], names(r)
    assert [x["score"] for x in r.json()["items"]] == [4, 3, 2]
    assert r.json()["total"] == 3 and r.json()["cities"] == ["Jaraguá do Sul"]
    assert names(c.get("/api/leads", headers=ctx["b"])) == ["Corupá Store"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"limit": 1, "offset": 1})) == ["Jaraguá Sem Fone"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"search": "antiga"})) == ["Antiga Modas"]
    assert names(c.get("/api/leads", headers=ctx["a"], params={"search": "0000000000103"})) == ["Antiga Modas"]

    r = c.get("/api/leads", headers=admin)
    assert r.json()["total"] == 5  # every new lead, discarded left out
    blu = next(x for x in r.json()["items"] if x["name"] == "Blu Fashion")
    assert blu["seller_id"] is None and blu["seller_name"] is None
    assert names(c.get("/api/leads", headers=admin, params={"seller_id": 0})) == ["Blu Fashion"]
    assert names(c.get("/api/leads", headers=admin, params={"seller_id": ctx["b_id"], "city": "corupa"})) == ["Corupá Store"]
    # the search also finds the city, accents ignored; the city filter takes part of the name
    assert names(c.get("/api/leads", headers=admin, params={"search": "CORUPÁ"})) == ["Corupá Store"]
    assert names(c.get("/api/leads", headers=admin, params={"search": "blumenau"})) == ["Blu Fashion"]
    assert sorted(names(c.get("/api/leads", headers=admin, params={"city": "jaragu"}))) == \
        ["Antiga Modas", "Jaraguá Sem Fone", "Jota Moda"]

    # detail: visible to the region's seller and the admin only
    assert c.get(f"/api/leads/{ids['corupa']}", headers=ctx["b"]).json()["seller_name"] == "Bruno"
    assert c.get(f"/api/leads/{ids['corupa']}", headers=ctx["a"]).status_code == 404
    assert c.get(f"/api/leads/{ids['blumenau']}", headers=ctx["a"]).status_code == 404
    assert c.get(f"/api/leads/{ids['blumenau']}", headers=admin).status_code == 200

    # a customer typed by hand with the lead's CNPJ (formatted) hides the lead at once
    c.post("/api/customers", headers=ctx["a"], json={**REQ, "name": "Antiga", "document": "10.000.000/0001-03"})
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


def check_score():
    # Receita phones: the 9th digit for old 8-digit mobiles, placeholders dropped, odd ones kept as typed
    assert receita_phone("41", "97605678") == "(41) 99760-5678" and receita_phone("041", "32437109") == "(41) 3243-7109"
    assert receita_phone("47", "991234567") == "(47) 99123-4567"
    assert [receita_phone(*p) for p in (("51", "99999999"), ("0000", "00000000"), ("0", "0"), ("47", ""))] == [None] * 4
    assert receita_phone("11", "1949284") == "11 1949284"
    assert is_mobile(receita_phone("41", "97605678")) and not is_mobile(receita_phone("41", "32437109"))
    assert lead_score(Lead(phone="(41) 99760-5678"), 0, TODAY, shared_phone=True) == 1  # only "debt not checked"
    assert is_mobile("47 991234567") and not is_mobile("47 33330000") and not is_mobile(None)
    assert is_mobile("46 99735351") and is_mobile("51 85205934") and not is_mobile("41 32926931")
    best = Lead(phone="47 991234567", email="a@b.c", in_debt=False, capital=60000, opened_at=TODAY - timedelta(days=400))
    assert lead_score(best, 5, TODAY) == 3 + 3 + 3 + 2 + 1 + 3
    debtor = Lead(phone="47 991234567", in_debt=True, capital=10000, opened_at=TODAY - timedelta(days=4000))
    assert lead_score(debtor, 0, TODAY) == 3 + 0 + 2
    assert lead_score(Lead(capital=999), 0, TODAY) == 1  # debt not checked: 1


def check_ranking_by_active_customers(ctx):
    """Same contact/new-store tier: the city with more active Di Marcy customers comes first."""
    c, admin = ctx["c"], ctx["admin"]
    # sorts after Corupá and Jota by name, so only the active-customers criterion can put it second
    add_lead("10000000000107", "Zz Blumenau", city="Blumenau", phone="1", opened_at=TODAY - timedelta(days=100))
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]
    product = c.post("/api/products", headers=admin, json={"reference": "R1", "description": "Blusão", "price": 100,
                                                           "color_ids": [color]}).json()["id"]
    cust = c.post("/api/customers", headers=admin, json={**REQ, "name": "Cliente Blu", "document": "77", "city": "Blumenau",
                                                         "state": "SC", "owner_id": None}).json()["id"]
    r = c.post("/api/orders", headers=admin, json={
        "customer_id": cust, "date": TODAY.isoformat(), "delivery_date": TODAY.isoformat(), "status": "delivered", "payment_method": "PIX",
        "payment_terms": "À vista", "items": [{"product_id": product, "color_id": color, "size": "P", "quantity": 1}]})
    assert r.status_code == 201, r.text
    top = [x["name"] for x in c.get("/api/leads", headers=admin).json()["items"]][:3]
    assert top[:2] == ["Blu Fashion", "Zz Blumenau"], top


def check_convert(ctx):
    c, admin, ids = ctx["c"], ctx["admin"], ctx["leads"]
    body = {**REQ, "name": "Jota Moda Ltda", "document": "10000000000101", "city": "Jaraguá do Sul", "state": "SC",
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

    # "Não recomendar": admin only, several at once, already-handled ones are skipped
    p1 = add_lead("30000000000101", "Fila Um", status="pending")
    p2 = add_lead("30000000000102", "Fila Dois", status="pending")
    body = {"ids": [p1, p2, ids["j_no_contact"]], "reason": "not_recommended"}
    assert c.post("/api/leads/discard", headers=ctx["a"], json=body).status_code == 403
    assert c.post("/api/leads/discard", headers=admin, json=body).json() == {"discarded": 2}
    with SessionLocal() as db:
        assert {db.get(Lead, i).discard_reason for i in (p1, p2)} == {"not_recommended"}
        assert db.get(Lead, ids["j_no_contact"]).discard_reason == "competitor"

    # "Não respondeu": retry in 7 days; the 3rd one discards
    nr = add_lead("40000000000101", "Sem Resposta", phone="47 99999-1111")
    assert c.post(f"/api/leads/{nr}/no-answer", headers=ctx["b"]).status_code == 404  # not Bruno's region
    r = c.post(f"/api/leads/{nr}/no-answer", headers=ctx["a"]).json()
    assert r == {"tries": 1, "discarded": False, "retry_on": (TODAY + timedelta(days=7)).isoformat()}, r
    row = next(x for x in c.get("/api/leads", headers=ctx["a"]).json()["items"] if x["id"] == nr)
    assert row["next_action_date"] == r["retry_on"]
    assert c.post(f"/api/leads/{nr}/no-answer", headers=ctx["a"]).json()["tries"] == 2
    assert c.post(f"/api/leads/{nr}/no-answer", headers=ctx["a"]).json() == {"tries": 3, "discarded": True, "retry_on": None}
    with SessionLocal() as db:
        assert (db.get(Lead, nr).status, db.get(Lead, nr).discard_reason) == ("discarded", "no_answer")
    assert c.post(f"/api/leads/{nr}/no-answer", headers=ctx["a"]).status_code == 409


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
    assert due[0]["seller_name"] and due[0]["user_name"], due  # "vendedor X · feito por Y"
    assert c.get("/api/contacts/due", headers=admin).json() == []  # reminders belong to who set them
    assert c.get("/api/dashboard", headers=ctx["a"]).json()["alerts"]["follow_ups_due"] == 1

    # the latest contact replaces the reminder: future date -> not due; no date -> no reminder
    contact(ctx["a"], lead_id=jl, next_action_date=tomorrow)
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []
    row = next(x for x in c.get("/api/leads", headers=ctx["a"]).json()["items"] if x["id"] == jl)
    assert row["next_action_date"] == tomorrow and row["last_contact_at"], row  # the list shows where Ana left off
    contact(ctx["a"], lead_id=jl, next_action_date=yesterday)
    assert len(c.get("/api/contacts/due", headers=ctx["a"]).json()) == 1
    contact(ctx["a"], lead_id=jl)
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []

    # history: newest first, visible to whoever sees the lead (admin too), not to Bruno
    hist = c.get("/api/contacts", headers=admin, params={"lead_id": jl}).json()
    assert len(hist) == 4 and hist[0]["next_action_date"] is None
    assert c.get("/api/contacts", headers=ctx["b"], params={"lead_id": jl}).status_code == 404
    assert c.get("/api/contacts", headers=ctx["a"]).status_code == 422

    # an orphan contact (its lead row is gone) must not break the due list or the dashboard
    with SessionLocal() as db:
        ana = db.query(User).filter(User.email == "a@t.com").one()
        orphan = Contact(user_id=ana.id, lead_id=999999, channel="call", next_action_date=TODAY)
        db.add(orphan)
        db.commit()
        orphan_id = orphan.id
    try:
        assert c.get("/api/contacts/due", headers=ctx["a"]).status_code == 200
        assert c.get("/api/dashboard", headers=ctx["a"]).status_code == 200
    finally:
        with SessionLocal() as db:
            db.query(Contact).filter(Contact.id == orphan_id).delete()
            db.commit()

    # discarded lead leaves the due list
    contact(ctx["a"], lead_id=jl, next_action_date=yesterday)
    c.post(f"/api/leads/{jl}/discard", headers=ctx["a"], json={"reason": "other"})
    assert contact(ctx["a"], lead_id=jl).status_code == 409  # a handled lead takes no more contacts
    assert c.get("/api/contacts", headers=ctx["a"], params={"lead_id": jl}).status_code == 200  # but its history stays readable
    assert c.get("/api/contacts/due", headers=ctx["a"]).json() == []

    # converting moves the history to the customer; customer contacts work the same way
    jl2 = add_lead("20000000000102", "Loja Converte")
    contact(ctx["a"], lead_id=jl2, next_action_date=yesterday)
    cust = c.post(f"/api/leads/{jl2}/convert", headers=ctx["a"], json={**REQ, "name": "Loja Converte", "document": "20000000000102"}).json()
    hist = c.get("/api/contacts", headers=ctx["a"], params={"customer_id": cust["id"]}).json()
    assert len(hist) == 1
    due = c.get("/api/contacts/due", headers=ctx["a"]).json()
    assert [(d["name"], d["kind"]) for d in due] == [("Loja Converte", "customer")], due
    assert c.get("/api/contacts", headers=ctx["b"], params={"customer_id": cust["id"]}).status_code == 404

    # deleting the customer puts the converted lead back to 'new' with its contact history
    assert c.delete(f"/api/customers/{cust['id']}", headers=ctx["a"]).status_code == 204
    with SessionLocal() as db:
        assert db.query(Contact).filter(Contact.customer_id == cust["id"]).count() == 0
        lead2 = db.get(Lead, jl2)
        assert (lead2.status, lead2.customer_id) == ("new", None)
    assert len(c.get("/api/contacts", headers=ctx["a"], params={"lead_id": jl2}).json()) == 1
    assert len(c.get("/api/contacts/due", headers=ctx["a"]).json()) == 1  # its reminder is live again


def check_edit(ctx):
    """Only the admin edits a lead; the monthly import keeps what was edited."""
    from app import lead_import
    c, admin, a = ctx["c"], ctx["admin"], ctx["a"]
    lid = add_lead("70000000000202", "RAZAO SOCIAL LTDA", phone="(47) 3333-4444")
    body = {"name": " Loja da Maria ", "phone": "(47) 99999-1111", "email": "", "address": "Rua B, 2"}
    assert c.put(f"/api/leads/{lid}", headers=a, json=body).status_code == 403
    assert c.put(f"/api/leads/{lid}", headers=admin, json={**body, "name": "  "}).status_code == 422
    r = c.put(f"/api/leads/{lid}", headers=admin, json=body)
    assert r.status_code == 200, r.text
    assert (r.json()["name"], r.json()["email"]) == ("Loja da Maria", None), r.json()
    row = {"name": "RAZAO SOCIAL LTDA", "phone": "(47) 3333-4444", "email": None, "address": "X", "raw_city": "Jaraguá do Sul",
           "state": "SC", "opened_at": None, "size": "me", "capital": 10, "in_debt": False}
    with SessionLocal() as db:
        lead_import.apply(db, {"70000000000202": row}, "2026-10", "t", TODAY)
        lead = db.get(Lead, lid)
        assert (lead.name, lead.phone, lead.address, lead.size) == ("Loja da Maria", "(47) 99999-1111", "Rua B, 2", "me")
    # Receita phones were mostly wrong: startup clears them, keeping the ones an admin typed in
    from app.main import _drop_lead_phones
    old = add_lead("70000000000303", "Loja Receita", phone="(47) 3333-5555")
    _drop_lead_phones()
    with SessionLocal() as db:
        assert db.get(Lead, old).phone is None and db.get(Lead, lid).phone == "(47) 99999-1111"
    # a lead typed in by the admin: pending, kept by the import even when the Receita doesn't list it
    new = {**body, "cnpj": "70.000.000/0004-04", "city": "Joinville", "state": "sc"}
    # a seller's: only in their region, and already theirs (new, not waiting for release)
    assert c.post("/api/leads", headers=a, json=new).status_code == 422
    assert c.get("/api/leads/my-cities", headers=a).json() == [{"city": "Jaraguá do Sul", "state": "SC"}]
    r = c.post("/api/leads", headers=a, json={**new, "cnpj": "70000000000505", "city": "jaragua do sul"})
    assert r.status_code == 201, r.text
    assert (r.json()["status"], r.json()["seller_id"]) == ("new", ctx["a_id"]), r.json()
    assert c.get(f"/api/leads/{r.json()['id']}", headers=a).status_code == 200
    assert c.post("/api/leads", headers=admin, json={**new, "cnpj": "123"}).status_code == 422
    r = c.post("/api/leads", headers=admin, json=new)
    assert r.status_code == 201, r.text
    made = r.json()
    assert (made["cnpj"], made["state"], made["status"], made["phone"]) == ("70000000000404", "SC", "pending", "(47) 99999-1111")
    assert c.post("/api/leads", headers=admin, json=new).status_code == 409
    with SessionLocal() as db:
        lead_import.apply(db, {}, "2026-11", "t", TODAY)
        assert db.get(Lead, made["id"]) is not None and db.get(Lead, old) is None
    assert c.post("/api/leads/discard", headers=admin, json={"ids": [made["id"]], "reason": "other"}).status_code == 200


def check_role_change(ctx):
    c, admin = ctx["c"], ctx["admin"]
    r = c.post("/api/users", headers=admin, json={
        "name": "Caio", "email": "caio@t.com", "password": "seller-pass-123", "role": "seller"})
    cid = r.json()["id"]
    assert c.put(f"/api/users/{cid}/cities", headers=admin, json=[{"city": "Guaramirim", "state": "SC"}]).status_code == 200
    lead = add_lead("70000000000101", "Loja Guaramirim", city="Guaramirim")
    r = c.put(f"/api/users/{cid}", headers=admin, json={
        "name": "Caio", "email": "caio@t.com", "role": "admin", "active": True})
    assert r.status_code == 200, r.text
    # an admin may keep a region (and work its leads like a seller): promoting doesn't drop it
    assert c.get(f"/api/users/{cid}/cities", headers=admin).json() == [{"city": "Guaramirim", "state": "SC"}]
    items = c.get("/api/leads", headers=admin, params={"search": "Guaramirim"}).json()["items"]
    assert [x["seller_id"] for x in items if x["id"] == lead] == [cid], items
    assert c.put(f"/api/users/{cid}/cities", headers=admin, json=[]).status_code == 200
    r = c.put(f"/api/users/{ctx['b_id']}/cities", headers=admin, json=[{"city": "Guaramirim", "state": "SC"}])
    assert r.status_code == 200, r.text


def check_pending_release(ctx):
    c, admin, a, b = ctx["c"], ctx["admin"], ctx["a"], ctx["b"]
    pa = add_lead("80000000000101", "Pend Jaragua", status="pending", size="me")
    pb = add_lead("80000000000102", "Pend Guaramirim", city="Guaramirim", status="pending")
    pn = add_lead("80000000000103", "Pend Sem Vendedor", city="Cidade Sem Vendedor", status="pending")
    for h in (a, b):
        r = c.get("/api/leads", headers=h, params={"limit": 200})
        assert not [x for x in r.json()["items"] if x["name"].startswith("Pend")]
        assert not [x for x in c.get("/api/leads", headers=h, params={"status": "pending"}).json()["items"]
                    if x["name"].startswith("Pend")]
    assert c.get(f"/api/leads/{pa}", headers=a).status_code == 404
    assert c.get("/api/contacts", headers=a, params={"lead_id": pa}).status_code == 404
    r = c.post("/api/contacts", headers=a, json={"lead_id": pa, "channel": "call", "notes": "x"})
    assert r.status_code == 404, r.text
    assert c.post(f"/api/leads/{pa}/discard", headers=a, json={"reason": "other"}).status_code == 404
    r = c.post(f"/api/leads/{pa}/convert", headers=a, json={**REQ, "name": "Xx", "document": "80000000000101", "city": "Jaraguá do Sul", "state": "SC"})
    assert r.status_code == 404, r.text
    assert c.get("/api/leads", headers=admin, params={"status": "foo"}).status_code == 422
    r = c.get("/api/leads", headers=admin, params={"status": "pending", "limit": 200})
    got = {x["id"]: x for x in r.json()["items"]}
    assert set(got) == {pa, pb, pn} and got[pa]["size"] == "me", got
    assert c.post("/api/leads/release", headers=a, json={"ids": [pa]}).status_code == 403
    assert c.post("/api/leads/release", headers=admin, json={"ids": []}).status_code == 422
    # release only after the admin's first contact: pending -> contacted ("Primeiro contato") -> new
    assert c.post("/api/leads/release", headers=admin, json={"ids": [pa]}).json()["released"] == 0
    for lid in (pa, pb, pn):
        assert c.post("/api/contacts", headers=admin, json={"lead_id": lid, "channel": "whatsapp"}).status_code == 201
    r = c.get("/api/leads", headers=admin, params={"status": "contacted", "limit": 200})
    assert {pa, pb, pn} <= {x["id"] for x in r.json()["items"]}, r.text
    assert not {pa, pb, pn} & {x["id"] for x in c.get("/api/leads", headers=admin, params={"status": "pending", "limit": 200}).json()["items"]}
    assert c.get(f"/api/leads/{pa}", headers=a).status_code == 404  # still the admin's
    week = lambda uid: c.get("/api/leads", headers=admin, params={"status": "contacted", "seller_id": uid}).json()["week"]  # noqa: E731
    assert week(ctx["a_id"]) == {"released": 0, "quota": 20}
    r = c.post("/api/leads/release", headers=admin, json={"ids": [pa, pb, pn]})
    assert r.json() == {"released": 2, "skipped_no_seller": 1, "skipped_other_seller": {}, "cities_added": []}, r.text
    assert week(ctx["a_id"]) == {"released": 1, "quota": 20}  # nothing is released automatically: only counted
    assert "week" not in c.get("/api/leads", headers=admin, params={"status": "pending"}).json()
    assert c.get(f"/api/leads/{pa}", headers=a).status_code == 200
    assert c.get(f"/api/leads/{pb}", headers=b).status_code == 200
    r = c.post("/api/leads/release", headers=admin, json={"ids": [pa, pb, pn]})
    assert r.json()["released"] == 0, r.text

    # "Liberar para": a city with no seller joins the chosen seller's region; another seller's city stays theirs
    pz = add_lead("80000000000191", "Pend Cidade Livre", city="Cidade Livre", status="contacted")
    pg = add_lead("80000000000192", "Pend Guaramirim 2", city="Guaramirim", status="contacted")
    assert c.post("/api/leads/release", headers=admin, json={"ids": [pz], "seller_id": 99999}).status_code == 400
    r = c.post("/api/leads/release", headers=admin, json={"ids": [pz, pg], "seller_id": ctx["a_id"]})
    got = r.json()
    assert got["released"] == 1 and got["skipped_no_seller"] == 0 and got["cities_added"] == ["Cidade Livre/SC"], got
    assert list(got["skipped_other_seller"].values()) == [1], got  # Guaramirim is b's
    assert c.get(f"/api/leads/{pz}", headers=a).status_code == 200
    assert "Cidade Livre" in [x["city"] for x in c.get(f"/api/users/{ctx['a_id']}/cities", headers=admin).json()]
    assert c.post("/api/leads/release", headers=admin, json={"ids": [pg]}).json()["released"] == 1  # to its city's seller
    # a return the admin scheduled before releasing passes to the seller
    pr = add_lead("80000000000194", "Pend Retorno", status="pending")
    r = c.post("/api/contacts", headers=admin, json={"lead_id": pr, "channel": "whatsapp", "notes": "Pediu para retornar depois",
                                                      "next_action_date": TODAY.isoformat()})
    assert r.status_code == 201, r.text
    due_names = lambda h: [d["name"] for d in c.get("/api/contacts/due", headers=h).json()]  # noqa: E731
    assert "Pend Retorno" in due_names(admin) and "Pend Retorno" not in due_names(a)
    c.post("/api/users", headers=admin, json={"name": "Outro Admin", "email": "adm2@t.com",
                                                          "password": "admin2-pass-123", "role": "admin"})
    admin2 = login(c, "adm2@t.com", "admin2-pass-123")
    assert "Pend Retorno" in due_names(admin2)  # before release: every admin's
    assert c.post("/api/leads/release", headers=admin, json={"ids": [pr]}).json()["released"] == 1
    assert "Pend Retorno" in due_names(a) and "Pend Retorno" not in due_names(admin) and "Pend Retorno" not in due_names(admin2)
    assert c.post(f"/api/leads/{pr}/discard", headers=admin, json={"reason": "other"}).status_code == 204
    # the admin can take leads like a seller: the city joins the admin's region
    pq = add_lead("80000000000193", "Pend Para Admin", city="Cidade do Admin", status="contacted")
    r = c.post("/api/leads/release", headers=admin, json={"ids": [pq], "seller_id": ctx["admin_id"]})
    assert r.json()["released"] == 1 and r.json()["cities_added"] == ["Cidade do Admin/SC"], r.text
    mine = c.get("/api/leads", headers=admin, params={"seller_id": ctx["admin_id"]}).json()["items"]
    assert [x["name"] for x in mine] == ["Pend Para Admin"] and mine[0]["seller_id"] == ctx["admin_id"], mine
    assert c.post(f"/api/leads/{pq}/discard", headers=admin, json={"reason": "other"}).status_code == 204
    c.put(f"/api/users/{ctx['admin_id']}/cities", headers=admin, json=[])
    for lid in (pz, pg, pn):
        assert c.post(f"/api/leads/{lid}/discard", headers=admin, json={"reason": "other"}).status_code == 204
    assert c.put(f"/api/users/{ctx['a_id']}/cities", headers=admin, json=[  # back to a's original region
        x for x in c.get(f"/api/users/{ctx['a_id']}/cities", headers=admin).json() if x["city"] != "Cidade Livre"]).status_code == 200

    import app.routers.settings as settings_router
    calls = []
    real_spawn = settings_router._spawn_import
    settings_router._spawn_import = lambda: calls.append(1)
    try:
        _check_import_now(ctx, calls, settings_router)
    finally:
        settings_router._spawn_import = real_spawn

    # admin follow-ups include pending leads; a seller-less lead goes back to Primeiro contato (releasable) when its customer is deleted
    pf = add_lead("80000000000104", "Pend Follow", city="Cidade Sem Vendedor", status="pending")
    r = c.post("/api/contacts", headers=admin, json={"lead_id": pf, "channel": "call", "notes": "x",
                                                      "next_action_date": (TODAY - timedelta(days=1)).isoformat()})
    assert r.status_code == 201, r.text
    assert "Pend Follow" in [d["name"] for d in c.get("/api/contacts/due", headers=admin).json()]
    lo = add_lead("80000000000105", "Sem Dono", city="Cidade Sem Vendedor", status="new")
    cu = c.post(f"/api/leads/{lo}/convert", headers=admin, json={**REQ, "name": "Sem Dono", "document": "80000000000105"}).json()
    assert c.delete(f"/api/customers/{cu['id']}", headers=admin).status_code == 204
    with SessionLocal() as db:
        assert db.get(Lead, lo).status == "contacted"

    # startup: pending leads the admin already talked to move to "Primeiro contato"; "Não respondeu" doesn't count
    from app.main import _contacted_leads
    talked, silent = add_lead("80000000000106", "Ja Falei", status="pending"), add_lead("80000000000107", "Mudo", status="pending")
    assert c.post(f"/api/leads/{silent}/no-answer", headers=admin).status_code == 200
    with SessionLocal() as db:
        db.add(Contact(lead_id=talked, user_id=ctx["admin_id"], channel="whatsapp"))
        db.commit()
    _contacted_leads()
    with SessionLocal() as db:
        assert (db.get(Lead, talked).status, db.get(Lead, silent).status) == ("contacted", "pending")


def _check_import_now(ctx, calls, settings_router):
    c, admin, a = ctx["c"], ctx["admin"], ctx["a"]
    assert c.post("/api/settings/lead-import", headers=a).status_code == 403
    assert c.post("/api/settings/lead-import", headers=admin).status_code == 202 and len(calls) == 1
    assert c.post("/api/settings/lead-import", headers=admin).status_code == 409 and len(calls) == 1
    with SessionLocal() as db:
        db.query(AppSettings).update({"lead_import_started_at": datetime.now() - timedelta(hours=5)})
        db.commit()
    assert c.post("/api/settings/lead-import", headers=admin).status_code == 202 and len(calls) == 2
    # a lock held by a dead process counts as free; by a live one it does not
    from app import lead_import
    real_alive = lead_import.pid_alive
    with SessionLocal() as db:
        db.query(AppSettings).update({"lead_import_started_at": lead_import.utcnow(), "lead_import_pid": 424242})
        db.commit()
    lead_import.pid_alive = lambda pid: True
    try:
        assert c.post("/api/settings/lead-import", headers=admin).status_code == 409 and len(calls) == 2
        lead_import.pid_alive = lambda pid: False
        assert c.post("/api/settings/lead-import", headers=admin).status_code == 202 and len(calls) == 3
    finally:
        lead_import.pid_alive = real_alive
    def boom():
        raise OSError("no spawn")
    settings_router._spawn_import = boom
    with SessionLocal() as db:
        db.query(AppSettings).update({"lead_import_started_at": None})
        db.commit()
    assert c.post("/api/settings/lead-import", headers=admin).status_code == 500
    with SessionLocal() as db:
        assert db.query(AppSettings).first().lead_import_started_at is None


def check_sellers_flag(ctx):
    """Prospecção starts admin-only (Configurações: leads_for_sellers); the rest of this file turns it on."""
    c, admin, a = ctx["c"], ctx["admin"], ctx["a"]
    assert c.get("/api/settings", headers=a).json()["leads_for_sellers"] is False
    for path in ("/api/leads", "/api/leads/1"):
        r = c.get(path, headers=a)
        assert r.status_code == 403 and "desativada" in r.json()["detail"], (path, r.text)
    assert c.get("/api/contacts", headers=a, params={"lead_id": 1}).status_code == 403
    assert c.get("/api/leads", headers=admin).status_code == 200  # the admin always has it
    s = c.get("/api/settings", headers=admin).json()
    body = {k: s[k] for k in ("allow_price_override", "max_discount_percent", "retail_markup_percent", "annual_goal")}
    assert c.put("/api/settings", headers=admin, json={**body, "leads_for_sellers": True}).status_code == 200
    assert c.get("/api/settings", headers=a).json()["leads_for_sellers"] is True
    assert c.get("/api/leads", headers=a).status_code == 200


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
    check_sellers_flag(ctx)
    check_settings(ctx)
    check_regions(ctx)
    check_score()
    check_listing(ctx)
    check_ranking_by_active_customers(ctx)
    check_convert(ctx)
    check_contacts(ctx)
    check_edit(ctx)
    check_role_change(ctx)
    check_pending_release(ctx)

print("test_leads OK")
