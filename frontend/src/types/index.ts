export type UserRole = 'citizen' | 'admin' | 'responder';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: UserRole;
  team_id?: string | null;
  active?: boolean;
}

export interface RegisterFormData {
  name: string;
  email: string;
  password: string;
  role: UserRole;
  phone?: string;
  team_id?: string;
  department?: string;
  admin_code?: string;
}

export interface LocationPoint {
  name: string;
  lat: number;
  lon: number;
}

export type IncidentStatus = 
  | 'reported' 
  | 'under_review' 
  | 'assigned' 
  | 'field_verified' 
  | 'blocked' 
  | 'clearance_proposed' 
  | 'cleared' 
  | 'rejected';

export interface EvidenceItem {
  id: string;
  incident_id: string;
  submitted_by: string;
  submitter_name: string;
  evidence_type: string;
  text_notes: string;
  water_depth_cm?: number | null;
  is_impassable?: boolean | null;
  photo_url?: string | null;
  created_at: string;
}

export interface Incident {
  id: string;
  road_edge_id?: string | null;
  road_name?: string | null;
  lat: number;
  lon: number;
  type: string;
  severity: 'low' | 'medium' | 'high' | 'critical';
  status: IncidentStatus;
  confidence: number;
  reported_by_id: string;
  reported_by_name: string;
  reports_count: number;
  merged?: boolean;            // set on the response to a report that was counted on an existing incident
  already_reported?: boolean;  // ...because this same user had already reported that spot
  assigned_team_id?: string | null;
  assigned_team_label?: string | null;
  assigned_responder_id?: string | null;
  assigned_responder_name?: string | null;
  verification_notes?: string | null;
  water_depth_cm?: number | null;
  restriction_notes?: string | null;
  is_blocked: boolean;
  is_mine?: boolean;
  created_at: string;
  updated_at: string;
  evidence_list: EvidenceItem[];
  agent_summary?: {
    edge_mapped?: string;
    distance_to_edge_m?: number;
    is_ambiguous?: boolean;
    confidence?: number;
    recommendation?: string;
    duplicate_cluster?: boolean;
    duplicate_of?: string | null;
  } | null;
}

export interface OsrmStep {
  icon: string;
  instruction: string;
  road: string;
  distance_m: number;
  duration_s: number;
  dist: string;
}

export interface RoutePathItem {
  type: 'fastest' | 'risk_aware' | 'alternative';
  label: string;
  edge_ids?: string[];
  path_nodes?: string[];
  node_names?: string[];
  coordinates: [number, number][];
  osrm_steps?: OsrmStep[];
  estimated_duration_s: number;
  base_duration_s: number;
  traffic_delay_s?: number;
  traffic_factor?: number;
  traffic_source?: TrafficSource;
  hazard_penalty_s: number;
  congestion_delay_s: number;
  distance_m: number;
  blocked_edges_crossed: number;
  risk_score: number;
  uncertainty: string;
  geometry_source?: string;
  /** Roads already closed within ~60 m of this route. */
  closed_incidents_passed?: number;
  /** Citizen reports still awaiting review or closure within ~60 m of this route. */
  reported_incidents_passed?: number;
}

/** tomtom_live: matched a TomTom route; tomtom_corridor: TomTom's best route used as an estimate; time_of_day_model: typical-hours fallback. */
export type TrafficSource = 'tomtom_live' | 'tomtom_corridor' | 'time_of_day_model';

export interface RouteCompareResponse {
  graph_version: number;
  data_mode: string;
  routes: RoutePathItem[];
  active_restrictions_count: number;
  reported_hazards_count: number;
  traffic_factor?: number;
  traffic_label?: string;
  traffic_source?: TrafficSource;
  message?: string;
}

export interface EdgeMetric {
  edge_id: string;
  road_name: string;
  source_node: string;
  target_node: string;
  baseline_load: number;
  disrupted_load: number;
  delta_load: number;
  capacity_proxy: number;
  base_travel_time_s: number;
  disrupted_travel_time_s: number;
  congestion_ratio: number;
  status: 'normal' | 'congested' | 'severely_congested' | 'blocked';
}

export interface RippleImpactResponse {
  run_id: string;
  graph_version: number;
  seed: number;
  total_trips: number;
  affected_trips: number;
  mean_baseline_duration_s: number;
  mean_disrupted_duration_s: number;
  mean_detour_s: number;
  pct_travel_time_increase: number;
  top_affected_edges: EdgeMetric[];
  blocked_edges: string[];
  edge_metrics: EdgeMetric[];
  timestamp: string;
}

export interface AgentEventItem {
  event_id: string;
  incident_id?: string | null;
  agent: string;
  action: string;
  input_refs: string[];
  result: Record<string, any>;
  data_mode: string;
  requires_approval: boolean;
  decision?: 'approved' | 'dismissed' | null;
  decided_at?: string | null;
  timestamp: string;
}

export interface AgentStatus {
  configured: boolean;
  missing_settings: string[];
  tools_enabled: boolean;
  agent_id: string | null;
  instance_url: string | null;
  tools_public_url: string;
  last_error: string | null;
  last_ok_at: number | null;
  tools: string[];
}

export interface AgentRecommendation {
  event_id: string;
  decision: 'approved' | 'dismissed' | null;
  decided_by?: string | null;
  decided_at?: string | null;
  incident_id: string;
  action: string;
  rationale: string;
  confidence: number;
  status_at_recommendation: string;
  team_id?: string | null;       // assign_team only
  responder_id?: string | null;  // assign_team only; null = team queue
  requires_human_approval: boolean;
  created_at: string;
}

export interface AuditEventItem {
  id: string;
  actor_id: string;
  actor_name: string;
  action: string;
  entity_type: string;
  entity_id: string;
  before_state?: Record<string, any> | null;
  after_state?: Record<string, any> | null;
  timestamp: string;
}

export interface BenchmarkResult {
  scenario_name: string;
  total_trips: number;
  blocked_corridor: string[];
  baseline_trips_crossing_blocked: number;
  baseline_pct_blocked: number;
  malemitra_trips_crossing_blocked: number;
  malemitra_pct_blocked: number;
  blocked_traversal_reduction_pct: number;
  baseline_mean_trip_time_s: number;
  malemitra_mean_trip_time_s: number;
  mean_detour_s: number;
  detour_tradeoff_pct: number;
  network_total_travel_time_increase_pct: number;
  no_route_trips_count: number;
  evaluation_runtime_ms: number;
  timestamp: string;
}

export interface ResponderAvailability {
  id: string;
  name: string;
  team_id: string | null;
  team_label: string | null;
  is_free: boolean;
  active_incident_ids: string[];
}

export interface ResponseTeam {
  id: string;
  label: string;
  status: string;
  current_incident_id?: string | null;
  demo_flag: boolean;
}

export interface RoadNetworkData {
  graph_version: number;
  nodes: { id: string; name: string; lat: number; lon: number }[];
  edges: {
    edge_id: string;
    source: string;
    target: string;
    road_name: string;
    length_m: number;
    travel_time_s: number;
    capacity_proxy: number;
    geometry: [number, number][];
    is_blocked: boolean;
    hazard_severity: string;
    water_depth_cm: number;
    simulated_flow: number;
  }[];
}
