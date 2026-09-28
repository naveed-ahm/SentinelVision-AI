"""User management (admin only)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, hash_password, require_admin
from app.models.user import User
from app.schemas.schemas import UserCreate, UserOut, UserUpdate
from app.services.audit import audit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return db.query(User).order_by(User.username).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    request: Request = None,
):
    if db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(409, "Username already exists")
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(409, "Email already exists")
    u = User(
        username=payload.username,
        email=payload.email,
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    audit(db, request, user, "user.create", u.username, f"role={u.role}")
    return u


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    request: Request = None,
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        u.hashed_password = hash_password(data.pop("password"))
    if "role" in data and u.id == user.id and data["role"] != "admin":
        raise HTTPException(400, "You cannot demote your own admin account")
    for k, v in data.items():
        setattr(u, k, v)
    db.commit()
    db.refresh(u)
    audit(db, request, user, "user.update", u.username, ",".join(data.keys()))
    return u


@router.delete("/{user_id}", status_code=204)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    request: Request = None,
):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")
    if u.id == user.id:
        raise HTTPException(400, "You cannot delete your own account")
    audit(db, request, user, "user.delete", u.username)
    db.delete(u)
    db.commit()
