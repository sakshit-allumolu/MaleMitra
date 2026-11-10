import React, { useState } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { useAuth } from '../context/AuthContext';
import { ApiClient } from '../services/api';
import { InteractiveMap } from '../components/InteractiveMap';
import { StatusBadge } from '../components/StatusBadge';
import { AgentTimeline } from '../components/AgentTimeline';
import { AuditLogViewer } from '../components/AuditLogViewer';
import { WatsonxSkillCatalog } from '../components/WatsonxSkillCatalog';
import {
  ShieldAlert, Users, CheckCircle2, XCircle, AlertTriangle,
  Send, UserCheck, RefreshCw, Activity, ArrowRight, Eye, ShieldCheck 
} from 'lucide-react';

export const AdminWorkspace: React.FC = () => {
  const { incidents, selectedIncident, setSelectedIncident, teams, refreshData, setHighlightedCoordinates } = useIncidents();
  const { currentUser } = useAuth();

  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [reviewNotes, setReviewNotes] = useState<string>('Evidence validated by Control Room Operator.');
  const [selectedTeam, setSelectedTeam] = useState<string>('team-alpha');
  const [assignNotes, setAssignNotes] = useState<string>('Dispatched rapid dewatering and traffic diversion crew.');
  const [blockNotes, setBlockNotes] = useState<string>('Authorized emergency road restriction due to verified >45cm standing water.');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'map' | 'timeline' | 'audit' | 'skills'>('map');

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
      await ApiClient.assignTeam(selectedIncident.id, selectedTeam, assignNotes);
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
          {['all', 'reported', 'under_review', 'assigned', 'field_verified', 'blocked', 'cleared'].map((st) => (
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
              {st.replace('_', ' ')}
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

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px', color: '#64748B' }}>
                    <span>Severity: <strong style={{ color: inc.severity === 'critical' ? '#B91C1C' : '#D97706' }}>{inc.severity.toUpperCase()}</strong></span>
                    {inc.assigned_team_label && (
                      <span style={{ color: '#6D28D9', fontWeight: 600 }}>🚒 {inc.assigned_team_label}</span>
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

              {/* Action 2: Assign Response Team (if reported or under_review) */}
              {['reported', 'under_review', 'assigned'].includes(selectedIncident.status) && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#F8FAFC', padding: '12px', borderRadius: '8px', border: '1px solid #E2E8F0' }}>
                  <select
                    value={selectedTeam}
                    onChange={(e) => setSelectedTeam(e.target.value)}
                    style={{ padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', fontWeight: 600 }}
                  >
                    {teams.map(t => (
                      <option key={t.id} value={t.id}>{t.label} ({t.status})</option>
                    ))}
                  </select>
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
                    Dispatch Team
                  </button>
                </div>
              )}

              {/* Action 3: Authorize Blockage (if verified or assigned) */}
              {['field_verified', 'assigned', 'under_review'].includes(selectedIncident.status) && !selectedIncident.is_blocked && (
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

              {/* Action 4: Authorize Reopening (if blocked or clearance proposed) */}
              {selectedIncident.is_blocked && (
                <div style={{ display: 'flex', gap: '10px', alignItems: 'center', backgroundColor: '#ECFDF5', padding: '12px', borderRadius: '8px', border: '1px solid #A7F3D0' }}>
                  <span style={{ fontSize: '12px', color: '#065F46', flex: 1 }}>
                    {selectedIncident.status === 'clearance_proposed' 
                      ? 'Responder submitted clearance evidence: Road safe to reopen.' 
                      : 'Road is currently blocked. Clearance can be authorized.'}
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

        {/* View Switcher Tabs: Map / Agent Timeline / Audit Trail / Skills */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
          <button
            onClick={() => setActiveTab('map')}
            style={{
              padding: '8px 14px',
              borderRadius: '6px',
              border: 'none',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              backgroundColor: activeTab === 'map' ? '#0B8B95' : '#E2E8F0',
              color: activeTab === 'map' ? '#FFF' : '#475569'
            }}
          >
            🗺️ Road Map & Overlay
          </button>
          <button
            onClick={() => setActiveTab('timeline')}
            style={{
              padding: '8px 14px',
              borderRadius: '6px',
              border: 'none',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              backgroundColor: activeTab === 'timeline' ? '#0B8B95' : '#E2E8F0',
              color: activeTab === 'timeline' ? '#FFF' : '#475569'
            }}
          >
            🤖 Agent Decision Timeline
          </button>
          <button
            onClick={() => setActiveTab('audit')}
            style={{
              padding: '8px 14px',
              borderRadius: '6px',
              border: 'none',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              backgroundColor: activeTab === 'audit' ? '#0B8B95' : '#E2E8F0',
              color: activeTab === 'audit' ? '#FFF' : '#475569'
            }}
          >
            🛡️ System Audit Trail
          </button>
          <button
            onClick={() => setActiveTab('skills')}
            style={{
              padding: '8px 14px',
              borderRadius: '6px',
              border: 'none',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              backgroundColor: activeTab === 'skills' ? '#0B8B95' : '#E2E8F0',
              color: activeTab === 'skills' ? '#FFF' : '#475569'
            }}
          >
            ⚙️ watsonx Skill Catalog
          </button>
        </div>

        {activeTab === 'map' && <InteractiveMap showRippleOverlay={true} height="480px" />}
        {activeTab === 'timeline' && <AgentTimeline />}
        {activeTab === 'audit' && <AuditLogViewer />}
        {activeTab === 'skills' && <WatsonxSkillCatalog />}
      </div>
    </div>
  );
};
