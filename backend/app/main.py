"""FastAPI application entry point."""
import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.core.database import Base, engine
from app.core.security import decode_token
from app.routers import (
    aimodules,  # optional extended AI modules (Re-ID, attributes, person, quality, anomaly)
    alerts,
    analytics,
    auth,
    cameras,
    events,
    gis,
    health,
    media,
    reports,
    settings as settings_router,
    streams,
    users,
    vehicles,
    watchlist,  # watchlist module (entries, hits, matching)
)

# Simple in-memory rate limiter (per-IP sliding window). Sufficient for the PoC;
# production deployments should front the API with a gateway-level limiter.
_rate_buckets: dict[str, deque] = defaultdict(lambda: deque(maxlen=settings.RATE_LIMIT_REQUESTS))


async def rate_limit_middleware(request: Request, call_next):
    path = request.url.path
    # Streaming endpoints are long-lived single requests; media is polled by
    # <img> tags. Counting them against the sliding window starves the UI.
    exempt = path.startswith(
        (f"{settings.API_V1_PREFIX}/streams/", f"{settings.API_V1_PREFIX}/media-api/")
    )
    if request.client and not exempt and path.startswith(settings.API_V1_PREFIX):
        ip = request.client.host
        now = monotonic()
        bucket = _rate_buckets[ip]
        while bucket and now - bucket[0] > settings.RATE_LIMIT_WINDOW:
            bucket.popleft()
        if len(bucket) >= settings.RATE_LIMIT_REQUESTS:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=status.HTTP_429_TOO_MANY_REQUESTS)
        bucket.append(now)
    return await call_next(request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    from app.services.alert_service import events_bus

    events_bus.set_loop(asyncio.get_running_loop())
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description=(
        "SentinelVision AI — Integrated CCTV Management & Video Analytics Platform "
        "(hackathon proof of concept). Camera management, live monitoring, AI vehicle "
        "detection, ANPR, vehicle search/tracking, GIS, alerts, reports and RBAC."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.ENVIRONMENT != "production":
    app.middleware("http")(rate_limit_middleware)

app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(users.router, prefix=settings.API_V1_PREFIX)
app.include_router(cameras.router, prefix=settings.API_V1_PREFIX)
app.include_router(streams.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)
app.include_router(vehicles.router, prefix=settings.API_V1_PREFIX)
app.include_router(alerts.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(gis.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)
app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(settings_router.router, prefix=settings.API_V1_PREFIX)
app.include_router(media.router, prefix=settings.API_V1_PREFIX)
app.include_router(aimodules.router, prefix=settings.API_V1_PREFIX)  # optional extended AI modules
app.include_router(watchlist.router, prefix=settings.API_V1_PREFIX)  # watchlist module


@app.websocket("/ws/dashboard")
@app.websocket("/api/v1/ws/dashboard")
async def ws_dashboard(websocket: WebSocket):
    """Live push channel: alerts + worker status. Client sends `token` first."""
    from app.services.alert_service import events_bus

    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        decode_token(first)
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=4401, reason="unauthorized")
        return

    events_bus.register(websocket)
    try:
        await websocket.send_json({"type": "connected", "demo_mode": settings.DEMO_MODE})
        while True:
            await websocket.receive_text()  # keepalive pings; ignore content
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        events_bus.unregister(websocket)
        try:
            await websocket.close()
        except Exception:
            pass


@app.websocket("/ws/live/{camera_id}")
@app.websocket("/api/v1/ws/live/{camera_id}")
async def ws_live(websocket: WebSocket, camera_id: int):
    """Live MJPEG-over-WebSocket for one camera (alternative to HTTP MJPEG)."""
    await websocket.accept()
    try:
        first = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        decode_token(first)
    except WebSocketDisconnect:
        return
    except Exception:
        await websocket.close(code=4401, reason="unauthorized")
        return

    from app.workers.spooler import spooler

    async def frame_sender() -> None:
        last_seq = -1
        while True:
            frame = await spooler.get_latest_annotated(camera_id, last_seq)
            if frame is not None:
                data, last_seq = frame
                await websocket.send_bytes(data)
            await asyncio.sleep(0.08)

    sender_task = asyncio.create_task(frame_sender())
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        sender_task.cancel()
        try:
            await websocket.close()
        except Exception:
            pass


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


@app.get("/api/health", include_in_schema=False)
def root_health():
    return {"status": "ok", "app": settings.APP_NAME, "demo_mode": settings.DEMO_MODE}


@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "docs": "/docs",
        "demo_mode": settings.DEMO_MODE,
        "environment": settings.ENVIRONMENT,
    }
