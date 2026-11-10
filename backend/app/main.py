import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from backend.app.config import settings
from backend.app.models.database import init_db, get_db_connection
from backend.app.api import auth, incidents, routes, simulations, teams, events, health
from backend.app.services.incident_service import incident_service

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="MaleMitra (ಮಳೆ ಮಿತ್ರ) - Connected Monsoon Mobility & Civic Response Platform with Graph Ripple Simulation",
    version=settings.VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix=settings.API_PREFIX)
app.include_router(incidents.router, prefix=settings.API_PREFIX)
app.include_router(routes.router, prefix=settings.API_PREFIX)
app.include_router(simulations.router, prefix=settings.API_PREFIX)
app.include_router(teams.router, prefix=settings.API_PREFIX)
app.include_router(events.router, prefix=settings.API_PREFIX)
app.include_router(health.router, prefix=settings.API_PREFIX)

@app.on_event("startup")
def on_startup():
    init_db()
    # Check if demo incidents exist; if not, create initial demo scenarios
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

# Mount Static Frontend if built
dist_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend/dist"))
if os.path.exists(dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(dist_dir, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi.json"):
            return {"detail": "Not Found"}
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
