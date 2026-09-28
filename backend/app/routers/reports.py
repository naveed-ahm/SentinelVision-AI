"""Report generation endpoints (CSV export)."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_operator
from app.models.user import User, utcnow
from app.services.audit import audit
from app.services.report_service import build_csv_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/csv")
def csv_report(
    start: datetime = Query(...),
    end: datetime = Query(...),
    title: str = Query("Operations report"),
    db: Session = Depends(get_db),
    user: User = Depends(require_operator),
    request: Request = None,
):
    if end <= start:
        from fastapi import HTTPException

        raise HTTPException(422, "end must be after start")
    filename, content = build_csv_report(db, start, end, title)
    audit(db, request, user, "report.csv", title, f"{start.isoformat()}..{end.isoformat()}")
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
