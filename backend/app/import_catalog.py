"""Imports a product catalog (references, descriptions, prices, sizes) and its colors from a JSON
file into the current database (DATABASE_URL / .env). Safe to run more than once: products are
matched by reference and colors by name (case-insensitive), so nothing is duplicated. Every
product gets every color of the file; colors a product already had are kept.

The data file is not versioned (the repository is public), only this script.

Usage, from backend/:
    python -m app.import_catalog catalogo.json            # dry run: reports, writes nothing
    python -m app.import_catalog catalogo.json --apply    # writes

JSON: {"colors":   [{"name": "Preto", "hex": "#1b1b1f"}],
       "products": [{"reference": "555", "description": "Blusa decote V", "price": 49.8,
                     "sizes": ["P", "M", "G"]}]}
"""
import json
import re
import sys
from collections import Counter

from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import SessionLocal
from .models import Color, Product

HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _clean(text) -> str:
    return " ".join(str(text or "").split())


def _validate(data: dict) -> None:
    for c in data["colors"]:
        if not _clean(c.get("name")) or not HEX.match(c.get("hex") or "#cccccc"):
            raise ValueError(f"Cor inválida: {c}")
    for p in data["products"]:
        sizes = [s for s in p.get("sizes", []) if _clean(s)]
        if (not _clean(p.get("reference")) or not _clean(p.get("description")) or not sizes
                or float(p.get("price", -1)) < 0 or any(len(_clean(s)) > 5 for s in sizes)):
            raise ValueError(f"Produto inválido: {p}")


def run(data: dict, db: Session, apply: bool) -> dict:
    _validate(data)  # all or nothing: a bad row stops the import before any write
    stats: Counter[str] = Counter()

    colors = []
    for c in data["colors"]:
        name = _clean(c["name"])
        color = db.query(Color).filter(func.lower(Color.name) == name.lower()).first()
        if color is None:
            color = Color(name=name, hex=c.get("hex") or "#cccccc")
            db.add(color)
            stats["colors_created"] += 1
        else:
            stats["colors_existing"] += 1
        colors.append(color)

    for p in data["products"]:
        ref = _clean(p["reference"])
        product = db.query(Product).filter(Product.reference == ref).first()
        if product is None:
            product = Product(reference=ref)
            db.add(product)
            stats["products_created"] += 1
        else:
            stats["products_updated"] += 1
        product.description = _clean(p["description"])
        product.price = round(float(p["price"]), 2)
        product.sizes = ",".join(_clean(s).upper() for s in p["sizes"] if _clean(s))
        product.active = True
        keep = {id(c): c for c in [*product.colors, *colors]}  # old colors stay, new ones are added
        product.colors = list(keep.values())

    if apply:
        db.commit()
    else:
        db.rollback()
    return dict(stats)


def main(argv: list[str]) -> None:
    if not argv or argv[0].startswith("-"):
        sys.exit(__doc__)
    with open(argv[0], encoding="utf-8") as f:
        data = json.load(f)
    apply = "--apply" in argv
    with SessionLocal() as db:
        stats = run(data, db, apply)
    print(f"Cores: {stats.get('colors_created', 0)} novas, {stats.get('colors_existing', 0)} já existiam")
    print(f"Produtos: {stats.get('products_created', 0)} novos, {stats.get('products_updated', 0)} atualizados")
    print("Gravado." if apply else "Simulação: nada foi gravado. Rode de novo com --apply para gravar.")


if __name__ == "__main__":
    main(sys.argv[1:])
