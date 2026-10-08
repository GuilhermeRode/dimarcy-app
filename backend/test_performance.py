"""List endpoints must not run one query per row. Run from backend/:  python test_performance.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import random
import tempfile
from datetime import date, timedelta

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Color, Customer, Order, OrderItem, Product, User  # noqa: E402

random.seed(1)
queries = 0


@event.listens_for(engine, "before_cursor_execute")
def _count(*_):
    global queries
    queries += 1


with TestClient(app) as c:
    with SessionLocal() as db:
        sellers = [User(name=f"Vendedor {i}", email=f"v{i}@t.com", password_hash="x", role="seller") for i in range(4)]
        colors = [Color(name=f"Cor {i}", hex="#cccccc") for i in range(10)]
        db.add_all(sellers + colors)
        db.flush()
        products = [Product(reference=f"R{i}", description=f"P{i}", price=100, sizes="M", colors=colors) for i in range(20)]
        customers = [Customer(name=f"Cliente {i}", document="1", city=f"Cidade {i % 10}", state="SC",
                              owner_id=sellers[i % 4].id) for i in range(60)]
        db.add_all(products + customers)
        db.flush()
        for _ in range(300):
            cust = random.choice(customers)
            o = Order(customer_id=cust.id, seller_id=cust.owner_id, date=date.today() - timedelta(days=random.randint(0, 300)),
                      delivery_date=date.today(), status=random.choice(["confirmed", "delivered", "quote"]),
                      payment_method="PIX", payment_terms="30", discount=0)
            o.items = [OrderItem(product_id=random.choice(products).id, color_id=random.choice(colors).id,
                                 size="M", quantity=2, unit_price=100) for _ in range(3)]
            db.add(o)
        db.commit()

    h = {"Authorization": "Bearer " + c.post("/api/auth/login", json={
        "email": "admin@test.com", "password": "admin-pass-123"}).json()["access_token"]}

    # 300 orders, 60 customers, 20 products: each list must stay at a fixed handful of queries
    # (the dashboard runs ~20 distinct ones; one query per row would be 60+ here)
    LIMIT = 25
    for path in ("/api/orders", "/api/dashboard", "/api/customers", "/api/customers/overview",
                 "/api/customers/by-city", "/api/products"):
        queries = 0
        r = c.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
        assert queries <= LIMIT, f"{path}: {queries} queries (one per row?)"
        print(f"{path:26} {queries:3} queries")

print("performance checks OK")
