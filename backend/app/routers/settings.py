"""Platform settings endpoints (admin only)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.models.system import PlatformSetting
from app.models.user import User
from app.schemas.schemas import SettingItem, SettingUpdate
from app.services.audit import audit

EDITABLE_KEYS = {
    "DETECTION_SAMPLE_INTERVAL": ("float", "Seconds between AI passes per camera"),
    "DETECTION_CONFIDENCE": ("float", "YOLO confidence threshold"),
    "OCR_MIN_CONFIDENCE": ("float", "Plate OCR confidence below which results need review"),
    "HEALTH_CHECK_INTERVAL": ("int", "Seconds between camera health checks"),
    "ALERT_OFFLINE_AFTER": ("int", "Seconds without frames before OFFLINE alert"),
    "MAX_CONCURRENT_STREAMS": ("int", "Maximum simultaneous video sources"),
    "DETECT_PERSONS": ("bool", "Enable person detection"),
    # --- optional extended AI modules (new, additive keys only) ---
    "ENABLE_REID": ("bool", "Vehicle Re-ID appearance matching (matches are unconfirmed)"),
    "ENABLE_ATTRIBUTES": ("bool", "Vehicle attribute recognition (color/body style)"),
    "ENABLE_PERSON_MODEL": ("bool", "Dedicated person detection model"),
    "ENABLE_QUALITY": ("bool", "Frame quality assessment"),
    "ENABLE_ANOMALY": ("bool", "Unusual vehicle movement review events"),
    "REID_SIMILARITY_THRESHOLD": ("float", "Cosine similarity above which a Re-ID match is recorded"),
    "ANOMALY_SPEED_LIMIT_KMPH": ("float", "Estimated speed above which movement is flagged for review"),
    "ENABLE_WATCHLIST": ("bool", "Watchlist matching on confirmed ANPR plate reads"),
    "WATCHLIST_MATCH_MIN_CONFIDENCE": ("float", "Minimum OCR confidence for a watchlist match"),
}

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingItem])
def list_settings(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = {r.key: r for r in db.query(PlatformSetting).all()}
    out = []
    for key, (_typ, desc) in EDITABLE_KEYS.items():
        row = rows.get(key)
        out.append(
            SettingItem(
                key=key,
                value=row.value if row else str(getattr(settings, key, "")),
                updated_at=row.updated_at if row else None,
                updated_by=row.updated_by if row else "",
            )
        )
    return out


@router.put("/{key}", response_model=SettingItem)
def update_setting(
    key: str,
    payload: SettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
    request: Request = None,
):
    if key not in EDITABLE_KEYS:
        raise HTTPException(400, f"Setting '{key}' is not editable")
    typ = EDITABLE_KEYS[key][0]
    try:
        if typ == "float":
            v = float(payload.value)
            if "CONFIDENCE" in key and not (0.0 < v < 1.0):
                raise ValueError
        elif typ == "int":
            v = int(payload.value)
        else:
            v = payload.value.lower() in ("1", "true", "yes", "on")
    except ValueError:
        raise HTTPException(422, f"Invalid value for {key} ({typ})")

    row = db.query(PlatformSetting).filter(PlatformSetting.key == key).first()
    if row is None:
        row = PlatformSetting(key=key)
        db.add(row)
    row.value = str(v)
    row.updated_by = user.username
    db.commit()
    db.refresh(row)

    # apply live where safe
    try:
        setattr(settings, key, v if typ != "bool" else bool(v))
    except Exception:
        pass

    audit(db, request, user, "settings.update", key, f"={v}")
    return SettingItem(key=key, value=row.value, updated_at=row.updated_at, updated_by=row.updated_by)


@router.get("/about")
def about(_user: User = Depends(get_current_user)):
    return {
        "app": settings.APP_NAME,
        "environment": settings.ENVIRONMENT,
        "demo_mode": settings.DEMO_MODE,
        "demo_notice": (
            "Demonstration mode: cameras and events may be synthetic and are labeled as demo data. "
            "No real government CCTV credentials are used."
            if settings.DEMO_MODE
            else "Production configuration — connect only cameras you are authorized to use."
        ),
        "max_streams": settings.MAX_CONCURRENT_STREAMS,
    }
