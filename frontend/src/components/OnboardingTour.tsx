import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { X, ChevronRight, ChevronLeft, Sparkles } from 'lucide-react';

interface TourStep {
  title: string;
  description: string;
  highlight?: string; // feature area name shown as a badge
  emoji: string;
}

const CITIZEN_STEPS: TourStep[] = [
  {
    emoji: '👋',
    title: 'Welcome to MaleMitra!',
    description: 'Your personal monsoon mobility companion for Bengaluru. This quick tour shows you how to use the app. You can skip at any time.',
    highlight: 'Getting Started',
  },
  {
    emoji: '📍',
    title: 'Report Waterlogging & Road Hazards',
    description: 'Spot flooding or a blocked road? Tap the map or use the Report button to geolocate and submit a hazard. Add severity, type, and notes.',
    highlight: 'Citizen Workspace',
  },
  {
    emoji: '🗺️',
    title: 'Get Safe Route Recommendations',
    description: 'Enter your origin and destination in the Route Planner. The system gives you a risk-aware alternative route that avoids blocked segments.',
    highlight: 'Route Planner',
  },
  {
    emoji: '⚡',
    title: 'Ripple Engine — See the City-Wide Impact',
    description: 'Open the Ripple Engine tab to see how a single flooded road cascades into traffic congestion across 150 simulated trips.',
    highlight: 'Ripple Engine Tab',
  },
  {
    emoji: '📊',
    title: 'Benchmark Results',
    description: 'The Benchmark tab shows hard numbers: 100% reduction in blocked-segment traversal and only a 3.9% time penalty for safe detours.',
    highlight: 'Benchmark Tab',
  },
];

const ADMIN_STEPS: TourStep[] = [
  {
    emoji: '👋',
    title: 'Welcome, Control Room Admin!',
    description: 'You manage the full incident lifecycle — from triage to field dispatch to road restriction authorisation.',
    highlight: 'Getting Started',
  },
  {
    emoji: '🔍',
    title: 'Review Incoming Reports',
    description: 'All citizen-submitted hazards appear in your queue with AI-generated confidence scores and road-edge mappings. Review and validate priority.',
    highlight: 'Triage Queue',
  },
  {
    emoji: '🚒',
    title: 'Dispatch Field Teams',
    description: 'Assign incidents to Team Alpha, Beta, or Gamma directly from the incident card. Teams receive the GPS-located task.',
    highlight: 'Team Dispatch',
  },
  {
    emoji: '🚧',
    title: 'Authorize Road Restrictions',
    description: "Once a responder verifies an impassable road, you'll see an \"Authorize Blockage\" action. This updates the live routing graph for all citizens.",
    highlight: 'Road Restrictions',
  },
  {
    emoji: '✅',
    title: 'Reopen Roads After Clearance',
    description: 'When field teams complete pumping, they propose clearance. You review the evidence and authorize reopening — closing the civic loop.',
    highlight: 'Road Reopening',
  },
];

const RESPONDER_STEPS: TourStep[] = [
  {
    emoji: '👋',
    title: 'Welcome, Field Responder!',
    description: 'You handle on-site inspections and water clearance operations. Your findings directly influence road routing for all Bengaluru commuters.',
    highlight: 'Getting Started',
  },
  {
    emoji: '📋',
    title: 'Your Assigned Tasks',
    description: 'The Field Tasks view shows incidents dispatched to your team. Each card has location, type, and severity from the citizen report.',
    highlight: 'Task List',
  },
  {
    emoji: '🔬',
    title: 'Submit On-Site Verification',
    description: 'After reaching the site, record water depth, whether the road is impassable, and your recommended action (closure / monitor / clear).',
    highlight: 'Field Verification',
  },
  {
    emoji: '🔧',
    title: 'Propose Clearance After Work',
    description: 'Once pumping is complete and water recedes below safe levels, submit a clearance proposal with evidence. The admin will authorize reopening.',
    highlight: 'Clearance Proposal',
  },
  {
    emoji: '⚡',
    title: 'See the Ripple Engine',
    description: 'Curious how your closure impacted traffic? Open the Ripple Engine tab to see cascading trip reassignments across the city.',
    highlight: 'Ripple Engine Tab',
  },
];

function getSteps(role: string | null): TourStep[] {
  if (role === 'admin') return ADMIN_STEPS;
  if (role === 'responder') return RESPONDER_STEPS;
  return CITIZEN_STEPS;
}

const LS_KEY = 'malemitra_tour_seen';
const LS_FIRST = 'malemitra_firstlogin';

export const OnboardingTour: React.FC = () => {
  const { currentUser, activeRole } = useAuth();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!currentUser) return;
    // Show tour for first-time registrations OR if they haven't seen it for this role
    const seenKey = `${LS_KEY}_${currentUser.id}`;
    const isFirst = localStorage.getItem(LS_FIRST) === '1';
    const hasSeen = localStorage.getItem(seenKey) === '1';
    if (isFirst || !hasSeen) {
      // Short delay so the main workspace loads first
      const t = setTimeout(() => { setOpen(true); setStep(0); }, 800);
      return () => clearTimeout(t);
    }
  }, [currentUser?.id]);

  const dismiss = () => {
    if (currentUser) {
      localStorage.setItem(`${LS_KEY}_${currentUser.id}`, '1');
      localStorage.removeItem(LS_FIRST);
    }
    setOpen(false);
  };

  if (!open || !currentUser) return null;

  const steps = getSteps(activeRole);
  const current = steps[step];
  const isLast = step === steps.length - 1;
  const isFirst = step === 0;

  const progressColor = activeRole === 'admin' ? '#C78420' : activeRole === 'responder' ? '#3576B8' : '#0B8B95';

  return (
    <div style={{
      position: 'fixed', inset: 0,
      backgroundColor: 'rgba(15,23,42,0.65)',
      backdropFilter: 'blur(3px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 3000, padding: '20px',
    }}>
      <div style={{
        backgroundColor: '#FFFFFF', borderRadius: '16px',
        width: '100%', maxWidth: '440px',
        boxShadow: '0 24px 48px -12px rgba(0,0,0,0.5)',
        overflow: 'hidden',
        border: `2px solid ${progressColor}33`,
      }}>
        {/* Progress bar */}
        <div style={{ height: '4px', backgroundColor: '#F1F5F9' }}>
          <div style={{
            height: '100%', borderRadius: '2px',
            backgroundColor: progressColor,
            width: `${((step + 1) / steps.length) * 100}%`,
            transition: 'width 0.3s ease',
          }} />
        </div>

        {/* Header */}
        <div style={{ padding: '16px 20px 0', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{
            fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
            color: progressColor, backgroundColor: `${progressColor}18`,
            padding: '3px 8px', borderRadius: '4px',
            display: 'flex', alignItems: 'center', gap: '4px',
          }}>
            <Sparkles size={10} />
            {current.highlight}
          </div>
          <button onClick={dismiss} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94A3B8', padding: '2px' }}>
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '20px 24px 24px', textAlign: 'center' }}>
          <div style={{ fontSize: '48px', marginBottom: '16px', lineHeight: 1 }}>
            {current.emoji}
          </div>
          <h2 style={{ fontSize: '18px', fontWeight: 800, color: '#1E293B', margin: '0 0 10px', lineHeight: 1.3 }}>
            {current.title}
          </h2>
          <p style={{ fontSize: '13px', color: '#64748B', lineHeight: 1.65, margin: '0 0 28px' }}>
            {current.description}
          </p>

          {/* Step indicator */}
          <div style={{ display: 'flex', justifyContent: 'center', gap: '6px', marginBottom: '20px' }}>
            {steps.map((_, i) => (
              <div key={i} style={{
                width: i === step ? '20px' : '7px', height: '7px', borderRadius: '4px',
                backgroundColor: i === step ? progressColor : '#E2E8F0',
                transition: 'all 0.25s ease',
              }} />
            ))}
          </div>

          {/* Buttons */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            {!isFirst && (
              <button onClick={() => setStep(s => s - 1)} style={{
                padding: '9px 16px', borderRadius: '8px',
                border: '1px solid #E2E8F0', backgroundColor: '#F8FAFC',
                color: '#475569', fontWeight: 600, fontSize: '13px',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '4px',
              }}>
                <ChevronLeft size={14} /> Back
              </button>
            )}

            <button
              onClick={isLast ? dismiss : () => setStep(s => s + 1)}
              style={{
                flex: 1, padding: '10px', borderRadius: '8px', border: 'none',
                backgroundColor: progressColor, color: '#FFF',
                fontWeight: 700, fontSize: '13px', cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                boxShadow: `0 2px 6px ${progressColor}44`,
              }}
            >
              {isLast ? '✓ Got it, let\'s go!' : <>Next <ChevronRight size={14} /></>}
            </button>
          </div>

          {!isLast && (
            <button onClick={dismiss} style={{
              marginTop: '12px', background: 'none', border: 'none',
              color: '#94A3B8', fontSize: '11px', cursor: 'pointer',
            }}>
              Skip tour
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
