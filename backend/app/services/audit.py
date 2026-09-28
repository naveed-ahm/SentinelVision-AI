"""Audit-trail helper."""
from fastapi import Request
from sqlalchemy.orm import Session

from app.models.system import AuditLog


def audit(db: Session, request: Request | None, user, action: str, resource: str = "", detail: str = "") -> None:
    """Record an audit entry. Never raises — auditing must not break requests."""
    try:
        entry = AuditLog(
            user_id=getattr(user, "id", None),
            username=getattr(user, "username", "system"),
            action=action,
            resource=resource[:120],
            detail=detail[:2000],
            ip_address=(request.client.host if request and request.client else ""),
        )
        db.add(entry)
        db.commit()
    except Exception:  # pragma: no cover
        db.rollback()
