from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginIn, TokenOut, UserOut
from ..security import create_token, get_current_user, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not u or not u.active or not verify_password(data.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return TokenOut(access_token=create_token(u.id), user=UserOut.model_validate(u))


@router.get("/me", response_model=UserOut)
def me(u: User = Depends(get_current_user)):
    return u
