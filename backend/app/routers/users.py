from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserIn, UserOut
from ..security import hash_password, require_admin

router = APIRouter(prefix="/users", tags=["users"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[UserOut])
def list_all(db: Session = Depends(get_db)):
    return db.query(User).order_by(User.name).all()


@router.post("", response_model=UserOut, status_code=201)
def create(data: UserIn, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(400, "A user with this email already exists.")
    if not data.password or len(data.password) < 6:
        raise HTTPException(400, "The password must be at least 6 characters long.")
    u = User(name=data.name, email=email, role=data.role, active=data.active,
              password_hash=hash_password(data.password))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@router.put("/{uid}", response_model=UserOut)
def update(uid: int, data: UserIn, db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User not found.")
    u.name, u.email, u.role, u.active = data.name, data.email.strip().lower(), data.role, data.active
    if data.password:
        if len(data.password) < 6:
            raise HTTPException(400, "The password must be at least 6 characters long.")
        u.password_hash = hash_password(data.password)
    db.commit()
    db.refresh(u)
    return u
