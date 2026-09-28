# SentinelVision AI — High-Level Design (HLD)

**Submission:** Gujarat Police Innovation Challenge 2026 — CCTV Integration & AI Video Analytics
**Track:** Model 1 (Centralised CCTV Registry & GIS Foundation — compulsory) **+ Model 2 hybrid (real-time AI analytics: detection, ANPR, tracking, watchlist, alerts)**
**Version:** 1.0 · September 2026
**Status:** Working platform (not a concept) — code at `github.com/naveed-ahm/SentinelVision-AI`

---

## 1. Executive Summary

Gujarat operates one of India's largest CCTV estates — 80,000+ cameras owned by 26+ departments
(Police, Health, GSRTC, Panchayat, Municipal) with **no unified view, no common metadata, and no
automated analysis**. Cameras are silos; investigations mean human eyes on dozens of feeds.

**SentinelVision AI** is a full-stack CCTV management and AI video analytics platform that:

1. **Registers every camera** — a central registry with location metadata, GIS mapping, health/uptime
   monitoring, and multi-department ownership (Model 1),
2. **Analyzes every feed in real time** — vehicle detection, ANPR plate reading, multi-camera vehicle
   tracking, watchlist matching, and automated alerting (Model 2), and
3. **Answers the two questions police actually ask** — *"Where is this vehicle?"* (cross-camera
   timestamped movement history) and *"Has this plate appeared anywhere?"* (watchlist + search).

The platform is **running today** on commodity hardware (one laptop with a consumer GPU) and is
verified end-to-end: 6 concurrent feeds, sub-second event latency, real watchlist hits with evidence
imagery, and 45 automated tests. Every architectural choice below is made for the leap from 6 cameras
to 80,000.

### Design principles

| Principle | How it shows up |
|---|---|
| Feed-first integration | Onboarding a camera = a registry row + a worker assignment. RTSP/WebRTC/HLS all supported. |
| One intelligence per stream, many streams per node | Ingestion workers scale horizontally; AI is per-stream, not per-platform. |
| Everything becomes searchable metadata | Video is never searched; plate reads and detections are. |
| Human-in-the-loop by design | Watchlist matches raise alerts for operators — never automated action. |
| Degrade gracefully | A dead camera is a registry status, not a platform outage. |

---

## 2. Problem Statement Mapping

### 2.1 Mandatory: Model 1 — Centralised CCTV Registry & GIS Foundation

| Model 1 requirement | SentinelVision capability |
|---|---|
| Single registry of all cameras | `cameras` table: code, name, department/owner, location name, lat/lng, source URL, credentials, status, health timestamps |
| Multi-department federation | `department` / owner fields on every camera; department-scoped listings and filters |
| GIS foundation | Interactive map page; every camera plotted; availability overlay (online = green / offline = red); location search |
| Camera health monitoring | Ingestion worker heartbeats + live-store freshness → `status`, `last_seen`, `last_error`; uptime % per camera over 24 h (`/analytics/camera-availability`) |
| Simulated gov-feed onboarding | Seeds and API support RTSP **and** file-based sources; the sandbox feeds (RTSP/WebRTC/HLS) onboard as ordinary registry rows |

### 2.2 Selected: Model 2 — Real-time AI Video Analytics

| Model 2 capability | SentinelVision implementation (verified live) |
|---|---|
| Vehicle / person detection | YOLOv8 (nano, CUDA) per stream, frame sampling at configurable intervals |
| ANPR | YOLO plate crops → PaddleOCR (PP-OCRv6). Live reads at 0.97–1.00 confidence on demo feeds |
| Vehicle tracking | ByteTrack-style IoU tracker per camera (stable track IDs) + cross-camera Re-ID (tiered: embedding → heuristic) |
| Watchlist matching | Normalized-plate matching on every confirmed ANPR read; severity-ranked hits with evidence crops; acknowledge workflow |
| Real-time alerts | Alert engine (watchlist hit, camera offline, tamper, anomaly…) → DB + WebSocket push to all dashboards in < 1 s |
| Cross-camera search | Vehicle search by plate/time/camera/class; **Track page**: plate → timeline → reconstructed route with stops |

### 2.3 Model 3 / Model 4 (edge/distributed patterns) — supported by design, not required for this submission

The worker architecture (below) is a hierarchical edge pattern in miniature: registry → scheduler →
per-stream analysis nodes → central bus. Section 6 shows how it grows into a full Model 3/4 tier
without changing the platform contract.

---

## 3. System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  SOURCES: 80,000 cameras — Police · Health · GSRTC · Panchayat · Municipal   │
│            RTSP / WebRTC / HLS / file (simulated feeds)                      │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │ pull (worker-assigned)
┌──────────────▼──────────────────────────────────────────────────────────────┐
│  INGESTION & ANALYTICS TIER (stateless, horizontally scalable)               │
│  ┌────────────┐  ┌──────────────────────────────────────────────────────┐   │
│  │ Supervisor │  │ StreamWorker (one per camera, thread-per-stream)     │   │
│  │ reassign,  │─▶│  decode ▶ sample ▶ YOLOv8 detect (CUDA)              │   │
│  │ heartbeat, │  │        ▶ plate detect ▶ PaddleOCR read               │   │
│  │ recover    │  │        ▶ IoU tracker ▶ Re-ID (tiered)                │   │
│  └────────────┘  │        ▶ watchlist matcher ▶ alert publisher         │   │
│                  │  fallback: MOG2 motion pipeline (degraded mode)      │   │
│                  └────────────┬─────────────────────────────────────────┘   │
│   shared GPU across workers · FPS cap · adaptive sampling                     │
└──────────────┬──────────────────────────────┬───────────────────────────────┘
               │ events / plate reads          │ annotated frames (ring buffer)
┌──────────────▼──────────────┐   ┌───────────▼──────────────────────────────┐
│  DATA TIER                  │   │  LIVE STORE (per-process ring buffers)   │
│  PostgreSQL (WAL discipline │   │  latest annotated frame per camera →     │
│  on SQLite in PoC)          │   │  MJPEG gateway + snapshot endpoints      │
│  detection_events           │   └───────────┬──────────────────────────────┘
│  plate_reads · watchlist*   │               │
│  alerts · camera registry   │               │
│  object storage: evidence   │               │
└──────────────┬──────────────┘               │
               │                              │
┌──────────────▼──────────────────────────────▼───────────────────────────────┐
│  API TIER — FastAPI (REST + WebSocket)                                       │
│  JWT RBAC (admin/operator/viewer) · rate limiting · streaming endpoints      │
│  REST: cameras, events, vehicles, watchlist CRUD, alerts, analytics, GIS,    │
│        reports, health, media ·  WS: dashboard bus, per-camera live          │
└──────────────┬──────────────────────────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────────────────────────┐
│  PRESENTATION TIER — React + TypeScript SPA                                  │
│  Command center · monitoring wall · GIS map · vehicle search/track ·         │
│  watchlist console · alerts/events · analytics · reports · RBAC admin        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Component responsibilities

| Component | Responsibility | PoC implementation | Production scaling |
|---|---|---|---|
| **Camera Registry** | Source of truth for cameras | `cameras` table + `/cameras` API + GIS page | Same, PostgreSQL + dept SSO sync |
| **Supervisor** | Assign streams to workers, heartbeat, reassign dead feeds | in-process supervise loop | K8s jobs / queue-based assignment per site |
| **StreamWorker** | Decode → detect → OCR → track → match → publish | Python thread, shared CUDA model instances | Container per node; 4–8 streams/GPU (L4/T4) |
| **Live Store** | Low-latency annotated frames to browsers | per-process ring buffer + MJPEG multipart gateway | Same pattern; Redis/mediasoup if cross-node fan-out needed |
| **Event Bus** | Alert fan-out to all clients | asyncio bus + WebSocket `/ws/dashboard` | NATS/Kafka + WS gateways |
| **Data Tier** | Searchable metadata + evidence | SQLAlchemy over SQLite (WAL) | PostgreSQL + TimescaleDB + S3/MinIO |
| **API Tier** | Authenticated access for UI + integrations | FastAPI, JWT RBAC, rate-limited | Same code, nginx/HTTP2, replicas |
| **Web Client** | Operations UI | React + TS SPA | Same |

### 3.2 Key request flows

**Feed onboarding (Model 1):** operator creates camera in registry (or bulk-imports a department's
list) → supervisor notices the unassigned enabled camera → assigns a worker → worker connects,
validates source, starts analysis → camera flips `online` with heartbeat; GIS + health pages reflect
it immediately.

**Detection → alert (Model 2):** frame sampled (interval-configurable, default 2 s) → YOLO detect →
plate crop → OCR read (confidence-gated, `WATCHLIST_MATCH_MIN_CONFIDENCE=0.70`) → normalized plate
compared against active watchlist → on match: evidence crop + DB hit + alert raised → WebSocket push
→ operator acknowledges in UI. Everything above is **observable live in the current build**.

**Hackathon live test (vehicle route):** organizers announce plate → operator runs Track: plate →
plate_reads joined to camera registry → timestamped, location-wise movement history + map polyline;
continues updating while the vehicle moves.

---

## 4. Data Model (core tables)

| Table | Purpose / key fields |
|---|---|
| `cameras` | Registry: code, name, department, location, lat/lng, rtsp_url, credentials (encrypted), enabled, status, last_seen, last_error, is_demo |
| `detection_events` | One row per tracked object crossing sampling gate: camera, timestamp, class, confidence, bbox, track_id, frame/evidence paths |
| `plate_reads` | ANPR results: plate_text (normalized), raw_text, ocr_confidence, needs_review, crop_path |
| `watchlist_entries` | category (stolen/wanted/missing/blacklist/custom), identifier (normalized), title, notes, severity, active |
| `watchlist_hits` | match record: entry, plate_text, ocr_confidence, camera, timestamp, evidence_path, acknowledged |
| `alerts` | type (watchlist_hit, camera_offline, tamper, anomaly…), severity, status, camera, title, description |
| `users` | RBAC: role admin/operator/viewer, hashed credentials |

Search paths are all index-backed: `(camera_id, timestamp)` on events, normalized `plate_text` on
reads/hits, `(status)` on cameras.

---

## 5. AI / Analytics Design

| Stage | Model | Detail |
|---|---|---|
| Detection | **YOLOv8n** (Ultralytics) | One instance per process, loaded once on CUDA; frame sampling bounds cost (FPS cap + sample interval are config). Vehicle classes: car, motorcycle, bus, truck, person. |
| Plate detection | YOLO plate head on detections | Crops saved as evidence; conf gate before OCR |
| ANPR | **PaddleOCR PP-OCRv6** | Version-adaptive wrapper (2.x/3.x APIs); textline orientation off for speed; regex normalization of Indian plate formats |
| Per-camera tracking | IoU (ByteTrack-style) | Stable IDs within a camera; ID-stable assignments feed the cross-camera layer |
| Cross-camera Re-ID | Tiered engine | Tier 1 embedding similarity (when model available); Tier 2 heuristic (class + plate + time-window + graph hops). Designed to answer "same vehicle across cams?" cheaply |
| Fallback pipeline | MOG2 background subtraction | When the detector returns nothing (degraded source), motion blobs still yield vehicle-class events with location metadata — the platform never goes blind |
| Watchlist matcher | Exact normalized-plate match, confidence-gated | Sub-ms; severity propagated to alert; every hit keeps its evidence crop for human verification |

**Measured on the PoC laptop (Ryzen 7 7445HS, consumer iGPU+dGPU path):** 6 concurrent streams,
YOLO on CUDA, OCR conf 0.97–1.00, event→dashboard latency < 1 s, sustained ~0.6 core / ~3 GB worker
footprint with sampling tuned — leaving headroom for 2–3× more streams on the same box.

---

## 6. Scalability Path: 6 → 80,000 cameras

The sandbox proves the analytics; the architecture below is what scales it. Growth is **linear and
horizontal at every tier** — no component is single-threaded by design.

| Tier | PoC (today) | 1,000 cams (city) | 80,000 cams (state) |
|---|---|---|---|
| Ingestion | 1 process, thread-per-stream, shared GPU | 3–5 worker nodes × 8 GPUs (L4/T4) | Hierarchical edge: district POPs, 8–16 streams/GPU node; state core aggregates metadata only |
| Streaming out | MJPEG gateway per process | Same, behind nginx | WebRTC/HLS at edge POPs; browsers never pull cross-district |
| Data | SQLite (WAL) | PostgreSQL single writer + read replicas | TimescaleDB partitions (events hot/cold), S3 evidence tiers, monthly rollups |
| Bus | asyncio WS fan-out | NATS cluster | Kafka/NATS regional; alerts geo-routed |
| API | 1 uvicorn | 2–4 replicas | Regional API clusters, HTTP/2 multiplexed |
| Client | SPA | Same | Same; viewport-scoped queries keep payloads flat regardless of camera count |

**Key scaling facts:**
- **Metadata is the product.** Detection/OCR turn 80,000 video feeds into rows; searching 80,000
  feeds becomes indexed SQL — the video itself is never queried for search.
- **Analytics is per-stream**, so capacity = worker nodes × streams/node. A district POP (8 × L4)
  handles ~1,500 streams at PoC-tuned sampling; 55 POPs cover the state.
- **Bandwidth stays local.** Edge POPs decode at the source; only events + JPEG evidence transit the
  WAN (KB-scale, not video-scale).
- **The registry degrades gracefully.** A dead district POP = cameras marked offline via heartbeat
  timeout — dashboards stay up, alerts fire, no cascade.

### 6.1 What we would add for production (explicit gaps)

Honest list, mapped to the judging criteria: PostgreSQL + S3 (PoC uses SQLite/filesystem),
multi-tenant department SSO + audit logs, VAHAN/SARTHI/eGujCop/AFIS/NAFIS correlation service
(behind a clean adapter interface already), WebRTC/HLS ingest for browser-native gov feeds, K8s
packaging + observability (metrics/tracing), model registry + drift monitoring, and DPDP-Act-aligned
retention/privacy controls (zone-based redaction, retention policies, access logging).

---

## 7. Security, Privacy & Compliance

- **AuthN/AuthZ:** JWT with role-based access (admin/operator/viewer); every API route guarded;
  media/stream endpoints token-gated (including `?access_token=` for `<img>` contexts).
- **Least privilege:** viewer = read-only; operator = operational actions; admin = user/registry
  management. Frontend hides and backend rejects unauthorized mutations (403, tested).
- **Evidence integrity:** every detection/plate/hit stores source camera + timestamp + evidence path;
  watchlist hits require human acknowledgment — no automated enforcement action.
- **Privacy by design:** DEMO-mode flag labels synthetic data everywhere it appears; production path
  includes retention windows, purpose-limited access logs, and redaction zones (Section 6.1). The
  platform is a decision-support tool for sworn operators, not a surveillance automaton.
- **Ops security:** secrets via environment (never in repo), rate limiting, HTTPS termination at
  gateway in production, dependency audit in CI.

---

## 8. Verification & Evidence (what judges can reproduce)

| Claim | Evidence |
|---|---|
| Working platform, not mock-up | Public repo + live UI walkthrough (login → command center → monitoring wall → watchlist) |
| Real-time analytics | Live monitoring page: 6 concurrent annotated streams, boxes + plate overlays |
| ANPR quality | Plate reads at 0.97–1.00 OCR confidence on demo feeds; every read keeps its crop |
| Watchlist end-to-end | Add plate → hit appears with evidence + alert + WS toast within one sampling cycle |
| Cross-camera tracking | Track page: plate → timestamped camera-by-camera route (the sandbox live-test deliverable) |
| Engineering rigor | 45 backend tests (API, RBAC, watchlist, AI services), CI on every push, seeded reproducible demo |
| Real-world resilience | MOG2 fallback, WAL against write contention, supervisor auto-recovery of dead feeds |

---

## 9. Delivery & Deployment

- **PoC hardware:** single Windows laptop (Ryzen 7, CUDA GPU), Python 3.13 + FastAPI, React 19,
  YOLOv8n + PaddleOCR on CUDA. Three processes: API, ingestion worker, web.
- **Reproducibility:** `requirements*.txt` + lockfile; `python app/seed.py` provisions registry,
  demo cameras, and demo watchlist; `pytest` (45) + `npm run build` gate in CI.
- **Sandbox onboarding plan (gov feeds):** ingest the provided RTSP/WebRTC/HLS endpoints as registry
  rows (webRTC/HLS via transcode-to-RTSP sidecar if needed) → same worker pipeline → Track page is
  the hackathon-day vehicle-route answer.
- **Requested at scale:** Kubernetes-managed worker pools with per-POP GPU nodes, PostgreSQL cluster,
  object storage, NATS — the same containers, orchestrated.

---

*All capabilities described as "verified" were demonstrated on the running system during development
and are reproducible from the public repository with the seeded demo environment.*
