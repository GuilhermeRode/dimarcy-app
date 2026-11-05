"""An existing database with the old seller_cities rule (one seller per city) is migrated at startup to
one row per seller and city, keeping its rows. Run: python test_seller_cities_migration.py"""
import os
import sqlite3
import tempfile

db_file = os.path.join(tempfile.mkdtemp(), "migration.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com", ADMIN_PASSWORD="admin-pass-123")

old = sqlite3.connect(db_file)
old.execute("""CREATE TABLE seller_cities (id INTEGER NOT NULL, user_id INTEGER NOT NULL, city VARCHAR(100) NOT NULL,
    state VARCHAR(2) NOT NULL, city_key VARCHAR(100) NOT NULL, PRIMARY KEY (id),
    CONSTRAINT uq_seller_cities_city UNIQUE (city_key, state), FOREIGN KEY(user_id) REFERENCES users (id))""")
old.execute("INSERT INTO seller_cities VALUES (7, 1, 'Joinville', 'SC', 'joinville')")
old.commit()
old.close()

from fastapi.testclient import TestClient  # noqa: E402  (after DATABASE_URL is set)
from app.main import app  # noqa: E402

for _ in range(2):  # the second startup must leave it alone (idempotent)
    with TestClient(app):
        pass

db = sqlite3.connect(db_file)
ddl = db.execute("SELECT sql FROM sqlite_master WHERE name = 'seller_cities'").fetchone()[0]
assert "uq_seller_cities_city " not in ddl and "uq_seller_cities_user_city" in ddl, ddl
assert db.execute("SELECT id, user_id, city_key FROM seller_cities").fetchall() == [(7, 1, "joinville")]
db.execute("INSERT INTO seller_cities (user_id, city, state, city_key) VALUES (2, 'Joinville', 'SC', 'joinville')")
try:
    db.execute("INSERT INTO seller_cities (user_id, city, state, city_key) VALUES (2, 'Joinville', 'SC', 'joinville')")
    raise AssertionError("the same seller got the same city twice")
except sqlite3.IntegrityError:
    pass
print("seller cities migration OK")
