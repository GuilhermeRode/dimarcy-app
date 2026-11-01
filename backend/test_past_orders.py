"""Past-orders import self-check (scripts/importar_pedidos_anteriores.py) against a database whose schema
the app itself created, plus the customer panel's overview. Run from backend/:  python test_past_orders.py
Uses a throwaway SQLite file, never dimarcy.db."""
import glob
import importlib.util
import os
import sqlite3
import tempfile

tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "dimarcy.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

con = sqlite3.connect(db)
with TestClient(app):  # the app creates the real schema
    pass
con.execute("INSERT INTO customers (name, city) VALUES ('Loja Dudi', 'Rodeio'), ('Telma', 'Palmeira'),"
            " ('Telma', 'Irati'), ('Vivi&ana', 'Rio Negrinho')")
con.commit()

spec = importlib.util.spec_from_file_location("imp", os.path.join("scripts", "importar_pedidos_anteriores.py"))
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def write(lines):
    path = os.path.join(tmp, "pedidos.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("data;cliente;cidade;valor\n" + "\n".join(lines) + "\n")
    return path


def count():
    try:
        return con.execute("SELECT count(*) FROM past_orders").fetchone()[0]
    except sqlite3.OperationalError:
        return None


good = write(["2026-01-27;LOJA  DUDI;Rodeio;15196.7", "2026-05-12;Télma;Palmeira;2378.8",
              "2026-06-01;Telma;Palmeira;100", "2025-11-05;Vivi&ana;Rio Negrinho;11220.96"])
importer.main([good, "--db", db])  # dry run: writes nothing, no backup
assert count() == 0 and not glob.glob(db + ".bak-*")

importer.main([good, "--db", db, "--apply"])
importer.main([good, "--db", db, "--apply"])  # running again replaces, never duplicates
assert count() == 4 and len(glob.glob(db + ".bak-*")) >= 1

# unknown customer or an ambiguous name with an unknown city: stops, keeps what's there
for bad in ("2026-01-01;Ninguém;Lugar;10", "2026-01-01;Telma;Curitiba;10"):
    try:
        importer.main([write([bad]), "--db", db, "--apply"])
        raise AssertionError("should have stopped")
    except SystemExit as e:
        assert e.code == 1
    assert count() == 4

# a reviewed cliente_id wins over the name; an unknown id stops everything
path = os.path.join(tmp, "ids.csv")
with open(path, "w", encoding="utf-8") as f:
    f.write("data;cliente;cidade;valor;cliente_id\n2026-01-01;Apelido;;50;1\n2026-01-02;Telma;Palmeira;10;\n")
found, problems = importer.match(importer.read_csv(path), con.execute("SELECT id, name, city FROM customers").fetchall())
assert found == [(1, "2026-01-01", 50.0), (2, "2026-01-02", 10.0)] and not problems
assert importer.match([("2026-01-01", "X", "", 1.0, 99)], [(1, "A", "")])[1]

with TestClient(app) as c:
    r = c.post("/api/auth/login", json={"email": "admin@test.com", "password": "admin-pass-123"})
    h = {"Authorization": "Bearer " + r.json()["access_token"]}
    rows = {(x["name"], x["city"]): x for x in c.get("/api/customers/overview", headers=h).json()}
    telma = rows[("Telma", "Palmeira")]
    assert telma["past_orders"] == [{"date": "2026-06-01", "amount": 100.0}, {"date": "2026-05-12", "amount": 2378.8}]
    assert telma["total"] == 0 and telma["orders"] == 0  # kept out of the app's own numbers
    assert rows[("Telma", "Irati")]["past_orders"] == []
    assert telma["last_order_date"] == "2026-06-01"  # no app order: the last past purchase counts
    assert telma["status"] == "inactive"  # only app orders make a customer active (same as the map)
    assert rows[("Telma", "Irati")]["last_order_date"] is None and rows[("Telma", "Irati")]["status"] == "inactive"
    dudi = rows[("Loja Dudi", "Rodeio")]
    assert c.delete(f"/api/customers/{dudi['id']}", headers=h).status_code == 400  # history blocks delete

print("ok")
