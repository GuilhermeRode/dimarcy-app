from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db
from .models import User

bearer = HTTPBearer(auto_error=False)
MIN_PASSWORD_LENGTH = 10

_hasher = PasswordHasher()
# Hashes created before the Argon2 switch are bcrypt ($2a$/$2b$/$2y$, 60 chars) —
# still verified below, and transparently upgraded to Argon2 on next login (see
# needs_rehash + its call site in routers/auth.py's login endpoint).
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, hash_: str) -> bool:
    if hash_.startswith(_BCRYPT_PREFIXES):
        return bcrypt.checkpw(password.encode(), hash_.encode())
    try:
        return _hasher.verify(hash_, password)
    except VerifyMismatchError:
        return False


def needs_rehash(hash_: str) -> bool:
    if hash_.startswith(_BCRYPT_PREFIXES):
        return True
    return _hasher.check_needs_rehash(hash_)


def create_token(user_id: int) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=settings.token_expire_minutes)
    return jwt.encode({"sub": str(user_id), "exp": exp}, settings.secret_key, algorithm="HS256")


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    error = HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired. Please log in again.")
    if not cred:
        raise error
    try:
        payload = jwt.decode(cred.credentials, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise error
    user = db.get(User, int(payload["sub"]))
    if not user or not user.active:
        raise error
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only administrators can do this.")
    return user
