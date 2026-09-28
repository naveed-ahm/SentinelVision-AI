# SentinelVision AI — Presentation Outline (PPT)

**Format:** ~14 slides · solution presentation for the Gujarat Police Innovation Challenge 2026
**Track:** Model 1 + Model 2 hybrid · Category 1/2 as registered
**Rule reminder:** slides carry the story; the working platform carries the proof. Export as PPT **or PDF** per portal requirements.

> Design language suggestion: dark command-center theme matching the product (deep navy + accent blue),
> consistent 2-line max per bullet, one visual per slide, demo screenshots from the live app.

---

### Slide 1 — Title
- **SentinelVision AI** — One Platform for 80,000 Eyes
- Integrated CCTV Management & Real-Time AI Video Analytics
- Team name · members · contact · track: Model 1+2 hybrid
- Visual: single hero shot of the command-center UI (live camera wall)

### Slide 2 — The Problem
- 80,000+ cameras across 26+ departments — **zero federation**: separate registries, separate rooms, separate truths
- Investigations today: teams manually hop feeds; a vehicle trail takes hours/days
- No ANPR at scale, no watchlists, no automatic alerts — cameras record, they don't *watch*
- Visual: "camera silos" diagram (department boxes, no connecting lines)

### Slide 3 — Our Answer (one-liner)
- Register every camera → Analyze every feed → Answer two questions instantly:
  **"Where is this vehicle?"** and **"Has this plate appeared?"**
- Visual: 3-step arrow (Registry → AI → Answer)

### Slide 4 — Solution Overview
- Full-stack platform: camera registry + GIS, live monitoring wall, real-time detection/ANPR,
  cross-camera vehicle tracking, watchlist console, alerting — **all working today**
- Visual: product architecture on one line: Cameras → AI Workers → Metadata → Dashboards
- Badge: "Working software, not a concept — repo + live demo"

### Slide 5 — Model Mapping (compliance slide — judges check this)
- **Model 1 (compulsory) ✔** Centralised registry: every camera with department, location, GIS plot,
  health/uptime monitoring, multi-department federation
- **Model 2 ✔** Real-time analytics: YOLOv8 detection, PaddleOCR ANPR, per-camera tracking +
  cross-camera Re-ID, watchlist matching, WebSocket alerts
- Hybrid architecture explicitly allowed; edge-ready path to Model 3/4 patterns (HLD §6)
- Visual: two-column checklist Model 1 | Model 2, every line ticked

### Slide 6 — Live Demo Script (what the jury will see)
1. Login → Command Center: 6 live feeds, stats updating in real time
2. Monitoring wall: annotated streams — vehicle boxes + **plate overlays drawn live**
3. Watchlist: add a plate → hit appears with evidence crop + alert within one sampling cycle
4. Track a plate: timestamped camera-by-camera route reconstructed on the map
- Visual: 4 numbered screenshot strips (use real captures)

### Slide 7 — Vehicle Route Reconstruction *(the sandbox live test)*
- Hackathon-day task: given a plate → **full route with timestamped, location-wise history**
- Mechanism: plate_reads ⟕ camera registry → timeline + map polyline; keeps updating while vehicle moves
- Visual: fake-but-shaped route card: plate, 5 camera stops with times, map line

### Slide 8 — AI Pipeline
- YOLOv8 (CUDA) per-stream detection → plate crop → PaddleOCR (0.97–1.00 conf live) →
  normalize → match watchlist / index for search
- Tiered cross-camera Re-ID (embedding → heuristic); MOG2 fallback keeps degraded feeds useful
- Visual: left-to-right pipeline diagram with a real evidence crop at the end

### Slide 9 — Architecture
- 4 tiers: Sources → Ingestion/Analytics workers → Data/API → Web
- Stateless workers, registry-driven assignment, ring-buffer live store, WS alert bus
- Visual: the HLD §3 diagram, simplified to fit

### Slide 10 — Evidence & Engineering Rigor
- 45 automated tests, CI on every push, seeded reproducible demo, JWT RBAC (3 roles)
- Live numbers from our run: 6 concurrent streams · <1 s event→dashboard latency · sustained on one consumer GPU
- Visual: test/CI badges + a latency counter screenshot

### Slide 11 — Scale Path: 6 → 80,000
- Analytics is per-stream → capacity = nodes × streams; district edge POPs (~1,500 cams each),
  state core keeps metadata only; bandwidth stays local (KB events, not video)
- Metadata is the product: 80k feeds become indexed rows — search at state scale = SQL
- Visual: horizontal growth bar: PoC → city → state (55 POPs)

### Slide 12 — Security, Privacy & Human-in-the-Loop
- JWT + RBAC; every watchlist match routes to a human for acknowledgment — decision support,
  never automated action; retention/redaction roadmap (DPDP-aligned) in HLD §7
- Visual: operator-acknowledgment screenshot of a watchlist hit

### Slide 13 — Roadmap to Production
- Postgres + object storage · VAHAN/SARTHI/eGujCop/AFIS/NAFIS correlation adapters ·
  WebRTC/HLS ingest · K8s worker pools + observability · department SSO + audit
- Visual: quarter-by-quarter timeline

### Slide 14 — Ask & Close
- "SentinelVision AI is running now — give us the feeds and a plate."
- Team + contact · repo link
- Visual: command-center hero again, single line of text

---

## Speaker notes (60-second version of the whole deck)

> Gujarat has eighty thousand cameras and no single picture. SentinelVision AI unifies them into one
> registry — every camera on a map with live health — and analyzes every feed in real time: vehicles,
> plates, watchlists, alerts. Everything you'll see is working software: our demo adds a plate to the
> watchlist and catches it on another camera within seconds, then reconstructs a vehicle's route with
> timestamps — exactly the live test you'll run on sandbox day. The same architecture scales from our
> six cameras to eighty thousand by pushing analytics to district edge nodes and keeping only
> searchable metadata at the core. We're not proposing a concept — it's built, tested, and ready for
> your feeds.

---

## Asset checklist (capture from the live app before exporting)
- [ ] Command center hero (Overview page, stats populated)
- [ ] Monitoring wall 2×2 with visible plate overlays
- [ ] Watchlist hit row with evidence thumbnail + ON-WATCHLIST banner
- [ ] Track page route (plate → timeline + map)
- [ ] Alerts feed with a watchlist_hit alert
- [ ] GIS map with camera pins
- [ ] Pipeline/architecture diagrams (redraw clean from HLD §3 and §5)
