import hashlib
import secrets
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..mailer import send_password_reset_email
from ..models import User
from ..schemas import ForgotPasswordIn, LoginIn, ProfileIn, ResetPasswordIn, TokenOut, UserOut
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


# "Forgot password" throttling — same shape as the login one above, kept separate
# so a burst of reset requests can't also lock someone out of logging in.
RESET_TOKEN_MINUTES = 30
MAX_RESET_REQUESTS = 3
RESET_BLOCK_SECONDS = 15 * 60
_reset_requests: dict[str, list[float]] = {}


def _recent_resets(key: str) -> list[float]:
    now = time.time()
    hits = [t for t in _reset_requests.get(key, []) if now - t < RESET_BLOCK_SECONDS]
    _reset_requests[key] = hits
    return hits


@router.post("/forgot-password")
def forgot_password(data: ForgotPasswordIn, request: Request, db: Session = Depends(get_db)):
    email = data.email.strip().lower()
    ip = request.client.host if request.client else "unknown"
    # Always the same response, whether the e-mail exists, is inactive, or we're throttling —
    # never let an attacker learn which accounts exist.
    generic = {"detail": "Se esse e-mail existir, enviamos um link para redefinir a senha."}
    if len(_recent_resets(f"email:{email}")) >= MAX_RESET_REQUESTS or \
            len(_recent_resets(f"ip:{ip}")) >= MAX_RESET_REQUESTS:
        return generic
    _reset_requests.setdefault(f"email:{email}", []).append(time.time())
    _reset_requests.setdefault(f"ip:{ip}", []).append(time.time())
    user = db.query(User).filter(User.email == email).first()
    if user and user.active:
        token = secrets.token_urlsafe(32)
        user.reset_token_hash = hashlib.sha256(token.encode()).hexdigest()
        user.reset_token_expires_at = datetime.utcnow() + timedelta(minutes=RESET_TOKEN_MINUTES)
        db.commit()
        reset_url = f"{settings.frontend_url.rstrip('/')}/#/reset-password?token={token}"
        send_password_reset_email(user.email, reset_url)
    return generic


@router.post("/reset-password")
def reset_password(data: ResetPasswordIn, db: Session = Depends(get_db)):
    if len(data.new_password) < 6:
        raise HTTPException(400, "The password must be at least 6 characters long.")
    token_hash = hashlib.sha256(data.token.encode()).hexdigest()
    user = db.query(User).filter(User.reset_token_hash == token_hash).first()
    if not user or not user.reset_token_expires_at or user.reset_token_expires_at < datetime.utcnow():
        raise HTTPException(400, "Link inválido ou expirado.")
    user.password_hash = hash_password(data.new_password)
    user.reset_token_hash = None
    user.reset_token_expires_at = None
    db.commit()
    return {"detail": "Senha redefinida com sucesso."}


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
