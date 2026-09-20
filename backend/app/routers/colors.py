from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Color, OrderItem
from ..schemas import ColorIn, ColorOut
from ..security import get_current_user

router = APIRouter(prefix="/colors", tags=["colors"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[ColorOut])
def list_all(db: Session = Depends(get_db)):
    return db.query(Color).order_by(Color.name).all()


@router.post("", response_model=ColorOut, status_code=201)
def create(data: ColorIn, db: Session = Depends(get_db)):
    if db.query(Color).filter(Color.name.ilike(data.name)).first():
        raise HTTPException(400, "A color with this name already exists.")
    c = Color(**data.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.put("/{cid}", response_model=ColorOut)
def update(cid: int, data: ColorIn, db: Session = Depends(get_db)):
    c = db.get(Color, cid)
    if not c:
        raise HTTPException(404, "Color not found.")
    c.name, c.hex = data.name, data.hex
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{cid}", status_code=204)
def delete(cid: int, db: Session = Depends(get_db)):
    c = db.get(Color, cid)
    if not c:
        raise HTTPException(404, "Color not found.")
    if db.query(OrderItem).filter(OrderItem.color_id == cid).first():
        raise HTTPException(400, "This color has already been used in orders and cannot be deleted.")
    db.delete(c)
    db.commit()
