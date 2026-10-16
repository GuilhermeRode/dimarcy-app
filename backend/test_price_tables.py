"""Retail price table + products restricted to sellers. Run from backend/:  python test_price_tables.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

TODAY = date.today().isoformat()


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")
    ids = {}
    for key, table in (("w", "wholesale"), ("r", "retail"), ("b", "both")):
        r = c.post("/api/users", headers=admin, json={"name": key, "email": f"{key}@t.com", "password": "seller-pass-123",
                                                      "role": "seller", "price_table": table})
        assert r.status_code == 201, r.text
        ids[key] = r.json()["id"]
    W, R, B = (login(c, f"{k}@t.com", "seller-pass-123") for k in "wrb")

    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]

    def product(ref, price, seller_ids=()):
        r = c.post("/api/products", headers=admin, json={"reference": ref, "description": "Blusão", "price": price,
                                                         "color_ids": [color], "seller_ids": list(seller_ids)})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    common = product("R1", 89.90)
    only_r = product("R2", 100, [ids["r"]])

    def order(h, pid, **extra):
        cid = c.post("/api/customers", headers=h, json={"name": "Cliente", "document": "1"}).json()["id"]
        return c.post("/api/orders", headers=h, json={
            "customer_id": cid, "delivery_date": TODAY, "status": "confirmed", "payment_method": "Pix",
            "payment_terms": "À vista", "items": [{"product_id": pid, "color_id": color, "size": "P", "quantity": 2}],
            **extra})

    # ---- price tables ----
    assert c.get("/api/settings", headers=W).json()["price_tables"] == ["wholesale"]
    assert c.get("/api/settings", headers=B).json()["price_tables"] == ["wholesale", "retail"]
    assert c.get("/api/settings", headers=R).json()["retail_markup_percent"] == 50

    o = order(W, common).json()
    assert (o["price_table"], o["items"][0]["unit_price"]) == ("wholesale", 89.90)
    assert order(W, common, price_table="retail").status_code == 400  # wholesale seller can't pick retail

    o = order(R, common).json()  # retail-only seller defaults to retail
    assert (o["price_table"], o["items"][0]["unit_price"], o["total"]) == ("retail", 134.85, 269.70), o

    assert order(B, common).json()["price_table"] == "wholesale"  # "both" defaults to wholesale
    o = order(B, common, price_table="retail").json()
    assert o["items"][0]["unit_price"] == 134.85
    # a seller's unit_price is ignored — the server prices it
    o = c.post("/api/orders", headers=B, json={**{"customer_id": o["customer_id"], "delivery_date": TODAY,
               "payment_method": "Pix", "payment_terms": "À vista", "price_table": "retail"},
               "items": [{"product_id": common, "color_id": color, "size": "P", "quantity": 1, "unit_price": 1}]}).json()
    assert o["items"][0]["unit_price"] == 134.85

    # the markup is an admin setting; editing a retail order keeps its table and recorded prices
    s = c.get("/api/settings", headers=admin).json()
    r = c.put("/api/settings", headers=admin, json={"allow_price_override": False, "max_discount_percent": 0,
                                                     "retail_markup_percent": 100, "monthly_goal": s["monthly_goal"]})
    assert r.json()["retail_markup_percent"] == 100
    edit = {"customer_id": o["customer_id"], "delivery_date": TODAY, "status": "confirmed", "payment_method": "Pix",
            "payment_terms": "À vista", "items": [{"product_id": common, "color_id": color, "size": "P", "quantity": 3},
                                                  {"product_id": only_r, "color_id": color, "size": "P", "quantity": 1}]}
    o = c.put(f"/api/orders/{o['id']}", headers=admin, json=edit).json()
    prices = {i["product_reference"]: i["unit_price"] for i in o["items"]}
    assert (o["price_table"], prices) == ("retail", {"R1": 134.85, "R2": 200.0}), (o["price_table"], prices)

    # ---- products restricted to sellers ----
    refs = lambda h: [p["reference"] for p in c.get("/api/products", headers=h).json()]  # noqa: E731
    assert refs(W) == ["R1"] and refs(B) == ["R1"]
    assert refs(R) == ["R1", "R2"] and refs(admin) == ["R1", "R2"]
    assert c.get(f"/api/products/{only_r}", headers=W).status_code == 404
    assert c.get(f"/api/products/{only_r}", headers=R).status_code == 200
    assert order(W, only_r).status_code == 400
    assert order(R, only_r).status_code == 201
    assert c.get(f"/api/products/{only_r}", headers=admin).json()["seller_ids"] == [ids["r"]]

    # ---- review fixes ----
    from app.settings_store import retail_price  # noqa: E402
    assert retail_price(0.15, 50) == 0.23 and retail_price(0.29, 50) == 0.44  # half cent rounds up, like the form
    assert c.get("/api/settings", headers=admin).json()["price_tables"] == ["wholesale", "retail"]
    assert order(admin, common, price_table="retail").status_code == 201
    # an older cached app that doesn't send the new fields must not wipe them
    c.put(f"/api/users/{ids['r']}", headers=admin, json={"name": "r", "email": "r@t.com", "role": "seller"})
    assert c.get("/api/settings", headers=R).json()["price_tables"] == ["retail"]
    c.put(f"/api/products/{only_r}", headers=admin, json={"reference": "R2", "description": "Blusão", "price": 100,
                                                          "color_ids": [color]})
    assert c.get(f"/api/products/{only_r}", headers=admin).json()["seller_ids"] == [ids["r"]]
    # only sellers can be picked; other ids are ignored
    p = c.put(f"/api/products/{only_r}", headers=admin, json={"reference": "R2", "description": "Blusão", "price": 100,
                                                              "color_ids": [color], "seller_ids": [1, ids["w"]]}).json()
    assert p["seller_ids"] == [ids["w"]], p["seller_ids"]

print("price tables + product sellers OK")
