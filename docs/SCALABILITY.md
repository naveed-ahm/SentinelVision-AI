# SentinelVision AI — Scalability Path

> **Honesty statement:** the current implementation is a PoC validated on a
> handful of sources on a laptop. Nothing below is a benchmark; it is an
> engineering plan with **explicit assumptions** so reviewers can check the math.
> Numbers marked ⚠️ are load-bearing assumptions that must be re-measured on
> target hardware before procurement decisions.

## 1. What the PoC already does right

- Video/AI work is isolated from the API process (no UI stalls from capture).
- The API is stateless beyond the in-memory rate limiter and WS bus — both have
  documented swap-outs (gateway limiter, Redis pub/sub).
- The live-frame store is a disk seam: replacing it with Redis/NATS keeps the
  API contract identical.
- Every hot table has covering indexes; pagination is server-side everywhere.
- Media lives on the filesystem behind a storage interface (swap for S3/MinIO).
- Worker count, source count, sampling interval and thresholds are config.

## 2. Load model (explicit assumptions)

| Parameter | ⚠️ Assumption | Basis |
|---|---|---|
| Cameras (target fleet) | 80,000 | hackathon brief |
| Simultaneously streamed to AI | 10% (8,000) | typical: AI only on priority corridors |
| Stream profile | 1080p @ 15 fps, H.264, 2 Mbps | typical city CCTV |
| AI sampling | 2 fps per camera (`DETECTION_SAMPLE_INTERVAL≈0.5`) | vehicles move slowly vs. frame rate |
| Detections persisted | ~1 per vehicle pass (throttled) | worker throttle 1 event / 2 s / track |
| ANPR on | 50% of AI cameras | plates readable only where cameras face traffic |
| Retention (events metadata) | 90 d | configurable |
| Retention (crop JPEGs ~40 KB) | 30 d | configurable |
| DB peak writes | ~6,000 events/s worst case ⚠️ | 8,000 cams × 2 fps × 40% pass-rate — must be measured; batching/sharding below assumes it is far lower in practice |

**AI compute sizing (rule-of-thumb, to be benchmarked):** a modern GPU sustains
roughly 10–20 concurrent 1080p→640px YOLOv8n streams at 2 fps inference. For
8,000 AI streams: **~400–800 GPU workers** — i.e. regional clusters of ~50–100
cameras per GPU node. This is an extrapolation from per-stream cost, not a
measured number; validate with the real model and pre-processing pipeline.

**Network:** AI ingest alone ≈ 8,000 × 2 Mbps ≈ **16 Gbps** within each region —
regional ingestion is mandatory; centralizing raw streams is not viable.

## 3. Target architecture (per region)

```
┌─ Region ──────────────────────────────────────────────────────┐
│  Camera → gateway/proxy (RTSP relay, per-site)                │
│    → Ingestion worker pool (K8s jobs/daemonsets, N per node)  │
│        → frames: Redis pub/sub or NATS (annotated JPEGs)      │
│        → events: message broker (RabbitMQ/Redpanda)           │
│    → Event sink service: batch upserts (COPY / executemany)   │
│    → PostgreSQL (primary + replica), partitioned event tables │
│    → Object store (S3/MinIO) for crops/plates                 │
│    → API replicas (stateless, behind LB) ← WS via Redis bus   │
└──────────────┬────────────────────────────────────────────────┘
               │ aggregated events/rollups (not raw streams)
               ▼
        Central cluster: global search, GIS, national dashboards,
        disaster-recovery replica of the summary DB
```

| PoC component | Production swap | Effort |
|---|---|---|
| `workers/live_store` (disk) | Redis pub/sub or NATS JetStream | small — one module |
| in-process `EventBus` | Redis pub/sub fan-out per API pod | small |
| in-memory rate limiter | gateway (nginx limit_req / cloud WAF) | none in app |
| `LocalStorage` | S3/MinIO via storage interface | small |
| sync SQLAlchemy writes | broker + batch writer (async) | medium |
| single worker process | K8s-managed worker pool, one shard per N cameras | medium |
| SQLite/Postgres single node | partitioned Postgres + read replicas (+ Citus if needed) | medium/large |

## 4. Database strategy at fleet scale

- **Partitioning:** `detection_events` and `vehicle_sightings` partitioned by
  month (declarative range partitioning); drop-partition for retention instead
  of DELETE storms.
- **Rollups:** hourly/daily aggregate tables (counts per camera/class, ANPR
  rate, availability) maintained by a scheduled job — the dashboard reads
  rollups, never raw scans. The current `analytics_service` already does all
  aggregation in SQL and is structured to switch sources.
- **Search:** plate lookups become index-only range scans on
  `(registration_number, timestamp)`; for >10⁹ sightings consider OpenSearch
  for free-text/time facets.
- **Connection hygiene:** pool per pod (`pool_size=10` currently), pgbouncer in
  front of Postgres for the writer fleet.

## 5. Camera health at scale

Health checks at 80k cameras cannot be sequential HTTP probes from one box.
Plan: workers report liveness with every frame batch (already the model —
`ALERT_OFFLINE_AFTER` based on frame age); a regional monitor only probes
cameras that have *not* reported, with exponential backoff — reducing probe
load to the (small) failing set.

## 6. What we deliberately do NOT claim

- No measured GPU throughput numbers (rule-of-thumb only, flagged above).
- No claim that MJPEG scales to thousands of concurrent viewers — at fleet
  scale the viewer path must move to HLS/WebRTC via a media server tier.
- No claim of tested multi-region failover; the DR design is a document-level
  proposal (regional autonomy + summary replication).

## 7. Near-term hardening roadmap (highest value first)

1. Broker-based event pipeline + batch writer (decouples DB from workers).
2. Redis live-frame store + WS bus → first true horizontal API scale-out.
3. HLS delivery tier (go2rtc or mediamtx) for multi-viewer monitoring walls.
4. Event-table partitioning + rollup job + retention automation.
5. Prometheus/Grafana metrics from worker stats (fps, inference latency, queue depth).
6. Object storage for media with lifecycle rules replacing local cleanup.
