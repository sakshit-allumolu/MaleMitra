import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useIncidents } from '../context/IncidentContext';
import {
  CloudRain, ShieldAlert, Navigation,
  BarChart3, Users, Activity, Sparkles,
  LogOut, ChevronDown, User
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { currentUser, activeRole, logout } = useAuth();
  const { graphVersion, activeView, setActiveView, setWalkthroughOpen } = useIncidents();
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  const roleLabel = activeRole === 'admin'
    ? 'Control Room Admin'
    : activeRole === 'responder'
      ? 'Field Responder'
      : 'Citizen Commuter';

  const roleColor = activeRole === 'admin'
    ? '#C78420'
    : activeRole === 'responder'
      ? '#3576B8'
      : '#0B8B95';

  // Nav items: each role sees only its own workspace + Ripple Engine + Benchmark
  const navItems = [
    ...(activeRole === 'citizen'
      ? [{ id: 'citizen', label: 'My Workspace', Icon: Navigation }]
      : []),
    ...(activeRole === 'admin'
      ? [{ id: 'admin', label: 'Control Room', Icon: ShieldAlert }]
      : []),
    ...(activeRole === 'responder'
      ? [{ id: 'responder', label: 'Field Tasks', Icon: Users }]
      : []),
    { id: 'ripple', label: 'Ripple Engine', Icon: Activity },
    { id: 'evaluation', label: 'Benchmark', Icon: BarChart3 },
  ] as { id: 'citizen' | 'admin' | 'responder' | 'ripple' | 'evaluation'; label: string; Icon: React.ElementType }[];

  return (
    <header style={{
      backgroundColor: '#123047',
      color: '#FFFFFF',
      borderBottom: '2px solid #0B8B95',
      boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
      position: 'sticky',
      top: 0,
      zIndex: 1000,
    }}>
      <div style={{
        maxWidth: '1440px',
        margin: '0 auto',
        padding: '12px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexWrap: 'wrap',
        gap: '12px',
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '40px', height: '40px', borderRadius: '10px',
            backgroundColor: '#0B8B95', display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 2px 4px rgba(11,139,149,0.4)',
          }}>
            <CloudRain size={24} color="#FFFFFF" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '18px', fontWeight: 800, letterSpacing: '-0.02em', margin: 0 }}>
                MaleMitra <span style={{ fontWeight: 400, opacity: 0.9 }}>| ಮಳೆ ಮಿತ್ರ</span>
              </h1>
            </div>
            <p style={{ fontSize: '12px', color: '#94A3B8', margin: 0 }}>
              Connected Monsoon Mobility & Civic Ripple Response Platform · Bengaluru
            </p>
          </div>
        </div>

        {/* Nav Tabs — only role-permitted views */}
        <nav style={{
          display: 'flex', alignItems: 'center', gap: '4px',
          backgroundColor: 'rgba(255,255,255,0.08)', padding: '4px', borderRadius: '8px',
        }}>
          {navItems.map(({ id, label, Icon }) => (
            <button
              key={id}
              onClick={() => setActiveView(id)}
              style={{
                display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 14px', borderRadius: '6px', border: 'none',
                cursor: 'pointer', fontWeight: 600, fontSize: '13px',
                backgroundColor: activeView === id ? '#0B8B95' : 'transparent',
                color: activeView === id ? '#FFFFFF' : '#CBD5E1',
                transition: 'all 0.15s ease',
              }}
            >
              <Icon size={15} />
              {label}
            </button>
          ))}
        </nav>

        {/* Right Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {/* Demo Walkthrough */}
          <button
            onClick={() => setWalkthroughOpen(true)}
            style={{
              display: 'flex', alignItems: 'center', gap: '6px',
              padding: '6px 12px', borderRadius: '6px',
              backgroundColor: '#C78420', color: '#FFFFFF',
              border: 'none', fontWeight: 700, fontSize: '12px', cursor: 'pointer',
              boxShadow: '0 2px 4px rgba(199,132,32,0.4)',
            }}
            title="Launch step-by-step demo guide"
          >
            <Sparkles size={14} />
            Demo Guide
          </button>

          {/* Graph Version Badge */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: '6px',
            backgroundColor: 'rgba(255,255,255,0.12)', padding: '4px 10px',
            borderRadius: '6px', fontSize: '12px', fontFamily: 'monospace',
          }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: '#10B981', display: 'inline-block' }} />
            Graph v{graphVersion}
          </div>

          {/* User Menu */}
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setUserMenuOpen(o => !o)}
              style={{
                display: 'flex', alignItems: 'center', gap: '8px',
                padding: '6px 12px', borderRadius: '8px',
                backgroundColor: 'rgba(255,255,255,0.1)',
                border: `1px solid ${roleColor}55`,
                color: '#FFFFFF', cursor: 'pointer', fontSize: '12px', fontWeight: 600,
              }}
            >
              <div style={{
                width: '26px', height: '26px', borderRadius: '50%',
                backgroundColor: roleColor, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <User size={14} color="#FFF" />
              </div>
              <div style={{ textAlign: 'left', lineHeight: 1.3 }}>
                <div style={{ fontSize: '12px', fontWeight: 700 }}>
                  {currentUser?.name?.split(' ')[0]}
                </div>
                <div style={{ fontSize: '10px', color: roleColor, fontWeight: 600, textTransform: 'uppercase' }}>
                  {roleLabel}
                </div>
              </div>
              <ChevronDown size={13} color="#94A3B8" />
            </button>

            {userMenuOpen && (
              <>
                {/* Backdrop */}
                <div
                  onClick={() => setUserMenuOpen(false)}
                  style={{ position: 'fixed', inset: 0, zIndex: 999 }}
                />
                {/* Dropdown */}
                <div style={{
                  position: 'absolute', right: 0, top: 'calc(100% + 6px)',
                  backgroundColor: '#1E293B', borderRadius: '8px',
                  border: '1px solid #334155', boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
                  minWidth: '220px', zIndex: 1000, overflow: 'hidden',
                }}>
                  {/* User info */}
                  <div style={{ padding: '12px 14px', borderBottom: '1px solid #334155' }}>
                    <div style={{ fontSize: '13px', fontWeight: 700, color: '#F1F5F9' }}>
                      {currentUser?.name}
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748B', marginTop: '2px' }}>
                      {currentUser?.email}
                    </div>
                    <div style={{
                      display: 'inline-block', marginTop: '6px',
                      fontSize: '10px', fontWeight: 700, textTransform: 'uppercase',
                      backgroundColor: `${roleColor}22`, color: roleColor,
                      padding: '2px 8px', borderRadius: '4px',
                    }}>
                      {roleLabel}
                    </div>
                  </div>

                  {/* Logout */}
                  <button
                    onClick={() => { logout(); setUserMenuOpen(false); }}
                    style={{
                      width: '100%', padding: '11px 14px', border: 'none',
                      backgroundColor: 'transparent', color: '#F87171',
                      cursor: 'pointer', textAlign: 'left', fontSize: '13px',
                      fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px',
                    }}
                  >
                    <LogOut size={14} />
                    Sign Out
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};
