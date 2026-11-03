"""Batches (lotes) self-check: orders join a batch and follow its column, moving the batch moves them,
an order moved on its own leaves it, deleting the batch only ungroups. Run from backend/:  python test_batches.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import sqlite3
import tempfile

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="", CHECK_EMAIL_DNS="false")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

with TestClient(app) as c:
    con = sqlite3.connect(db_file)
    con.execute("INSERT INTO customers (name, city) VALUES ('Loja A', 'Rodeio')")
    for status in ("confirmed", "confirmed", "quote"):
        con.execute("INSERT INTO orders (customer_id, seller_id, date, delivery_date, status, price_table, discount,"
                    " notify_customer) VALUES (1, 1, '2026-11-01', '2026-12-01', ?, 'wholesale', 0, 1)", (status,))
    con.commit()

    r = c.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin-pass-123"})
    H = {"Authorization": "Bearer " + r.json()["access_token"]}

    def order(oid):
        return c.get(f"/api/orders/{oid}", headers=H).json()

    b = c.post("/api/batches", headers=H, json={"name": "Lote 12/11"}).json()
    assert b["status"] == "in_production"

    for oid in (1, 2):  # joining takes the batch's column
        assert c.put(f"/api/orders/{oid}/batch", headers=H, json={"batch_id": b["id"]}).status_code == 200
    assert order(1)["status"] == "in_production" and order(1)["batch_name"] == "Lote 12/11"
    assert order(3)["batch_id"] is None and order(3)["status"] == "quote"

    c.patch(f"/api/batches/{b['id']}", headers=H, json={"status": "shipped"})  # the whole batch moves
    assert order(1)["status"] == order(2)["status"] == "shipped"

    c.patch("/api/orders/2/status", headers=H, json={"status": "in_production"})  # moved alone: leaves the batch
    assert order(2)["batch_id"] is None and order(1)["batch_id"] == b["id"]

    assert c.delete(f"/api/batches/{b['id']}", headers=H).status_code == 204  # ungroup only
    assert order(1)["batch_id"] is None and order(1)["status"] == "shipped"
    assert c.get("/api/batches", headers=H).json() == []

    assert c.put("/api/orders/1/batch", headers=H, json={"batch_id": 999}).status_code == 404
    assert c.post("/api/batches", headers=H, json={"name": ""}).status_code == 422

print("ok")
