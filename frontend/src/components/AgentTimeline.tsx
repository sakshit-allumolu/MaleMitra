import React, { useState } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { AgentEventItem } from '../types';
import { Activity, Bot, CheckCircle2, ChevronRight, Clock, ShieldAlert, Cpu } from 'lucide-react';

export const AgentTimeline: React.FC = () => {
  const { agentEvents } = useIncidents();
  const [selectedEvent, setSelectedEvent] = useState<AgentEventItem | null>(null);

  const getAgentBadge = (agent: string) => {
    switch (agent) {
      case 'incident_intelligence':
        return { label: 'Incident Intelligence Agent', color: '#0369A1', bg: '#E0F2FE' };
      case 'mobility':
        return { label: 'Mobility & Rerouting Agent', color: '#0B8B95', bg: '#E6FFFA' };
      case 'ripple_impact':
        return { label: 'Ripple Impact Agent', color: '#C78420', bg: '#FEF3C7' };
      case 'response_coordinator':
        return { label: 'Response Coordinator Agent', color: '#6D28D9', bg: '#EDE9FE' };
      default:
        return { label: agent, color: '#475569', bg: '#F1F5F9' };
    }
  };

  return (
    <div style={{
      backgroundColor: '#FFFFFF',
      borderRadius: '10px',
      border: '1px solid #E2E8F0',
      padding: '16px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
      height: '100%',
      display: 'flex',
      flexDirection: 'column'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #E2E8F0', paddingBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Cpu size={18} color="#0B8B95" />
          <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: '#1E293B' }}>
            Multi-Agent Decision Timeline
          </h3>
        </div>
        <span style={{ fontSize: '11px', color: '#64748B', backgroundColor: '#F1F5F9', padding: '2px 8px', borderRadius: '4px' }}>
          {agentEvents.length} events logged
        </span>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '10px', paddingRight: '4px', maxHeight: '480px' }}>
        {agentEvents.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#94A3B8', fontSize: '13px' }}>
            No agent events triggered yet. Submit a report or run a simulation to see agent decisions.
          </div>
        ) : (
          agentEvents.map((ev) => {
            const badge = getAgentBadge(ev.agent);
            const isSelected = selectedEvent?.event_id === ev.event_id;

            return (
              <div
                key={ev.event_id}
                onClick={() => setSelectedEvent(isSelected ? null : ev)}
                style={{
                  padding: '10px 12px',
                  borderRadius: '8px',
                  border: `1px solid ${isSelected ? '#0B8B95' : '#E2E8F0'}`,
                  backgroundColor: isSelected ? '#F0FDFA' : '#FAFAFA',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                  <span style={{
                    fontSize: '11px',
                    fontWeight: 700,
                    color: badge.color,
                    backgroundColor: badge.bg,
                    padding: '2px 6px',
                    borderRadius: '4px'
                  }}>
                    {badge.label}
                  </span>
                  <span style={{ fontSize: '11px', color: '#94A3B8', display: 'flex', alignItems: 'center', gap: '3px' }}>
                    <Clock size={11} />
                    {new Date(ev.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <div style={{ fontSize: '13px', fontWeight: 600, color: '#1E293B', marginBottom: '4px' }}>
                  ⚙️ Action: <code>{ev.action}</code>
                </div>

                {ev.incident_id && (
                  <div style={{ fontSize: '11px', color: '#64748B', marginBottom: '4px' }}>
                    Target: <strong>{ev.incident_id}</strong>
                  </div>
                )}

                {/* Expanded Payload view */}
                {isSelected && (
                  <div style={{
                    marginTop: '8px',
                    padding: '8px',
                    borderRadius: '6px',
                    backgroundColor: '#1E293B',
                    color: '#E2E8F0',
                    fontSize: '11px',
                    fontFamily: 'monospace',
                    overflowX: 'auto'
                  }}>
                    <div style={{ color: '#38BDF8', fontWeight: 700, marginBottom: '4px' }}>// Input References</div>
                    <pre style={{ margin: '0 0 6px 0' }}>{JSON.stringify(ev.input_refs, null, 2)}</pre>
                    <div style={{ color: '#34D399', fontWeight: 700, marginBottom: '4px' }}>// Typed Result Output</div>
                    <pre style={{ margin: 0 }}>{JSON.stringify(ev.result, null, 2)}</pre>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
