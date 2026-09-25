import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Color, OrderItem, Product
from ..schemas import ProductIn, ProductOut
from ..security import get_current_user
from ..uploads import read_validated_image

router = APIRouter(prefix="/products", tags=["products"], dependencies=[Depends(get_current_user)])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "products"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _apply(p: Product, data: ProductIn, db: Session):
    p.reference = data.reference.strip()
    p.description = data.description.strip()
    p.collection = data.collection
    p.price = data.price
    p.sizes = ",".join(t.strip().upper() for t in data.sizes if t.strip())
    p.active = data.active
    p.colors = db.query(Color).filter(Color.id.in_(data.color_ids)).all() if data.color_ids else []


@router.get("", response_model=list[ProductOut])
def list_all(search: str = "", active_only: bool = False, db: Session = Depends(get_db)):
    q = db.query(Product)
    if search:
        t = f"%{search}%"
        q = q.filter(or_(Product.reference.ilike(t), Product.description.ilike(t), Product.collection.ilike(t)))
    if active_only:
        q = q.filter(Product.active.is_(True))
    return q.order_by(Product.reference).all()


@router.get("/{pid}", response_model=ProductOut)
def get(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found.")
    return p


@router.post("", response_model=ProductOut, status_code=201)
def create(data: ProductIn, db: Session = Depends(get_db)):
    if db.query(Product).filter(Product.reference == data.reference.strip()).first():
        raise HTTPException(400, "A product with this reference already exists.")
    p = Product()
    _apply(p, data, db)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.put("/{pid}", response_model=ProductOut)
def update(pid: int, data: ProductIn, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found.")
    _apply(p, data, db)
    db.commit()
    db.refresh(p)
    return p


@router.post("/{pid}/image", response_model=ProductOut)
def upload_image(pid: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found.")
    content = read_validated_image(file)

    old_path = None
    if p.image_url:
        old_path = UPLOAD_DIR / Path(p.image_url).name

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{pid}_{uuid.uuid4().hex}{ext}"
    with open(UPLOAD_DIR / filename, "wb") as out:
        out.write(content)

    p.image_url = f"/uploads/products/{filename}"
    db.commit()
    db.refresh(p)

    if old_path and old_path.exists():
        old_path.unlink(missing_ok=True)
    return p


@router.delete("/{pid}/image", response_model=ProductOut)
def remove_image(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found.")
    if p.image_url:
        old_path = UPLOAD_DIR / Path(p.image_url).name
        old_path.unlink(missing_ok=True)
        p.image_url = None
        db.commit()
        db.refresh(p)
    return p


@router.delete("/{pid}", status_code=204)
def delete(pid: int, db: Session = Depends(get_db)):
    p = db.get(Product, pid)
    if not p:
        raise HTTPException(404, "Product not found.")
    if db.query(OrderItem).filter(OrderItem.product_id == pid).first():
        raise HTTPException(400, "This product is already used in orders. Deactivate it instead of deleting.")
    db.delete(p)
    db.commit()
