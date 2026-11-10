import { 
  Incident, RouteCompareResponse, RippleImpactResponse, 
  AgentEventItem, AuditEventItem, BenchmarkResult, ResponseTeam, RoadNetworkData 
} from '../types';

const API_BASE = '/api/v1';

export class ApiClient {
  private static token: string = 'usr-citizen-1';

  static setAuthToken(token: string) {
    this.token = token;
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

  // Location Geosearch (Bengaluru places / OpenStreetMap Nominatim / Google Maps API style search)
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
  }): Promise<Incident> {
    const res = await fetch(`${API_BASE}/reports`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error('Failed to submit report');
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

  static async assignTeam(id: string, team_id: string, notes?: string): Promise<Incident> {
    const res = await fetch(`${API_BASE}/incidents/${id}/assign`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: JSON.stringify({ team_id, notes: notes || 'Dispatched team.' })
    });
    if (!res.ok) throw new Error('Failed to assign team');
    return res.json();
  }

  static async verifyIncident(id: string, data: {
    findings: string;
    water_depth_cm: number;
    is_impassable: boolean;
    recommended_action: string;
    evidence_note?: string;
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
    if (!res.ok) throw new Error('Failed to compare routes');
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
    const res = await fetch(`${API_BASE}/simulations/benchmark/run`);
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

  static async getMyTasks(): Promise<Incident[]> {
    const res = await fetch(`${API_BASE}/teams/me/tasks`, { headers: this.getHeaders() });
    if (!res.ok) throw new Error('Failed to fetch responder tasks');
    const data = await res.json();
    return data.tasks || [];
  }

  // Events
  static async getAgentEvents(): Promise<AgentEventItem[]> {
    const res = await fetch(`${API_BASE}/events/agent`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.events || [];
  }

  static async getAuditEvents(): Promise<AuditEventItem[]> {
    const res = await fetch(`${API_BASE}/events/audit`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.audits || [];
  }
}
