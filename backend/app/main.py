import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool
from backend.app import shared
from backend.app.config import settings, production_problems
from backend.app.models.database import init_db, get_db_connection, startup_lock
from backend.app.api import auth, incidents, routes, simulations, teams, events, health, agents, agent_tools, notifications, uploads
from backend.app.services.incident_service import incident_service
from backend.app.services.live_traffic_service import live_traffic
from backend.app.services.notification_service import dispatcher as notification_dispatcher

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper(),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("malemitra")


def seed_demo_incidents() -> None:
    """DEMO_MODE only: create two sample incidents when the database is empty (once, even with N workers)."""
    with startup_lock("seed"):
        _seed_demo_incidents()


def _seed_demo_incidents() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM incidents")
    count = cursor.fetchone()[0]
    conn.close()

    if count == 0:
        # Seed Demo Incident 1: Sony World Junction severe waterlogging (Reported -> Assigned)
        inc1 = incident_service.create_report(
            user_id="usr-citizen-1",
            user_name="Citizen Commuter (Pooja)",
            lat=12.9352,
            lon=77.6245,
            inc_type="waterlogging",
            severity="critical",
            description="Sony World Junction underpass completely submerged. Water rising past knee level (>45cm). Vehicles stalling.",
            evidence_note="Observed 2 cars stranded at junction entrance."
        )
        # Seed Demo Incident 2: Indiranagar 100ft Road drain overflow (Reported)
        incident_service.create_report(
            user_id="usr-citizen-2",
            user_name="Citizen Driver (Kiran)",
            lat=12.9710,
            lon=77.6435,
            inc_type="drain_overflow",
            severity="medium",
            description="Storm drain overflowing across 100ft Road near 12th Main junction. Puddle depth ~20cm. Slow moving traffic.",
            evidence_note="Debris blocking roadside storm grates."
        )
        # Advance Incident 1 to Assigned for immediate responder demo
        if inc1 and "id" in inc1:
            incident_service.admin_review(inc1["id"], "usr-admin-1", "BBMP Monsoon Control Room Admin", "Priority critical waterlogging report verified via citizen photo evidence.")
            incident_service.admin_assign_team(inc1["id"], "usr-admin-1", "BBMP Monsoon Control Room Admin", "team-alpha", "Dispatch pump truck and inspection team.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.DEMO_MODE:
        problems = production_problems()
        if problems:
            raise RuntimeError("Refusing to start with DEMO_MODE=false and insecure settings:\n - "
                               + "\n - ".join(problems))
    elif production_problems():
        log.warning("DEMO_MODE is on: demo accounts, public admin sign-up code and legacy tokens are enabled. "
                    "Set DEMO_MODE=false (and JWT_SECRET, CORS_ORIGINS) before any public deployment.")
    init_db()
    restored = incident_service.restore_graph_state()
    log.info("Restored road graph from database: %s", restored)
    if settings.SHARED_SYNC_ENABLED:
        shared.sync_graph(force=True)  # also recomputes flows for any closures restored above
    live_traffic.start()
    notification_dispatcher.start()
    if settings.DEMO_MODE:
        seed_demo_incidents()
    yield
    live_traffic.stop()
    notification_dispatcher.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MaleMitra (ಮಳೆ ಮಿತ್ರ) - Connected Monsoon Mobility & Civic Response Platform with Graph Ripple Simulation",
    version=settings.VERSION,
    lifespan=lifespan,
)

@app.exception_handler(RequestValidationError)
async def log_agent_tool_validation_errors(request: Request, exc: RequestValidationError):
    """Orchestrate reports any 4xx as a vague "network error"; record what it actually sent so it can be fixed."""
    if "/agent-tools/" in request.url.path:
        log.warning("agent tool call rejected path=%s errors=%s body=%r", request.url.path,
                    [{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()], str(exc.body or "")[:300])
    return await request_validation_exception_handler(request, exc)


# CORS: the SPA is served by this app (same origin), so no cross-origin access is needed by default.
_cors_origins = settings.CORS_ORIGINS or (["*"] if settings.DEMO_MODE else [])
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# The SPA only needs: its own bundle, Leaflet CSS (unpkg, SRI-pinned), OSM tiles and Nominatim search.
_DOC_PATHS = ("/docs", "/redoc", "/openapi.json")
_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://unpkg.com",
    "img-src 'self' data: blob: https://*.tile.openstreetmap.org https://unpkg.com",
    "font-src 'self' data:",
    "connect-src 'self' https://nominatim.openstreetmap.org",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])


@app.middleware("http")
async def request_logging_and_headers(request: Request, call_next):
    request_id = uuid.uuid4().hex[:8]
    start = time.perf_counter()
    if settings.SHARED_SYNC_ENABLED and request.url.path.startswith(settings.API_PREFIX):
        try:
            # Another worker may have closed a road or changed hazards since our last request.
            await run_in_threadpool(shared.sync_graph)
        except Exception:
            log.exception("rid=%s graph sync failed; serving with possibly stale road state", request_id)
    try:
        response = await call_next(request)
    except Exception:
        log.exception("Unhandled error rid=%s %s %s", request_id, request.method, request.url.path)
        raise
    ms = (time.perf_counter() - start) * 1000
    if request.url.path != f"{settings.API_PREFIX}/health" and not request.url.path.startswith("/assets"):
        log.info("rid=%s %s %s -> %s %.0fms", request_id, request.method, request.url.path, response.status_code, ms)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), payment=(), usb=()"
    if not request.url.path.startswith(_DOC_PATHS):  # Swagger/ReDoc load assets from a CDN
        response.headers.setdefault("Content-Security-Policy", _CSP)  # keep stricter route-level CSPs
    if settings.HSTS_ENABLED and request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Include Routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(incidents.router, prefix=settings.API_PREFIX)
app.include_router(routes.router, prefix=settings.API_PREFIX)
app.include_router(simulations.router, prefix=settings.API_PREFIX)
app.include_router(teams.router, prefix=settings.API_PREFIX)
app.include_router(events.router, prefix=settings.API_PREFIX)
app.include_router(health.router, prefix=settings.API_PREFIX)
app.include_router(agents.router, prefix=settings.API_PREFIX)
app.include_router(agent_tools.router, prefix=settings.API_PREFIX)
app.include_router(notifications.router, prefix=settings.API_PREFIX)
app.include_router(uploads.router, prefix=settings.API_PREFIX)

# Mount Static Frontend if built
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")
    
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        if full_path.startswith(("api/", "docs", "openapi.json", "redoc")) or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        # Serve real files from the build (favicon etc.), never anything outside dist_dir.
        candidate = os.path.realpath(os.path.join(dist_dir, full_path))
        if full_path and candidate.startswith(os.path.realpath(dist_dir) + os.sep) and os.path.isfile(candidate):
            return FileResponse(candidate)
        index_file = os.path.join(dist_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"platform": settings.PROJECT_NAME, "version": settings.VERSION}
else:
    @app.get("/")
    def root():
        return {
            "platform": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "documentation": "/docs",
            "health": "/api/v1/health"
        }
