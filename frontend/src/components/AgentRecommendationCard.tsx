import React, { useEffect, useState } from 'react';
import { ApiClient } from '../services/api';
import { useIncidents } from '../context/IncidentContext';
import { AgentRecommendation, Incident } from '../types';
import { Bot, Sparkles, Check, X } from 'lucide-react';
import { AgentReply } from './AgentReply';
import { ResponderPicker, useResponders } from './ResponderPicker';

const ACTION_LABEL: Record<string, string> = {
  request_triage: 'Triage this report',
  assign_team: 'Assign a response team',
  reject_duplicate: 'Reject as duplicate',
  request_field_verification: 'Wait for / request field verification',
  propose_block: 'Authorize road closure',
  propose_reopen: 'Authorize reopening',
  monitor: 'Keep monitoring',
  escalate: 'Escalate'
};

// What "Approve" does for each action. Advisory actions have no workflow step: approving just acknowledges them.
const APPROVE_LABEL: Record<string, string> = {
  request_triage: 'Approve & confirm review',
  assign_team: 'Approve & dispatch team',
  reject_duplicate: 'Approve & reject report',
  propose_block: 'Approve & close road',
  propose_reopen: 'Approve & reopen road'
};

export const AgentRecommendationCard: React.FC<{ incident: Incident }> = ({ incident }) => {
  const { teams, refreshData } = useIncidents();
  const [rec, setRec] = useState<AgentRecommendation | null>(null);
  const [reply, setReply] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);
  const [deciding, setDeciding] = useState<boolean>(false);
  const [teamId, setTeamId] = useState<string>('');
  const [responderId, setResponderId] = useState<string>('');
  const responders = useResponders();

  useEffect(() => {
    let cancelled = false;
    setRec(null);
    setReply(null);
    setError(null);
    ApiClient.getRecommendation(incident.id).then(r => { if (!cancelled) setRec(r); });
    return () => { cancelled = true; };
  }, [incident.id]);

  useEffect(() => {
    if (!teamId && teams.length > 0) setTeamId(teams[0].id);
  }, [teams, teamId]);

  // Preselect what the agent recommended; the admin can still change it before approving.
  useEffect(() => {
    if (rec?.action === 'assign_team') {
      if (rec.team_id) setTeamId(rec.team_id);
      setResponderId(rec.responder_id || '');
    }
  }, [rec?.event_id]);

  const analyze = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await ApiClient.analyzeIncident(incident.id);
      setRec(res.recommendation);
      setReply(res.reply || null);
      await refreshData();   // refresh the timeline
    } catch (e: any) {
      setError(e.message || 'Agent analysis failed');
    } finally {
      setBusy(false);
    }
  };

  const decide = async (decision: 'approve' | 'dismiss') => {
    if (!rec) return;
    setDeciding(true);
    setError(null);
    try {
      const res = await ApiClient.decideRecommendation(
        rec.event_id, decision,
        rec.action === 'assign_team' ? { team_id: teamId, responder_id: responderId || null } : {});
      setRec(res.recommendation);
      await refreshData();   // incident status, queue and timeline all change
    } catch (e: any) {
      setError(e.message || 'Could not record the decision');
    } finally {
      setDeciding(false);
    }
  };

  // A recommendation made at an earlier workflow step is history, not advice for the current step.
  const stale = !!rec && rec.status_at_recommendation !== incident.status;
  const decided = !!rec?.decision;
  const open = !!rec && !decided;
  const advisory = !!rec && !APPROVE_LABEL[rec.action];

  const buttonBase: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: '5px', padding: '5px 12px', borderRadius: '5px',
    fontWeight: 700, fontSize: '11px'
  };

  return (
    <div style={{ marginBottom: '12px', padding: '10px 12px', backgroundColor: '#F5F3FF', border: '1px solid #DDD6FE', borderRadius: '6px', fontSize: '12px', color: '#4C1D95' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px' }}>
        <strong style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
          <Bot size={14} /> watsonx Orchestrate agent
        </strong>
        <button
          onClick={analyze}
          disabled={busy || deciding}
          style={{
            display: 'flex', alignItems: 'center', gap: '5px', padding: '4px 10px', borderRadius: '5px', border: 'none',
            backgroundColor: '#6D28D9', color: '#FFF', fontWeight: 700, fontSize: '11px', cursor: busy ? 'not-allowed' : 'pointer'
          }}
        >
          <Sparkles size={12} /> {busy ? 'Analysing…' : rec ? 'Re-analyse' : 'Ask agent'}
        </button>
      </div>

      {error && <div style={{ marginTop: '6px', color: '#B91C1C' }}>{error}</div>}

      {rec && (
        <div style={{ marginTop: '8px' }}>
          <div style={{ fontWeight: 700 }}>
            Recommends: {ACTION_LABEL[rec.action] || rec.action}
            <span style={{ fontWeight: 500 }}> ({Math.round(rec.confidence * 100)}% confidence)</span>
          </div>
          <div style={{ marginTop: '2px', color: '#5B21B6' }}>{rec.rationale}</div>
          {rec.action === 'assign_team' && (
            <div style={{ marginTop: '2px', fontWeight: 600 }}>
              {rec.responder_id
                ? `Suggested responder: ${responders.find(r => r.id === rec.responder_id)?.name || rec.responder_id}`
                : 'No free responder found: suggests the team queue.'}
            </div>
          )}

          {decided && (
            <div style={{
              marginTop: '8px', padding: '6px 10px', borderRadius: '5px', fontWeight: 700, fontSize: '11px',
              backgroundColor: rec.decision === 'approved' ? '#ECFDF5' : '#F1F5F9',
              color: rec.decision === 'approved' ? '#065F46' : '#475569',
              border: `1px solid ${rec.decision === 'approved' ? '#A7F3D0' : '#CBD5E1'}`
            }}>
              {rec.decision === 'approved'
                ? (advisory ? 'Acknowledged by admin' : 'Approved by admin — action carried out')
                : 'Dismissed by admin — no changes made'}
              {rec.decided_at ? ` · ${new Date(rec.decided_at).toLocaleTimeString()}` : ''}
            </div>
          )}

          {open && (
            <div style={{ marginTop: '8px', display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px' }}>
              {rec.action === 'assign_team' && !stale && (
                <select
                  value={teamId}
                  onChange={e => { setTeamId(e.target.value); setResponderId(''); }}
                  style={{ padding: '5px 8px', borderRadius: '5px', border: '1px solid #C4B5FD', fontSize: '11px', fontWeight: 600 }}
                >
                  {teams.map(t => <option key={t.id} value={t.id}>{t.label} ({t.status})</option>)}
                </select>
              )}
              {rec.action === 'assign_team' && !stale && (
                <ResponderPicker
                  teamId={teamId}
                  value={responderId}
                  onChange={setResponderId}
                  responders={responders}
                  style={{ padding: '5px 8px', fontSize: '11px', border: '1px solid #C4B5FD' }}
                />
              )}
              <button
                onClick={() => decide('approve')}
                disabled={deciding || stale || (rec.action === 'assign_team' && !teamId)}
                title={stale ? 'The incident has moved on since this was recommended — re-analyse first.' : undefined}
                style={{
                  ...buttonBase, border: 'none', color: '#FFF',
                  backgroundColor: deciding || stale ? '#A7B0BE' : '#059669',
                  cursor: deciding || stale ? 'not-allowed' : 'pointer'
                }}
              >
                <Check size={12} /> {APPROVE_LABEL[rec.action] || 'Acknowledge'}
              </button>
              <button
                onClick={() => decide('dismiss')}
                disabled={deciding}
                style={{ ...buttonBase, border: '1px solid #94A3B8', backgroundColor: '#FFF', color: '#475569', cursor: deciding ? 'not-allowed' : 'pointer' }}
              >
                <X size={12} /> Dismiss
              </button>
            </div>
          )}

          <div style={{ marginTop: '6px', fontSize: '11px', color: '#7C3AED' }}>
            {open && stale
              ? `Made when the incident was "${rec.status_at_recommendation}" — the status has changed since, so re-analyse before relying on it. `
              : ''}
            {open ? 'Advisory only: you decide.' : ''}
          </div>
        </div>
      )}

      {reply && (
        <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #DDD6FE', color: '#334155' }}>
          <AgentReply text={reply} />
        </div>
      )}
    </div>
  );
};
