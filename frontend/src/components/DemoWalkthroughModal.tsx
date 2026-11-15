import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useIncidents } from '../context/IncidentContext';
import { ApiClient } from '../services/api';
import {
  Sparkles, X,
  ShieldAlert, Navigation, Users, Activity, Play
} from 'lucide-react';

export const DemoWalkthroughModal: React.FC = () => {
  const { walkthroughOpen, setWalkthroughOpen, refreshData, setActiveView, calculateRoutes, triggerSimulation, incidents } = useIncidents();
  const { login } = useAuth();

  // Switch to a demo role by re-logging as that account
  const switchDemoUser = async (email: string) => {
    try {
      await login(email, 'demo123');
    } catch {
      // Silent: demo accounts are always seeded
    }
  };
  const [currentStep, setCurrentStep] = useState<number>(1);
  const [createdIncId, setCreatedIncId] = useState<string | null>(null);
  const [isExecuting, setIsExecuting] = useState<boolean>(false);
  const [stepStatus, setStepStatus] = useState<string>('');

  const getTargetIncidentId = (): string | null => {
    if (createdIncId) return createdIncId;
    const sony = incidents.find(i => i.road_name?.toLowerCase().includes('sony') || i.road_name?.toLowerCase().includes('80ft'));
    if (sony) return sony.id;
    return incidents[0]?.id || null;
  };

  if (!walkthroughOpen) return null;

  const steps = [
    {
      num: 1,
      role: 'Citizen Commuter',
      title: 'Submit Geotagged Waterlogging Report',
      desc: 'Citizen reports 50cm deep waterlogging at Sony World Junction (Koramangala). System associates coordinates to road edge and logs Incident Intelligence Agent summary.',
      actionLabel: '1. Submit Citizen Report',
      execute: async () => {
        setIsExecuting(true);
        try {
          await switchDemoUser('citizen@malemitra.in');
          setActiveView('citizen');
          setStepStatus('Submitting citizen report...');
          const res = await ApiClient.createReport({
            lat: 12.9365,
            lon: 77.6260,
            type: 'waterlogging',
            severity: 'critical',
            description: 'Sony World Junction underpass heavily flooded. Water rising above knee level (>45cm).',
            evidence_note: 'Multiple vehicles stalled at junction entrance.'
          });
          setCreatedIncId(res.id);
          await refreshData();
          setStepStatus(`Report created: ${res.id} mapped to ${res.road_name || 'road'}`);
          setCurrentStep(2);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to submit report'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 2,
      role: 'BBMP Administrator',
      title: 'Review Triage & Dispatch Field Team',
      desc: 'Control Room Admin reviews citizen evidence, validates priority, and dispatches Response Team Alpha (Stormwater Unit).',
      actionLabel: '2. Review & Assign Team Alpha',
      execute: async () => {
        setIsExecuting(true);
        try {
          const targetId = createdIncId || getTargetIncidentId();
          if (!targetId) {
            throw new Error('No incident found. Please run Step 1 first.');
          }
          await switchDemoUser('admin@malemitra.in');
          setActiveView('admin');
          setStepStatus('Reviewing and assigning field team...');
          // Attempt review if not already reviewed
          try {
            await ApiClient.reviewIncident(targetId, 'High-confidence citizen report confirmed via image evidence.');
          } catch (reviewErr: any) {
            console.warn('Review step note (already reviewed/assigned):', reviewErr?.message);
          }
          try {
            await ApiClient.assignTeam(targetId, 'team-alpha', 'Dispatched rapid suction pump truck and inspection crew.');
          } catch (assignErr: any) {
            console.warn('Assign step note (already assigned):', assignErr?.message);
          }
          setCreatedIncId(targetId);
          await refreshData();
          setStepStatus(`Assigned Team Alpha to incident ${targetId}`);
          setCurrentStep(3);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to review/assign'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 3,
      role: 'Field Responder',
      title: 'On-Site Inspection & Impassable Verification',
      desc: 'Inspector Ramesh inspects Sony World Junction, records water depth of 55cm, confirms road is impassable, and recommends emergency closure.',
      actionLabel: '3. Submit Field Verification',
      execute: async () => {
        setIsExecuting(true);
        try {
          const targetId = createdIncId || getTargetIncidentId();
          if (!targetId) throw new Error('No incident found. Please run Step 1 first.');
          await switchDemoUser('responder1@malemitra.in');
          setActiveView('responder');
          setStepStatus('Submitting on-site responder findings...');
          await ApiClient.verifyIncident(targetId, {
            findings: 'On-site inspection confirms 55cm standing water across both carriageways. Inundation hazard high.',
            water_depth_cm: 55.0,
            is_impassable: true,
            recommended_action: 'authorize_closure',
            evidence_note: 'Water level gauge reading 55cm; stormwater grates choked with silt.'
          });
          setCreatedIncId(targetId);
          await refreshData();
          setStepStatus('Field verification submitted. Ready for admin authorization.');
          setCurrentStep(4);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to verify incident'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 4,
      role: 'BBMP Administrator',
      title: 'Authorize Road Restriction (Graph Version Increments)',
      desc: 'Administrator authorizes formal road closure based on responder evidence. Road segment is excluded from routing and graph_version increments.',
      actionLabel: '4. Authorize Road Blockage',
      execute: async () => {
        setIsExecuting(true);
        try {
          const targetId = createdIncId || getTargetIncidentId();
          if (!targetId) throw new Error('No incident found. Please run Step 1 first.');
          await switchDemoUser('admin@malemitra.in');
          setActiveView('admin');
          setStepStatus('Authorizing emergency road restriction...');
          await ApiClient.authorizeRestriction(targetId, 'authorize_block', 'Authorized road closure by Monsoon Control Room.');
          setCreatedIncId(targetId);
          await refreshData();
          setStepStatus('Road blockage authorized. Graph version updated.');
          setCurrentStep(5);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to authorize blockage'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 5,
      role: 'Citizen Commuter',
      title: 'Dynamic Rerouting: Blocked Edge Excluded',
      desc: 'Citizen route query from Silk Board to Indiranagar normally passes Sony World Junction. With the road closed, the risk-aware route detours around it on real streets.',
      actionLabel: '5. Compare Risk-Aware Routes',
      execute: async () => {
        setIsExecuting(true);
        try {
          await switchDemoUser('citizen@malemitra.in');
          setActiveView('citizen');
          setStepStatus('Calculating risk-aware route comparison...');
          await calculateRoutes({ lat: 12.9170, lon: 77.6230 }, { lat: 12.9780, lon: 77.6410 });
          setStepStatus('Route comparison calculated: Blocked edge avoided with safe detour.');
          setCurrentStep(6);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to calculate routes'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 6,
      role: 'Ripple Engine',
      title: 'Cascading Impact Simulation (150 Synthetic Trips)',
      desc: 'Ripple Engine models how traffic redirects across 150 synthetic trips, identifying congestion deltas on parallel detour corridors (Koramangala 80ft Rd, Intermediate Ring Rd).',
      actionLabel: '6. Run Ripple Simulation',
      execute: async () => {
        setIsExecuting(true);
        try {
          // Ripple Engine is an operator tool (not shown to citizens), so run it as admin
          await switchDemoUser('admin@malemitra.in');
          setStepStatus('Executing Ripple Engine trip reassignments...');
          await triggerSimulation(['edge-7', 'edge-8']);
          setStepStatus('Ripple simulation complete. Cascade load deltas computed.');
          setCurrentStep(7);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to run simulation'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 7,
      role: 'Field Responder',
      title: 'Pumping Complete: Propose Clearance',
      desc: 'Stormwater team clears storm drains and operates dewatering pumps. Water recedes below 10cm; responder proposes reopening.',
      actionLabel: '7. Propose Road Clearance',
      execute: async () => {
        setIsExecuting(true);
        try {
          const targetId = createdIncId || getTargetIncidentId();
          if (!targetId) throw new Error('No incident found. Please run Step 1 first.');
          await switchDemoUser('responder1@malemitra.in');
          setActiveView('responder');
          setStepStatus('Submitting clearance proposal...');
          await ApiClient.proposeClearance(targetId, 'Pumps operated for 90 minutes. Water drained below 5cm. Silt cleared from drains.');
          setCreatedIncId(targetId);
          await refreshData();
          setStepStatus('Clearance proposal submitted with evidence.');
          setCurrentStep(8);
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to propose clearance'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    },
    {
      num: 8,
      role: 'BBMP Administrator',
      title: 'Authorize Reopening (Loop Complete)',
      desc: 'Admin confirms clearance, lifts road restriction, releases Response Team, and increments graph_version back to open state.',
      actionLabel: '8. Authorize Reopening & Restore',
      execute: async () => {
        setIsExecuting(true);
        try {
          const targetId = createdIncId || getTargetIncidentId();
          if (!targetId) throw new Error('No incident found. Please run Step 1 first.');
          await switchDemoUser('admin@malemitra.in');
          setActiveView('admin');
          setStepStatus('Authorizing road reopening...');
          await ApiClient.authorizeRestriction(targetId, 'authorize_reopen', 'Reopening confirmed. Road safe for standard vehicular traffic.');
          setCreatedIncId(targetId);
          await refreshData();
          setStepStatus('Road reopened! Full uninterrupted civic cycle complete.');
        } catch (err: any) {
          setStepStatus(`Error: ${err.message || 'Failed to authorize reopening'}`);
        } finally {
          setIsExecuting(false);
        }
      }
    }
  ];

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(15, 23, 42, 0.75)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 2000,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '780px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.2)',
        overflow: 'hidden',
        border: '1px solid #E2E8F0',
        maxHeight: '90vh',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Modal Header */}
        <div style={{
          backgroundColor: '#123047',
          color: '#FFFFFF',
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Sparkles size={20} color="#FBBF24" />
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>
                MaleMitra | E2E Judge Demonstration Guide
              </h2>
              <p style={{ fontSize: '12px', color: '#94A3B8', margin: 0 }}>
                Uninterrupted Civic Loop: Citizen → Admin → Responder → Graph Update → Rerouting → Ripple Impact → Reopening
              </p>
            </div>
          </div>
          <button
            onClick={() => setWalkthroughOpen(false)}
            style={{ backgroundColor: 'transparent', border: 'none', color: '#CBD5E1', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Step Progress Tracker */}
        <div style={{ display: 'flex', backgroundColor: '#F8FAFC', borderBottom: '1px solid #E2E8F0', overflowX: 'auto', padding: '10px 16px', gap: '8px' }}>
          {steps.map((st) => (
            <div
              key={st.num}
              onClick={() => setCurrentStep(st.num)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 10px',
                borderRadius: '6px',
                cursor: 'pointer',
                fontSize: '11px',
                fontWeight: currentStep === st.num ? 700 : 500,
                backgroundColor: currentStep === st.num ? '#0B8B95' : currentStep < st.num ? '#E2E8F0' : '#D1FAE5',
                color: currentStep === st.num ? '#FFFFFF' : currentStep < st.num ? '#475569' : '#065F46',
                whiteSpace: 'nowrap'
              }}
            >
              <span>{st.num}</span>
              <span>{st.role.split(' ')[0]}</span>
            </div>
          ))}
        </div>

        {/* Current Step Body */}
        <div style={{ padding: '24px', flex: 1, overflowY: 'auto' }}>
          {steps.map((st) => {
            if (st.num !== currentStep) return null;

            return (
              <div key={st.num}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                  <span style={{ fontSize: '12px', fontWeight: 700, color: '#0B8B95', backgroundColor: '#E6FFFA', padding: '2px 8px', borderRadius: '4px' }}>
                    STEP {st.num} OF 8: {st.role.toUpperCase()}
                  </span>
                </div>

                <h3 style={{ fontSize: '18px', fontWeight: 800, color: '#1E293B', marginBottom: '10px' }}>
                  {st.title}
                </h3>

                <p style={{ fontSize: '14px', color: '#475569', lineHeight: 1.6, marginBottom: '20px' }}>
                  {st.desc}
                </p>

                {stepStatus && (
                  <div style={{ padding: '10px 14px', backgroundColor: '#F0FDFA', border: '1px solid #CCFBF1', borderRadius: '8px', fontSize: '12px', color: '#0F766E', marginBottom: '20px' }}>
                    ⚡ {stepStatus}
                  </div>
                )}

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '16px', borderTop: '1px solid #E2E8F0' }}>
                  <button
                    onClick={() => setCurrentStep(Math.max(1, currentStep - 1))}
                    disabled={currentStep === 1}
                    style={{
                      padding: '8px 16px',
                      borderRadius: '6px',
                      border: '1px solid #CBD5E1',
                      backgroundColor: '#FFFFFF',
                      color: '#475569',
                      fontSize: '13px',
                      fontWeight: 600,
                      cursor: currentStep === 1 ? 'not-allowed' : 'pointer',
                      opacity: currentStep === 1 ? 0.5 : 1
                    }}
                  >
                    Previous Step
                  </button>

                  <button
                    onClick={st.execute}
                    disabled={isExecuting}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      padding: '10px 20px',
                      borderRadius: '6px',
                      border: 'none',
                      backgroundColor: '#0B8B95',
                      color: '#FFFFFF',
                      fontSize: '14px',
                      fontWeight: 700,
                      cursor: isExecuting ? 'not-allowed' : 'pointer',
                      boxShadow: '0 4px 6px -1px rgba(11, 139, 149, 0.4)'
                    }}
                  >
                    <Play size={16} />
                    {isExecuting ? 'Executing Workflow...' : st.actionLabel}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
