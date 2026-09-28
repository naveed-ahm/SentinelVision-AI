"""Watchlist endpoints: CRUD for entries of interest + recorded hits + lookup.

New endpoints ONLY. Follows the platform's RBAC conventions:
  - read: any authenticated user
  - create/update/delete: operator and admin (require_operator)
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_operator
from app.models.user import User, utcnow
from app.models.watchlist import WatchlistEntry, WatchlistHit
from app.schemas.schemas import (
    WatchlistEntryCreate,
    WatchlistEntryOut,
    WatchlistEntryUpdate,
    WatchlistHitOut,
)
from app.services.audit import audit
from app.services.watchlist_service import normalize_plate, watchlist_service

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


def _out(db: Session, e: WatchlistEntry) -> WatchlistEntryOut:
    data = WatchlistEntryOut.model_validate(e)
    data.hit_count = db.query(WatchlistHit).filter(WatchlistHit.entry_id == e.id).count()
    return data


@router.get("/status")
def status(_user: User = Depends(get_current_user)):
    return {**watchlist_service.status(), "normalization": "uppercase + alphanumerics only"}


@router.get("", response_model=list[WatchlistEntryOut])
def list_entries(
    category: str | None = None,
    active: bool | None = None,
    q: str | None = Query(None, max_length=64, description="identifier fragment"),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(WatchlistEntry)
    if category:
        query = query.filter(WatchlistEntry.category == category)
    if active is not None:
        query = query.filter(WatchlistEntry.active.is_(active))
    if q:
        frag = normalize_plate(q)
        query = query.filter(WatchlistEntry.identifier_value.like(f"%{frag}%"))
    entries = query.order_by(WatchlistEntry.created_at.desc()).limit(500).all()
    return [_out(db, e) for e in entries]


@router.post("", response_model=WatchlistEntryOut, status_code=201)
def create_entry(
    payload: WatchlistEntryCreate,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    normalized = normalize_plate(payload.identifier_value)
    if len(normalized) < 4:
        raise HTTPException(422, "Identifier must contain at least 4 alphanumeric characters")
    dup = (
        db.query(WatchlistEntry)
        .filter(
            WatchlistEntry.identifier_type == payload.identifier_type,
            WatchlistEntry.identifier_value == normalized,
        )
        .first()
    )
    if dup:
        raise HTTPException(409, f"Entry already exists for '{normalized}' (id {dup.id})")
    entry = WatchlistEntry(
        category=payload.category,
        identifier_type=payload.identifier_type,
        identifier_value=normalized,
        display_value=payload.identifier_value.strip()[:64],
        title=payload.title,
        notes=payload.notes,
        severity=payload.severity,
        active=payload.active,
        expires_at=payload.expires_at,
        created_by=user.id,
        is_demo=False,  # operator-entered data is real data, never demo
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    audit(db, request, user, "watchlist.create", str(entry.id), f"{payload.category}:{normalized}")
    return _out(db, entry)


@router.patch("/{entry_id}", response_model=WatchlistEntryOut)
def update_entry(
    entry_id: int,
    payload: WatchlistEntryUpdate,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    entry = db.get(WatchlistEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Watchlist entry not found")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(entry, field, value)
    entry.updated_at = utcnow()
    db.commit()
    db.refresh(entry)
    audit(db, request, user, "watchlist.update", str(entry.id), ",".join(changes.keys()))
    return _out(db, entry)


@router.delete("/{entry_id}", status_code=204)
def delete_entry(
    entry_id: int,
    request: Request = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    entry = db.get(WatchlistEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Watchlist entry not found")
    audit(db, request, user, "watchlist.delete", str(entry.id), f"{entry.category}:{entry.identifier_value}")
    db.delete(entry)
    db.commit()


@router.get("/hits", response_model=list[WatchlistHitOut])
def list_hits(
    entry_id: int | None = None,
    camera_id: int | None = None,
    acknowledged: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(WatchlistHit)
    if entry_id:
        q = q.filter(WatchlistHit.entry_id == entry_id)
    if camera_id:
        q = q.filter(WatchlistHit.camera_id == camera_id)
    if acknowledged is not None:
        q = q.filter(WatchlistHit.acknowledged.is_(acknowledged))
    return q.order_by(WatchlistHit.timestamp.desc()).limit(limit).all()


@router.post("/hits/{hit_id}/ack", response_model=WatchlistHitOut)
def ack_hit(
    hit_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
):
    hit = db.get(WatchlistHit, hit_id)
    if not hit:
        raise HTTPException(404, "Hit not found")
    hit.acknowledged = True
    db.commit()
    db.refresh(hit)
    return hit


@router.get("/check/{plate}")
def check_plate(
    plate: str,
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Is this plate on the active watchlist? (lookup only — records nothing)"""
    normalized = normalize_plate(plate)
    entries = (
        db.query(WatchlistEntry)
        .filter(
            WatchlistEntry.active.is_(True),
            WatchlistEntry.identifier_type == "plate",
            WatchlistEntry.identifier_value == normalized,
        )
        .all()
    )
    return {
        "plate": normalized,
        "on_watchlist": bool(entries),
        "entries": [
            {
                "id": e.id,
                "category": e.category,
                "title": e.title,
                "severity": e.severity,
                "display_value": e.display_value,
            }
            for e in entries
        ],
    }
