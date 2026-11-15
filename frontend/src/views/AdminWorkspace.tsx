import React, { useState } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { useAuth } from '../context/AuthContext';
import { ApiClient } from '../services/api';
import { InteractiveMap } from '../components/InteractiveMap';
import { StatusBadge } from '../components/StatusBadge';
import { AgentTimeline } from '../components/AgentTimeline';
import { AuditLogViewer } from '../components/AuditLogViewer';
import { OrchestratePanel } from '../components/OrchestratePanel';
import { AgentRecommendationCard } from '../components/AgentRecommendationCard';
import { ResponderPicker, useResponders } from '../components/ResponderPicker';
import {
  ShieldAlert, Users, CheckCircle2, XCircle, AlertTriangle,
  Send, UserCheck, RefreshCw, Activity, ArrowRight, Eye, ShieldCheck, UserPlus, Info
} from 'lucide-react';
import { evaluatePassword } from '../components/LoginPage';

export const AdminWorkspace: React.FC = () => {
  const { incidents, selectedIncident, setSelectedIncident, teams, refreshData, setHighlightedCoordinates } = useIncidents();
  const { currentUser } = useAuth();

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [reviewNotes, setReviewNotes] = useState<string>('Evidence validated by Control Room Operator.');
  const [selectedTeam, setSelectedTeam] = useState<string>('team-alpha');
  const [selectedResponder, setSelectedResponder] = useState<string>('');
  const responders = useResponders();
  const [assignNotes, setAssignNotes] = useState<string>('Dispatched rapid dewatering and traffic diversion crew.');
  const [blockNotes, setBlockNotes] = useState<string>('Authorized emergency road restriction due to verified >45cm standing water.');
  const [rejectNotes, setRejectNotes] = useState<string>('Rejected: duplicate or invalid report.');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'map' | 'timeline' | 'audit' | 'skills' | 'users'>('map');

  // ── Create Account form state ──
  const [newRole, setNewRole] = useState<'responder' | 'admin' | 'citizen'>('responder');
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [newTeam, setNewTeam] = useState('team-alpha');
  const [newPhone, setNewPhone] = useState('');
  const [newDept, setNewDept] = useState('BBMP Monsoon Control Room');
  const [newShowPwd, setNewShowPwd] = useState(false);
  const [newError, setNewError] = useState<string | null>(null);
  const [newSuccess, setNewSuccess] = useState<string | null>(null);
  const [newLoading, setNewLoading] = useState(false);

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setNewError(null);
    setNewSuccess(null);
    const str = evaluatePassword(newPassword);
    if (str.score < 5) {
      setNewError('Password does not meet all requirements.');
      return;
    }
    setNewLoading(true);
    try {
      const created = await ApiClient.adminCreateUser({
        name: newName.trim(),
        email: newEmail.trim(),
        password: newPassword,
        role: newRole,
        team_id: newRole === 'responder' ? newTeam : undefined,
        phone: newPhone || undefined,
      });
      setNewSuccess(`Account created: ${created.name} (${created.role}) — ${created.email}`);
      setNewName(''); setNewEmail(''); setNewPassword(''); setNewPhone('');
    } catch (err: any) {
      setNewError(err.message || 'Failed to create account.');
    } finally {
      setNewLoading(false);
    }
  };

  const filteredIncidents = incidents.filter(inc => {
    if (statusFilter === 'all') return true;
    return inc.status === statusFilter;
  });

  const handleReview = async () => {
    if (!selectedIncident) return;
    setIsProcessing(true);
    try {
      await ApiClient.reviewIncident(selectedIncident.id, reviewNotes);
      await refreshData();
    } catch (e: any) {
      alert(`Review error: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAssign = async () => {
    if (!selectedIncident) return;
    setIsProcessing(true);
    try {
      await ApiClient.assignTeam(selectedIncident.id, selectedTeam, assignNotes, selectedResponder || undefined);
      await refreshData();
    } catch (e: any) {
      alert(`Assign error: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAuthorizeBlock = async () => {
    if (!selectedIncident) return;
    setIsProcessing(true);
    try {
      await ApiClient.authorizeRestriction(selectedIncident.id, 'authorize_block', blockNotes);
      await refreshData();
    } catch (e: any) {
      alert(`Authorization error: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleReject = async () => {
    if (!selectedIncident) return;
    if (!window.confirm('Reject this report as duplicate / invalid? This cannot be undone.')) return;
    setIsProcessing(true);
    try {
      await ApiClient.authorizeRestriction(selectedIncident.id, 'reject', rejectNotes);
      await refreshData();
    } catch (e: any) {
      alert(`Reject error: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleAuthorizeReopen = async () => {
    if (!selectedIncident) return;
    setIsProcessing(true);
    try {
      await ApiClient.authorizeRestriction(selectedIncident.id, 'authorize_reopen', 'Reopening confirmed. Road clear.');
      await refreshData();
    } catch (e: any) {
      alert(`Reopening error: ${e.message}`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '20px', alignItems: 'start' }}>
      {/* Left Column: Admin Incident Queue */}
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '10px',
        border: '1px solid #E2E8F0',
        padding: '18px',
        boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
        display: 'flex',
        flexDirection: 'column',
        maxHeight: '820px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #E2E8F0', paddingBottom: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldAlert size={18} color="#0B8B95" />
            <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: '#1E293B' }}>
              Control Room Queue
            </h2>
          </div>
          <button
            onClick={() => refreshData()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              padding: '4px 8px',
              borderRadius: '4px',
              border: '1px solid #CBD5E1',
              backgroundColor: '#F8FAFC',
              fontSize: '11px',
              fontWeight: 600,
              cursor: 'pointer'
            }}
          >
            <RefreshCw size={12} /> Refresh
          </button>
        </div>

        {/* Status Filters */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '14px' }}>
          {['all', 'reported', 'under_review', 'assigned', 'field_verified', 'blocked', 'clearance_proposed', 'cleared', 'rejected'].map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              style={{
                padding: '4px 8px',
                borderRadius: '4px',
                border: 'none',
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                backgroundColor: statusFilter === st ? '#123047' : '#F1F5F9',
                color: statusFilter === st ? '#FFFFFF' : '#475569'
              }}
            >
              {st.replace(/_/g, ' ')}
            </button>
          ))}
        </div>

        {/* Incident List */}
        <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '8px', paddingRight: '4px' }}>
          {filteredIncidents.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px 0', color: '#94A3B8', fontSize: '13px' }}>
              No incidents matching filter.
            </div>
          ) : (
            filteredIncidents.map((inc) => {
              const isSelected = selectedIncident?.id === inc.id;

              return (
                <div
                  key={inc.id}
                  onClick={() => {
                    setSelectedIncident(inc);
                    setHighlightedCoordinates([inc.lat, inc.lon]);
                  }}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    border: `1.5px solid ${isSelected ? '#0B8B95' : '#E2E8F0'}`,
                    backgroundColor: isSelected ? '#F0FDFA' : '#FAFAFA',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <span style={{ fontSize: '11px', fontFamily: 'monospace', fontWeight: 700, color: '#64748B' }}>
                      {inc.id}
                    </span>
                    <StatusBadge status={inc.status} size="sm" />
                  </div>

                  <div style={{ fontWeight: 700, fontSize: '13px', color: '#1E293B', marginBottom: '2px' }}>
                    {inc.road_name || 'Waterlogging Hazard'}
                  </div>

                  <div style={{ fontSize: '12px', color: '#475569', marginBottom: '6px', lineHeight: 1.3 }}>
                    {inc.evidence_list[0]?.text_notes || 'Reported hazard disruption'}
                  </div>

                  {/* Triage signals: AI confidence, corroborating reports, duplicate flag */}
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginBottom: '6px' }}>
                    <span
                      title={inc.agent_summary?.recommendation || 'Location-match confidence'}
                      style={{
                        fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px',
                        color: inc.confidence >= 0.8 ? '#065F46' : inc.confidence >= 0.6 ? '#92400E' : '#B91C1C',
                        backgroundColor: inc.confidence >= 0.8 ? '#D1FAE5' : inc.confidence >= 0.6 ? '#FEF3C7' : '#FEE2E2',
                      }}
                    >
                      {Math.round(inc.confidence * 100)}% match
                    </span>
                    {inc.reports_count > 1 && (
                      <span
                        title="Independent citizen reports of the same spot. More reports means a more serious hazard."
                        style={{
                          fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px',
                          color: inc.reports_count >= 3 ? '#9A3412' : '#1E40AF',
                          backgroundColor: inc.reports_count >= 3 ? '#FFEDD5' : '#DBEAFE'
                        }}
                      >
                        {inc.reports_count} reports
                      </span>
                    )}
                    {inc.agent_summary?.duplicate_cluster && (
                      <span style={{ fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px', color: '#6D28D9', backgroundColor: '#EDE9FE' }}>
                        Possible duplicate of {inc.agent_summary.duplicate_of}
                      </span>
                    )}
                    {inc.agent_summary?.is_ambiguous && (
                      <span style={{ fontSize: '10px', fontWeight: 700, padding: '1px 6px', borderRadius: '4px', color: '#92400E', backgroundColor: '#FEF3C7' }}>
                        Ambiguous location
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: '#64748B' }}>
                    <span>Severity: <strong style={{ color: inc.severity === 'critical' ? '#B91C1C' : '#D97706' }}>{inc.severity.toUpperCase()}</strong></span>
                    {inc.assigned_team_label && (
                      <span style={{ color: '#6D28D9', fontWeight: 600 }}>
                        🚒 {inc.assigned_team_label} · {inc.assigned_responder_name || 'team queue'}
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Right Column: Selected Incident Detail & Authorization Panel + Map / Agent Timeline */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        
        {/* Selected Incident Action Panel */}
        {selectedIncident ? (
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '10px',
            border: '2px solid #0B8B95',
            padding: '20px',
            boxShadow: '0 4px 12px rgba(11, 139, 149, 0.08)'
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '14px', borderBottom: '1px solid #E2E8F0', paddingBottom: '12px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#0B8B95', backgroundColor: '#E6FFFA', padding: '2px 6px', borderRadius: '4px' }}>
                    INCIDENT DETAILS
                  </span>
                  <span style={{ fontSize: '12px', fontFamily: 'monospace', color: '#64748B' }}>
                    {selectedIncident.id}
                  </span>
                </div>
                <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#1E293B', margin: '4px 0' }}>
                  {selectedIncident.road_name || 'Waterlogging Hazard'}
                </h3>
                <div style={{ fontSize: '12px', color: '#64748B' }}>
                  Reported by: <strong>{selectedIncident.reported_by_name}</strong> • Coordinates: ({selectedIncident.lat}, {selectedIncident.lon})
                </div>
              </div>

              <StatusBadge status={selectedIncident.status} size="lg" />
            </div>

            <AgentRecommendationCard incident={selectedIncident} />

            {selectedIncident.agent_summary?.recommendation && (
              <div style={{ marginBottom: '12px', padding: '8px 12px', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', borderRadius: '6px', fontSize: '12px', color: '#075985' }}>
                <strong>Triage assistant:</strong> {selectedIncident.agent_summary.recommendation}
                {' '}(location match {Math.round(selectedIncident.confidence * 100)}%
                {selectedIncident.reports_count > 1 ? `, ${selectedIncident.reports_count} reports` : ''})
              </div>
            )}

            {/* Evidence & Verification Logs */}
            <div style={{ marginBottom: '16px' }}>
              <div style={{ fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '6px', textTransform: 'uppercase' }}>
                Evidence & Verification Trail
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {selectedIncident.evidence_list.map((ev, idx) => (
                  <div key={idx} style={{ padding: '8px 12px', backgroundColor: '#F8FAFC', borderRadius: '6px', border: '1px solid #E2E8F0', fontSize: '12px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '2px' }}>
                      <strong style={{ color: '#0F766E' }}>{ev.submitter_name} ({ev.evidence_type})</strong>
                      <span style={{ fontSize: '10px', color: '#94A3B8' }}>{new Date(ev.created_at).toLocaleTimeString()}</span>
                    </div>
                    <div style={{ color: '#334155' }}>{ev.text_notes}</div>
                    {ev.photo_url && (
                      <a href={ev.photo_url} target="_blank" rel="noreferrer">
                        <img src={ev.photo_url} alt="Submitted evidence" style={{ marginTop: '6px', maxWidth: '100%', maxHeight: '160px', borderRadius: '6px', border: '1px solid #E2E8F0' }} />
                      </a>
                    )}
                    {ev.water_depth_cm && (
                      <div style={{ marginTop: '2px', color: '#B91C1C', fontWeight: 600 }}>
                        Measured Water Depth: {ev.water_depth_cm} cm
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>

            {/* Admin State Mutation Actions */}
            <div style={{ borderTop: '1px solid #E2E8F0', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div style={{ fontSize: '13px', fontWeight: 700, color: '#1E293B' }}>
                Administrative Workflow Actions:
              </div>

              {/* Action 1: Review & Triage (if reported) */}
              {selectedIncident.status === 'reported' && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <input
                    type="text"
                    value={reviewNotes}
                    onChange={(e) => setReviewNotes(e.target.value)}
                    placeholder="Triage review notes..."
                    style={{ flex: 1, padding: '8px 10px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                  />
                  <button
                    onClick={handleReview}
                    disabled={isProcessing}
                    style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#0B8B95', color: '#FFF', fontWeight: 700, fontSize: '12px', cursor: 'pointer' }}
                  >
                    Confirm Review
                  </button>
                </div>
              )}

              {/* Reject duplicate / invalid report (reported or under_review only) */}
              {['reported', 'under_review'].includes(selectedIncident.status) && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <input
                    type="text"
                    value={rejectNotes}
                    onChange={(e) => setRejectNotes(e.target.value)}
                    placeholder="Reason for rejection..."
                    style={{ flex: 1, padding: '8px 10px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                  />
                  <button
                    onClick={handleReject}
                    disabled={isProcessing}
                    style={{ padding: '8px 16px', borderRadius: '6px', border: '1px solid #94A3B8', backgroundColor: '#FFF', color: '#475569', fontWeight: 700, fontSize: '12px', cursor: 'pointer' }}
                  >
                    Reject Report
                  </button>
                </div>
              )}

              {/* Action 2: Assign Response Team (only after triage review) */}
              {['under_review', 'assigned'].includes(selectedIncident.status) && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <select
                    value={selectedTeam}
                    onChange={(e) => { setSelectedTeam(e.target.value); setSelectedResponder(''); }}
                    style={{ padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', fontWeight: 600 }}
                  >
                    {teams.map(t => (
                      <option key={t.id} value={t.id}>{t.label} ({t.status})</option>
                    ))}
                  </select>
                  <ResponderPicker
                    teamId={selectedTeam}
                    value={selectedResponder}
                    onChange={setSelectedResponder}
                    responders={responders}
                  />
                  <input
                    type="text"
                    value={assignNotes}
                    onChange={(e) => setAssignNotes(e.target.value)}
                    placeholder="Dispatch instructions..."
                    style={{ flex: 1, padding: '8px 10px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                  />
                  <button
                    onClick={handleAssign}
                    disabled={isProcessing}
                    style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#6D28D9', color: '#FFF', fontWeight: 700, fontSize: '12px', cursor: 'pointer' }}
                  >
                    {selectedIncident.status === 'assigned' ? 'Reassign' : selectedResponder ? 'Dispatch Responder' : 'Send to Team Queue'}
                  </button>
                </div>
              )}

              {/* Closure is gated on responder evidence */}
              {['reported', 'under_review', 'assigned'].includes(selectedIncident.status) && (
                <div style={{ padding: '10px 12px', borderRadius: '8px', border: '1px dashed #CBD5E1', backgroundColor: '#F8FAFC', fontSize: '12px', color: '#64748B' }}>
                  {selectedIncident.status === 'assigned'
                    ? 'Road closure unlocks after the assigned responder submits an on-site field verification.'
                    : 'Triage and dispatch a field team first — a road can only be closed after on-site verification.'}
                </div>
              )}

              {/* Action 3: Authorize Blockage (only after field verification) */}
              {selectedIncident.status === 'field_verified' && !selectedIncident.is_blocked && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#FEF2F2', padding: '12px', borderRadius: '8px', border: '1px solid #FEE2E2' }}>
                  <input
                    type="text"
                    value={blockNotes}
                    onChange={(e) => setBlockNotes(e.target.value)}
                    placeholder="Authorization notes..."
                    style={{ flex: 1, padding: '8px 10px', borderRadius: '6px', border: '1px solid #FCA5A5', fontSize: '12px' }}
                  />
                  <button
                    onClick={handleAuthorizeBlock}
                    disabled={isProcessing}
                    style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#B91C1C', color: '#FFF', fontWeight: 700, fontSize: '12px', cursor: 'pointer' }}
                  >
                    Authorize Road Blockage
                  </button>
                </div>
              )}

              {/* Action 4: Reopening — only once the responder has proposed clearance */}
              {selectedIncident.is_blocked && selectedIncident.status === 'blocked' && (
                <div style={{ padding: '10px 12px', borderRadius: '8px', border: '1px dashed #CBD5E1', backgroundColor: '#F8FAFC', fontSize: '12px', color: '#64748B' }}>
                  Road is closed. Reopening unlocks after the responder submits clearance evidence.
                </div>
              )}
              {selectedIncident.status === 'clearance_proposed' && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#ECFDF5', padding: '12px', borderRadius: '8px', border: '1px solid #A7F3D0' }}>
                  <span style={{ fontSize: '12px', color: '#065F46', flex: 1 }}>
                    Responder submitted clearance evidence: review it above, then reopen the road.
                  </span>
                  <button
                    onClick={handleAuthorizeReopen}
                    disabled={isProcessing}
                    style={{ padding: '8px 16px', borderRadius: '6px', border: 'none', backgroundColor: '#059669', color: '#FFF', fontWeight: 700, fontSize: '12px', cursor: 'pointer' }}
                  >
                    Authorize Reopening
                  </button>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ backgroundColor: '#F8FAFC', padding: '20px', borderRadius: '10px', border: '1px dashed #CBD5E1', textAlign: 'center', color: '#64748B' }}>
            Select an incident from the queue on the left to inspect evidence, dispatch response teams, or authorize road closures.
          </div>
        )}

        {/* View Switcher Tabs */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          {([
            { key: 'map',      label: '🗺️ Road Map & Overlay' },
            { key: 'timeline', label: '🤖 Agent Decision Timeline' },
            { key: 'audit',    label: '🛡️ System Audit Trail' },
            { key: 'skills',   label: '🤖 watsonx Orchestrate Agent' },
            { key: 'users',    label: '👤 Manage Accounts' },
          ] as const).map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              style={{
                padding: '8px 14px', borderRadius: '6px', border: 'none',
                fontWeight: 700, fontSize: '12px', cursor: 'pointer',
                backgroundColor: activeTab === key ? '#0B8B95' : '#E2E8F0',
                color: activeTab === key ? '#FFF' : '#475569',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {activeTab === 'map' && <InteractiveMap showRippleOverlay={true} height="480px" />}
        {activeTab === 'timeline' && <AgentTimeline />}
        {activeTab === 'audit' && <AuditLogViewer />}
        {activeTab === 'skills' && <OrchestratePanel />}

        {/* ── Manage Accounts Tab ── */}
        {activeTab === 'users' && (() => {
          const inputStyle: React.CSSProperties = {
            width: '100%', padding: '8px 10px', borderRadius: '6px',
            border: '1px solid #CBD5E1', fontSize: '13px', outline: 'none',
            boxSizing: 'border-box', color: '#1E293B',
          };
          const labelStyle: React.CSSProperties = {
            fontSize: '12px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '4px',
          };
          const pwStr = evaluatePassword(newPassword);
          return (
            <div style={{ backgroundColor: '#FFFFFF', borderRadius: '10px', border: '1px solid #E2E8F0', padding: '20px', boxShadow: '0 2px 6px rgba(0,0,0,0.04)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px', borderBottom: '1px solid #E2E8F0', paddingBottom: '12px' }}>
                <UserPlus size={18} color="#0B8B95" />
                <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: '#1E293B' }}>Create Staff Account</h2>
              </div>

              {/* Info notice */}
              <div style={{ display: 'flex', gap: '10px', padding: '10px 12px', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', borderRadius: '8px', fontSize: '12px', color: '#0369A1', marginBottom: '16px' }}>
                <Info size={14} style={{ flexShrink: 0, marginTop: '1px' }} />
                <span>Responder and Administrator accounts can only be created here. Citizens self-register at the login page.</span>
              </div>

              {newError && (
                <div style={{ padding: '10px 12px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '6px', fontSize: '12px', color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
                  <XCircle size={14} />{newError}
                </div>
              )}
              {newSuccess && (
                <div style={{ padding: '10px 12px', backgroundColor: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: '6px', fontSize: '12px', color: '#166534', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '14px' }}>
                  <CheckCircle2 size={14} />{newSuccess}
                </div>
              )}

              <form onSubmit={handleCreateUser} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Role selector */}
                <div>
                  <label style={labelStyle}>Account Role</label>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                    {([
                      { role: 'responder', label: 'Responder' },
                      { role: 'admin',     label: 'Admin' },
                      { role: 'citizen',   label: 'Citizen' },
                    ] as const).map(({ role, label }) => (
                      <button key={role} type="button" onClick={() => setNewRole(role)} style={{
                        padding: '9px 6px', borderRadius: '6px',
                        border: `1.5px solid ${newRole === role ? '#0B8B95' : '#E2E8F0'}`,
                        backgroundColor: newRole === role ? '#F0FDFA' : '#FAFAFA',
                        cursor: 'pointer', fontSize: '12px', fontWeight: newRole === role ? 700 : 500,
                        color: newRole === role ? '#0F766E' : '#475569',
                      }}>
                        {label}
                      </button>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={labelStyle}>Full Name</label>
                    <input type="text" value={newName} onChange={e => setNewName(e.target.value)}
                      placeholder="Inspector Ramesh" style={inputStyle} required />
                  </div>
                  <div>
                    <label style={labelStyle}>Email Address</label>
                    <input type="email" value={newEmail} onChange={e => setNewEmail(e.target.value)}
                      placeholder="staff@malemitra.in" style={inputStyle} required />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div>
                    <label style={labelStyle}>Phone (Optional)</label>
                    <input type="tel" value={newPhone} onChange={e => setNewPhone(e.target.value)}
                      placeholder="+91 98765 43210" style={inputStyle} />
                  </div>
                  {newRole === 'responder' && (
                    <div>
                      <label style={labelStyle}>Response Team</label>
                      <select value={newTeam} onChange={e => setNewTeam(e.target.value)} style={{ ...inputStyle, fontWeight: 600 }}>
                        <option value="team-alpha">Team Alpha — Stormwater & Dewatering</option>
                        <option value="team-beta">Team Beta — Traffic & Debris</option>
                        <option value="team-gamma">Team Gamma — Quick Drainage & Silt</option>
                      </select>
                    </div>
                  )}
                  {newRole === 'admin' && (
                    <div>
                      <label style={labelStyle}>Department</label>
                      <input type="text" value={newDept} onChange={e => setNewDept(e.target.value)}
                        placeholder="BBMP Monsoon Control Room" style={inputStyle} />
                    </div>
                  )}
                </div>

                <div>
                  <label style={labelStyle}>Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type={newShowPwd ? 'text' : 'password'}
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      placeholder="••••••••"
                      style={{ ...inputStyle, paddingRight: '36px' }}
                      required
                    />
                    <button type="button" onClick={() => setNewShowPwd(p => !p)}
                      style={{ position: 'absolute', right: '10px', top: '10px', background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}>
                      <Eye size={15} />
                    </button>
                  </div>
                  {newPassword && (
                    <div style={{ marginTop: '6px' }}>
                      <div style={{ display: 'flex', gap: '3px', marginBottom: '3px' }}>
                        {[1,2,3,4,5].map(i => (
                          <div key={i} style={{ flex: 1, height: '4px', borderRadius: '2px', backgroundColor: i <= pwStr.score ? pwStr.color : '#E2E8F0', transition: 'background-color 0.2s' }} />
                        ))}
                      </div>
                      <span style={{ fontSize: '11px', color: pwStr.color, fontWeight: 700 }}>{pwStr.label}</span>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={newLoading || pwStr.score < 5}
                  style={{
                    padding: '10px', borderRadius: '6px', border: 'none',
                    backgroundColor: (newLoading || pwStr.score < 5) ? '#94A3B8' : '#123047',
                    color: '#FFF', fontWeight: 700, fontSize: '13px',
                    cursor: (newLoading || pwStr.score < 5) ? 'not-allowed' : 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                  }}
                >
                  <UserPlus size={14} />
                  {newLoading ? 'Creating…' : `Create ${newRole.charAt(0).toUpperCase() + newRole.slice(1)} Account`}
                </button>
              </form>
            </div>
          );
        })()}
      </div>
    </div>
  );
};
