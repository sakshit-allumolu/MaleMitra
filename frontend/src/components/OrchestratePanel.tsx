import React, { useCallback, useEffect, useState } from 'react';
import { ApiClient } from '../services/api';
import { useIncidents } from '../context/IncidentContext';
import { AgentReply } from './AgentReply';
import { AgentStatus } from '../types';
import { Bot, RefreshCw, Send, CheckCircle2, AlertTriangle, Wrench } from 'lucide-react';

const TOOL_INFO: Record<string, string> = {
  map_to_edge: 'Snap a GPS point to the nearest road segment',
  list_open_incidents: 'List open incidents',
  get_incident_context: 'Evidence, road state and duplicates for one incident',
  compute_route: 'Fastest vs risk-aware route scores',
  estimate_bpr_load: 'Congestion (volume/capacity, BPR delay) on a segment',
  run_ripple_what_if: 'Sandboxed what-if: trips affected if roads close',
  submit_recommendation: 'Record a recommendation for admin approval (never changes state)'
};

export const OrchestratePanel: React.FC = () => {
  const { agentEvents } = useIncidents();
  const [status, setStatus] = useState<AgentStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [message, setMessage] = useState<string>('Which open incident needs attention first, and why?');
  const [reply, setReply] = useState<string | null>(null);
  const [chatError, setChatError] = useState<string | null>(null);
  const [isAsking, setIsAsking] = useState<boolean>(false);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await ApiClient.getAgentStatus());
      setStatusError(null);
    } catch (e: any) {
      setStatusError(e.message || 'Could not load agent status');
    }
  }, []);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const toolCalls = agentEvents.filter(ev => ev.agent === 'watsonx_orchestrate' && ev.action.startsWith('tool:'));
  const callCount = (tool: string) => toolCalls.filter(ev => ev.action === `tool:${tool}`).length;

  const ask = async () => {
    if (!message.trim()) return;
    setIsAsking(true);
    setChatError(null);
    setReply(null);
    try {
      const res = await ApiClient.chatWithAgent(message.trim());
      setReply(res.reply || '(The agent returned an empty reply.)');
    } catch (e: any) {
      setChatError(e.message || 'Agent request failed');
    } finally {
      setIsAsking(false);
      loadStatus();
    }
  };

  const connected = !!status?.configured && !status.last_error;

  return (
    <div style={{
      backgroundColor: '#FFFFFF', borderRadius: '10px', border: '1px solid #E2E8F0', padding: '18px',
      boxShadow: '0 2px 6px rgba(0,0,0,0.04)', display: 'flex', flexDirection: 'column', gap: '14px'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: '10px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Bot size={18} color="#0B8B95" />
          <h3 style={{ fontSize: '15px', fontWeight: 800, margin: 0, color: '#1E293B' }}>watsonx Orchestrate Agent</h3>
        </div>
        <button
          onClick={loadStatus}
          title="Refresh status"
          style={{ border: 'none', background: 'transparent', cursor: 'pointer', color: '#64748B', display: 'flex' }}
        >
          <RefreshCw size={15} />
        </button>
      </div>

      {statusError && (
        <div style={{ fontSize: '12px', color: '#B91C1C' }}>{statusError}</div>
      )}

      {status && (
        <div style={{
          padding: '10px 12px', borderRadius: '8px', fontSize: '12px',
          backgroundColor: status.configured ? (status.last_error ? '#FEF2F2' : '#F0FDF4') : '#FFFBEB',
          border: `1px solid ${status.configured ? (status.last_error ? '#FECACA' : '#BBF7D0') : '#FDE68A'}`,
          color: '#334155'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, marginBottom: '4px' }}>
            {connected ? <CheckCircle2 size={14} color="#16A34A" /> : <AlertTriangle size={14} color={status.configured ? '#DC2626' : '#D97706'} />}
            {!status.configured
              ? 'Not connected to watsonx Orchestrate'
              : status.last_error ? 'Configured, last request failed' : 'Configured'}
          </div>
          {!status.configured && (
            <div>
              Set <code>{status.missing_settings.join(', ')}</code> on the backend and restart. See <code>orchestrate/README.md</code>.
              Until then the incident-management features work normally, but no AI analysis is available.
            </div>
          )}
          {status.configured && status.last_error && <div>{status.last_error}</div>}
          <div style={{ marginTop: '4px', color: '#64748B' }}>
            Tool endpoints: {status.tools_enabled ? 'enabled' : 'disabled (AGENT_TOOL_API_KEY not set)'} • Public URL: {status.tools_public_url}
          </div>
        </div>
      )}

      <div>
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '6px' }}>
          Ask the agent
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <input
            value={message}
            onChange={e => setMessage(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !isAsking) ask(); }}
            maxLength={2000}
            style={{ flex: 1, padding: '8px 10px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px' }}
          />
          <button
            onClick={ask}
            disabled={isAsking || !status?.configured}
            title={status?.configured ? 'Send to the Orchestrate agent' : 'Orchestrate is not configured'}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 14px', borderRadius: '6px', border: 'none',
              backgroundColor: status?.configured ? '#0B8B95' : '#94A3B8', color: '#FFF', fontWeight: 700, fontSize: '12px',
              cursor: isAsking || !status?.configured ? 'not-allowed' : 'pointer'
            }}
          >
            <Send size={13} /> {isAsking ? 'Thinking…' : 'Ask'}
          </button>
        </div>
        {chatError && <div style={{ marginTop: '8px', fontSize: '12px', color: '#B91C1C' }}>{chatError}</div>}
        {reply && (
          <div style={{ marginTop: '8px', padding: '12px 14px', borderRadius: '8px', backgroundColor: '#F8FAFC', border: '1px solid #E2E8F0', fontSize: '13px', color: '#1E293B' }}>
            <AgentReply text={reply} />
          </div>
        )}
      </div>

      <div>
        <div style={{ fontSize: '12px', fontWeight: 700, color: '#475569', textTransform: 'uppercase', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Wrench size={13} /> Tools the agent can call
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {(status?.tools ?? Object.keys(TOOL_INFO)).map(tool => (
            <div key={tool} style={{ display: 'flex', justifyContent: 'space-between', gap: '10px', fontSize: '12px', padding: '6px 10px', backgroundColor: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
              <span><code style={{ fontWeight: 700 }}>{tool}</code> <span style={{ color: '#64748B' }}>— {TOOL_INFO[tool] || ''}</span></span>
              <span style={{ color: '#0F766E', fontWeight: 700, whiteSpace: 'nowrap' }}>{callCount(tool)} calls</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: '6px', fontSize: '11px', color: '#64748B' }}>
          Call counts come from the real tool-call log (last 50 events). Every call is audited in the Agent Timeline.
        </div>
      </div>
    </div>
  );
};
