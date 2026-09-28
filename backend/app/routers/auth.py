"""Authentication endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user, verify_password
from app.models.user import User
from app.schemas.schemas import Token, UserOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request: Request = None,
):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        audit(db, request, None, "login.failed", form.username, "invalid credentials")
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    token = create_access_token(user.username, {"role": user.role})
    audit(db, request, user, "login.success", user.username, "JWT issued")
    return Token(
        access_token=token,
        role=user.role,
        username=user.username,
        full_name=user.full_name or "",
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/logout")
def logout(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Stateless JWT: the client discards the token; audit the event.
    audit(db, request, user, "logout", user.username)
    return {"detail": "logged out"}
