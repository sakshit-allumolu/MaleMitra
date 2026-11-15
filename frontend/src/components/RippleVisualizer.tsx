import React, { useState, useMemo } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { Activity, Play, TrendingUp, Info, X, ChevronDown, ChevronUp } from 'lucide-react';

export const RippleVisualizer: React.FC = () => {
  const { rippleResult, roadNetwork, triggerSimulation, isLoading } = useIncidents();

  // ── Controls ─────────────────────────────────────────────────────────────
  const [tripCount, setTripCount] = useState<number>(150);
  const [selectedEdgeIds, setSelectedEdgeIds] = useState<string[]>([]);
  const [edgeDropdownOpen, setEdgeDropdownOpen] = useState(false);
  const [useRealBlockages, setUseRealBlockages] = useState(true);

  // Currently live-blocked edges from the graph
  const liveBlockedEdges = useMemo(() => {
    if (!roadNetwork?.edges) return [];
    return roadNetwork.edges.filter(e => e.is_blocked);
  }, [roadNetwork]);

  // Hypothetical edge options (all edges, for what-if analysis)
  const edgeOptions = useMemo(() => {
    if (!roadNetwork?.edges) return [];
    return roadNetwork.edges.map(e => ({
      id: e.edge_id,
      label: `${e.road_name.replace(/ \((North|South|East|West)bound\)/g, '')} (${e.edge_id})`,
      isLive: e.is_blocked,
    }));
  }, [roadNetwork]);

  const toggleEdge = (id: string) => {
    setSelectedEdgeIds(prev =>
      prev.includes(id) ? prev.filter(e => e !== id) : [...prev, id]
    );
  };

  const handleRunSim = () => {
    // Combine: live real blockages (if toggled on) + user-selected hypothetical ones
    const liveIds = useRealBlockages ? liveBlockedEdges.map(e => e.edge_id) : [];
    const allIds = Array.from(new Set([...liveIds, ...selectedEdgeIds]));
    triggerSimulation(allIds.length > 0 ? allIds : undefined, tripCount);
  };

  const tripCountLabel = `${tripCount} trips`;

  const sliderBackground = () => {
    const pct = ((tripCount - 50) / (500 - 50)) * 100;
    return `linear-gradient(to right, #0B8B95 ${pct}%, #E2E8F0 ${pct}%)`;
  };

  const selectedEdgeLabels = selectedEdgeIds.map(id => {
    const e = edgeOptions.find(o => o.id === id);
    return e ? e.label.split('(')[0].trim() : id;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>

      {/* ── Header & Controls Card ─────────────────────────────────────────── */}
      <div style={{
        backgroundColor: '#FFFFFF', borderRadius: '10px',
        border: '1px solid #E2E8F0', padding: '20px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
      }}>
        {/* Title */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
          <div style={{ backgroundColor: '#FEF3C7', color: '#C78420', padding: '6px', borderRadius: '8px', display: 'flex' }}>
            <Activity size={20} />
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0, color: '#1E293B' }}>
            Ripple Impact Simulator
          </h2>
        </div>

        {/* How it works explanation */}
        <div style={{ backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', borderRadius: '8px', padding: '14px 16px', marginBottom: '20px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#1E293B', marginBottom: '8px' }}>How this works</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', fontSize: '12px', color: '#475569', lineHeight: 1.5 }}>
            <div>
              <span style={{ fontWeight: 700, color: '#DC2626' }}>🛑 Live blockages</span> are real road closures authorized by the Control Room from verified field reports. These affect actual routing right now.
            </div>
            <div>
              <span style={{ fontWeight: 700, color: '#C78420' }}>🧪 What-if scenarios</span> let you hypothetically block any road to see how traffic would cascade — without affecting real routing. Think of it as a planning tool.
            </div>
            <div>
              <span style={{ fontWeight: 700, color: '#0B8B95' }}>📊 BPR model</span> assigns {tripCount} synthetic trips across the network and measures how flow shifts and congestion builds up using the Bureau of Public Roads formula.
            </div>
          </div>
        </div>

        {/* Live blockages status */}
        <div style={{ marginBottom: '16px' }}>
          <div style={{ fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '8px' }}>
            🛑 Current Live Blockages
            <span style={{ fontSize: '11px', fontWeight: 400, color: '#94A3B8', marginLeft: '6px' }}>
              (authorized by Control Room — affect real routing)
            </span>
          </div>
          {liveBlockedEdges.length === 0 ? (
            <div style={{ padding: '10px 12px', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', borderRadius: '6px', fontSize: '12px', color: '#065F46', display: 'flex', alignItems: 'center', gap: '6px' }}>
              ✅ No roads currently blocked. All corridors are open.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {liveBlockedEdges.map(e => (
                <div key={e.edge_id} style={{ padding: '8px 12px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '6px', fontSize: '12px', color: '#B91C1C', display: 'flex', justifyContent: 'space-between' }}>
                  <span>🛑 <strong>{e.road_name.replace(/ \((North|South|East|West)bound\)/g, '')}</strong></span>
                  <span style={{ fontFamily: 'monospace', fontSize: '10px', color: '#DC2626' }}>{e.edge_id}</span>
                </div>
              ))}
              <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '12px', color: '#475569', cursor: 'pointer', marginTop: '2px' }}>
                <input type="checkbox" checked={useRealBlockages} onChange={e => setUseRealBlockages(e.target.checked)} />
                Include these live blockages in simulation
              </label>
            </div>
          )}
        </div>

        {/* Controls Row */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' }}>

          {/* Trip Count Slider */}
          <div style={{ flex: '1 1 260px', minWidth: '220px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <label style={{ fontSize: '12px', fontWeight: 700, color: '#475569' }}>
                Synthetic Trip Population
              </label>
              <span style={{
                fontSize: '12px', fontWeight: 800, color: '#0B8B95',
                backgroundColor: '#F0FDFA', padding: '1px 8px', borderRadius: '4px',
              }}>
                {tripCountLabel}
              </span>
            </div>
            <input
              type="range" min={50} max={500} step={10}
              value={tripCount}
              onChange={e => setTripCount(Number(e.target.value))}
              style={{
                width: '100%', height: '5px', borderRadius: '3px', outline: 'none',
                cursor: 'pointer', appearance: 'none', WebkitAppearance: 'none',
                background: sliderBackground(),
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#94A3B8', marginTop: '3px' }}>
              <span>50</span><span>150 (default)</span><span>500</span>
            </div>
            <p style={{ fontSize: '11px', color: '#94A3B8', margin: '4px 0 0' }}>
              Higher counts show more stable BPR-weighted equilibrium results.
            </p>
          </div>

          {/* Hypothetical Blocked Edge Multi-Select */}
          <div style={{ flex: '1 1 280px', minWidth: '240px' }}>
            <label style={{ fontSize: '12px', fontWeight: 700, color: '#C78420', display: 'block', marginBottom: '4px' }}>
              🧪 Add Hypothetical Blockage(s)
            </label>
            <p style={{ fontSize: '11px', color: '#94A3B8', margin: '0 0 6px' }}>
              Select roads to block for this simulation only — does not affect real routing.
              {selectedEdgeIds.length > 0 && <span style={{ color: '#C78420', fontWeight: 700 }}> {selectedEdgeIds.length} selected</span>}
            </p>
            <div style={{ position: 'relative' }}>
              <button
                type="button"
                onClick={() => setEdgeDropdownOpen(o => !o)}
                style={{
                  width: '100%', padding: '8px 12px', borderRadius: '6px',
                  border: '1px solid #CBD5E1', backgroundColor: '#FFFFFF',
                  textAlign: 'left', fontSize: '12px', fontWeight: 600, color: '#1E293B',
                  cursor: 'pointer', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                  {selectedEdgeIds.length === 0
                    ? 'None (use current graph state)'
                    : selectedEdgeLabels.slice(0, 2).join(', ') + (selectedEdgeLabels.length > 2 ? ` +${selectedEdgeLabels.length - 2}` : '')}
                </span>
                {edgeDropdownOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              </button>

              {edgeDropdownOpen && (
                <>
                  <div onClick={() => setEdgeDropdownOpen(false)}
                    style={{ position: 'fixed', inset: 0, zIndex: 100 }} />
                  <div style={{
                    position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0, zIndex: 101,
                    backgroundColor: '#FFFFFF', border: '1px solid #E2E8F0', borderRadius: '8px',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.12)', maxHeight: '200px', overflowY: 'auto',
                  }}>
                    <div style={{ padding: '6px', borderBottom: '1px solid #E2E8F0', display: 'flex', gap: '6px' }}>
                      <button onClick={() => setSelectedEdgeIds(edgeOptions.map(e => e.id))}
                        style={{ flex: 1, fontSize: '11px', fontWeight: 700, padding: '4px', border: '1px solid #0B8B95', borderRadius: '4px', backgroundColor: '#F0FDFA', color: '#0F766E', cursor: 'pointer' }}>
                        Select All
                      </button>
                      <button onClick={() => setSelectedEdgeIds([])}
                        style={{ flex: 1, fontSize: '11px', fontWeight: 700, padding: '4px', border: '1px solid #E2E8F0', borderRadius: '4px', backgroundColor: '#F8FAFC', color: '#64748B', cursor: 'pointer' }}>
                        Clear
                      </button>
                    </div>
                    {edgeOptions.map(opt => (
                      <div key={opt.id}
                        onClick={() => toggleEdge(opt.id)}
                        style={{
                          padding: '8px 12px', cursor: 'pointer', fontSize: '11px',
                          display: 'flex', alignItems: 'center', gap: '8px',
                          backgroundColor: selectedEdgeIds.includes(opt.id) ? '#F0FDFA' : 'transparent',
                          color: selectedEdgeIds.includes(opt.id) ? '#0F766E' : '#1E293B',
                          borderBottom: '1px solid #F1F5F9',
                        }}
                      >
                        <div style={{
                          width: '14px', height: '14px', borderRadius: '3px', flexShrink: 0,
                          border: `1.5px solid ${selectedEdgeIds.includes(opt.id) ? '#0B8B95' : '#CBD5E1'}`,
                          backgroundColor: selectedEdgeIds.includes(opt.id) ? '#0B8B95' : 'transparent',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                          {selectedEdgeIds.includes(opt.id) && (
                            <svg width="8" height="6" viewBox="0 0 8 6" fill="none">
                              <path d="M1 3L3 5L7 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          )}
                        </div>
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {opt.isLive && <span style={{ color: '#DC2626', marginRight: '4px' }}>🛑</span>}
                          {opt.label}
                        </span>
                        {opt.isLive && (
                          <span style={{ fontSize: '9px', fontWeight: 700, color: '#DC2626', backgroundColor: '#FEE2E2', padding: '1px 4px', borderRadius: '3px', flexShrink: 0 }}>LIVE</span>
                        )}
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Run Button */}
          <button
            onClick={handleRunSim}
            disabled={isLoading}
            style={{
              display: 'flex', alignItems: 'center', gap: '8px',
              backgroundColor: isLoading ? '#94A3B8' : '#0B8B95', color: '#FFFFFF',
              border: 'none', borderRadius: '8px', padding: '10px 22px',
              fontWeight: 700, fontSize: '13px', cursor: isLoading ? 'not-allowed' : 'pointer',
              boxShadow: isLoading ? 'none' : '0 2px 6px rgba(11,139,149,0.35)',
              whiteSpace: 'nowrap', alignSelf: 'flex-end', height: '38px',
            }}
          >
            <Play size={15} />
            {isLoading ? 'Simulating…' : `Run with ${tripCountLabel}`}
          </button>
        </div>

        {/* Result Summary Cards */}
        {rippleResult && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '12px', marginTop: '20px' }}>
            {[
              { label: 'Total Trips Simulated', value: `${rippleResult.total_trips}`, sub: 'Active O-D pairs on network', bg: '#F0FDFA', border: '#CCFBF1', text: '#134E4A', sub2: '#14B8A6' },
              { label: 'Rerouted Trips', value: `${rippleResult.affected_trips} (${Math.round((rippleResult.affected_trips / rippleResult.total_trips) * 100)}%)`, sub: 'Redirected from blocked road', bg: '#FEF2F2', border: '#FEE2E2', text: '#991B1B', sub2: '#EF4444' },
              { label: 'Mean Detour Added', value: `+${rippleResult.mean_detour_s}s`, sub: 'Avg added journey time', bg: '#FFFBEB', border: '#FEF3C7', text: '#92400E', sub2: '#F59E0B' },
              { label: 'Network Delay Δ', value: `+${rippleResult.pct_travel_time_increase}%`, sub: 'BPR corridor congestion', bg: '#EFF6FF', border: '#DBEAFE', text: '#1E40AF', sub2: '#3B82F6' },
            ].map(card => (
              <div key={card.label} style={{ backgroundColor: card.bg, border: `1px solid ${card.border}`, padding: '14px', borderRadius: '8px' }}>
                <span style={{ fontSize: '11px', fontWeight: 600, color: card.sub2 }}>{card.label}</span>
                <div style={{ fontSize: '22px', fontWeight: 800, color: card.text, marginTop: '2px' }}>{card.value}</div>
                <span style={{ fontSize: '11px', color: card.sub2 }}>{card.sub}</span>
              </div>
            ))}
          </div>
        )}

        {!rippleResult && (
          <div style={{ marginTop: '20px', padding: '24px', backgroundColor: '#F8FAFC', borderRadius: '8px', textAlign: 'center', border: '1px dashed #CBD5E1' }}>
            <Activity size={28} color="#CBD5E1" style={{ margin: '0 auto 8px', display: 'block' }} />
            <p style={{ fontSize: '13px', color: '#94A3B8', margin: 0 }}>
              Configure trip population and blocked roads above, then click <strong>Run</strong> to see cascading impact.
            </p>
          </div>
        )}
      </div>

      {/* ── Congested Corridors Table ─────────────────────────────────────── */}
      {rippleResult && (
        <div style={{
          backgroundColor: '#FFFFFF', borderRadius: '10px',
          border: '1px solid #E2E8F0', padding: '20px',
          boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <TrendingUp size={18} color="#C78420" />
              <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: '#1E293B' }}>
                Top Congested Detour Corridors
              </h3>
            </div>
            <span style={{ fontSize: '12px', color: '#64748B' }}>Ranked by Δ load · {rippleResult.total_trips} trips · {rippleResult.blocked_edges.length} blocked edge(s)</span>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px', textAlign: 'left' }}>
              <thead>
                <tr style={{ backgroundColor: '#F8FAFC', borderBottom: '2px solid #E2E8F0', color: '#475569', fontWeight: 700 }}>
                  {['Road Segment', 'Baseline', 'Disrupted', 'Δ Trips', 'Capacity', 'Congestion', 'Status'].map(h => (
                    <th key={h} style={{ padding: '9px 12px', whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rippleResult.top_affected_edges.map((m) => (
                  <tr key={m.edge_id} style={{ borderBottom: '1px solid #F1F5F9' }}>
                    <td style={{ padding: '10px 12px', fontWeight: 600, color: '#1E293B', maxWidth: '220px' }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{m.road_name}</div>
                      <div style={{ fontSize: '10px', color: '#94A3B8', fontFamily: 'monospace' }}>{m.edge_id}</div>
                    </td>
                    <td style={{ padding: '10px 12px', color: '#475569' }}>{m.baseline_load}</td>
                    <td style={{ padding: '10px 12px', fontWeight: 700, color: m.delta_load > 0 ? '#B91C1C' : '#475569' }}>{m.disrupted_load}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <span style={{
                        fontWeight: 700, fontSize: '11px',
                        color: m.delta_load > 0 ? '#B91C1C' : '#059669',
                        backgroundColor: m.delta_load > 0 ? '#FEE2E2' : '#ECFDF5',
                        padding: '2px 7px', borderRadius: '4px',
                      }}>
                        {m.delta_load > 0 ? `+${m.delta_load}` : m.delta_load}
                      </span>
                    </td>
                    <td style={{ padding: '10px 12px', color: '#64748B' }}>{m.capacity_proxy}</td>
                    <td style={{ padding: '10px 12px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '60px', height: '5px', backgroundColor: '#E2E8F0', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{
                            width: `${Math.min(100, m.congestion_ratio * 100)}%`, height: '100%',
                            backgroundColor: m.congestion_ratio >= 1.25 ? '#B91C1C' : m.congestion_ratio >= 0.85 ? '#C78420' : '#0B8B95',
                          }} />
                        </div>
                        <span style={{ fontSize: '11px', fontWeight: 600 }}>{m.congestion_ratio}x</span>
                      </div>
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      {m.status === 'severely_congested'
                        ? <span style={{ fontSize: '10px', fontWeight: 700, color: '#B91C1C', backgroundColor: '#FEE2E2', padding: '2px 7px', borderRadius: '4px' }}>⚡ Severe</span>
                        : m.status === 'congested'
                          ? <span style={{ fontSize: '10px', fontWeight: 700, color: '#C78420', backgroundColor: '#FEF3C7', padding: '2px 7px', borderRadius: '4px' }}>⚠️ Congested</span>
                          : <span style={{ fontSize: '10px', fontWeight: 600, color: '#059669', backgroundColor: '#ECFDF5', padding: '2px 7px', borderRadius: '4px' }}>Normal</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ marginTop: '12px', padding: '10px 14px', backgroundColor: '#F8FAFC', borderRadius: '6px', fontSize: '11px', color: '#64748B', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Info size={14} color="#0B8B95" />
            <span>
              BPR function: <code>t = t₀ [1 + 0.20 × (v/c)²·⁵]</code> · Capacity is a synthetic proxy · Not a real-time traffic guarantee.
            </span>
          </div>
        </div>
      )}
    </div>
  );
};
