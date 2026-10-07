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

    # ---- empty database renders ----
    r = c.get("/api/dashboard", headers=admin)
    assert r.status_code == 200, r.text
    assert r.json()["alerts"] == {"customers_at_risk": 0, "customers_never_ordered": 0,
                                  "late_orders": 0, "oldest_late_days": None}
    assert c.get("/api/customers/overview", headers=admin).json() == []

    # ---- catalog ----
    color = c.post("/api/colors", headers=admin, json={"name": "Preto", "hex": "#111111"}).json()
    product = c.post("/api/products", headers=admin, json={
        "reference": "R1", "description": "Blusão", "price": 100, "color_ids": [color["id"]]}).json()

    def customer(headers, name):
        r = c.post("/api/customers", headers=headers, json={"name": name, "document": "123"})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def order(headers, cid, days_ago, status="delivered", delivery_days_ago=None):
        d = TODAY - timedelta(days=days_ago)
        dd = TODAY - timedelta(days=days_ago if delivery_days_ago is None else delivery_days_ago)
        r = c.post("/api/orders", headers=headers, json={
            "customer_id": cid, "date": d.isoformat(), "delivery_date": dd.isoformat(), "status": status,
            "payment_method": "PIX", "payment_terms": "À vista",
            "items": [{"product_id": product["id"], "color_id": color["id"], "size": "P", "quantity": 1}]})
        assert r.status_code == 201, r.text
        return r.json()["id"]

    c_active = customer(seller_a, "Ácida Modas")
    c60, c61 = customer(seller_a, "Cliente 60"), customer(seller_a, "Cliente 61")
    c150, c151 = customer(seller_a, "Cliente 150"), customer(seller_a, "Cliente 151")
    c_quote = customer(seller_a, "Só Orçamento")
    customer(seller_a, "Nunca Comprou")
    c_reassigned = customer(seller_a, "Atendido Pelo Admin")
    c_b = customer(seller_b, "Cliente do Bruno")

    order(seller_a, c_active, 0)
    for cid, days in ((c60, 60), (c61, 61), (c150, 150), (c151, 151)):
        order(seller_a, cid, days)
    order(seller_a, c_quote, 5, status="quote")
    late1 = order(seller_a, c_active, 10, status="confirmed", delivery_days_ago=1)
    late2 = order(seller_a, c_active, 10, status="in_production", delivery_days_ago=3)
    order(seller_a, c_active, 10, status="shipped", delivery_days_ago=5)      # shipped: not late
    order(seller_a, c_active, 10, status="confirmed", delivery_days_ago=0)    # due today: not late
    order(seller_a, c_active, 10, status="canceled", delivery_days_ago=9)     # canceled: not late
    admin_order = order(admin, c_reassigned, 2)  # admin sold to Ana's customer
    order(seller_b, c_b, 1)

    # ---- overview: statuses, seller scoping ----
    ov_a = {r["name"]: r for r in c.get("/api/customers/overview", headers=seller_a).json()}
    assert {n: r["status"] for n, r in ov_a.items()} == {
        "Ácida Modas": "active", "Cliente 60": "active", "Cliente 61": "at_risk", "Cliente 150": "at_risk",
        "Cliente 151": "inactive", "Só Orçamento": "never_ordered", "Nunca Comprou": "never_ordered",
        "Atendido Pelo Admin": "never_ordered"}, ov_a
    assert ov_a["Atendido Pelo Admin"]["recent_orders"] == []  # admin's sale is not Ana's
    acida = ov_a["Ácida Modas"]
    assert acida["orders"] == 5 and acida["total"] == 500.0  # delivered + confirmed x2 + in_production + shipped
    assert len(acida["recent_orders"]) == 3 and acida["colors"] == ["Preto"]
    assert acida["last_order_date"] == TODAY.isoformat()
    ov_b = c.get("/api/customers/overview", headers=seller_b).json()
    assert [r["name"] for r in ov_b] == ["Cliente do Bruno"]
    ov_admin = {r["name"]: r for r in c.get("/api/customers/overview", headers=admin).json()}
    assert ov_admin["Atendido Pelo Admin"]["recent_orders"][0]["id"] == admin_order

    # ---- late filter ----
    late_ids = {o["id"] for o in c.get("/api/orders", headers=seller_a, params={"late": 1}).json()}
    assert late_ids == {late1, late2}, late_ids
    assert c.get("/api/orders", headers=seller_b, params={"late": 1}).json() == []

    # ---- dashboard alerts agree with the overview ----
    d = c.get("/api/dashboard", headers=seller_a).json()
    assert d["alerts"] == {"customers_at_risk": 2, "customers_never_ordered": 3,
                           "late_orders": 2, "oldest_late_days": 3}, d["alerts"]
    da = c.get("/api/dashboard", headers=admin).json()
    assert da["alerts"]["customers_at_risk"] == sum(r["status"] == "at_risk" for r in ov_admin.values())

    # ---- period validation ----
    assert c.get("/api/dashboard", headers=admin, params={"start": "2026-10-07", "end": "2026-10-01"}).status_code == 400
    assert c.get("/api/dashboard", headers=admin, params={"start": "2020-01-01", "end": "2026-10-07"}).status_code == 400

    # ---- sales_series: daily up to 31 days, weekly beyond, clipped ----
    week = {"start": (TODAY - timedelta(days=6)).isoformat(), "end": TODAY.isoformat()}
    s7 = c.get("/api/dashboard", headers=admin, params=week).json()
    assert len(s7["sales_series"]) == 7 and s7["sales_series"][0]["start"] == week["start"]
    year = c.get("/api/dashboard", headers=admin, params={"start": "2026-01-01", "end": TODAY.isoformat()}).json()
    starts = [p["start"] for p in year["sales_series"]]
    assert starts[0] == "2026-01-01" and starts[1] == "2026-01-05"  # Thu 1st, then Monday the 5th
    assert round(sum(p["value"] for p in year["sales_series"]), 2) == year["kpis"]["revenue"]

    # ---- previous period of the same length ----
    day60 = (TODAY - timedelta(days=60)).isoformat()
    p = c.get("/api/dashboard", headers=admin, params={"start": day60, "end": day60}).json()
    assert p["kpis"]["revenue"] == 100 and p["previous_kpis"]["revenue"] == 100  # day 60 vs day 61

    # ---- goals: prorated, admin-only company goal, sellers with zero sales listed ----
    assert s7["goal"] == 14000.0  # 60800 * 7 / 30.4
    sellers = {s["name"]: s for s in s7["by_seller"]}
    assert sellers["Ana Vendas"]["goal"] == 7000.0  # 30400 * 7 / 30.4
    assert sellers["Bruno Vendas"]["goal"] is None
    new_user("Carla Nova", "carla@test.com")
    new_user("Davi Inativo", "davi@test.com", active=False)
    names = {s["name"] for s in c.get("/api/dashboard", headers=admin, params=week).json()["by_seller"]}
    assert "Carla Nova" in names and "Davi Inativo" not in names, names
    sa7 = c.get("/api/dashboard", headers=seller_a, params=week).json()
    assert sa7["goal"] == 7000.0  # the seller gets their own goal, never the company's
    assert [s["name"] for s in sa7["by_seller"]] == ["Ana Vendas"]

    # ---- every city counts toward the total (Faturamento's "Outras" needs the full list) ----
    from app.database import SessionLocal
    from app.models import Customer
    with SessionLocal() as db:  # straight to the DB: the API would geocode each city over the network
        ana_id = next(s["id"] for s in s7["by_seller"] if s["name"] == "Ana Vendas")
        city_customers = [Customer(name=f"Loja {i}", document="1", city=f"Cidade {i}", state="SC", owner_id=ana_id)
                          for i in range(51)]
        db.add_all(city_customers)
        db.commit()
        city_ids = [x.id for x in city_customers]
    for cid in city_ids:
        order(seller_a, cid, 1)
    wk = c.get("/api/dashboard", headers=admin, params=week).json()
    assert round(sum(x["value"] for x in wk["by_city"]), 2) == wk["kpis"]["revenue"], len(wk["by_city"])

print("dashboard checks OK")
