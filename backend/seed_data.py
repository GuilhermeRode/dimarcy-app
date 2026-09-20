"""Seeds colors and references from the Winter 2027 collection (price zeroed: adjust in the system).
Usage: python seed_data.py"""
from app.database import Base, SessionLocal, engine
from app.models import Color, Product

COLORS = [("Natural", "#EDE6D8"), ("Marrom", "#6B4535"), ("Marinho", "#1F2A48"),
          ("Bordô", "#7E1F3B"), ("Oliva", "#8A8563"), ("Mescla", "#C9C6C0"), ("Chocolate", "#4A2E28")]

PRODUCTS = [
    ("000045", "Blusão de tricot xadrez"),
    ("000046", "Conjunto cardigan com blusa"),
    ("000048", "Blusa gola polo listrada"),
    ("000049", "Blusa gola polo com cordão"),
    ("000051", "Blusão gola alta"),
    ("000052", "Blusão gola alta com pontos trança"),
    ("000054", "Blusa com abertura nas laterais"),
]

Base.metadata.create_all(engine)
with SessionLocal() as db:
    for name, hx in COLORS:
        if not db.query(Color).filter_by(name=name).first():
            db.add(Color(name=name, hex=hx))
    db.commit()
    all_colors = db.query(Color).all()
    for ref, desc in PRODUCTS:
        if not db.query(Product).filter_by(reference=ref).first():
            db.add(Product(reference=ref, description=desc, collection="Inverno 2027", price=0, colors=all_colors))
    db.commit()
print("Done.")
