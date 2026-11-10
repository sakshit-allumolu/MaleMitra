# MaleMitra (ಮಳೆ ಮಿತ್ರ)
### A Connected Monsoon Mobility and Civic Response Platform
**IBM Bobathon 2026 Submission • Theme: Smarter Streets, Better Living**

---

## 1. Executive Summary & Value Proposition

During heavy Bengaluru monsoon rainfall, commuters receive fragmented information about waterlogged roads, while citizen hazard reports, municipal control room review, and field verification are disconnected. This causes dangerous vehicle entrapment in submerged underpasses and uncoordinated response dispatch.

**MaleMitra (ಮಳೆ ಮಿತ್ರ)** connects the complete incident-to-response loop into a single deployable modular monolith:
1. **Citizen Workspace**: Submit geotagged waterlogging reports, view map hazards with verified provenance, and compare **Direct vs. MaleMitra Risk-Aware Detour vs. Alternative Corridor** routes.
2. **Administrator Workspace**: Control room triage queue, spatial road edge association, response team dispatch, and emergency road restriction/reopening authorization.
3. **Simulated Emergency Responder Workspace**: Mobile-optimized field view for on-site inspection, water depth measurement (cm), impassability verification, and dewatering clearance proposals.
4. **Signature Innovation — Graph-Based Ripple Engine**: Models how one verified road closure dynamically redirects 150 synthetic monsoon trips across bounded Bengaluru corridors (Koramangala, Indiranagar, Domlur, Ejipura, HSR, Silk Board), calculating cascading traffic migration ($\Delta v$) and Bureau of Public Roads (BPR) congestion delays.

```
Citizen Report ──► Spatial Edge Mapping ──► IncidentAgent Evidence Summary
      ▲                                                   │
      │                                                   ▼
Rerouted Citizen Route ◄── Graph Version++ ◄── Admin Closure Authorization
      │                                                   │
      ▼                                                   ▼
Ripple Engine Recomputes 150 Trips              Responder Field Inspection
(Cascade Congestion Deltas)                     (55cm Depth & Impassable Verified)
```

---

## 2. Measurable Impact & Benchmark Results

MaleMitra includes a standalone, reproducible evaluation harness ([`backend/eval_benchmark.py`](backend/eval_benchmark.py:1)) running 150 seeded Origin-Destination trips on the bounded Bengaluru road graph:

| Metric | Baseline (Blind Shortest Path) | MaleMitra (Risk & Ripple Aware) | Demonstrated Impact |
| :--- | :---: | :---: | :---: |
| **Trips Crossing Blocked Road** | **38 trips (25.3%)** | **0 trips (0.0%)** | **100% Elimination of Blocked Exposure** |
| **Mean Trip Duration** | 366.7 seconds | 381.0 seconds | +14.2s (+3.9%) Detour Trade-off |
| **Stranded / No Route Rate** | 0.0% | 0.0% | Full Network Reachability Preserved |
| **Evaluation Harness Runtime** | — | **8.8 ms** | Fast, Deterministic Pure Python Engine |

*Benchmark outputs are persisted to [`backend/app/data/benchmark_results.json`](backend/app/data/benchmark_results.json) and [`backend/app/data/benchmark_results.csv`](backend/app/data/benchmark_results.csv).*

---

## 3. Pre-Seeded Demo Accounts

All demo accounts use password **`demo123`** and can be switched instantly via the top navigation bar dropdown:

| Role | Name | Email | Default Team / Authority |
| :--- | :--- | :--- | :--- |
| **Citizen** | Pooja (Citizen Commuter) | `citizen@malemitra.in` | Submit reports, compare routes, track hazards |
| **Administrator** | BBMP Monsoon Control Room Admin | `admin@malemitra.in` | Review triage, dispatch teams, authorize road closures/reopenings |
| **Responder 1** | Inspector Ramesh | `responder1@malemitra.in` | Team Alpha (Stormwater & Dewatering Pump Unit) |
| **Responder 2** | Officer Kavitha | `responder2@malemitra.in` | Team Beta (Traffic & Debris Unit) |

---

## 4. Multi-Agent System Architecture

MaleMitra orchestrates 4 logical agents with typed tool contracts and audit logging:

1. **Incident Intelligence Agent** ([`backend/app/services/agent_service.py`](backend/app/services/agent_service.py:1)):
   - Tools: `classify_report`, `find_nearby_reports`, `map_to_edge`
   - Maps geotagged $(lat, lon)$ to candidate road edge via Haversine perpendicular projection; flags parallel ambiguity and computes confidence score.
2. **Mobility Agent** ([`backend/app/services/agent_service.py`](backend/app/services/agent_service.py:1)):
   - Tools: `compute_fastest`, `compute_risk_aware`, `compare_routes`
   - Computes generalized edge cost: $W(e) = T(e) + \lambda \cdot R(e) + \mu \cdot C(e)$ and Yen's k-shortest diverse paths.
3. **Ripple Impact Agent** ([`backend/app/services/ripple_service.py`](backend/app/services/ripple_service.py:1)):
   - Tools: `assign_trips`, `estimate_load`, `compare_scenarios`
   - Simulates 150 synthetic trips, applies Frank-Wolfe / BPR equilibrium curve: $t = t_0 [1 + \alpha (v/c)^\beta]$, and identifies top affected detour corridors.
4. **Response Coordinator Agent** ([`backend/app/services/agent_service.py`](backend/app/services/agent_service.py:1)):
   - Tools: `recommend_priority`, `propose_assignment`, `request_review`
   - Suggests response team dispatch based on hazard severity and proximity.

---

## 5. Technology Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS / Custom Civic Design System (`#123047` navy, `#0B8B95` teal, `#3576B8` rain blue, `#C78420` amber, `#B53A3A` red), Leaflet Map with custom SVG pins, Lucide Icons.
- **Backend**: Python 3.9+ / 3.11, FastAPI, Pydantic v2, Starlette, SQLite3 with WAL mode.
- **Algorithms**: Pure Python Graph Engine (`RoadGraph`), Dijkstra shortest path, Yen's k-shortest paths, Haversine spatial indexing, BPR congestion delay function.
- **Testing & QA**: Pytest test suite covering acceptance tests T01–T15 with 100% pass rate.

---

## 6. How to Run Locally

### Quick Start (Python + Node.js)

1. **Start Backend API Server**:
   ```bash
   ./venv/bin/python3 -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   *Backend API & Swagger Docs will be available at `http://localhost:8000/docs`.*

2. **Start Frontend Development Server**:
   ```bash
   cd frontend
   npm run dev
   ```
   *Open `http://localhost:5173` in your browser.*

3. **Run Evaluation Benchmark CLI**:
   ```bash
   ./venv/bin/python3 backend/eval_benchmark.py
   ```

4. **Run Pytest Acceptance Test Suite**:
   ```bash
   ./venv/bin/python3 -m pytest backend/tests/
   ```

---

## 7. Docker Deployment

To build and run the entire modular monolith in a single container:

```bash
docker-compose up --build
```
*Application available at `http://localhost:8000`.*

---

## 8. Authentic IBM Bob Story

Throughout the implementation of MaleMitra, **IBM Bob** was used to scaffold typed contracts, implement routing logic, debug failing regression tests, and evaluate network impact:

1. **Typed Scaffolding**: IBM Bob generated the complete Pydantic v2 schema contract ([`backend/app/models/schemas.py`](backend/app/models/schemas.py:1)) and the 8-state incident machine (`reported` $\rightarrow$ `under_review` $\rightarrow$ `assigned` $\rightarrow$ `field_verified` $\rightarrow$ `blocked` $\rightarrow$ `clearance_proposed` $\rightarrow$ `cleared`).
2. **Graph-Based Ripple Engine Implementation**: Bob authored the pure-Python Dijkstra and Bureau of Public Roads (BPR) delay curves in [`backend/app/services/ripple_service.py`](backend/app/services/ripple_service.py:1) to ensure deterministic execution without bulky external GIS overhead.
3. **Test-Driven Debugging**: When initial acceptance tests failed due to asynchronous Starlette testclient table initialization, Bob applied surgical diffs to [`backend/app/models/database.py`](backend/app/models/database.py:1), immediately resolving all 17 acceptance tests.
4. **Reproducible Benchmark Generation**: Bob generated the evaluation harness ([`backend/eval_benchmark.py`](backend/eval_benchmark.py:1)) providing empirical proof of the 100% reduction in blocked segment traversal.

---
*Made with IBM Bob for Bobathon 2026*
