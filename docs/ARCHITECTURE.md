# SentinelVision AI — Architecture

## 1. Process model

```
┌────────────────────────────────────────────────────────────────────────────┐
│                              BROWSER (React SPA)                           │
│   REST (axios) · WebSocket /ws/dashboard · <img> MJPEG per camera tile     │
└───────────────┬────────────────────────────────────────────▲───────────────┘
                │ same-origin (vite proxy dev / nginx prod)   │
┌───────────────▼────────────────────────────────────────────┴───────────────┐
│                            API PROCESS (uvicorn)                           │
│  FastAPI routers: auth · users · cameras · streams · events · vehicles     │
│  alerts · analytics · gis · reports · health · settings · media            │
│  Security: JWT (bcrypt), RBAC dependencies, in-memory rate limiter         │
│  WS: alert/event fan-out (in-process bus)                                  │
│  Streams: reads latest annotated JPEG per camera from the live store       │
└───────────────┬───────────────────────────────────────────▲────────────────┘
                │ SQLAlchemy (sync)                         │ disk reads
┌───────────────▼──────────────┐        ┌───────────────────┴────────────────┐
│   PostgreSQL / SQLite        │        │  LIVE FRAME STORE (data/media/live)│
│   users, cameras, creds,     │        │  per camera: <code>.jpg + .json    │
│   events, vehicles,          │        │  atomic rename writes              │
│   sightings, plate_reads,    │        └───────────────────▲────────────────┘
│   alerts, audit, health      │                            │ atomic publish
└───────────────▲──────────────┘        ┌───────────────────┴────────────────┐
                │ SQLAlchemy            │     INGESTION WORKER PROCESS       │
                │                       │  supervisor thread: sync workers   │
                └───────────────────────┤  per camera thread:                │
                                        │   VideoCapture (RTSP/file/webcam)  │
                                        │   → frame pacing (FPS cap)         │
                                        │   → YOLO detect (sampled)          │
                                        │   → IoU tracker (ByteTrack-style)  │
                                        │   → ANPR crop → OCR → validate     │
                                        │   → persist events/sightings       │
                                        │   → raise alerts (bus publish)     │
                                        └────────────────────────────────────┘
```

Key point: **the API never decodes video or runs models.** Heavy work lives in the
worker process, so a stalled camera or slow model cannot freeze the UI. The two
processes share only the database and the small on-disk live-frame store.

## 2. Video pipeline (worker)

1. **Source resolution** — `rtsp://` URLs are assembled from the camera row +
   its credential row (username/password injected URL-encoded at connect time).
   `file` protocol loops a local video (demo mode); `webcam` opens device 0.
2. **Capture** — `cv2.VideoCapture` (FFmpeg backend for RTSP), decoded frames
   paced to `INGEST_FPS_LIMIT` (default 12 fps). Interrupted streams reconnect
   with exponential backoff (2 s → 30 s).
3. **Sampling** — AI runs every `DETECTION_SAMPLE_INTERVAL` seconds per camera,
   not per frame; all frames still go to the live store for smooth viewing.
4. **Detection** — one shared YOLO model (yolov8n by default) filters COCO
   classes {car, motorcycle, bus, truck} and optionally `person`.
5. **Tracking** — IoU/centroid tracker (ByteTrack philosophy: keep low-score
   detections briefly) assigns stable track IDs, feeds bbox history.
6. **ANPR** — lower-central plate crop proposal → grayscale ×2 upscale →
   bilateral filter → CLAHE → PaddleOCR → regex normalization against Indian
   plate format. Reads below `OCR_MIN_CONFIDENCE` or failing the format are
   stored with `needs_review=true` and surface in the review queue.
7. **Persistence** — detections are throttled per track (≥2 hits, 1 event / 2 s)
   with vehicle crop JPEG saved under `data/media/<code>/detections/`. A plate
   read that passes validation upserts a `Vehicle` and appends a
   `VehicleSighting` (the cross-camera join key is the *plate text only*).
8. **Publishing** — annotated JPEG → live store; detection/camera-status/alert
   messages → event bus (WebSocket fan-out).

## 3. Data model

| Table | Purpose / notes |
|---|---|
| `users` | bcrypt hashes, role ∈ {admin, operator, viewer}, last_login |
| `cameras` | identity, coordinates, protocol, redacted URL, status, health timestamps, `is_demo` |
| `camera_credentials` | per-camera username/secret/channel — never serialized |
| `detection_events` | one row per persisted detection: class, confidence, bbox, track_id, image path, FK → plate_read |
| `plate_reads` | raw + normalized text, OCR confidence, needs_review, correction audit (who/when) |
| `vehicles` | identity per registration number, first/last seen, sighting count |
| `vehicle_sightings` | vehicle ↔ event ↔ camera ↔ timestamp (unique per event) |
| `alerts` | type, severity, status, assignee, FKs to camera/event |
| `audit_logs` | who/what/when/IP for security-relevant operations |
| `system_health` | latest snapshot per component |
| `platform_settings` | runtime-tunable parameters (DB-persisted, admin-edited) |

Indexes cover the hot paths: events by (camera, time), (class, time);
sightings by (vehicle, time); alerts by (status, time). Timestamps are stored
UTC (`DateTime(timezone=True)`) and rendered in the browser's local zone.
Migrations are managed with Alembic (`backend/alembic/versions`).

## 4. Live streaming to the browser

Browsers cannot play RTSP natively. Options considered:

| Option | Verdict for PoC |
|---|---|
| **MJPEG over HTTP** (chosen) | trivial, robust, auth-friendly (`<img>` + query token); bandwidth-heavy at high res |
| WebSocket binary frames | implemented as `/ws/live/{id}` (alternative transport) |
| HLS via FFmpeg segments | lower bandwidth, but adds segment latency + storage churn |
| WebRTC (go2rtc/mediamtx) | best latency/CPU at scale; external dependency — recommended upgrade |

The worker publishes the latest annotated JPEG for each camera via atomic file
renames; the API streams it as `multipart/x-mixed-replace`. Any number of
stateless API replicas can serve the same store (see SCALABILITY).

## 5. Graceful degradation

| Missing component | Behaviour |
|---|---|
| `ultralytics`/`torch` | worker streams raw video, no detections; AI pages show `DEGRADED` with install hint |
| `paddleocr` | detection persists without plate reads; ANPR marked degraded |
| Ingestion worker down | UI tiles show camera status/last error; rest of the platform fully usable |
| PostgreSQL unreachable | FastAPI returns 500s with JSON detail; worker retries with backoff; `/api/health` reports DB `error` |
| Unreachable RTSP source | worker marks camera `error` with message, retries with backoff, alert on offline |

## 6. Security architecture

- **AuthN**: OAuth2 password flow → JWT (HS256, configurable expiry).
- **AuthZ**: dependency matrix — `require_admin` (users, deletes, settings) /
  `require_operator` (camera mutations, alert actions, corrections, reports) /
  any authenticated (reads). Enforced in routers, tested in the suite.
- **Secrets**: env vars only; camera credentials isolated; redaction on read.
- **Audit**: logins (success/failure), camera CRUD, user CRUD, alert actions,
  settings changes, report exports — with username + IP.
- **Input validation**: Pydantic schemas on every write; path-traversal guard in
  media resolution; code/username format constraints.
- **Transport**: TLS terminates at your reverse proxy in production; nginx config
  provided.

## 7. Demonstration mode

`DEMO_MODE=true` seeds six Ahmedabad cameras, 24 h of synthetic events/plates
and alerts, every row flagged `is_demo`. The UI renders a `DEMO` badge next to
synthetic records and a global banner on the dashboard. Attaching a real,
authorized source to a camera switches that camera to live data without code
changes. The synthetic `demo_traffic.mp4` generator additionally burns
"SYNTHETIC DEMO FOOTAGE" into the frames themselves.
