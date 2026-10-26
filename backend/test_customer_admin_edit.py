"""Editing a customer: an admin may save with blanks (only the name is required); a seller still has to
fill every field. Run from backend/:  python test_customer_admin_edit.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="", CHECK_EMAIL_DNS="false")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routers import customers as _customers_router  # noqa: E402

_customers_router.geocode_and_cache_background = lambda *a: None
FULL = {"document": "12345678000190", "state_registration": "ISENTO", "phone": "54999998888", "email": "cliente@gmail.com",
        "city": "Caxias do Sul", "state": "RS", "address": "Rua A, 1"}
BLANK = {k: "" for k in FULL}


def login(c, email, password):
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


with TestClient(app) as c:
    admin = login(c, "admin@test.com", "admin-pass-123")
    seller_id = c.post("/api/users", headers=admin, json={"name": "Ana", "email": "a@t.com", "password": "seller-pass-123",
                                                          "role": "seller"}).json()["id"]
    seller = login(c, "a@t.com", "seller-pass-123")
    mine = c.post("/api/customers", headers=seller, json={"name": "Loja da Ana", **FULL}).json()

    # registering still needs everything, admin included
    assert c.post("/api/customers", headers=admin, json={"name": "Nova", **BLANK}).status_code == 422

    # admin: blanks are saved as empty, filled fields are still formatted
    r = c.put(f"/api/customers/{mine['id']}", headers=admin, json={"name": "Loja da Ana", **BLANK, "phone": "54 3333 4444",
                                                                    "owner_id": None})
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["phone"] == "(54) 3333-4444" and got["owner_id"] is None
    assert all(got[k] is None for k in ("document", "email", "city", "state", "address", "state_registration")), got
    # ...but the name is required, and a filled-in e-mail must still be valid
    assert c.put(f"/api/customers/{mine['id']}", headers=admin, json={"name": "", **BLANK}).status_code == 422
    assert c.put(f"/api/customers/{mine['id']}", headers=admin, json={"name": "Loja", **BLANK, "email": "x"}).status_code == 400

    # seller: every field still required on edit
    c.put(f"/api/customers/{mine['id']}", headers=admin, json={"name": "Loja da Ana", **FULL, "owner_id": seller_id})
    r = c.put(f"/api/customers/{mine['id']}", headers=seller, json={"name": "Loja da Ana", **FULL, "state_registration": ""})
    assert r.status_code == 422 and r.json()["detail"][0]["loc"] == ["state_registration"], r.text
    assert c.put(f"/api/customers/{mine['id']}", headers=seller, json={"name": "Loja da Ana", **BLANK}).status_code == 422
    assert c.put(f"/api/customers/{mine['id']}", headers=seller, json={"name": "Loja da Ana", **FULL}).status_code == 200

print("customer admin edit OK")
