"""Alert creation + publication on the WebSocket event bus."""
import asyncio
import threading

from fastapi import WebSocket
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.alert import Alert
from app.models.user import utcnow


class EventBus:
    """In-process pub/sub broadcast to dashboard WebSocket clients.

    Single-process PoC. For horizontal scaling, back this with Redis pub/sub.
    Safe to publish from the asyncio loop or from worker threads.
    """

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._recent: list[dict] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def publish(self, message: dict) -> None:
        with self._lock:
            self._recent = [*self._recent[-49:], message]
        dead: list[WebSocket] = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    def publish_now(self, message: dict) -> None:
        """Publish from sync context (worker thread or request handler)."""
        if self._loop is None or self._loop.is_closed():
            return

        def _spawn() -> None:
            asyncio.ensure_future(self.publish(message))

        try:
            self._loop.call_soon_threadsafe(_spawn)
        except RuntimeError:
            pass

    def register(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def unregister(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)


events_bus = EventBus()


def raise_alert(
    db: Session,
    alert_type: str,
    title: str,
    description: str,
    severity: str = "info",
    camera_id: int | None = None,
    event_id: int | None = None,
    is_demo: bool = False,
) -> Alert | None:
    """Create an alert and push it to connected dashboards. Never raises."""
    try:
        alert = Alert(
            alert_type=alert_type,
            severity=severity,
            camera_id=camera_id,
            event_id=event_id,
            title=title[:200],
            description=description[:2000],
            is_demo=is_demo,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        events_bus.publish_now(
            {
                "type": "alert",
                "alert": {
                    "id": alert.id,
                    "alert_type": alert.alert_type,
                    "severity": alert.severity,
                    "camera_id": alert.camera_id,
                    "title": alert.title,
                    "description": alert.description,
                    "created_at": alert.created_at.isoformat() if alert.created_at else None,
                    "is_demo": alert.is_demo,
                },
            }
        )
        return alert
    except Exception:
        db.rollback()
        return None


def maybe_offline_alert(db: Session, camera) -> None:
    last = camera.last_connected_at
    if last is None or (utcnow() - last).total_seconds() > settings.ALERT_OFFLINE_AFTER:
        raise_alert(
            db,
            "camera_offline",
            f"Camera offline: {camera.name}",
            f"{camera.code} at {camera.location_name or 'unknown location'} has not produced frames recently.",
            severity="warning",
            camera_id=camera.id,
            is_demo=camera.is_demo,
        )
