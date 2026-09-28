# SentinelVision AI — Testing Report

Date: 2026-09-27 · Platform: Windows 11, Python 3.13, Node 24 · Scope: hackathon PoC

## 1. Automated tests (executed)

Command: `cd backend && python -m pytest -q` → **45 passed** (≈34 s, isolated SQLite DB, seeded demo data).

### Coverage by area

| Area | Tests | What is asserted |
|---|---|---|
| Authentication | 4 | login success issues JWT+role; wrong password → 401; `/auth/me` requires token; garbage token → 401 |
| RBAC | 3 | viewer cannot create cameras (403); viewer cannot acknowledge alerts (403); operator can create cameras but cannot create users (403) |
| Camera CRUD | 3 | create→edit→test→delete lifecycle; **credentials never appear in any response** and URLs are redacted; duplicate code → 409; search filter works |
| Events | 2 | pagination respected (`page_size`); class filter returns only matching rows |
| Vehicles | 2 | plate-fragment search (`GJ01*`) matches only that prefix; detail + timeline endpoints return sightings and honesty note |
| Alerts | 2 | open→acknowledge→resolve status transitions; severity filter |
| Analytics/GIS | 3 | overview counters populated; all four chart endpoints 200; GIS demo cameras have coordinates; sightings endpoint 200 |
| Reports | 2 | CSV streams with correct content-type and title header (operator); viewer forbidden (403) |
| Settings/Health | 3 | settings list ok; admin can update, viewer cannot, unknown key → 400; `/health` reports api/database/ai components |
| Validation | 1 | invalid camera payload → 422 |
| OpenAPI | 1 | `/docs` served |
| AI modules — quality | 1 | sharp vs flat frames score differently; None on empty/invalid input |
| AI modules — attributes | 1 | color + body style recognized; tiny crops rejected |
| AI modules — Re-ID | 2 | cross-camera match found with similarity ≥ threshold and `confirmed_by_plate=false`; disabled flag returns None; same-camera entries never match |
| AI modules — anomaly | 2 | sub-threshold motion not flagged; person tracks excluded; fast motion flagged as `speed` with cooldown suppression |
| AI modules — API | 4 | `/ai-modules/status` shape; all listings require auth; empty listings return `[]`; new tables exist and existing vehicle endpoint unaffected |
| AI modules — isolation | 1 | a module throwing mid-persist does not break `_persist_detection` |
| Watchlist — normalization | 1 | separators/symbols stripped, uppercase; no lookalike folding (letter O stays O) |
| Watchlist — CRUD + RBAC | 3 | create→update→delete lifecycle; duplicate identifier → 409; viewer can read but gets 403 on write |
| Watchlist — lookup | 1 | `/watchlist/check/{plate}` normalizes `gj-33-tt-3311` and matches entry |
| Watchlist — matching gates | 1 | hit + alert recorded on confident read; below 0.70 confidence → no hit; expired entry → no hit |
| Watchlist — isolation | 1 | DB failure inside matching returns None instead of breaking ingestion |
| Watchlist — API/seed | 1 | `/watchlist/hits` shape; settings expose ENABLE_WATCHLIST + WATCHLIST_MATCH_MIN_CONFIDENCE |

### Error-path handling (implemented in code, exercised manually)

| Fault | Expected behaviour | Verified |
|---|---|---|
| RTSP URL unreachable | camera → `error`, message stored, backoff reconnect, API unaffected | ✅ manual (unroutable IP) |
| Demo file missing | camera → `error` "Cannot open source" | ✅ manual |
| No source URL configured | camera → `error`, retry loop, tile shows informative state | ✅ manual |
| AI stack not installed | worker streams video without detections; `/health` shows `degraded` + install hint | ✅ manual (default env) |
| OCR returns garbage/low confidence | stored with `needs_review=true`, surfaces in review queue; never auto-promoted to a vehicle identity | ✅ by construction + seed data review flow |
| DB connection failure | API returns structured 500 detail; worker logs and retries | ⚠️ partially manual (SQLite rename during run) |
| Malformed JWT / expired | 401 from `decode_token` | ✅ automated |
| Path traversal on media | 400 rejected (`..` guard) | ✅ code inspection + unit-style check |

### AI-module degradation & integration (verified live on the demo feed)

| Fault / scenario | Expected behaviour | Verified |
|---|---|---|
| `ultralytics` not installed | person module reports `available=false, error="No module named 'ultralytics'"`; worker loop unaffected | ✅ live log |
| Quality module with no heavy deps | samples demo feed every 100 frames; scores persisted with `is_demo=true` | ✅ live (`/ai-modules/quality/summary`) |
| Re-ID / anomaly with YOLO degraded | 0 rows (no detections to feed them); no fabricated data | ✅ live |
| Module disabled via flag/settings | call sites short-circuit before any work | ✅ unit test |
| Module raising mid-persist | swallowed by per-call-site handler; detection persist continues | ✅ unit test |

## 2. Manual test checklist (executed for the demo)

| # | Scenario | Result |
|---|---|---|
| 1 | Login as each role; menu/actions differ (viewer read-only) | ✅ |
| 2 | Overview loads stats from API; charts render; DEMO banner visible | ✅ |
| 3 | Live monitoring 3×2 grid; offline tiles show clear error + Retry; focus view streams demo video continuously >5 min | ✅ |
| 4 | Camera edit: attach `demo_traffic.mp4` → tile goes online within ~5 s | ✅ |
| 5 | Camera test-connection on unreachable RTSP → graceful failure message | ✅ |
| 6 | Credential entry: password never visible in UI after save; RTSP shown redacted | ✅ |
| 7 | Event history filters (camera/class/time/plate) + pagination | ✅ |
| 8 | Vehicle search `GJ01` → sightings timeline with honesty note | ✅ |
| 9 | GIS map: markers for 6 demo cameras; sighting diamonds; path polyline only for ≥2 recorded points | ✅ |
| 10 | Alerts: live toast/indicator on new alert; acknowledge/resolve persist after reload | ✅ |
| 11 | Reports: CSV downloads, opens in Excel, contains only real rows | ✅ |
| 12 | User management: create viewer, demote/enable/disable, self-protection guards | ✅ |
| 13 | Settings: update `DETECTION_CONFIDENCE` as admin; blocked as viewer | ✅ |
| 14 | WebSocket: LIVE indicator reflects API availability; reconnects after API restart | ✅ |
| 15 | Full-page reload deep-link (e.g. `#/events`) lands on login when unauthenticated, then returns | ✅ |

## 3. Not tested (honest scope)

- No GPU/CUDA execution verified (no CUDA device in the dev environment); code path exists and is config-gated.
- No long-duration soak test; no memory profiling beyond spot checks.
- No multi-worker (multi-process ingestion) run — supervision model is single-process by design in the PoC.
- No browser matrix testing beyond Chromium; MJPEG works in all evergreen browsers but tile counts were validated in one.
- Cross-camera correlation validated with seeded plate data; end-to-end ANPR accuracy on real plates requires authorized field footage and is **not** claimed.

## 4. Reproducing

```bash
# backend suite
cd backend && python -m pytest -q

# frontend typecheck + production build
cd frontend && npm run build
```
