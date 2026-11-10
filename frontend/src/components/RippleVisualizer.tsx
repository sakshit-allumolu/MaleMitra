import React, { useState } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { Activity, Play, AlertTriangle, ArrowRight, ShieldCheck, TrendingUp, Info } from 'lucide-react';

export const RippleVisualizer: React.FC = () => {
  const { rippleResult, roadNetwork, triggerSimulation, isLoading } = useIncidents();
  const [selectedEdgeId, setSelectedEdgeId] = useState<string>('edge-7');

  const handleRunSim = () => {
    triggerSimulation(selectedEdgeId ? [selectedEdgeId] : undefined);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Top Header Card */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '10px',
        border: '1px solid #E2E8F0',
        padding: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                backgroundColor: '#FEF3C7',
                color: '#C78420',
                padding: '6px',
                borderRadius: '8px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center'
              }}>
                <Activity size={20} />
              </div>
              <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#1E293B' }}>
                Graph-Based Ripple Impact Engine
              </h2>
            </div>
            <p style={{ fontSize: '13px', color: '#64748B', marginTop: '4px', maxWidth: '700px', margin: '4px 0 0 0' }}>
              Models how one verified road obstruction redirects synthetic monsoon OD trips (150 trips) across Bengaluru's bounded network, calculating edge load deltas and Bureau of Public Roads (BPR) congestion delays.
            </p>
          </div>

          {/* Interactive Simulation Trigger */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#F8FAFC', padding: '10px 14px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', marginBottom: '2px' }}>
                Inject Test Blockage:
              </label>
              <select
                value={selectedEdgeId}
                onChange={(e) => setSelectedEdgeId(e.target.value)}
                style={{
                  backgroundColor: '#FFFFFF',
                  border: '1px solid #CBD5E1',
                  borderRadius: '6px',
                  padding: '6px 10px',
                  fontSize: '12px',
                  fontWeight: 600,
                  color: '#1E293B',
                  outline: 'none',
                  minWidth: '220px'
                }}
              >
                {roadNetwork?.edges.map((e) => (
                  <option key={e.edge_id} value={e.edge_id}>
                    {e.road_name} ({e.edge_id})
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleRunSim}
              disabled={isLoading}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                backgroundColor: '#0B8B95',
                color: '#FFFFFF',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 16px',
                fontWeight: 700,
                fontSize: '13px',
                cursor: isLoading ? 'not-allowed' : 'pointer',
                opacity: isLoading ? 0.7 : 1,
                alignSelf: 'flex-end',
                boxShadow: '0 2px 4px rgba(11, 139, 149, 0.3)'
              }}
            >
              <Play size={15} />
              {isLoading ? 'Simulating...' : 'Run Ripple'}
            </button>
          </div>
        </div>

        {/* Primary Metric Summary Cards */}
        {rippleResult && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px', marginTop: '20px' }}>
            <div style={{ backgroundColor: '#F0FDFA', border: '1px solid #CCFBF1', padding: '14px', borderRadius: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#0F766E' }}>Total Seeded Trips</span>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#134E4A', marginTop: '2px' }}>
                {rippleResult.total_trips} trips
              </div>
              <span style={{ fontSize: '11px', color: '#14B8A6' }}>Bounded Koramangala network</span>
            </div>

            <div style={{ backgroundColor: '#FEF2F2', border: '1px solid #FEE2E2', padding: '14px', borderRadius: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#B91C1C' }}>Rerouted Disrupted Trips</span>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#991B1B', marginTop: '2px' }}>
                {rippleResult.affected_trips} trips ({Math.round((rippleResult.affected_trips / rippleResult.total_trips) * 100)}%)
              </div>
              <span style={{ fontSize: '11px', color: '#EF4444' }}>Redirected away from hazard</span>
            </div>

            <div style={{ backgroundColor: '#FFFBEB', border: '1px solid #FEF3C7', padding: '14px', borderRadius: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#B45309' }}>Mean Detour Incurred</span>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#92400E', marginTop: '2px' }}>
                +{rippleResult.mean_detour_s}s
              </div>
              <span style={{ fontSize: '11px', color: '#F59E0B' }}>Average added journey duration</span>
            </div>

            <div style={{ backgroundColor: '#EFF6FF', border: '1px solid #DBEAFE', padding: '14px', borderRadius: '8px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600, color: '#1D4ED8' }}>Network Delay Delta</span>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#1E40AF', marginTop: '2px' }}>
                +{rippleResult.pct_travel_time_increase}%
              </div>
              <span style={{ fontSize: '11px', color: '#3B82F6' }}>BPR simulated corridor congestion</span>
            </div>
          </div>
        )}
      </div>

      {/* Top Affected Road Corridors Table */}
      {rippleResult && (
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '10px',
          border: '1px solid #E2E8F0',
          padding: '20px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} color="#C78420" />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#1E293B' }}>
                Cascading Impact: Top Congested Detour Corridors
              </h3>
            </div>
            <span style={{ fontSize: '12px', color: '#64748B' }}>
              Ranked by modeled traffic migration (Δ flow)
            </span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
                  <th style={{ padding: '10px 14px' }}>Road Segment</th>
                  <th style={{ padding: '10px 14px' }}>Baseline Flow</th>
                  <th style={{ padding: '10px 14px' }}>Disrupted Flow</th>
                  <th style={{ padding: '10px 14px' }}>Delta (Δ Trips)</th>
                  <th style={{ padding: '10px 14px' }}>Capacity Proxy</th>
                  <th style={{ padding: '10px 14px' }}>Congestion Ratio</th>
                  <th style={{ padding: '10px 14px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {rippleResult.top_affected_edges.map((metric) => (
                  <tr key={metric.edge_id} style={{ borderBottom: '1px solid #E2E8F0', transition: 'background-color 0.1s' }}>
                    <td style={{ padding: '12px 14px', fontWeight: 600, color: '#1E293B' }}>
                      {metric.road_name}
                      <div style={{ fontSize: '11px', color: '#64748B', fontFamily: 'monospace' }}>
                        {metric.edge_id} ({metric.source_node} → {metric.target_node})
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px', color: '#475569' }}>
                      {metric.baseline_load} trips
                    </td>
                    <td style={{ padding: '12px 14px', fontWeight: 700, color: metric.delta_load > 0 ? '#B91C1C' : '#475569' }}>
                      {metric.disrupted_load} trips
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      <span style={{
                        fontWeight: 700,
                        color: metric.delta_load > 0 ? '#B91C1C' : '#059669',
                        backgroundColor: metric.delta_load > 0 ? '#FEE2E2' : '#ECFDF5',
                        padding: '2px 8px',
                        borderRadius: '4px'
                      }}>
                        {metric.delta_load > 0 ? `+${metric.delta_load}` : metric.delta_load}
                      </span>
                    </td>
                    <td style={{ padding: '12px 14px', color: '#475569' }}>
                      {metric.capacity_proxy} v/slice
                    </td>
                    <td style={{ padding: '12px 14px', fontWeight: 600 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{
                          flex: 1,
                          height: '6px',
                          backgroundColor: '#E2E8F0',
                          borderRadius: '3px',
                          overflow: 'hidden',
                          maxWidth: '80px'
                        }}>
                          <div style={{
                            width: `${Math.min(100, metric.congestion_ratio * 100)}%`,
                            height: '100%',
                            backgroundColor: metric.congestion_ratio >= 1.25 ? '#B91C1C' : metric.congestion_ratio >= 0.85 ? '#C78420' : '#0B8B95'
                          }} />
                        </div>
                        <span>{metric.congestion_ratio}x</span>
                      </div>
                    </td>
                    <td style={{ padding: '12px 14px' }}>
                      {metric.status === 'severely_congested' ? (
                        <span style={{ fontSize: '11px', fontWeight: 700, color: '#B91C1C', backgroundColor: '#FEE2E2', padding: '3px 8px', borderRadius: '4px' }}>
                          ⚡ Severe Congestion
                        </span>
                      ) : metric.status === 'congested' ? (
                        <span style={{ fontSize: '11px', fontWeight: 700, color: '#C78420', backgroundColor: '#FEF3C7', padding: '3px 8px', borderRadius: '4px' }}>
                          ⚠️ Congested Detour
                        </span>
                      ) : (
                        <span style={{ fontSize: '11px', fontWeight: 600, color: '#059669', backgroundColor: '#ECFDF5', padding: '3px 8px', borderRadius: '4px' }}>
                          Normal Flow
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: '14px', padding: '10px 14px', backgroundColor: '#F8FAFC', borderRadius: '6px', fontSize: '12px', color: '#64748B', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={15} color="#0B8B95" />
            <span>
              <strong>Simulation Guardrail:</strong> Capacity is a synthetic proxy. Travel delays are computed via BPR function $t = t_0 [1 + 0.2(v/c)^{2.5}]$. Not a certified real-time traffic guarantee.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
