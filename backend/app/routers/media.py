"""Authenticated media access. Mounted under /media-api (token required)."""
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.security import get_current_user
from app.models.user import User
from app.services.storage import storage

router = APIRouter(prefix="/media-api", tags=["media"])


@router.get("/{rel_path:path}")
def get_media(rel_path: str, _user: User = Depends(get_current_user)):
    if ".." in rel_path or rel_path.startswith("/"):
        raise HTTPException(400, "Invalid path")
    if not storage.exists(rel_path):
        raise HTTPException(404, "Media not found")
    try:
        data = storage.open_bytes(rel_path)
    except Exception:
        raise HTTPException(404, "Media not found")
    return Response(content=data, media_type="image/jpeg")
