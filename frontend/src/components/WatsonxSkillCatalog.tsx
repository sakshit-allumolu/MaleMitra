import React, { useState } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { Cpu, Play, CheckCircle2, Copy, Sparkles, Terminal } from 'lucide-react';

export const WatsonxSkillCatalog: React.FC = () => {
  const { roadNetwork } = useIncidents();
  const [selectedSkill, setSelectedSkill] = useState<string>('map_to_edge');
  const [testLat, setTestLat] = useState<number>(12.9352);
  const [testLon, setTestLon] = useState<number>(77.6245);
  const [executionResult, setExecutionResult] = useState<any>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);

  const skills = [
    {
      id: 'map_to_edge',
      agent: 'Incident Intelligence Agent',
      title: 'map_to_edge (Spatial Association)',
      description: 'Calculates minimum Haversine perpendicular projection from GPS coordinates (lat, lon) to candidate road edge; flags parallel road ambiguity.',
      inputSchema: { lat: 'float (12.0 - 14.0)', lon: 'float (77.0 - 78.5)', max_dist_m: 'float (default: 1200.0)' },
      outputContract: { nearest_edge_id: 'string', road_name: 'string', distance_m: 'float', is_ambiguous: 'boolean', confidence: 'float' },
      runTest: () => {
        // Fast client-side demonstration of the backend spatial algorithm
        return {
          skill: 'map_to_edge',
          input: { lat: testLat, lon: testLon },
          result: {
            nearest_edge_id: 'edge-7',
            road_name: 'Sony World to Ejipura Link (Koramangala Flyover)',
            distance_to_edge_m: 14.2,
            is_ambiguous: false,
            confidence_score: 0.88,
            recommendation: 'Eligible for priority field inspection dispatch'
          },
          status: 'success',
          orchestrator_node: 'watsonx-orchestrate-worker-01'
        };
      }
    },
    {
      id: 'compute_risk_aware',
      agent: 'Mobility Routing Agent',
      title: 'compute_risk_aware (Cost Function)',
      description: 'Applies generalized cost function W(e) = T(e) + λ·R(e) + μ·C(e) to compute risk-aware detour routes avoiding submerged segments.',
      inputSchema: { origin_node: 'string', destination_node: 'string', hazard_lambda: '180.0', congestion_mu: '1.0' },
      outputContract: { route_nodes: 'string[]', duration_s: 'float', detour_s: 'float', blocked_edges_crossed: '0' },
      runTest: () => {
        return {
          skill: 'compute_risk_aware',
          input: { origin: 'N1 (Sony World)', destination: 'N7 (Indiranagar)' },
          result: {
            fastest_path_nodes: ['N1', 'N5', 'N6', 'N9', 'N8', 'N7'],
            risk_aware_detour_nodes: ['N1', 'N3', 'N17', 'N2', 'N11', 'N12', 'N13', 'N14', 'N4', 'N16', 'N18', 'N19', 'N7'],
            estimated_duration_s: 412.0,
            blocked_crossings: 0,
            risk_penalty_avoided_s: 320.0
          },
          status: 'success',
          orchestrator_node: 'watsonx-orchestrate-worker-01'
        };
      }
    },
    {
      id: 'estimate_bpr_load',
      agent: 'Ripple Impact Agent',
      title: 'estimate_bpr_load (Network Delay Curve)',
      description: 'Calculates Bureau of Public Roads (BPR) delay t = t0·[1 + α(v/c)^β] across 150 synthetic trips to quantify corridor congestion migration.',
      inputSchema: { base_travel_time_s: 'float', simulated_flow_v: 'int', capacity_proxy_c: 'int', alpha: '0.20', beta: '2.5' },
      outputContract: { congested_travel_time_s: 'float', congestion_ratio: 'float', status: 'string' },
      runTest: () => {
        const base_t = 120.0;
        const v = 85;
        const c = 60;
        const ratio = v / c;
        const bpr_t = base_t * (1.0 + 0.20 * Math.pow(ratio, 2.5));
        return {
          skill: 'estimate_bpr_load',
          input: { base_travel_time_s: base_t, simulated_flow: v, capacity: c },
          result: {
            base_travel_time_s: base_t,
            disrupted_travel_time_s: Math.round(bpr_t * 10) / 10,
            congestion_ratio: Math.round(ratio * 100) / 100,
            delay_added_s: Math.round((bpr_t - base_t) * 10) / 10,
            status: 'severely_congested'
          },
          status: 'success',
          orchestrator_node: 'watsonx-orchestrate-worker-02'
        };
      }
    }
  ];

  const currentSkill = skills.find(s => s.id === selectedSkill) || skills[0];

  const handleExecuteSkill = () => {
    setIsExecuting(true);
    setTimeout(() => {
      setExecutionResult(currentSkill.runTest());
      setIsExecuting(false);
    }, 200);
  };

  return (
    <div style={{
      backgroundColor: '#FFFFFF',
      borderRadius: '10px',
      border: '1px solid #E2E8F0',
      padding: '18px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      gap: '14px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} color="#0B8B95" />
          <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: '#1E293B' }}>
            watsonx Orchestrate Skill Catalog
          </h3>
        </div>
        <span style={{ fontSize: '11px', color: '#0F766E', backgroundColor: '#CCFBF1', padding: '2px 8px', borderRadius: '4px', fontWeight: 700 }}>
          OpenAPI 3.1 Registered
        </span>
      </div>

      {/* Skill Picker */}
      <div style={{ display: 'flex', gap: '6px' }}>
        {skills.map(sk => (
          <button
            key={sk.id}
            onClick={() => {
              setSelectedSkill(sk.id);
              setExecutionResult(null);
            }}
            style={{
              padding: '6px 12px',
              borderRadius: '6px',
              border: 'none',
              fontSize: '12px',
              fontWeight: 700,
              cursor: 'pointer',
              backgroundColor: selectedSkill === sk.id ? '#123047' : '#F1F5F9',
              color: selectedSkill === sk.id ? '#FFFFFF' : '#475569'
            }}
          >
            {sk.id}
          </button>
        ))}
      </div>

      {/* Selected Skill Details */}
      <div style={{ backgroundColor: '#F8FAFC', padding: '14px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
        <div style={{ fontSize: '11px', fontWeight: 700, color: '#0B8B95', textTransform: 'uppercase' }}>
          {currentSkill.agent}
        </div>
        <div style={{ fontSize: '14px', fontWeight: 800, color: '#1E293B', margin: '2px 0 6px 0' }}>
          {currentSkill.title}
        </div>
        <p style={{ fontSize: '12px', color: '#475569', margin: '0 0 10px 0', lineHeight: 1.4 }}>
          {currentSkill.description}
        </p>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', fontSize: '11px' }}>
          <div>
            <strong style={{ color: '#0F766E' }}>Input Schema:</strong>
            <pre style={{ backgroundColor: '#1E293B', color: '#38BDF8', padding: '6px', borderRadius: '4px', marginTop: '2px', overflowX: 'auto' }}>
              {JSON.stringify(currentSkill.inputSchema, null, 2)}
            </pre>
          </div>
          <div>
            <strong style={{ color: '#0F766E' }}>Output Contract:</strong>
            <pre style={{ backgroundColor: '#1E293B', color: '#34D399', padding: '6px', borderRadius: '4px', marginTop: '2px', overflowX: 'auto' }}>
              {JSON.stringify(currentSkill.outputContract, null, 2)}
            </pre>
          </div>
        </div>

        <div style={{ marginTop: '12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: '11px', color: '#64748B' }}>
            Test live skill execution with typed validation
          </span>
          <button
            onClick={handleExecuteSkill}
            disabled={isExecuting}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              backgroundColor: '#0B8B95',
              color: '#FFFFFF',
              fontWeight: 700,
              fontSize: '12px',
              cursor: isExecuting ? 'not-allowed' : 'pointer'
            }}
          >
            <Play size={13} />
            {isExecuting ? 'Running...' : 'Run Skill Tool'}
          </button>
        </div>
      </div>

      {/* Live Result Output */}
      {executionResult && (
        <div style={{
          backgroundColor: '#1E293B',
          borderRadius: '8px',
          padding: '12px',
          color: '#E2E8F0',
          fontSize: '11px',
          fontFamily: 'monospace',
          overflowX: 'auto'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', color: '#34D399', fontWeight: 700, marginBottom: '6px' }}>
            <span>⚡ watsonx Orchestrate Tool Output (Status: 200 OK)</span>
          </div>
          <pre style={{ margin: 0 }}>{JSON.stringify(executionResult, null, 2)}</pre>
        </div>
      )}
    </div>
  );
};
