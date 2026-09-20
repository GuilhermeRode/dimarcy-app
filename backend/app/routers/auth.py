import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginIn, ProfileIn, TokenOut, UserOut
from ..security import create_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

AVATAR_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
THEMES = {"light", "dark"}


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == data.email.strip().lower()).first()
    if not u or not u.active or not verify_password(data.password, u.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    return TokenOut(access_token=create_token(u.id), user=UserOut.model_validate(u))


@router.get("/me", response_model=UserOut)
def me(u: User = Depends(get_current_user)):
    return u


@router.put("/me", response_model=UserOut)
def update_me(data: ProfileIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    email = data.email.strip().lower()
    changing_password = bool(data.new_password)
    if (email != user.email or changing_password) and not (
        data.current_password and verify_password(data.current_password, user.password_hash)
    ):
        raise HTTPException(400, "Senha atual incorreta.")
    if email != user.email and db.query(User).filter(User.email == email, User.id != user.id).first():
        raise HTTPException(400, "A user with this email already exists.")

    user.name = data.name.strip()
    user.email = email
    if changing_password:
        if len(data.new_password) < 6:
            raise HTTPException(400, "The password must be at least 6 characters long.")
        user.password_hash = hash_password(data.new_password)
    if data.theme in THEMES:
        user.theme = data.theme
    db.commit()
    db.refresh(user)
    return user


@router.post("/me/avatar", response_model=UserOut)
def upload_avatar(file: UploadFile = File(...), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(400, "Send an image file (JPEG, PNG, WEBP or GIF).")
    old_path = AVATAR_DIR / Path(user.avatar_url).name if user.avatar_url else None

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
    with open(AVATAR_DIR / filename, "wb") as out:
        out.write(file.file.read())

    user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(user)

    if old_path and old_path.exists():
        old_path.unlink(missing_ok=True)
    return user


@router.delete("/me/avatar", response_model=UserOut)
def remove_avatar(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.avatar_url:
        (AVATAR_DIR / Path(user.avatar_url).name).unlink(missing_ok=True)
        user.avatar_url = None
        db.commit()
        db.refresh(user)
    return user
