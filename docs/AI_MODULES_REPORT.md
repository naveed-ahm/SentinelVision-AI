# SentinelVision AI — Extended AI Modules Integration Report

Date: 2026-09-27 · Scope: 5 new optional AI modules added as independent, switchable services. **No existing feature, API, table, or UI element was modified or removed.**

---

## 1. New models added

| # | Module | Service file | What it produces | Storage |
|---|---|---|---|---|
| 1 | **Vehicle Attribute Recognition** | `app/services/attributes_service.py` | Vehicle color (HSV histogram tier), body-style refinement of the YOLO class | `vehicle_attributes` table |
| 2 | **Vehicle Re-identification** | `app/services/reid_service.py` | Appearance fingerprints (HSV+edge heuristic, optional torch embedding); cross-camera candidate matches, cosine similarity | `reid_matches` table + in-memory gallery |
| 3 **Person Detection** | `app/services/person_service.py` | Person bounding boxes + confidence from its OWN model instance (separate from vehicle YOLO) | `person_detections` table |
| 4 | **Image Quality Assessment** | `app/services/quality_service.py` | Blur / brightness / visibility scores + composite verdict per sampled frame | `quality_metrics` table |
| 5 **Anomaly Detection** | `app/services/anomaly_service.py` | Unusual movement findings: high estimated speed, loitering, wrong-way travel → **review events only** | `anomaly_reviews` table + `anomaly_review` alert type |

Design guarantees (all verified):

- Every module: independent service file, lazy singleton (loaded once, never re-loaded), `available` / `load_error` flags, `ENABLE_*` config flag, GPU-when-available + CPU fallback for torch tiers.
- Every call site in the worker is wrapped in its own `try/except` and short-circuits on its flag — a failing module cannot affect vehicle detection, ANPR, tracking, or the live stream (unit-tested).
- Re-ID matches are stored `status="unconfirmed"`; only a *plate-confirmed* pairing (both sides have the same confirmed plate) is stored `confirmed`. Appearance alone is never identity.
- Anomaly output is `severity="info"` review events ("human review required") — never criminal classification.
- Quality scoring is informational only; low scores never pause or gate the pipeline.
- Real predictions vs demo data: every new row carries `is_demo` copied from the camera, and the UI's existing `DemoBadge` convention marks it.

## 2. New files created

```
backend/app/models/ai_modules.py            5 new tables (VehicleAttribute, ReidMatch, QualityMetric, PersonDetection, AnomalyReview)
backend/app/services/attributes_service.py  vehicle color / body-style recognition
backend/app/services/reid_service.py        appearance gallery + cross-camera matcher
backend/app/services/person_service.py      dedicated person model wrapper
backend/app/services/quality_service.py     blur/brightness/visibility assessor
backend/app/services/anomaly_service.py     movement heuristics engine
backend/app/services/_embedding_model.py    shared optional torch embedding helper + heuristic fallback descriptor
backend/app/routers/aimodules.py            /api/v1/ai-modules/* endpoints (status + queries + review actions)
backend/tests/test_ai_modules.py            12 new tests (unit + API + pipeline isolation)
docs/AI_MODULES_REPORT.md                   this report
```

## 3. Existing files modified (additive changes only)

| File | Change |
|---|---|
| `backend/app/core/config.py` | Added new keys only: `ENABLE_REID/ATTRIBUTES/PERSON_MODEL/QUALITY/ANOMALY`, `REID_SIMILARITY_THRESHOLD`, `REID_MATCH_TTL_MINUTES`, `REID_HISTORY_SIZE`, `ANOMALY_SPEED_LIMIT_KMPH`, `ANOMALY_MIN_TRACK_HISTORY`, `ANOMALY_COOLDOWN_SECONDS`, `QUALITY_SAMPLE_EVERY_N`, `QUALITY_LOW_THRESHOLD`, `PERSON_MODEL_WEIGHTS`, `VEHICLE_ATTRIBUTE_WEIGHTS` |
| `backend/app/models/__init__.py` | Registered the 5 new model classes (existing imports untouched) |
| `backend/app/schemas/schemas.py` | Appended new response models (`VehicleAttributeOut`, `ReidMatchOut`, `QualityMetricOut`, `PersonDetectionOut`, `AnomalyReviewOut`, `AiModulesStatus`) after the existing ones |
| `backend/app/main.py` | Imported + included `aimodules.router` (2 lines) |
| `backend/app/routers/settings.py` | Added the 5 `ENABLE_*` toggles + 2 thresholds to `EDITABLE_KEYS` (admin-tunable at runtime) |
| `backend/app/workers/ingestion.py` | Hooked optional module calls into `_persist_detection` and the frame loop; each hook: flag check → lazy import → own try/except. Existing logic paths unchanged; failure isolation unit-tested |
| `frontend/src/api/types.ts` | Appended new optional-module interfaces |
| `frontend/src/pages/Analytics.tsx` | One new status card for the 5 modules (existing cards/markup untouched) |
| `frontend/src/pages/VehicleSearch.tsx` | Attribute chips inside the existing sightings modal (fetched best-effort; failure = chips simply absent) |
| `frontend/src/pages/Tracking.tsx` | One optional "AI: color type" line per vehicle card (single batched request) |
| `backend/requirements-ai.txt` | Documented optional deps for the new modules |
| `.env.example` | Added the new env keys block |
| `README.md`, `docs/TESTING.md` | Documentation of the new modules + updated test counts |

No existing database table, column, endpoint path, auth rule, or UI component was altered. New tables auto-create via the existing `Base.metadata.create_all` in lifespan (Alembic migration can be generated with `alembic revision --autogenerate` when deploying via migrations).

## 4. Dependencies

**Nothing new is required.** All five modules function today on the existing stack (FastAPI/SQLAlchemy/OpenCV/numpy):

- Quality, Anomaly, Attributes (heuristic tier), Re-ID (heuristic tier): pure OpenCV + numpy — zero extra packages.
- Person Detection: uses the same optional `ultralytics` the vehicle detector uses (not installed in this environment → degrades with a clear `load_error`, by design).
- Optional learned-embedding tier (Re-ID/attributes sharpening): `torch` (listed under "optional" in `requirements-ai.txt`); absent torch falls back to heuristics automatically.

## 5. Setup

No setup steps beyond the existing quick start. Defaults: all five modules **enabled**. To disable any module:

- Runtime: **Settings** page (admin) → toggle `ENABLE_REID`, `ENABLE_ATTRIBUTES`, `ENABLE_PERSON_MODEL`, `ENABLE_QUALITY`, `ENABLE_ANOMALY` (takes effect immediately; worker respects flags per frame).
- Or env: set `ENABLE_QUALITY=false` etc. in `backend/.env` / `.env.example`-derived file.

New endpoints (all authenticated like the rest of the API):
`GET /api/v1/ai-modules/status` · `GET .../attributes` · `GET .../attributes/recent-by-vehicle` · `GET .../events/{id}/attributes` · `GET .../reid-matches` · `POST .../reid-matches/{id}/confirm` (decision=`confirmed|rejected`) · `GET .../quality` · `GET .../quality/summary` · `GET .../persons` · `GET .../anomalies` · `POST .../anomalies/{id}/review`.

## 6. Test results

| Check | Result |
|---|---|
| `cd backend && python -m pytest -q` | **37 passed** (25 pre-existing + 12 new) in ≈34 s |
| `cd frontend && npm run build` | ✅ built (pre-existing chunk-size warning only) |
| New-module unit tests (quality scoring, color/body-style, Re-ID cross-camera match + disabled-flag, anomaly speed/person-exclusion/cooldown) | ✅ |
| API tests (status shape, auth required, empty listings, new tables exist, existing vehicle endpoint unaffected) | ✅ |
| Pipeline-isolation test (module throwing mid-persist does not break `_persist_detection`) | ✅ |
| Live: worker started with all modules; person module degraded with `No module named 'ultralytics'`; worker loop unaffected | ✅ observed in log |
| Live: quality metrics persisted from the demo feed (`/ai-modules/quality/summary`: 20 samples, camera 1, composite ≈ 0.62, `is_demo=true`) | ✅ |
| Live: Re-ID/anomaly rows = 0 while YOLO is degraded (no fabricated data) | ✅ |
| Live: MJPEG snapshot 200 (37 KB), worker status RUNNING, vehicle search, alerts, plate-read review queue, analytics overview (465 events), GIS (6 cameras) all still 200 | ✅ |
| UI: new "Extended AI modules" card renders on the existing Analytics page in the same design language (verified in browser) | ✅ |

## 7. Remaining limitations (honest list)

- **Model-backed paths not executed locally**: `ultralytics`/`torch` are not installed in this environment, so person detection was verified only through its degradation path, and the optional torch embedding tier only through its fallback. The heuristic tiers (attributes color/body-style, Re-ID similarity, anomaly motion, quality scoring) ARE executed and tested for real.
- Anomaly speed estimation uses a single-camera px→meter calibration from median vehicle width; it is an order-of-magnitude review aid, not a calibrated speed gun. Direction/loitering heuristics need a few minutes to calibrate per camera.
- Re-ID heuristic embeddings are coarse (color+edge); they will produce both false candidates and misses. That is why every match is unconfirmed and human review is the workflow.
- Quality sampling is fixed-interval (1/100 frames); a production system would tie sampling to scene change or detection density.
- Person rows are presence-only (no re-ID, no face recognition — by policy).
- Docker daemon was offline in this environment; compose files are provided but the new modules were not exercised inside containers.
- Anomaly review events reuse the existing alerts table via the new `anomaly_review` type (no new alert infrastructure was added, to avoid touching existing schemas).
