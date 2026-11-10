import React, { useState } from 'react';
import { useAuth, DEMO_ACCOUNTS } from '../context/AuthContext';
import { UserRole, RegisterFormData } from '../types';
import { 
  LogIn, UserPlus, X, ShieldAlert, Users, 
  Navigation, CheckCircle2, AlertCircle, Key, Lock, Mail, User, Phone, Building2 
} from 'lucide-react';

export const AuthModal: React.FC = () => {
  const { 
    authModalOpen, 
    authModalTab, 
    closeAuthModal, 
    openAuthModal, 
    login, 
    register, 
    switchUser 
  } = useAuth();

  // Login Form State
  const [loginEmail, setLoginEmail] = useState<string>('citizen@malemitra.in');
  const [loginPassword, setLoginPassword] = useState<string>('demo123');
  const [loginError, setLoginError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  // Register Form State
  const [regName, setRegName] = useState<string>('');
  const [regEmail, setRegEmail] = useState<string>('');
  const [regPassword, setRegPassword] = useState<string>('');
  const [regRole, setRegRole] = useState<UserRole>('citizen');
  const [regPhone, setRegPhone] = useState<string>('');
  const [regTeam, setRegTeam] = useState<string>('team-alpha');
  const [regDept, setRegDept] = useState<string>('BBMP Monsoon Control Room');
  const [regAdminCode, setRegAdminCode] = useState<string>('');
  const [regError, setRegError] = useState<string | null>(null);
  const [isRegistering, setIsRegistering] = useState<boolean>(false);

  if (!authModalOpen) return null;

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setIsLoggingIn(true);
    try {
      await login(loginEmail, loginPassword);
    } catch (err: any) {
      setLoginError(err.message || 'Login failed. Please check your credentials.');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);
    setIsRegistering(true);
    try {
      const data: RegisterFormData = {
        name: regName,
        email: regEmail,
        password: regPassword,
        role: regRole,
        phone: regPhone,
        team_id: regRole === 'responder' ? regTeam : undefined,
        department: regRole === 'admin' ? regDept : undefined,
        admin_code: regRole === 'admin' ? regAdminCode : undefined
      };
      await register(data);
    } catch (err: any) {
      setRegError(err.message || 'Registration failed.');
    } finally {
      setIsRegistering(false);
    }
  };

  const handleQuickDemoSelect = (accId: string) => {
    switchUser(accId);
    closeAuthModal();
  };

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
      zIndex: 2500,
      padding: '20px'
    }}>
      <div style={{
        backgroundColor: '#FFFFFF',
        borderRadius: '12px',
        width: '100%',
        maxWidth: '540px',
        boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.25)',
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
          <div>
            <h2 style={{ fontSize: '17px', fontWeight: 800, margin: 0 }}>
              MaleMitra Portal Access
            </h2>
            <p style={{ fontSize: '12px', color: '#94A3B8', margin: 0 }}>
              Login or Register as Citizen, Field Responder, or Control Room Administrator
            </p>
          </div>
          <button
            onClick={closeAuthModal}
            style={{ backgroundColor: 'transparent', border: 'none', color: '#CBD5E1', cursor: 'pointer' }}
          >
            <X size={20} />
          </button>
        </div>

        {/* Tab Switcher */}
        <div style={{ display: 'flex', borderBottom: '1px solid #E2E8F0', backgroundColor: '#F8FAFC' }}>
          <button
            onClick={() => openAuthModal('login')}
            style={{
              flex: 1,
              padding: '12px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              backgroundColor: authModalTab === 'login' ? '#FFFFFF' : 'transparent',
              color: authModalTab === 'login' ? '#0B8B95' : '#64748B',
              borderBottom: authModalTab === 'login' ? '2px solid #0B8B95' : 'none'
            }}
          >
            <LogIn size={15} />
            Sign In
          </button>

          <button
            onClick={() => openAuthModal('register')}
            style={{
              flex: 1,
              padding: '12px',
              border: 'none',
              cursor: 'pointer',
              fontWeight: 700,
              fontSize: '13px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              backgroundColor: authModalTab === 'register' ? '#FFFFFF' : 'transparent',
              color: authModalTab === 'register' ? '#0B8B95' : '#64748B',
              borderBottom: authModalTab === 'register' ? '2px solid #0B8B95' : 'none'
            }}
          >
            <UserPlus size={15} />
            New Account Registration
          </button>
        </div>

        {/* Modal Body */}
        <div style={{ padding: '24px', flex: 1, overflowY: 'auto' }}>
          
          {/* 1. LOGIN TAB */}
          {authModalTab === 'login' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Quick Demo Account Selector */}
              <div>
                <div style={{ fontSize: '11px', fontWeight: 700, color: '#64748B', textTransform: 'uppercase', marginBottom: '8px' }}>
                  ⚡ Quick Demo One-Click Login:
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                  {DEMO_ACCOUNTS.map((acc) => (
                    <button
                      key={acc.id}
                      onClick={() => handleQuickDemoSelect(acc.id)}
                      style={{
                        padding: '8px 10px',
                        borderRadius: '6px',
                        border: '1px solid #E2E8F0',
                        backgroundColor: '#F8FAFC',
                        cursor: 'pointer',
                        textAlign: 'left',
                        fontSize: '11px',
                        transition: 'background-color 0.1s'
                      }}
                    >
                      <div style={{ fontWeight: 700, color: '#1E293B' }}>{acc.name.split(' ')[0]} {acc.name.split(' ')[1] || ''}</div>
                      <div style={{ color: '#0B8B95', textTransform: 'uppercase', fontSize: '10px', fontWeight: 600 }}>
                        {acc.role}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ textAlign: 'center', position: 'relative', margin: '4px 0' }}>
                <span style={{ backgroundColor: '#FFF', padding: '0 8px', fontSize: '11px', color: '#94A3B8', position: 'relative', zIndex: 1 }}>
                  OR SIGN IN WITH CREDENTIALS
                </span>
                <div style={{ position: 'absolute', top: '50%', left: 0, right: 0, borderTop: '1px solid #E2E8F0' }} />
              </div>

              {loginError && (
                <div style={{ padding: '10px 12px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '6px', fontSize: '12px', color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertCircle size={15} />
                  <span>{loginError}</span>
                </div>
              )}

              <form onSubmit={handleLoginSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>
                    Email Address
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      type="email"
                      value={loginEmail}
                      onChange={(e) => setLoginEmail(e.target.value)}
                      placeholder="citizen@malemitra.in"
                      style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px' }}
                      required
                    />
                  </div>
                </div>

                <div>
                  <label style={{ fontSize: '12px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '3px' }}>
                    Password
                  </label>
                  <input
                    type="password"
                    value={loginPassword}
                    onChange={(e) => setLoginPassword(e.target.value)}
                    placeholder="••••••••"
                    style={{ width: '100%', padding: '8px 10px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '13px' }}
                    required
                  />
                </div>

                <button
                  type="submit"
                  disabled={isLoggingIn}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '10px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: '#0B8B95',
                    color: '#FFFFFF',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: isLoggingIn ? 'not-allowed' : 'pointer',
                    marginTop: '4px',
                    boxShadow: '0 2px 4px rgba(11, 139, 149, 0.3)'
                  }}
                >
                  <LogIn size={15} />
                  {isLoggingIn ? 'Signing In...' : 'Sign In to Workspace'}
                </button>
              </form>
            </div>
          )}

          {/* 2. REGISTER TAB */}
          {authModalTab === 'register' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              
              {/* Role Selection */}
              <div>
                <label style={{ fontSize: '12px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '6px' }}>
                  Register Account Role:
                </label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                  {[
                    { role: 'citizen' as UserRole, label: 'Citizen Commuter', icon: Navigation },
                    { role: 'responder' as UserRole, label: 'Field Responder', icon: Users },
                    { role: 'admin' as UserRole, label: 'Control Admin', icon: ShieldAlert }
                  ].map((r) => {
                    const IconComp = r.icon;
                    const isSelected = regRole === r.role;
                    return (
                      <button
                        key={r.role}
                        type="button"
                        onClick={() => setRegRole(r.role)}
                        style={{
                          padding: '10px 6px',
                          borderRadius: '6px',
                          border: `1.5px solid ${isSelected ? '#0B8B95' : '#E2E8F0'}`,
                          backgroundColor: isSelected ? '#F0FDFA' : '#FAFAFA',
                          cursor: 'pointer',
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'center',
                          gap: '4px',
                          fontSize: '11px',
                          fontWeight: isSelected ? 700 : 500,
                          color: isSelected ? '#0F766E' : '#475569'
                        }}
                      >
                        <IconComp size={16} color={isSelected ? '#0B8B95' : '#64748B'} />
                        <span>{r.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {regError && (
                <div style={{ padding: '10px 12px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '6px', fontSize: '12px', color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <AlertCircle size={15} />
                  <span>{regError}</span>
                </div>
              )}

              <form onSubmit={handleRegisterSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                    Full Name
                  </label>
                  <input
                    type="text"
                    value={regName}
                    onChange={(e) => setRegName(e.target.value)}
                    placeholder={regRole === 'responder' ? 'Inspector S. Gowda' : regRole === 'admin' ? 'Officer Anand' : 'Pooja Sharma'}
                    style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                    required
                  />
                </div>

                <div>
                  <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={regEmail}
                    onChange={(e) => setRegEmail(e.target.value)}
                    placeholder="user@malemitra.in"
                    style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                    required
                  />
                </div>

                <div>
                  <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                    Password
                  </label>
                  <input
                    type="password"
                    value={regPassword}
                    onChange={(e) => setRegPassword(e.target.value)}
                    placeholder="••••••••"
                    style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                    required
                  />
                </div>

                {/* Role Specific Fields */}
                {regRole === 'citizen' && (
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                      Contact Phone (Optional)
                    </label>
                    <input
                      type="tel"
                      value={regPhone}
                      onChange={(e) => setRegPhone(e.target.value)}
                      placeholder="+91 98765 43210"
                      style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                    />
                  </div>
                )}

                {regRole === 'responder' && (
                  <div>
                    <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                      Assigned Emergency Response Unit
                    </label>
                    <select
                      value={regTeam}
                      onChange={(e) => setRegTeam(e.target.value)}
                      style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px', fontWeight: 600 }}
                    >
                      <option value="team-alpha">Team Alpha - Stormwater Response (Dewatering Pumps)</option>
                      <option value="team-beta">Team Beta - Traffic &amp; Debris Unit</option>
                      <option value="team-gamma">Team Gamma - Quick Drainage &amp; Silt Unit</option>
                    </select>
                  </div>
                )}

                {regRole === 'admin' && (
                  <>
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '2px' }}>
                        Municipal Department
                      </label>
                      <input
                        type="text"
                        value={regDept}
                        onChange={(e) => setRegDept(e.target.value)}
                        placeholder="BBMP Monsoon Control Room"
                        style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #CBD5E1', fontSize: '12px' }}
                      />
                    </div>
                    <div>
                      <label style={{ fontSize: '11px', fontWeight: 700, color: '#B91C1C', display: 'block', marginBottom: '2px' }}>
                        Admin Verification Passcode (Enter 'bbmp2026')
                      </label>
                      <input
                        type="password"
                        value={regAdminCode}
                        onChange={(e) => setRegAdminCode(e.target.value)}
                        placeholder="bbmp2026"
                        style={{ width: '100%', padding: '7px 9px', borderRadius: '6px', border: '1px solid #FCA5A5', fontSize: '12px' }}
                        required
                      />
                    </div>
                  </>
                )}

                <button
                  type="submit"
                  disabled={isRegistering}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px',
                    padding: '10px',
                    borderRadius: '6px',
                    border: 'none',
                    backgroundColor: '#0B8B95',
                    color: '#FFFFFF',
                    fontWeight: 700,
                    fontSize: '13px',
                    cursor: isRegistering ? 'not-allowed' : 'pointer',
                    marginTop: '6px',
                    boxShadow: '0 2px 4px rgba(11, 139, 149, 0.3)'
                  }}
                >
                  <UserPlus size={15} />
                  {isRegistering ? 'Registering Account...' : `Register as ${regRole.toUpperCase()}`}
                </button>
              </form>
            </div>
          )}

        </div>
      </div>
    </div>
  );
};
