from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

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
    email: str
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str
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
    lat: float
    lon: float
    type: str = "waterlogging"
    severity: str = "medium"
    description: str
    evidence_note: Optional[str] = None
    photo_url: Optional[str] = None

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
    verification_notes: Optional[str] = None
    water_depth_cm: Optional[float] = None
    restriction_notes: Optional[str] = None
    is_blocked: bool = False
    created_at: str
    updated_at: str
    evidence_list: List[EvidenceItem] = []
    agent_summary: Optional[Dict[str, Any]] = None

class ReviewRequest(BaseModel):
    notes: Optional[str] = "Review completed by Control Room Admin."
    initial_severity: Optional[str] = None

class AssignRequest(BaseModel):
    team_id: str
    priority: Optional[str] = "high"
    notes: Optional[str] = "Dispatched field verification unit."

class VerifyRequest(BaseModel):
    findings: str
    water_depth_cm: float = 45.0
    is_impassable: bool = True
    recommended_action: str = "authorize_closure"  # or "monitor" or "clear"
    evidence_note: Optional[str] = None
    photo_url: Optional[str] = None

class ProposeClearanceRequest(BaseModel):
    clearance_findings: str = "Drain cleared and water receded below 10cm. Road safe for standard vehicular traffic."
    evidence_note: Optional[str] = None

class RestrictionRequest(BaseModel):
    action: str  # "authorize_block" or "authorize_reopen" or "reject"
    restriction_type: Optional[str] = "total_closure"
    notes: Optional[str] = None

# Routing
class RouteCompareRequest(BaseModel):
    origin: LatLon
    destination: LatLon
    scenario_id: Optional[str] = None

class RoutePathItem(BaseModel):
    type: str  # "fastest", "risk_aware", "alternative"
    label: str
    edge_ids: List[str]
    path_nodes: List[str]
    coordinates: List[List[float]]  # [[lat, lon], ...]
    estimated_duration_s: float
    base_duration_s: float
    hazard_penalty_s: float
    congestion_delay_s: float
    distance_m: float
    blocked_edges_crossed: int
    risk_score: float
    uncertainty: str = "Modeled using graph topology & synthetic monsoon conditions. Not a guaranteed safe route."

class RouteCompareResponse(BaseModel):
    graph_version: int
    data_mode: str = "simulated_incidents"
    routes: List[RoutePathItem]
    active_restrictions_count: int
    reported_hazards_count: int
    message: Optional[str] = None

# Ripple Simulation
class SimulationRunCreate(BaseModel):
    seed: int = 42
    iterations: int = 2
    custom_blocked_edge_ids: Optional[List[str]] = None
    scenario_label: Optional[str] = "Live Disruption Ripple Test"

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
