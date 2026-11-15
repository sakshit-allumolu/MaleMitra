import {
  Incident, RouteCompareResponse, RippleImpactResponse,
  AgentEventItem, AuditEventItem, BenchmarkResult, ResponseTeam, RoadNetworkData,
  AgentStatus, AgentRecommendation, ResponderAvailability
} from '../types';

const API_BASE = '/api/v1';

// A 401 on a request that carried a session token means the session expired or was revoked
// (logout elsewhere, password change): send the user back to the sign-in page.
const _nativeFetch = window.fetch.bind(window);
window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
  const res = await _nativeFetch(input, init);
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
  const auth = new Headers(init?.headers).get('Authorization');
  if (res.status === 401 && auth && auth !== 'Bearer ' && url.includes(API_BASE)
      && !url.includes('/auth/login') && !url.includes('/auth/register')) {
    ApiClient.handleUnauthorized();
  }
  return res;
};

// FastAPI sends `detail` as a string for our own errors and as a list for request-validation errors.
// Show the first readable message instead of a generic fallback.
function detailText(err: any, fallback: string): string {
  const d = err?.detail;
  if (typeof d === 'string') return d;
  if (Array.isArray(d) && d.length > 0) {
    const first = d[0];
    const msg = String(first?.msg ?? first?.message ?? '').replace(/^Value error,\s*/, '');
    if (msg) {
      const field = Array.isArray(first?.loc) ? String(first.loc[first.loc.length - 1]) : '';
      return field && !msg.toLowerCase().includes(field.toLowerCase()) && !/outside/i.test(msg) ? `${field}: ${msg}` : msg;
    }
  }
  return fallback;
}

export class ApiClient {
  // Start from the saved session so a hot reload or first render still has the user's token.
  private static token: string = localStorage.getItem('malemitra_token') || '';
  private static onUnauthorized: (() => void) | null = null;

  static setAuthToken(token: string) {
    this.token = token;
  }

  /** Called once when an authenticated request is rejected (expired or revoked session). */
  static setUnauthorizedHandler(handler: (() => void) | null) {
    this.onUnauthorized = handler;
  }

  static handleUnauthorized() {
    if (this.token && this.onUnauthorized) this.onUnauthorized();
  }

  static async logoutRemote() {
    if (!this.token) return;
    try {
      await fetch(`${API_BASE}/auth/logout`, { method: 'POST', headers: this.getHeaders() });
    } catch {
      /* best effort: the local session is cleared regardless */
    }
  }

  static getHeaders() {
    return {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.token}`
    };
  }

  // Auth
  static async loginUser(email: string, password: string) {
    const res = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Login failed. Please check your credentials.');
    }
    return res.json();
  }

  static async registerUser(data: {
    name: string;
    email: string;
    password: string;
    role: string;
    phone?: string;
    team_id?: string;
    department?: string;
    admin_code?: string;
  }) {
    const res = await fetch(`${API_BASE}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Registration failed.');
    }
    return res.json();
  }

  static async forgotPassword(email: string): Promise<{ message: string; debug_token: string | null }> {
    const res = await fetch(`${API_BASE}/auth/forgot-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Request failed.');
    }
    return res.json();
  }

  static async resetPassword(token: string, new_password: string): Promise<{ message: string }> {
    const res = await fetch(`${API_BASE}/auth/reset-password`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, new_password })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Password reset failed.');
    }
    return res.json();
  }

  // Location Geosearch (Bengaluru places / OpenStreetMap Nominatim)
  static async searchLocations(query: string): Promise<{ name: string; lat: number; lon: number }[]> {
    if (!query || query.trim().length < 2) return [];
    try {
      const encoded = encodeURIComponent(`${query.trim()}, Bengaluru, Karnataka, India`);
      const res = await fetch(`https://nominatim.openstreetmap.org/search?format=json&q=${encoded}&limit=5&bounded=1&viewbox=77.45,13.15,77.80,12.80`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.map((item: any) => ({
        name: item.display_name.split(',')[0] + ', ' + (item.display_name.split(',')[1] || '').trim(),
        lat: parseFloat(item.lat),
        lon: parseFloat(item.lon)
      }));
    } catch {
      return [];
    }
  }

  // Incidents
  static async withdrawReport(incidentId: string): Promise<{ message: string; incident_id: string }> {
    const res = await fetch(`${API_BASE}/incidents/${incidentId}/withdraw`, {
      method: 'POST',
      headers: this.getHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to withdraw report');
    }
    return res.json();
  }

  static async getIncidents(): Promise<Incident[]> {
    const res = await fetch(`${API_BASE}/incidents`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch incidents');
    return res.json();
  }

  static async getIncidentDetail(id: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch incident detail');
    return res.json();
  }

  static async createReport(data: {
    lat: number;
    lon: number;
    type: string;
    severity: string;
    description: string;
    evidence_note?: string;
    photo_id?: string;
  }): Promise<Incident> {
    const res = await fetch(`${API_BASE}/reports`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data)
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err, 'Failed to submit report'));
    }
    return res.json();
  }

  /** Upload a JPEG/PNG; the server validates it, strips location metadata and returns an id for `photo_id`. */
  static async uploadPhoto(file: File): Promise<{ id: string; url: string }> {
    const res = await fetch(`${API_BASE}/uploads`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.token}`, 'Content-Type': 'application/octet-stream' },
      body: file
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err, 'Photo upload failed'));
    }
    return res.json();
  }

  static async reviewIncident(id: string, notes: string, initial_severity?: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/review`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ notes, initial_severity })
    });
    if (!res.ok) throw new Error('Failed to review incident');
    return res.json();
  }

  static async assignTeam(id: string, team_id: string, notes?: string, responder_id?: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/assign`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ team_id, responder_id: responder_id || null, notes: notes || 'Dispatched team.' })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err, 'Failed to assign team'));
    }
    return res.json();
  }

  static async claimIncident(id: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/claim`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err, 'Could not take this task'));
    }
    return res.json();
  }

  static async getResponders(): Promise<ResponderAvailability[]> {
    const res = await fetch(`${API_BASE}/teams/responders`, { headers: this.getHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.responders || [];
  }

  static async verifyIncident(id: string, data: {
    findings: string;
    water_depth_cm: number;
    is_impassable: boolean;
    recommended_action: string;
    evidence_note?: string;
    photo_id?: string;
  }): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/verify`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to submit verification');
    return res.json();
  }

  static async proposeClearance(id: string, clearance_findings: string, evidence_note?: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/clearance`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ clearance_findings, evidence_note })
    });
    if (!res.ok) throw new Error('Failed to propose clearance');
    return res.json();
  }

  static async authorizeRestriction(id: string, action: 'authorize_block' | 'authorize_reopen' | 'reject', notes?: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/restriction`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ action, notes })
    });
    if (!res.ok) throw new Error('Failed to authorize restriction');
    return res.json();
  }

  // Routing
  static async compareRoutes(origin: { lat: number; lon: number }, destination: { lat: number; lon: number }): Promise<RouteCompareResponse> {
    const res = await fetch(`${API_BASE}/routes/compare`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ origin, destination })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const e: Error & { status?: number } = new Error(detailText(err, 'Failed to compare routes'));
      e.status = res.status;
      throw e;
    }
    return res.json();
  }

  static async getRoadNetwork(): Promise<RoadNetworkData> {
    const res = await fetch(`${API_BASE}/routes/network`);
    if (!res.ok) throw new Error('Failed to fetch road network');
    return res.json();
  }

  // Simulations
  static async runSimulation(
    custom_blocked_edge_ids?: string[],
    seed: number = 42,
    trip_count?: number
  ): Promise<RippleImpactResponse> {
    const res = await fetch(`${API_BASE}/simulations`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ seed, iterations: 2, custom_blocked_edge_ids, trip_count })
    });
    if (!res.ok) throw new Error('Failed to run simulation');
    return res.json();
  }

  static async runBenchmark(): Promise<BenchmarkResult> {
    const res = await fetch(`${API_BASE}/simulations/benchmark/run`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to execute benchmark');
    return res.json();
  }

  // Teams
  static async getTeams(): Promise<ResponseTeam[]> {
    const res = await fetch(`${API_BASE}/teams`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch teams');
    const data = await res.json();
    return data.teams || [];
  }

  static async getMyTasks(): Promise<{ tasks: Incident[]; queue: Incident[]; is_free: boolean }> {
    const res = await fetch(`${API_BASE}/teams/me/tasks`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch responder tasks');
    const data = await res.json();
    return { tasks: data.tasks || [], queue: data.queue || [], is_free: !!data.is_free };
  }

  // Events
  static async getAgentEvents(): Promise<AgentEventItem[]> {
    const res = await fetch(`${API_BASE}/events/agent`, { headers: this.getHeaders() });
    if (!res.ok) return []; // 403 for non-admin roles: the timeline is control-room only
    const data = await res.json();
    return data.events || [];
  }

  // watsonx Orchestrate agent
  static async getAgentStatus(): Promise<AgentStatus> {
    const res = await fetch(`${API_BASE}/agents/status`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch agent status');
    return res.json();
  }

  static async chatWithAgent(message: string): Promise<{ reply: string }> {
    const res = await fetch(`${API_BASE}/agents/chat`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ message })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Agent request failed');
    }
    return res.json();
  }

  static async analyzeIncident(id: string): Promise<{ reply: string; recommendation: AgentRecommendation | null }> {
    const res = await fetch(`${API_BASE}/agents/analyze/${id}`, {
      method: 'POST',
      headers: this.getHeaders()
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Agent analysis failed');
    }
    return res.json();
  }

  static async decideRecommendation(
    eventId: string, decision: 'approve' | 'dismiss',
    opts: { notes?: string; team_id?: string; responder_id?: string | null } = {}
  ): Promise<{ recommendation: AgentRecommendation | null; incident: Incident }> {
    const res = await fetch(`${API_BASE}/agents/recommendations/${eventId}/decision`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ decision, ...opts })
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(detailText(err, 'Could not record the decision'));
    }
    return res.json();
  }

  static async getRecommendation(id: string): Promise<AgentRecommendation | null> {
    const res = await fetch(`${API_BASE}/agents/recommendation/${id}`, { headers: this.getHeaders() });
    if (!res.ok) return null;
    const data = await res.json();
    return data.recommendation || null;
  }

  static async getAuditEvents(): Promise<AuditEventItem[]> {
    const res = await fetch(`${API_BASE}/events/audit`, { headers: this.getHeaders() });
    if (!res.ok) return [];
    const data = await res.json();
    return data.audits || [];
  }
}
