"""Customers-by-city map data self-check. Run from backend/:  python test_cities.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app import clock  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Customer  # noqa: E402

TODAY = date(2026, 10, 7)
clock.today_br = lambda: TODAY


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")
    ana = c.post("/api/users", headers=admin, json={"name": "Ana", "email": "a@t.com", "password": "seller-pass-123"}).json()
    bruno = c.post("/api/users", headers=admin, json={"name": "Bruno", "email": "b@t.com", "password": "seller-pass-123"}).json()
    A = login(c, "a@t.com", "seller-pass-123")
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()["id"]
    product = c.post("/api/products", headers=admin, json={"reference": "R1", "description": "Blusão", "price": 100,
                                                           "color_ids": [color]}).json()["id"]

    with SessionLocal() as db:  # straight to the DB: the API would geocode each city over the network
        rows = [("Loja 1", "Rio do Sul", "SC", ana["id"]), ("Loja 2", " Rio  do Súl ", "sc", ana["id"]),
                ("Loja 3", "Rio do Sul", "SC", bruno["id"]), ("Loja 4", "Curitiba", "PR", bruno["id"]),
                ("Loja 5", "Blumenau", "SC", ana["id"]), ("Sem cidade", None, None, ana["id"])]
        objs = [Customer(name=n, document="1", city=ci, state=uf, owner_id=o, lat=-27.2 if ci else None,
                         lng=-49.6 if ci else None) for n, ci, uf, o in rows]
        db.add_all(objs)
        db.commit()
        cid = {o.name: o.id for o in objs}

    def order(cust, days_ago, qty, status="delivered"):
        d = (TODAY - timedelta(days=days_ago)).isoformat()
        r = c.post("/api/orders", headers=admin, json={
            "customer_id": cid[cust], "date": d, "delivery_date": d, "status": status,
            "payment_method": "PIX", "payment_terms": "À vista",
            "items": [{"product_id": product, "color_id": color, "size": "P", "quantity": qty}]})
        assert r.status_code == 201, r.text

    order("Loja 1", 5, 10)               # Rio do Sul: R$ 1.000
    order("Loja 1", 20, 2)               # Rio do Sul: R$ 200
    order("Loja 2", 60, 3)               # Rio do Sul: R$ 300 (only inside 90 days / 12 months)
    order("Loja 3", 2, 1, "quote")       # a quote is not a sale
    order("Loja 4", 400, 5)              # Curitiba: older than 12 months
    order("Loja 5", 1, 4, "canceled")    # canceled is not a sale

    def cities(**params):
        r = c.get("/api/customers/by-city", headers=admin, params=params)
        assert r.status_code == 200, r.text
        return {f"{x['city']}/{x['state']}": x for x in r.json()}

    m30 = cities(days=30)
    rs = m30["Rio do Sul/SC"]  # " Rio  do Súl "/"sc" (accent, spaces, case) grouped with "Rio do Sul"/"SC"
    assert (rs["registered"], rs["active"], rs["orders"], rs["revenue"]) == (3, 1, 2, 1200.0), rs
    assert rs["average_ticket"] == 600.0 and rs["last_order_date"] == (TODAY - timedelta(days=5)).isoformat()
    assert rs["lat"] == -27.2
    assert m30["Curitiba/PR"]["active"] == 0 and m30["Curitiba/PR"]["average_ticket"] is None
    assert m30["Curitiba/PR"]["last_order_date"] == (TODAY - timedelta(days=400)).isoformat()
    assert m30["Blumenau/SC"]["active"] == 0  # canceled only
    assert "None/None" not in m30 and len(m30) == 3  # customers without a city are left out

    m90 = cities(days=90)
    assert (m90["Rio do Sul/SC"]["active"], m90["Rio do Sul/SC"]["revenue"]) == (2, 1500.0)

    # seller filter = the seller's portfolio (customer owner)
    mana = cities(days=365, owner_id=ana["id"])
    assert mana["Rio do Sul/SC"]["registered"] == 2 and "Curitiba/PR" not in mana

    # admin-only, bounded period
    assert c.get("/api/customers/by-city", headers=A).status_code == 403
    assert c.get("/api/customers/by-city", headers=admin, params={"days": 0}).status_code == 422
    assert c.get("/api/customers/by-city", headers=admin, params={"days": 5000}).status_code == 422

print("city checks OK")
