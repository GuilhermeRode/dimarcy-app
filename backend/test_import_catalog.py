"""Catalog import self-check. Run from backend/:  python test_import_catalog.py
Uses a throwaway SQLite file, never dimarcy.db."""
import os
import tempfile

db_file = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update(DATABASE_URL=f"sqlite:///{db_file}", ADMIN_EMAIL="admin@test.com",
                  ADMIN_PASSWORD="admin-pass-123", RESEND_API_KEY="")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.import_catalog import run  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Color, Product  # noqa: E402

with TestClient(app):  # creates the tables
    pass

with SessionLocal() as db:  # what production already has
    bordo, preto = Color(name="Bordô", hex="#6b1e2e"), Color(name="PRETO", hex="#000000")
    db.add_all([bordo, preto, Product(reference="555", description="Antiga", price=10, sizes="U", colors=[bordo])])
    db.commit()

DATA = {
    "colors": [{"name": "Preto", "hex": "#1b1b1f"}, {"name": "Caramelo", "hex": "#b9783f"}],
    "products": [
        {"reference": "555", "description": "Blusa  decote V ", "price": 49.8, "sizes": ["P", "M", "G", "GG", "XGG"]},
        {"reference": 1113, "description": "Calça Barra italiana", "price": 129.9, "sizes": ["p", "m"]},
    ],
}


def snapshot():
    with SessionLocal() as db:
        return ({c.name: c.hex for c in db.query(Color)},
                {p.reference: (p.description, float(p.price), p.sizes, sorted(c.name for c in p.colors))
                 for p in db.query(Product)})


before = snapshot()

# dry run: reports, writes nothing
with SessionLocal() as db:
    assert run(DATA, db, apply=False) == {"colors_created": 1, "colors_existing": 1,
                                          "products_created": 1, "products_updated": 1}
assert snapshot() == before

# apply
with SessionLocal() as db:
    run(DATA, db, apply=True)
colors, products = snapshot()
assert colors == {"Bordô": "#6b1e2e", "PRETO": "#000000", "Caramelo": "#b9783f"}  # "Preto" matched "PRETO"
assert products["555"] == ("Blusa decote V", 49.8, "P,M,G,GG,XGG", ["Bordô", "Caramelo", "PRETO"])  # old color kept
assert products["1113"] == ("Calça Barra italiana", 129.9, "P,M", ["Caramelo", "PRETO"])

# running again changes nothing and duplicates nothing
with SessionLocal() as db:
    assert run(DATA, db, apply=True) == {"colors_existing": 2, "products_updated": 2}
assert snapshot() == (colors, products)

# bad rows are rejected before anything is written
for bad in ({"reference": "9", "description": "X", "price": -1, "sizes": ["P"]},
            {"reference": "9", "description": "", "price": 1, "sizes": ["P"]},
            {"reference": "9", "description": "X", "price": 1, "sizes": []},
            {"reference": "", "description": "X", "price": 1, "sizes": ["P"]}):
    with SessionLocal() as db:
        try:
            run({"colors": [], "products": [bad]}, db, apply=True)
            raise AssertionError(f"accepted {bad}")
        except ValueError:
            pass
assert snapshot() == (colors, products)

print("import checks OK")
