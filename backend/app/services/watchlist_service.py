"""Watchlist matching service (optional, independent; ENABLE_WATCHLIST).

Checks ANPR plate text against active watchlist entries and records hits with
an alert + WebSocket push. Never modifies the ANPR pipeline: the check runs
AFTER a plate read is persisted and any failure is swallowed by the caller.
"""
from __future__ import annotations

import logging
import threading

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.watchlist import WatchlistEntry, WatchlistHit
from app.services.alert_service import events_bus, raise_alert

logger = logging.getLogger("sentinelvision.watchlist")

def normalize_plate(text: str) -> str:
    """Uppercase + strip non-alphanumerics.

    Deliberately does NOT fold look-alike characters (O->0, B->8, …): both the
    watchlist entry and the OCR text pass through the same normalization, so
    separator/format differences are absorbed while genuine letter/digit
    distinctions are preserved — predictable matching without false positives.
    Low-confidence OCR output is handled by the existing review-queue workflow.
    """
    raw = (text or "").upper().strip()
    return "".join(ch for ch in raw if ch.isalnum())


class WatchlistService:
    """Thread-safe singleton around DB watchlist checks."""

    def __init__(self) -> None:
        self._lock = threading.Lock()

    def load(self) -> bool:
        return True  # pure DB service; no external deps

    @property
    def available(self) -> bool:
        return settings.ENABLE_WATCHLIST

    def check_plate(
        self,
        db: Session,
        *,
        plate_text: str,
        ocr_confidence: float,
        plate_read_id: int | None = None,
        event_id: int | None = None,
        camera_id: int | None = None,
        evidence_path: str = "",
        is_demo: bool = False,
        camera_name: str = "",
    ) -> WatchlistHit | None:
        """Match one confirmed plate read against active entries.

        Returns the created WatchlistHit, or None when no match / module
        disabled / below confidence threshold. NEVER raises into the pipeline.
        """
        if not settings.ENABLE_WATCHLIST:
            return None
        normalized = normalize_plate(plate_text)
        if len(normalized) < 4 or ocr_confidence < settings.WATCHLIST_MATCH_MIN_CONFIDENCE:
            return None
        try:
            entries = (
                db.query(WatchlistEntry)
                .filter(
                    WatchlistEntry.active.is_(True),
                    WatchlistEntry.identifier_type == "plate",
                    WatchlistEntry.identifier_value == normalized,
                )
                .all()
            )
            if not entries:
                return None
            entry = entries[0]
            # expiry guard (tz-safe for SQLite naive datetimes)
            if entry.expires_at is not None:
                from app.models.user import utcnow

                exp = entry.expires_at
                if exp.tzinfo is None:
                    from datetime import timezone

                    exp = exp.replace(tzinfo=timezone.utc)
                if utcnow() > exp:
                    return None

            with self._lock:
                hit = WatchlistHit(
                    entry_id=entry.id,
                    plate_read_id=plate_read_id,
                    event_id=event_id,
                    camera_id=camera_id,
                    plate_text=normalized[:20],
                    ocr_confidence=round(ocr_confidence, 4),
                    match_type="exact",
                    evidence_path=evidence_path[:255],
                    is_demo=is_demo,
                )
                db.add(hit)
                db.commit()
                db.refresh(hit)

            title = entry.title or f"Watchlist match: {entry.display_value or normalized}"
            sev = entry.severity if entry.severity in ("info", "warning", "critical") else "warning"
            alert = raise_alert(
                db,
                "watchlist_hit",
                f"{entry.category.replace('_', ' ').title()} match — {normalized}",
                f"Watchlisted plate {entry.display_value or normalized} ({entry.category.replace('_', ' ')})"
                f" read on {camera_name or 'camera'} with {ocr_confidence * 100:.0f}% OCR confidence."
                " Verify evidence before any action — OCR matches require human confirmation.",
                severity=sev,
                camera_id=camera_id,
                event_id=event_id,
                is_demo=is_demo,
            )
            if alert is not None:
                hit.alert_id = alert.id
                db.commit()
            events_bus.publish_now(
                {
                    "type": "watchlist_hit",
                    "watchlist_hit": {
                        "id": hit.id,
                        "entry_id": entry.id,
                        "category": entry.category,
                        "plate": normalized,
                        "confidence": round(ocr_confidence, 3),
                        "camera_id": camera_id,
                        "camera_name": camera_name or None,
                        "severity": sev,
                        "title": title,
                        "timestamp": hit.timestamp.isoformat() if hit.timestamp else None,
                        "is_demo": is_demo,
                    },
                }
            )
            return hit
        except Exception as exc:
            db.rollback()
            logger.warning("watchlist check failed (pipeline unaffected): %s", exc)
            return None

    def status(self) -> dict:
        return {"enabled": settings.ENABLE_WATCHLIST, "min_confidence": settings.WATCHLIST_MATCH_MIN_CONFIDENCE}


watchlist_service = WatchlistService()
