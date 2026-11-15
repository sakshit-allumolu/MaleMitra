import os
from pydantic import BaseModel

try:  # optional: load project-root .env (real environment variables still take precedence)
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class Settings(BaseModel):
    PROJECT_NAME: str = "MaleMitra (ಮಳೆ ಮಿತ್ರ)"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api/v1"
    # SQLite file (single host). Ignored when DATABASE_URL is set; still the base for the uploads folder.
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "backend/app/data/malemitra.db")
    # PostgreSQL connection string (postgresql://user:pass@host:5432/db). When set it replaces SQLite and
    # makes several workers / replicas on different hosts safe.
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    # Optional schema inside that database (created on startup); used by the test-suite for isolation.
    DATABASE_SCHEMA: str = os.getenv("DATABASE_SCHEMA", "")
    # Per-process connection pool. Keep WEB_CONCURRENCY * DB_POOL_MAX below PostgreSQL's max_connections.
    DB_POOL_MIN: int = int(os.getenv("DB_POOL_MIN", "1"))
    DB_POOL_MAX: int = int(os.getenv("DB_POOL_MAX", "10"))
    DB_POOL_TIMEOUT_SECONDS: float = float(os.getenv("DB_POOL_TIMEOUT_SECONDS", "15"))
    DEFAULT_JWT_SECRET: str = "malemitra-secret-key-bobathon-2026"
    JWT_SECRET: str = os.getenv("JWT_SECRET", "malemitra-secret-key-bobathon-2026")
    # DEMO_MODE=true: seeds demo users/incidents, accepts the demo passwords, shows the reset token
    # in the API response and allows self-service admin/responder sign-up with a public code.
    # Set DEMO_MODE=false for any real deployment (startup then refuses insecure settings).
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "true").lower() == "true"
    # Signed session tokens expire after this many seconds.
    SESSION_TTL_SECONDS: int = int(os.getenv("SESSION_TTL_SECONDS", "28800"))
    # Accept a bare user id as the bearer token (insecure; local dev and the test-suite only).
    # MUST be false on any public deployment.
    # Defaults to DEMO_MODE, so turning demo mode off also turns this off.
    ALLOW_LEGACY_TOKENS: bool = os.getenv(
        "ALLOW_LEGACY_TOKENS", os.getenv("DEMO_MODE", "true")).lower() == "true"
    # Comma-separated list of allowed browser origins. Empty = same-origin only (the built SPA is
    # served by this app). In DEMO_MODE with nothing set, "*" is used for convenience.
    CORS_ORIGINS: list = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
    # Return the password-reset token in the forgot-password response (no email channel needed for a demo).
    # Anyone could then reset any account, so set false on a public URL.
    EXPOSE_RESET_TOKEN: bool = os.getenv(
        "EXPOSE_RESET_TOKEN", os.getenv("DEMO_MODE", "true")).lower() == "true"
    # Public sign-up may only create citizens unless DEMO_MODE. Real admin/responder accounts are
    # created by an admin (POST /auth/users) or, for the first admin, via BOOTSTRAP_ADMIN_* below.
    ADMIN_SIGNUP_CODE: str = os.getenv("ADMIN_SIGNUP_CODE", "bbmp2026")  # demo only
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
    # Operational endpoints (timeline, audit log, SSE stream, teams) require a login.
    # In-memory rate limits (per client IP; single-process). 0 disables a limit.
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    RATE_LIMIT_AUTH_PER_MIN: int = int(os.getenv("RATE_LIMIT_AUTH_PER_MIN", "20"))
    # Per-account brute-force lockout: this many wrong passwords within the window blocks logins for it.
    LOGIN_MAX_FAILURES: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    LOGIN_LOCKOUT_SECONDS: int = int(os.getenv("LOGIN_LOCKOUT_SECONDS", "900"))
    RATE_LIMIT_REPORTS_PER_HOUR: int = int(os.getenv("RATE_LIMIT_REPORTS_PER_HOUR", "30"))
    RATE_LIMIT_SIMULATIONS_PER_MIN: int = int(os.getenv("RATE_LIMIT_SIMULATIONS_PER_MIN", "10"))
    # Photo uploads: stored on disk next to the database unless UPLOAD_DIR is set (mount a volume there).
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "")
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    RATE_LIMIT_UPLOADS_PER_HOUR: int = int(os.getenv("RATE_LIMIT_UPLOADS_PER_HOUR", "20"))
    # Cross-worker consistency: each request/SSE tick checks a shared epoch in the DB and rebuilds the
    # in-memory road graph when another worker changed it. Required when running >1 worker or replica.
    SHARED_SYNC_ENABLED: bool = os.getenv("SHARED_SYNC_ENABLED", "true").lower() == "true"
    MAX_SSE_CLIENTS: int = int(os.getenv("MAX_SSE_CLIENTS", "100"))

    # ── Notifications (transactional outbox + background dispatcher) ────────────
    # Email goes out through SMTP when SMTP_HOST is set. SMS/push go to a webhook you operate
    # (a gateway such as Twilio/MSG91 behind a tiny relay): we POST signed JSON to NOTIFY_WEBHOOK_URL.
    # With neither configured, messages are only logged (DEMO_MODE, or NOTIFY_LOG_ONLY=true).
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", "MaleMitra <no-reply@malemitra.local>")
    SMTP_STARTTLS: bool = os.getenv("SMTP_STARTTLS", "true").lower() == "true"
    SMTP_SSL: bool = os.getenv("SMTP_SSL", "false").lower() == "true"  # implicit TLS (port 465)
    NOTIFY_WEBHOOK_URL: str = os.getenv("NOTIFY_WEBHOOK_URL", "")
    NOTIFY_WEBHOOK_SECRET: str = os.getenv("NOTIFY_WEBHOOK_SECRET", "")  # HMAC-SHA256 signing key
    NOTIFY_LOG_ONLY: bool = os.getenv("NOTIFY_LOG_ONLY", "false").lower() == "true"
    NOTIFY_ENABLED: bool = os.getenv("NOTIFY_ENABLED", "true").lower() == "true"
    NOTIFY_POLL_SECONDS: float = float(os.getenv("NOTIFY_POLL_SECONDS", "5"))
    NOTIFY_MAX_ATTEMPTS: int = int(os.getenv("NOTIFY_MAX_ATTEMPTS", "6"))
    NOTIFY_TIMEOUT_SECONDS: int = int(os.getenv("NOTIFY_TIMEOUT_SECONDS", "10"))
    
    # Area covered by the hand-built road graph (Koramangala, Indiranagar, Domlur, HSR, Ejipura). Only inside this
    # box (plus a small margin) are reports mapped to graph edges and graph risk scores used for routing.
    MIN_LAT: float = 12.9000
    MAX_LAT: float = 12.9950
    MIN_LON: float = 77.5800
    MAX_LON: float = 77.6800

    # Service area for the whole city: min_lon,min_lat,max_lon,max_lat. Routes and incident reports are accepted
    # only inside it. Default is the compose OSRM_BBOX inset by ~2 km, because OSRM silently snaps points outside
    # its map to the nearest edge road and returns a plausible but wrong route. Keep it inside OSRM_BBOX if you
    # change either.
    ROUTE_AREA_BBOX: str = os.getenv("ROUTE_AREA_BBOX", "77.42,12.82,77.78,13.13")
    
    # A new report within this many metres of an open incident is counted on that incident instead of
    # creating another one (0 disables merging). Phone GPS is typically 5-10 m off, hence the default.
    DUPLICATE_RADIUS_M: float = float(os.getenv("DUPLICATE_RADIUS_M", "10"))

    # Congestion BPR function parameters
    BPR_ALPHA: float = 0.20
    BPR_BETA: float = 2.5
    
    # Routing Penalty Weights (seconds equivalence)
    HAZARD_LAMBDA: float = 180.0  # Reported unverified hazard penalty in seconds
    CONGESTION_MU: float = 1.0    # Modeled congestion delay multiplier

    # Live traffic (TomTom Traffic Flow Segment Data). Disabled when no key is set.
    TOMTOM_API_KEY: str = os.getenv("TOMTOM_API_KEY", "")
    LIVE_TRAFFIC_POLL_SECONDS: int = int(os.getenv("LIVE_TRAFFIC_POLL_SECONDS", "1020"))
    LIVE_TRAFFIC_DAILY_REQUEST_BUDGET: int = int(os.getenv("LIVE_TRAFFIC_DAILY_REQUEST_BUDGET", "2400"))  # free tier = 2500/day
    LIVE_TRAFFIC_TTL_SECONDS: int = int(os.getenv("LIVE_TRAFFIC_TTL_SECONDS", "2400"))  # ignore readings older than this
    LIVE_TRAFFIC_MIN_CONFIDENCE: float = 0.5
    LIVE_TRAFFIC_MAX_VC: float = 3.0

    # Traffic-aware routing (TomTom Routing API). Gives live-traffic ETAs for /routes/compare. Needs
    # TOMTOM_API_KEY; the budget is a rolling 24h cap shared by all workers and counts against the same
    # TomTom quota as the flow poller above (free tier = 2500/day across both).
    TOMTOM_ROUTING_ENABLED: bool = os.getenv("TOMTOM_ROUTING_ENABLED", "true").lower() == "true"
    TOMTOM_ROUTING_DAILY_BUDGET: int = int(os.getenv("TOMTOM_ROUTING_DAILY_BUDGET", "800"))
    TOMTOM_ROUTING_TIMEOUT_SECONDS: float = float(os.getenv("TOMTOM_ROUTING_TIMEOUT_SECONDS", "5"))
    TOMTOM_ROUTING_CACHE_TTL_SECONDS: int = int(os.getenv("TOMTOM_ROUTING_CACHE_TTL_SECONDS", "120"))

    # watsonx Orchestrate agent integration.
    # AGENT_TOOL_API_KEY: shared secret Orchestrate sends (X-API-Key) when calling our tool endpoints.
    # Tools are disabled (401) until it is set, so nothing is exposed by default.
    AGENT_TOOL_API_KEY: str = os.getenv("AGENT_TOOL_API_KEY", "")
    # Public base URL Orchestrate can reach (e.g. an ngrok https URL). Written into the exported OpenAPI spec.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
    # Orchestrate connection (Orchestrate API key -> bearer token -> instance REST API).
    # Default token URL is for Orchestrate SaaS keys (Settings > API details > Generate API key).
    # For a classic IBM Cloud API key set ORCHESTRATE_IAM_URL=https://iam.cloud.ibm.com/identity/token
    ORCHESTRATE_API_KEY: str = os.getenv("ORCHESTRATE_API_KEY", "")
    ORCHESTRATE_INSTANCE_URL: str = os.getenv("ORCHESTRATE_INSTANCE_URL", "").rstrip("/")
    ORCHESTRATE_IAM_URL: str = os.getenv(
        "ORCHESTRATE_IAM_URL", "https://account-iam.platform.saas.ibm.com/api/2.0/apikeys/token")
    ORCHESTRATE_AGENT_ID: str = os.getenv("ORCHESTRATE_AGENT_ID", "")
    # Path templates are configurable because the exact REST path depends on the Orchestrate
    # edition/version; confirm against your instance's API reference. {agent_id} is substituted.
    ORCHESTRATE_CHAT_PATH: str = os.getenv("ORCHESTRATE_CHAT_PATH", "/v1/orchestrate/{agent_id}/chat/completions")
    ORCHESTRATE_TIMEOUT_SECONDS: int = int(os.getenv("ORCHESTRATE_TIMEOUT_SECONDS", "60"))

    # Send Strict-Transport-Security on HTTPS responses. Defaults on outside demo mode.
    HSTS_ENABLED: bool = os.getenv(
        "HSTS_ENABLED", "false" if os.getenv("DEMO_MODE", "true").lower() == "true" else "true").lower() == "true"

    # Road-following geometry via OSRM. Self-host OSRM for production; the public demo server is
    # rate-limited and has no SLA. Failures fall back to graph geometry (circuit breaker below).
    OSRM_ENABLED: bool = os.getenv("OSRM_ENABLED", "true").lower() == "true"
    OSRM_BASE_URL: str = os.getenv("OSRM_BASE_URL", "https://router.project-osrm.org/route/v1/driving")
    OSRM_VERIFY_TLS: bool = os.getenv(
        "OSRM_VERIFY_TLS", "false" if os.getenv("DEMO_MODE", "true").lower() == "true" else "true").lower() == "true"
    OSRM_TIMEOUT_SECONDS: float = float(os.getenv("OSRM_TIMEOUT_SECONDS", "4"))
    OSRM_CACHE_TTL_SECONDS: int = int(os.getenv("OSRM_CACHE_TTL_SECONDS", "600"))
    OSRM_BREAKER_THRESHOLD: int = int(os.getenv("OSRM_BREAKER_THRESHOLD", "3"))
    OSRM_BREAKER_COOLDOWN_SECONDS: int = int(os.getenv("OSRM_BREAKER_COOLDOWN_SECONDS", "60"))


settings = Settings()


def in_graph_area(lat: float, lon: float, margin_deg: float = 0.0) -> bool:
    """True when the point is inside the hand-built road graph (MIN/MAX_LAT/LON)."""
    return (settings.MIN_LAT - margin_deg <= lat <= settings.MAX_LAT + margin_deg
            and settings.MIN_LON - margin_deg <= lon <= settings.MAX_LON + margin_deg)


def in_service_area(lat: float, lon: float) -> bool:
    """True when the point is inside the city-wide area (ROUTE_AREA_BBOX) that routing and reports support."""
    min_lon, min_lat, max_lon, max_lat = (float(v) for v in settings.ROUTE_AREA_BBOX.split(","))
    return min_lat <= lat <= max_lat and min_lon <= lon <= max_lon


def production_problems(s: "Settings" = settings) -> list:
    """Reasons this configuration is unsafe for a real deployment (empty list = fine)."""
    problems = []
    if s.JWT_SECRET == s.DEFAULT_JWT_SECRET or len(s.JWT_SECRET) < 32:
        problems.append("JWT_SECRET must be set to a random value of at least 32 characters.")
    if s.ALLOW_LEGACY_TOKENS:
        problems.append("ALLOW_LEGACY_TOKENS must be false (a bare user id would otherwise be a valid login).")
    if "*" in s.CORS_ORIGINS:
        problems.append("CORS_ORIGINS must list explicit origins, not '*'.")
    return problems
