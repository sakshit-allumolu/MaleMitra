from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from backend.app.config import settings

# Reports are only meaningful inside the modelled service area (plus a small margin).
_MARGIN_DEG = 0.02
IncidentTypeName = Literal["waterlogging", "drain_overflow", "fallen_tree_water", "manhole_hazard", "road_submerged"]
SeverityName = Literal["low", "medium", "high", "critical"]

class LatLon(BaseModel):
    lat: float = Field(..., ge=12.0, le=14.0)
    lon: float = Field(..., ge=77.0, le=78.5)

class UserRole(str):
    CITIZEN = "citizen"
    ADMIN = "admin"
    RESPONDER = "responder"

class IncidentStatus(str):
    REPORTED = "reported"
    UNDER_REVIEW = "under_review"
    ASSIGNED = "assigned"
    FIELD_VERIFIED = "field_verified"
    BLOCKED = "blocked"
    CLEARANCE_PROPOSED = "clearance_proposed"
    CLEARED = "cleared"
    REJECTED = "rejected"

class IncidentType(str):
    WATERLOGGING = "waterlogging"
    DRAIN_OVERFLOW = "drain_overflow"
    FALLEN_TREE_WATER = "fallen_tree_water"
    MANHOLE_HAZARD = "manhole_hazard"
    ROAD_SUBMERGED = "road_submerged"

class IncidentSeverity(str):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Auth
class LoginRequest(BaseModel):
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=200)

class RegisterRequest(BaseModel):
    name: str = Field(..., max_length=100)
    email: str = Field(..., max_length=200)
    password: str = Field(..., max_length=200)
    role: str = "citizen"
    phone: Optional[str] = None
    team_id: Optional[str] = None
    department: Optional[str] = None
    admin_code: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    name: str
    role: str
    team_id: Optional[str] = None

class UserProfile(BaseModel):
    id: str
    name: str
    email: str
    role: str
    team_id: Optional[str] = None
    active: bool = True

# Response Teams
class ResponseTeam(BaseModel):
    id: str
    label: str
    status: str
    current_incident_id: Optional[str] = None
    demo_flag: bool = True
    assigned_count: int = 0

# Incidents
class EvidenceItem(BaseModel):
    id: str
    incident_id: str
    submitted_by: str
    submitter_name: str
    evidence_type: str  # "citizen_report", "responder_inspection", "admin_authorization", "clearance_evidence"
    text_notes: str
    water_depth_cm: Optional[float] = None
    is_impassable: Optional[bool] = None
    photo_url: Optional[str] = None
    created_at: str

class ReportCreateRequest(BaseModel):
    lat: float = Field(..., ge=12.0, le=14.0)
    lon: float = Field(..., ge=77.0, le=78.5)
    type: IncidentTypeName = "waterlogging"
    severity: SeverityName = "medium"
    description: str = Field(..., min_length=3, max_length=2000)
    evidence_note: Optional[str] = Field(None, max_length=2000)
    # Id returned by POST /uploads (a stored, validated, metadata-stripped photo). Preferred.
    photo_id: Optional[str] = Field(None, pattern=r"^[0-9a-f]{32}$")
    # External link kept for API/agent callers; it is only a reference and counts for nothing in credibility.
    photo_url: Optional[str] = Field(None, max_length=500, pattern=r"^https?://")

    @field_validator("lat")
    @classmethod
    def _lat_in_service_area(cls, v: float) -> float:
        if not (settings.MIN_LAT - _MARGIN_DEG <= v <= settings.MAX_LAT + _MARGIN_DEG):
            raise ValueError("Location is outside the MaleMitra service area (Koramangala, Indiranagar, HSR, Domlur, Ejipura, Silk Board).")
        return v

    @field_validator("lon")
    @classmethod
    def _lon_in_service_area(cls, v: float) -> float:
        if not (settings.MIN_LON - _MARGIN_DEG <= v <= settings.MAX_LON + _MARGIN_DEG):
            raise ValueError("Location is outside the MaleMitra service area (Koramangala, Indiranagar, HSR, Domlur, Ejipura, Silk Board).")
        return v

class IncidentDetail(BaseModel):
    id: str
    road_edge_id: Optional[str] = None
    road_name: Optional[str] = None
    lat: float
    lon: float
    type: str
    severity: str
    status: str
    confidence: float = 0.85
    reported_by_id: str
    reported_by_name: str
    reports_count: int = 1
    assigned_team_id: Optional[str] = None
    assigned_team_label: Optional[str] = None
    assigned_responder_id: Optional[str] = None
    assigned_responder_name: Optional[str] = None
    verification_notes: Optional[str] = None
    water_depth_cm: Optional[float] = None
    restriction_notes: Optional[str] = None
    is_blocked: bool = False
    created_at: str
    updated_at: str
    evidence_list: List[EvidenceItem] = []
    agent_summary: Optional[Dict[str, Any]] = None

class ReviewRequest(BaseModel):
    notes: Optional[str] = Field("Review completed by Control Room Admin.", max_length=1000)
    initial_severity: Optional[SeverityName] = None

class AssignRequest(BaseModel):
    team_id: str = Field(..., max_length=64)
    responder_id: Optional[str] = Field(None, max_length=64)  # omit to leave the incident in the team queue
    priority: Optional[str] = Field("high", max_length=20)
    notes: Optional[str] = Field("Dispatched field verification unit.", max_length=1000)

class VerifyRequest(BaseModel):
    findings: str = Field(..., min_length=3, max_length=2000)
    water_depth_cm: float = Field(45.0, ge=0, le=500)
    is_impassable: bool = True
    recommended_action: Literal["authorize_closure", "monitor", "clear"] = "authorize_closure"
    evidence_note: Optional[str] = Field(None, max_length=2000)
    photo_id: Optional[str] = Field(None, pattern=r"^[0-9a-f]{32}$")
    photo_url: Optional[str] = Field(None, max_length=500, pattern=r"^https?://")

class ProposeClearanceRequest(BaseModel):
    clearance_findings: str = Field(
        "Drain cleared and water receded below 10cm. Road safe for standard vehicular traffic.", max_length=2000)
    evidence_note: Optional[str] = Field(None, max_length=2000)

class RestrictionRequest(BaseModel):
    action: Literal["authorize_block", "authorize_reopen", "reject"]
    restriction_type: Optional[str] = Field("total_closure", max_length=40)
    notes: Optional[str] = Field(None, max_length=1000)

# Routing
class RouteCompareRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    scenario_id: Optional[str] = None

class OsrmStep(BaseModel):
    icon: str = "→"
    instruction: str
    road: str = ""
    distance_m: int = 0
    duration_s: int = 0
    dist: str = ""

class RoutePathItem(BaseModel):
    type: str  # "fastest", "risk_aware", "alternative"
    label: str
    edge_ids: List[str] = []
    path_nodes: List[str] = []
    node_names: List[str] = []
    coordinates: List[List[float]]  # [[lat, lon], ...]
    osrm_steps: List[OsrmStep] = []
    estimated_duration_s: float
    base_duration_s: float
    traffic_delay_s: float = 0.0
    traffic_factor: float = 1.0
    traffic_source: str = "time_of_day_model"  # tomtom_live | tomtom_corridor | time_of_day_model
    hazard_penalty_s: float
    congestion_delay_s: float
    distance_m: float
    blocked_edges_crossed: int
    risk_score: float
    uncertainty: str = "Modeled using graph topology & synthetic monsoon conditions. Not a guaranteed safe route."
    geometry_source: str = "graph"

class RouteCompareResponse(BaseModel):
    graph_version: int
    data_mode: str = "simulated_incidents"
    routes: List[RoutePathItem]
    active_restrictions_count: int
    reported_hazards_count: int
    traffic_factor: float = 1.0
    traffic_label: str = ""
    traffic_source: str = "time_of_day_model"
    message: Optional[str] = None

# Ripple Simulation
class SimulationRunCreate(BaseModel):
    seed: int = 42
    iterations: int = Field(2, ge=1, le=5)
    custom_blocked_edge_ids: Optional[List[str]] = Field(None, max_length=20)
    trip_count: Optional[int] = Field(None, ge=10, le=500)  # None uses the default 150 stored trips
    scenario_label: Optional[str] = Field("Live Disruption Ripple Test", max_length=100)

class EdgeMetric(BaseModel):
    edge_id: str
    road_name: str
    source_node: str
    target_node: str
    baseline_load: int
    disrupted_load: int
    delta_load: int
    capacity_proxy: int
    base_travel_time_s: float
    disrupted_travel_time_s: float
    congestion_ratio: float
    status: str  # "normal", "congested", "severely_congested", "blocked"

class RippleImpactResponse(BaseModel):
    run_id: str
    graph_version: int
    seed: int
    total_trips: int
    affected_trips: int
    mean_baseline_duration_s: float
    mean_disrupted_duration_s: float
    mean_detour_s: float
    pct_travel_time_increase: float
    top_affected_edges: List[EdgeMetric]
    blocked_edges: List[str]
    edge_metrics: List[EdgeMetric]
    timestamp: str

# Agent Events
class AgentEventItem(BaseModel):
    event_id: str
    incident_id: Optional[str] = None
    agent: str  # "incident_intelligence", "mobility", "ripple_impact", "response_coordinator"
    action: str
    input_refs: List[str]
    result: Dict[str, Any]
    data_mode: str = "simulated"
    requires_approval: bool = False
    timestamp: str

# Evaluation Benchmark
class BenchmarkResult(BaseModel):
    scenario_name: str
    total_trips: int
    baseline_trips_crossing_blocked: int
    baseline_pct_blocked: float
    malemitra_trips_crossing_blocked: int
    malemitra_pct_blocked: float
    blocked_traversal_reduction_pct: float
    baseline_mean_trip_time_s: float
    malemitra_mean_trip_time_s: float
    mean_detour_s: float
    detour_tradeoff_pct: float
    network_total_travel_time_increase_pct: float
    no_route_trips_count: int
    evaluation_runtime_ms: float
    timestamp: str
