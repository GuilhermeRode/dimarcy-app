import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import LoginIn, ProfileIn, TokenOut, UserOut
from ..security import create_token, get_current_user, hash_password, verify_password
from ..uploads import read_validated_image

router = APIRouter(prefix="/auth", tags=["auth"])

AVATAR_DIR = Path(__file__).resolve().parent.parent.parent / "uploads" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
THEMES = {"light", "dark"}

# Login throttling: in-memory per-process, so it resets on restart and isn't
# shared across multiple backend instances — fine at this app's scale (a
# single server). A multi-instance deploy would need a shared store instead.
MAX_LOGIN_ATTEMPTS = 5
LOGIN_BLOCK_SECONDS = 15 * 60
_login_failures: dict[str, list[float]] = {}


def _recent_failures(key: str) -> list[float]:
    now = time.time()
    hits = [t for t in _login_failures.get(key, []) if now - t < LOGIN_BLOCK_SECONDS]
    _login_failures[key] = hits
    return hits


def _register_login_failure(email: str, ip: str) -> None:
    now = time.time()
    _login_failures.setdefault(f"email:{email}", []).append(now)
    _login_failures.setdefault(f"ip:{ip}", []).append(now)


def _clear_login_failures(email: str, ip: str) -> None:
    _login_failures.pop(f"email:{email}", None)
    _login_failures.pop(f"ip:{ip}", None)


@router.post("/login", response_model=TokenOut)
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    if len(_recent_failures(f"email:{email}")) >= MAX_LOGIN_ATTEMPTS or \
            len(_recent_failures(f"ip:{ip}")) >= MAX_LOGIN_ATTEMPTS:
        raise HTTPException(429, "Muitas tentativas. Tente novamente em alguns minutos.")
    u = db.query(User).filter(User.email == email).first()
    if not u or not u.active or not verify_password(data.password, u.password_hash):
        _register_login_failure(email, ip)
        print(f"[auth] Failed login attempt for {email} from {ip}")
        raise HTTPException(401, "Incorrect email or password.")
    _clear_login_failures(email, ip)
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
    content = read_validated_image(file)
    old_path = AVATAR_DIR / Path(user.avatar_url).name if user.avatar_url else None

    ext = Path(file.filename or "").suffix.lower() or ".jpg"
    filename = f"{user.id}_{uuid.uuid4().hex}{ext}"
    with open(AVATAR_DIR / filename, "wb") as out:
        out.write(content)

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
