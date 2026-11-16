from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import jwt

from app.core.config import settings

# Using the bcrypt library directly: passlib is unmaintained and crashes with
# bcrypt >= 4.1 ("module 'bcrypt' has no attribute '__about__'" / 72-byte errors).


def _prep(password: str) -> bytes:
    # bcrypt only uses the first 72 bytes; truncate explicitly so long
    # passwords never raise.
    return password.encode("utf-8")[:72]


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_prep(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str | int, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return jwt.encode({"exp": expire, "sub": str(subject)}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
