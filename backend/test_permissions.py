"""Seller isolation self-check: a seller only ever reaches their own customers, their own orders
and their own numbers — through every endpoint. Run from backend/:  python test_permissions.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

TODAY = date.today()


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")
    ids = {}
    for key, name in (("a", "Ana"), ("b", "Bruno")):
        r = c.post("/api/users", headers=admin, json={"name": name, "email": f"{key}@t.com", "password": "seller-pass-123",
                                                      "role": "seller", "monthly_goal": 1000 if key == "a" else 2000})
        ids[key] = r.json()["id"]
    A, B = login(c, "a@t.com", "seller-pass-123"), login(c, "b@t.com", "seller-pass-123")

    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]
    product = c.post("/api/products", headers=admin, json={"reference": "R1", "description": "Blusão", "price": 100,
                                                           "color_ids": [color]}).json()["id"]

    def customer(h, name, **extra):
        r = c.post("/api/customers", headers=h, json={"name": name, "document": "123", **extra})
        assert r.status_code == 201, r.text
        return r.json()

    def order(h, cid, qty=1, status="delivered"):
        return c.post("/api/orders", headers=h, json={
            "customer_id": cid, "date": TODAY.isoformat(), "delivery_date": (TODAY - timedelta(days=2)).isoformat(),
            "status": status, "payment_method": "PIX", "payment_terms": "À vista",
            "items": [{"product_id": product, "color_id": color, "size": "P", "quantity": qty}]})

    cA = customer(A, "Cliente da Ana")
    cB = customer(B, "Cliente do Bruno")
    c_none = customer(admin, "Sem Dono", owner_id=None)
    oA = order(A, cA["id"], qty=1, status="confirmed").json()["id"]  # late: delivery date passed
    oB = order(B, cB["id"], qty=2).json()["id"]
    o_admin = order(admin, cA["id"], qty=5).json()["id"]  # admin sold to Ana's customer

    # ---- customers ----
    assert [x["name"] for x in c.get("/api/customers", headers=B).json()] == ["Cliente do Bruno"]
    assert [x["name"] for x in c.get("/api/customers", headers=B, params={"search": "Ana"}).json()] == []
    for cid in (cA["id"], c_none["id"]):
        assert c.get(f"/api/customers/{cid}", headers=B).status_code == 404
        assert c.put(f"/api/customers/{cid}", headers=B, json={"name": "Hack", "document": "1"}).status_code == 404
        assert c.delete(f"/api/customers/{cid}", headers=B).status_code == 404
    assert c.get(f"/api/customers/{cA['id']}", headers=admin).json()["name"] == "Cliente da Ana"  # untouched
    # a seller can't create or move a customer into someone else's portfolio
    assert customer(B, "Tentativa", owner_id=ids["a"])["owner_id"] == ids["b"]
    r = c.put(f"/api/customers/{cB['id']}", headers=B, json={"name": "Cliente do Bruno", "document": "1",
                                                             "owner_id": ids["a"]})
    assert r.json()["owner_id"] == ids["b"]
    names_b = {x["name"] for x in c.get("/api/customers/overview", headers=B).json()}
    assert names_b == {"Cliente do Bruno", "Tentativa"}, names_b

    # ---- orders ----
    assert [o["id"] for o in c.get("/api/orders", headers=B).json()] == [oB]
    assert c.get("/api/orders", headers=B, params={"customer_id": cA["id"]}).json() == []
    for oid in (oA, o_admin):
        assert c.get(f"/api/orders/{oid}", headers=B).status_code == 404
    assert c.get(f"/api/orders/{o_admin}", headers=A).status_code == 404  # sold by admin, not by Ana
    assert order(B, cA["id"]).status_code == 400  # can't sell to Ana's customer
    assert order(B, c_none["id"]).status_code == 400  # nor to an unowned one
    for oid in (oA, oB):  # editing, status changes and deletion are admin-only
        assert c.put(f"/api/orders/{oid}", headers=B, json={}).status_code == 403
        assert c.patch(f"/api/orders/{oid}/status", headers=B, json={"status": "canceled"}).status_code == 403
        assert c.delete(f"/api/orders/{oid}", headers=B).status_code == 403
    assert {o["id"] for o in c.get("/api/orders", headers=admin).json()} == {oA, oB, o_admin}

    # ---- dashboard: only the seller's own numbers ----
    d = c.get("/api/dashboard", headers=B).json()
    assert d["kpis"]["revenue"] == 200 and d["kpis"]["orders"] == 1, d["kpis"]
    assert [s["name"] for s in d["by_seller"]] == ["Bruno"]
    assert [x["name"] for x in d["top_customers"]] == ["Cliente do Bruno"]
    assert sum(m["orders"] for m in d["monthly_sales"]) == 1
    assert d["alerts"]["late_orders"] == 0  # Ana's late order is not Bruno's
    days = (TODAY - date(TODAY.year, 1, 1)).days + 1  # default period: 1 Jan to today
    assert d["goal"] == round(2000 * days / 30.4, 2), d["goal"]  # Bruno's own goal, not the company's
    da = c.get("/api/dashboard", headers=A).json()
    assert da["kpis"]["revenue"] == 100 and da["alerts"]["late_orders"] == 1  # admin's sale excluded
    assert "60800" not in str(d) and "monthly_goal" not in str(d)

    # ---- admin-only areas ----
    assert c.get("/api/users", headers=B).status_code == 403
    assert c.post("/api/users", headers=B, json={"name": "X", "email": "x@t.com", "password": "seller-pass-123"}).status_code == 403
    assert c.put(f"/api/users/{ids['b']}", headers=B, json={"name": "Bruno", "email": "b@t.com", "role": "admin"}).status_code == 403
    assert c.put("/api/settings", headers=B, json={"allow_price_override": True, "max_discount_percent": 100}).status_code == 403
    assert "monthly_goal" not in c.get("/api/settings", headers=B).json()

    # ---- no self-promotion through the profile ----
    r = c.put("/api/auth/me", headers=B, json={"name": "Bruno", "email": "b@t.com", "role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "seller"
    assert c.get("/api/users", headers=B).status_code == 403

    # ---- a deactivated seller's token stops working ----
    c.put(f"/api/users/{ids['b']}", headers=admin, json={"name": "Bruno", "email": "b@t.com", "role": "seller", "active": False})
    assert c.get("/api/customers", headers=B).status_code == 401
    assert c.get("/api/dashboard", headers=B).status_code == 401

print("permission checks OK")
