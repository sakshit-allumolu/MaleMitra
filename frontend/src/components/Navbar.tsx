import React from 'react';
import { useAuth, DEMO_ACCOUNTS } from '../context/AuthContext';
import { useIncidents } from '../context/IncidentContext';
import {
  CloudRain, ShieldAlert, Navigation, BarChart3,
  Users, Activity, CheckCircle, Sparkles, BookOpen, LogIn, UserPlus, LogOut
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { currentUser, switchUser, activeRole, setActiveRole, openAuthModal, logout } = useAuth();
  const { graphVersion, activeView, setActiveView, setWalkthroughOpen } = useIncidents();

  return (
    <header style={{
      backgroundColor: '#123047',
      color: '#FFFFFF',
      borderBottom: '2px solid #0B8B95',
      boxShadow: '0 2px 8px rgba(0, 0, 0, 0.15)',
      position: 'sticky',
      top: 0,
      zIndex: 1000
    }}>
      <div style={{
        maxWidth: '1440px',
        margin: '0 auto',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px'
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            backgroundColor: '#0B8B95',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 4px rgba(11, 139, 149, 0.4)'
          }}>
            <CloudRain size={24} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '18px', fontWeight: 800, letterSpacing: '-0.02em', margin: 0 }}>
                MaleMitra <span style={{ fontWeight: 400, opacity: 0.9 }}>| ಮಳೆ ಮಿತ್ರ</span>
              </h1>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                textTransform: 'uppercase',
                backgroundColor: 'rgba(11, 139, 149, 0.3)',
                color: '#6EE7B7',
                padding: '2px 6px',
                borderRadius: '4px',
                border: '1px solid rgba(110, 231, 183, 0.4)'
              }}>
                IBM Bobathon 2026
              </span>
            </div>
            <p style={{ fontSize: '12px', color: '#94A3B8', margin: 0 }}>
              Connected Monsoon Mobility & Civic Ripple Response Platform • Bengaluru
            </p>
          </div>
        </div>

        {/* Workspace Nav Tabs */}
        <nav style={{ display: 'flex', alignItems: 'center', gap: '6px', backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '4px', borderRadius: '8px' }}>
          <button
            onClick={() => { setActiveView('citizen'); setActiveRole('citizen'); }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeView === 'citizen' ? '#0B8B95' : 'transparent',
              color: activeView === 'citizen' ? '#FFFFFF' : '#CBD5E1',
              transition: 'all 0.15s ease'
            }}
          >
            <Navigation size={15} />
            Citizen
          </button>

          <button
            onClick={() => { setActiveView('admin'); setActiveRole('admin'); }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeView === 'admin' ? '#0B8B95' : 'transparent',
              color: activeView === 'admin' ? '#FFFFFF' : '#CBD5E1',
              transition: 'all 0.15s ease'
            }}
          >
            <ShieldAlert size={15} />
            Administrator
          </button>

          <button
            onClick={() => { setActiveView('responder'); setActiveRole('responder'); }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeView === 'responder' ? '#0B8B95' : 'transparent',
              color: activeView === 'responder' ? '#FFFFFF' : '#CBD5E1',
              transition: 'all 0.15s ease'
            }}
          >
            <Users size={15} />
            Field Responder
          </button>

          <button
            onClick={() => setActiveView('ripple')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeView === 'ripple' ? '#0B8B95' : 'transparent',
              color: activeView === 'ripple' ? '#FFFFFF' : '#CBD5E1',
              transition: 'all 0.15s ease'
            }}
          >
            <Activity size={15} />
            Ripple Engine
          </button>

          <button
            onClick={() => setActiveView('evaluation')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: '6px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 600,
              fontSize: '13px',
              backgroundColor: activeView === 'evaluation' ? '#0B8B95' : 'transparent',
              color: activeView === 'evaluation' ? '#FFFFFF' : '#CBD5E1',
              transition: 'all 0.15s ease'
            }}
          >
            <BarChart3 size={15} />
            Benchmark
          </button>
        </nav>

        {/* Right Controls: Demo Walkthrough + Graph Version + User Switcher */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Demo Walkthrough Button */}
          <button
            onClick={() => setWalkthroughOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              borderRadius: '6px',
              backgroundColor: '#C78420',
              color: '#FFFFFF',
              border: 'none',
              fontWeight: 700,
              fontSize: '12px',
              cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(199, 132, 32, 0.4)'
            }}
            title="Launch step-by-step judge demonstration guide"
          >
            <Sparkles size={14} />
            Demo Walkthrough
          </button>

          {/* Graph Version Badge */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'rgba(255, 255, 255, 0.12)',
            padding: '4px 10px',
            borderRadius: '6px',
            fontSize: '12px',
            fontFamily: 'monospace'
          }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10B981' }} />
            <span>Graph v{graphVersion}</span>
          </div>

          {/* Auth Login/Register Modal Launcher */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <button
              onClick={() => openAuthModal('login')}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '6px 10px',
                borderRadius: '6px',
                border: '1px solid #0B8B95',
                backgroundColor: '#1E293B',
                color: '#E2E8F0',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer'
              }}
              title="Sign in with email or register new role account"
            >
              <LogIn size={13} color="#0B8B95" />
              <span>Sign In / Register</span>
            </button>

            {/* Demo User Switcher */}
            <select
              value={currentUser.id}
              onChange={(e) => switchUser(e.target.value)}
              style={{
                backgroundColor: '#1E293B',
                color: '#FFFFFF',
                border: '1px solid #475569',
                borderRadius: '6px',
                padding: '6px 10px',
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
                outline: 'none'
              }}
              title="Quick demo user switcher"
            >
              {DEMO_ACCOUNTS.map((acc) => (
                <option key={acc.id} value={acc.id}>
                  👤 {acc.name.split(' ')[0]} ({acc.role.toUpperCase()})
                </option>
              ))}
              {!DEMO_ACCOUNTS.some(a => a.id === currentUser.id) && (
                <option value={currentUser.id}>
                  👤 {currentUser.name} ({currentUser.role.toUpperCase()})
                </option>
              )}
            </select>
          </div>
        </div>
      </div>
    </header>
  );
};
