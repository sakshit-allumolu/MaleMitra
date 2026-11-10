import React, { useState, useEffect } from 'react';
import { useIncidents } from '../context/IncidentContext';
import { useAuth } from '../context/AuthContext';
import { ApiClient } from '../services/api';
import { StatusBadge } from '../components/StatusBadge';
import { Incident } from '../types';
import { 
  Users, CheckCircle2, AlertTriangle, Send, MapPin, 
  Camera, Droplets, ShieldAlert, Check, RefreshCw 
} from 'lucide-react';

export const ResponderWorkspace: React.FC = () => {
  const { incidents, refreshData, setHighlightedCoordinates } = useIncidents();
  const { currentUser } = useAuth();

  const [myTasks, setMyTasks] = useState<Incident[]>([]);
  const [selectedTask, setSelectedTask] = useState<Incident | null>(null);

  // Field Verification Form State
  const [waterDepth, setWaterDepth] = useState<number>(55);
  const [isImpassable, setIsImpassable] = useState<boolean>(true);
  const [findings, setFindings] = useState<string>('On-site inspection confirms deep standing water across both lanes. Vehicles stalling.');
  const [recommendedAction, setRecommendedAction] = useState<string>('authorize_closure');
  const [evidenceNote, setEvidenceNote] = useState<string>('Staff gauge reading 55cm at underpass entrance.');
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Clearance Form State
  const [clearanceFindings, setClearanceFindings] = useState<string>('Dewatering pumps operated for 2 hours. Storm grates cleared of silt. Water depth below 5cm.');

  useEffect(() => {
    // Filter tasks assigned to current responder's team (or all active tasks)
    const teamId = currentUser.team_id || 'team-alpha';
    const assigned = incidents.filter(i => i.assigned_team_id === teamId || !i.assigned_team_id);
    setMyTasks(assigned);
    if (assigned.length > 0 && !selectedTask) {
      setSelectedTask(assigned[0]);
    }
  }, [incidents, currentUser]);

  const handleVerifySubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask) return;
    setIsSubmitting(true);
    setSuccessMsg(null);
    try {
      await ApiClient.verifyIncident(selectedTask.id, {
        findings,
        water_depth_cm: waterDepth,
        is_impassable: isImpassable,
        recommended_action: recommendedAction,
        evidence_note: evidenceNote
      });
      setSuccessMsg('Field verification submitted! Sent to Control Room for road closure authorization.');
      await refreshData();
    } catch (err: any) {
      alert(`Verification error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClearanceSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTask) return;
    setIsSubmitting(true);
    setSuccessMsg(null);
    try {
      await ApiClient.proposeClearance(selectedTask.id, clearanceFindings, 'Field inspection confirms drain clearance complete.');
      setSuccessMsg('Clearance proposal submitted! Control Room notified to authorize reopening.');
      await refreshData();
    } catch (err: any) {
      alert(`Clearance error: ${err.message}`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '900px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header Banner */}
      <div style={{
        backgroundColor: '#123047',
        color: '#FFFFFF',
        borderRadius: '10px',
        padding: '18px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '42px',
            height: '42px',
            borderRadius: '8px',
            backgroundColor: '#0B8B95',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Users size={24} color="#FFF" />
          </div>
          <div>
            <h2 style={{ fontSize: '18px', fontWeight: 800, margin: 0 }}>
              Field Response Workspace
            </h2>
            <p style={{ fontSize: '12px', color: '#94A3B8', margin: 0 }}>
              Responder: <strong>{currentUser.name}</strong> • Unit: <strong>{currentUser.team_id || 'Team Alpha (Stormwater)'}</strong>
            </p>
          </div>
        </div>

        <button
          onClick={() => refreshData()}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 14px',
            borderRadius: '6px',
            backgroundColor: '#0B8B95',
            color: '#FFFFFF',
            border: 'none',
            fontSize: '12px',
            fontWeight: 700,
            cursor: 'pointer'
          }}
        >
          <RefreshCw size={14} /> Refresh Assigned Tasks
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '20px', alignItems: 'start' }}>
        {/* Left Column: Assigned Tasks List */}
        <div style={{
          backgroundColor: '#FFFFFF',
          borderRadius: '10px',
          border: '1px solid #E2E8F0',
          padding: '16px',
          boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
          display: 'flex',
          flexDirection: 'column',
          gap: '10px'
        }}>
          <div style={{ fontSize: '13px', fontWeight: 800, color: '#1E293B', paddingBottom: '8px', borderBottom: '1px solid #E2E8F0' }}>
            Assigned Field Tasks ({myTasks.length})
          </div>

          {myTasks.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '24px 0', color: '#94A3B8', fontSize: '12px' }}>
              No tasks currently assigned. Standby for dispatch.
            </div>
          ) : (
            myTasks.map((task) => {
              const isSelected = selectedTask?.id === task.id;

              return (
                <div
                  key={task.id}
                  onClick={() => {
                    setSelectedTask(task);
                    setHighlightedCoordinates([task.lat, task.lon]);
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
                      {task.id}
                    </span>
                    <StatusBadge status={task.status} size="sm" />
                  </div>

                  <div style={{ fontWeight: 700, fontSize: '13px', color: '#1E293B', marginBottom: '2px' }}>
                    {task.road_name || 'Waterlogging Site'}
                  </div>

                  <div style={{ fontSize: '11px', color: '#64748B' }}>
                    📍 Coordinates: ({task.lat}, {task.lon})
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Field Inspection & Verification Actions */}
        {selectedTask ? (
          <div style={{
            backgroundColor: '#FFFFFF',
            borderRadius: '10px',
            border: '1px solid #E2E8F0',
            padding: '20px',
            boxShadow: '0 2px 6px rgba(0,0,0,0.04)',
            display: 'flex',
            flexDirection: 'column',
            gap: '16px'
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', borderBottom: '1px solid #E2E8F0', paddingBottom: '12px' }}>
              <div>
                <span style={{ fontSize: '11px', fontWeight: 700, color: '#0B8B95', backgroundColor: '#E6FFFA', padding: '2px 6px', borderRadius: '4px' }}>
                  ACTIVE FIELD INSPECTION
                </span>
                <h3 style={{ fontSize: '17px', fontWeight: 800, color: '#1E293B', margin: '4px 0' }}>
                  {selectedTask.road_name || 'Waterlogging Hazard'}
                </h3>
                <div style={{ fontSize: '12px', color: '#64748B' }}>
                  Citizen Report: "{selectedTask.evidence_list[0]?.text_notes || 'Hazard reported'}"
                </div>
              </div>

              <StatusBadge status={selectedTask.status} size="md" />
            </div>

            {successMsg && (
              <div style={{
                padding: '10px 14px',
                backgroundColor: '#ECFDF5',
                border: '1px solid #A7F3D0',
                borderRadius: '6px',
                fontSize: '12px',
                color: '#065F46',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}>
                <CheckCircle2 size={16} color="#059669" />
                <span>{successMsg}</span>
              </div>
            )}

            {/* Form 1: On-site Verification (if not yet blocked or clearance proposed) */}
            {['assigned', 'under_review', 'reported'].includes(selectedTask.status) && (
              <form onSubmit={handleVerifySubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#1E293B' }}>
                  Submit On-Site Inspection Findings:
                </div>

                {/* Water Depth Slider */}
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>
                    <span>Measured Water Depth (cm):</span>
                    <span style={{ color: waterDepth > 35 ? '#B91C1C' : '#0B8B95', fontSize: '14px' }}>
                      {waterDepth} cm {waterDepth > 35 ? '(Impassable Depth)' : '(Passable with caution)'}
                    </span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="100"
                    value={waterDepth}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setWaterDepth(val);
                      setIsImpassable(val >= 35);
                    }}
                    style={{ width: '100%', cursor: 'pointer' }}
                  />
                </div>

                {/* Impassable Toggle */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', backgroundColor: '#F8FAFC', padding: '10px 14px', borderRadius: '6px', border: '1px solid #E2E8F0' }}>
                  <input
                    type="checkbox"
                    id="impassable-check"
                    checked={isImpassable}
                    onChange={(e) => setIsImpassable(e.target.checked)}
                    style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                  />
                  <label htmlFor="impassable-check" style={{ fontSize: '13px', fontWeight: 700, color: '#1E293B', cursor: 'pointer' }}>
                    Road is impassable for standard vehicular traffic (Recommend Hard Closure)
                  </label>
                </div>

                {/* Findings Text */}
                <div>
                  <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                    Detailed Inspection Findings
                  </label>
                  <textarea
                    rows={3}
                    value={findings}
                    onChange={(e) => setFindings(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', backgroundColor: '#F8FAFC', resize: 'none' }}
                    required
                  />
                </div>

                {/* Evidence Note */}
                <div>
                  <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                    Field Evidence Note / Gauge Calibration
                  </label>
                  <input
                    type="text"
                    value={evidenceNote}
                    onChange={(e) => setEvidenceNote(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', backgroundColor: '#F8FAFC' }}
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '10px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: '#0B8B95',
                    color: '#FFFFFF',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                    boxShadow: '0 2px 4px rgba(11, 139, 149, 0.3)'
                  }}
                >
                  <Send size={15} />
                  {isSubmitting ? 'Submitting Verification...' : 'Submit Verified Finding to Admin'}
                </button>
              </form>
            )}

            {/* Form 2: Propose Clearance (if currently blocked) */}
            {selectedTask.is_blocked && (
              <form onSubmit={handleClearanceSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px', backgroundColor: '#F0FDF4', padding: '16px', borderRadius: '8px', border: '1px solid #BBF7D0' }}>
                <div style={{ fontSize: '13px', fontWeight: 800, color: '#166534' }}>
                  🌊 Dewatering Complete: Propose Clearance & Road Reopening
                </div>

                <div>
                  <label style={{ fontSize: '11px', fontWeight: 700, color: '#166534', display: 'block', marginBottom: '2px' }}>
                    Clearance Findings (Water Receded / Silt Cleared)
                  </label>
                  <textarea
                    rows={2}
                    value={clearanceFindings}
                    onChange={(e) => setClearanceFindings(e.target.value)}
                    style={{ width: '100%', padding: '8px', borderRadius: '6px', border: '1px solid #86EFAC', fontSize: '12px', backgroundColor: '#FFFFFF', resize: 'none' }}
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={isSubmitting}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '10px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: '#16A34A',
                    color: '#FFFFFF',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: isSubmitting ? 'not-allowed' : 'pointer',
                    boxShadow: '0 2px 4px rgba(22, 163, 74, 0.3)'
                  }}
                >
                  <Check size={16} />
                  {isSubmitting ? 'Submitting Clearance...' : 'Recommend Clearance to Control Room'}
                </button>
              </form>
            )}
          </div>
        ) : (
          <div style={{ backgroundColor: '#F8FAFC', padding: '24px', borderRadius: '10px', border: '1px dashed #CBD5E1', textAlign: 'center', color: '#64748B' }}>
            Select an assigned task on the left to begin on-site field verification.
          </div>
        )}
      </div>
    </div>
  );
};
