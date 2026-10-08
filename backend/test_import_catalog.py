"""Catalog import self-check (scripts/importar_catalogo.py) against a database whose schema the app
itself created. Run from backend/:  python test_import_catalog.py
Uses a throwaway SQLite file, never dimarcy.db."""
import glob
import importlib.util
import json
import os
import sqlite3
import tempfile

tmp = tempfile.mkdtemp()
db = os.path.join(tmp, "dimarcy.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

with TestClient(app):  # the app creates the real schema
    pass

con = sqlite3.connect(db)  # what production already has
con.execute("INSERT INTO colors (name, hex) VALUES ('PRETO', '#000000'), ('Bordô', '#6b1e2e')")
con.execute("INSERT INTO products (reference, description, price, sizes, active) VALUES ('555', 'Antiga', 10, 'U', 1)")
con.execute("INSERT INTO product_color VALUES ((SELECT id FROM products WHERE reference = '555'),"
            " (SELECT id FROM colors WHERE name = 'Bordô'))")
con.commit()
con.close()

spec = importlib.util.spec_from_file_location("importar_catalogo", os.path.join("scripts", "importar_catalogo.py"))
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)


def write(name, data):
    path = os.path.join(tmp, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return path


catalog = write("catalogo.json", {
    "colors": [{"name": "Preto", "hex": "#1b1b1f"}, {"name": "Caramelo", "hex": "#b9783f"}],
    "products": [
        {"reference": "555", "description": "Blusa  decote V ", "price": 49.8, "sizes": ["P", "M", "G", "GG", "XGG"]},
        {"reference": 1113, "description": "Calça Barra italiana", "price": 129.9, "sizes": ["p", "m"]},
    ],
})


def snapshot():
    c = sqlite3.connect(db)
    colors = dict(c.execute("SELECT name, hex FROM colors"))
    products = {ref: (desc, price, sizes) for ref, desc, price, sizes
                in c.execute("SELECT reference, description, price, sizes FROM products")}
    links = {ref: sorted(n for (n,) in c.execute(
        "SELECT colors.name FROM product_color JOIN colors ON colors.id = color_id"
        " JOIN products ON products.id = product_id WHERE reference = ?", (ref,))) for ref in products}
    c.close()
    return colors, products, links


before = snapshot()
importer.main([catalog, "--db", db])  # dry run: reports, writes nothing, no backup
assert snapshot() == before
assert not glob.glob(db + ".bak-*")

importer.main([catalog, "--db", db, "--apply"])
colors, products, links = snapshot()
assert colors == {"PRETO": "#000000", "Bordô": "#6b1e2e", "Caramelo": "#b9783f"}  # "Preto" reused "PRETO"
assert products == {"555": ("Blusa decote V", 49.8, "P,M,G,GG,XGG"), "1113": ("Calça Barra italiana", 129.9, "P,M")}
assert links == {"555": ["Bordô", "Caramelo", "PRETO"], "1113": ["Caramelo", "PRETO"]}  # old color kept
assert len(glob.glob(db + ".bak-*")) == 1  # safety copy before writing

importer.main([catalog, "--db", db, "--apply"])  # running again duplicates nothing
assert snapshot() == (colors, products, links)

# a bad row stops everything, before any backup or write
for bad in ({"reference": "9", "description": "X", "price": -1, "sizes": ["P"]},
            {"reference": "9", "description": "", "price": 1, "sizes": ["P"]},
            {"reference": "9", "description": "X", "price": 1, "sizes": []},
            {"reference": "", "description": "X", "price": 1, "sizes": ["P"]}):
    try:
        importer.main([write("bad.json", {"colors": [], "products": [bad]}), "--db", db, "--apply"])
        raise AssertionError(f"accepted {bad}")
    except ValueError:
        pass
assert snapshot() == (colors, products, links)

# wrong path: clear error, nothing created
try:
    importer.main([catalog, "--db", os.path.join(tmp, "nao-existe.db")])
    raise AssertionError("missing database accepted")
except SystemExit as e:
    assert "não encontrado" in str(e)
assert not os.path.exists(os.path.join(tmp, "nao-existe.db"))

print("import checks OK")
