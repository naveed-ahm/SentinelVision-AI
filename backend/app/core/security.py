"""Password hashing, JWT creation/validation and RBAC dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except Exception:
        return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": subject, "exp": expire, "iat": datetime.now(timezone.utc)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token") from exc


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    payload = decode_token(token)
    username = payload.get("sub")
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or inactive")
    return user


def get_current_user_flexible(
    request: Request,
    db: Session = Depends(get_db),
    token: str | None = Depends(oauth2_scheme_optional),
) -> User:
    """Like get_current_user but also accepts `?access_token=` in the query.

    Needed for <img src="/streams/N/mjpeg"> tags which cannot set headers.
    Only the stream endpoints use this; keep it out of sensitive routes.
    """
    tok = token or request.query_params.get("access_token")
    if not tok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return get_current_user(token=tok, db=db)


ROLE_LEVELS = {"viewer": 1, "operator": 2, "admin": 3}


def require_roles(*roles: str):
    """Dependency factory: allow only the listed roles (admin always allowed)."""

    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role == "admin" or user.role in roles:
            return user
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")

    return checker


# Convenience dependencies used across routers
require_admin = require_roles()
require_operator = require_roles("operator")
