import React, { useState, useCallback } from 'react';
import { useAuth } from '../context/AuthContext';
import { UserRole, RegisterFormData } from '../types';
import { ApiClient } from '../services/api';
import {
  CloudRain, LogIn, UserPlus, AlertCircle, Eye, EyeOff,
  Navigation, Users, ShieldAlert, CheckCircle2, KeyRound, ArrowLeft, Send
} from 'lucide-react';

// ── Password policy ────────────────────────────────────────────────────────────
export interface PasswordStrength {
  score: number; // 0-5
  label: string;
  color: string;
  checks: { label: string; passed: boolean }[];
}

export function evaluatePassword(pw: string): PasswordStrength {
  const checks = [
    { label: 'At least 8 characters', passed: pw.length >= 8 },
    { label: 'Uppercase letter (A–Z)', passed: /[A-Z]/.test(pw) },
    { label: 'Lowercase letter (a–z)', passed: /[a-z]/.test(pw) },
    { label: 'Number (0–9)', passed: /\d/.test(pw) },
    { label: 'Special character (!@#$…)', passed: /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>/?`~]/.test(pw) },
  ];
  const score = checks.filter(c => c.passed).length;
  const labels = ['', 'Weak', 'Weak', 'Fair', 'Good', 'Strong'];
  const colors = ['#E2E8F0', '#EF4444', '#F97316', '#EAB308', '#22C55E', '#0B8B95'];
  return { score, label: pw ? labels[score] : '', color: colors[score], checks };
}

function PasswordStrengthMeter({ password }: { password: string }) {
  const str = evaluatePassword(password);
  if (!password) return null;
  return (
    <div style={{ marginTop: '6px' }}>
      {/* Bar */}
      <div style={{ display: 'flex', gap: '3px', marginBottom: '4px' }}>
        {[1, 2, 3, 4, 5].map(i => (
          <div key={i} style={{
            flex: 1, height: '4px', borderRadius: '2px',
            backgroundColor: i <= str.score ? str.color : '#E2E8F0',
            transition: 'background-color 0.2s',
          }} />
        ))}
      </div>
      {/* Label */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
        <span style={{ fontSize: '11px', color: str.color, fontWeight: 700 }}>{str.label}</span>
      </div>
      {/* Checklist */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px 8px' }}>
        {str.checks.map(c => (
          <div key={c.label} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '10px', color: c.passed ? '#16A34A' : '#94A3B8' }}>
            <CheckCircle2 size={10} color={c.passed ? '#16A34A' : '#CBD5E1'} />
            {c.label}
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────────────
type Tab = 'login' | 'register' | 'forgot' | 'reset';

export const LoginPage: React.FC = () => {
  const { login, register } = useAuth();
  const [tab, setTab] = useState<Tab>('login');

  // ── Login ──
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [loginShowPwd, setLoginShowPwd] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [loginLoading, setLoginLoading] = useState(false);

  // ── Register ──
  const [regName, setRegName] = useState('');
  const [regEmail, setRegEmail] = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regConfirm, setRegConfirm] = useState('');
  const [regShowPwd, setRegShowPwd] = useState(false);
  const [regRole, setRegRole] = useState<UserRole>('citizen');
  const [regPhone, setRegPhone] = useState('');
  const [regTeam, setRegTeam] = useState('team-alpha');
  const [regDept, setRegDept] = useState('BBMP Monsoon Control Room');
  const [regAdminCode, setRegAdminCode] = useState('');
  const [regError, setRegError] = useState<string | null>(null);
  const [regLoading, setRegLoading] = useState(false);

  // ── Forgot Password ──
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotError, setForgotError] = useState<string | null>(null);
  const [forgotToken, setForgotToken] = useState<string | null>(null); // demo: returned directly

  // ── Reset Password ──
  const [resetToken, setResetToken] = useState('');
  const [resetPwd, setResetPwd] = useState('');
  const [resetConfirm, setResetConfirm] = useState('');
  const [resetShowPwd, setResetShowPwd] = useState(false);
  const [resetLoading, setResetLoading] = useState(false);
  const [resetError, setResetError] = useState<string | null>(null);
  const [resetSuccess, setResetSuccess] = useState(false);

  const pwStrength = evaluatePassword(regPassword);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoginError(null);
    setLoginLoading(true);
    try {
      await login(loginEmail.trim(), loginPassword);
    } catch (err: any) {
      setLoginError(err.message || 'Invalid email or password.');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setRegError(null);

    if (regPassword !== regConfirm) {
      setRegError('Passwords do not match.');
      return;
    }
    if (pwStrength.score < 5) {
      setRegError('Password does not meet all requirements. Check the checklist above.');
      return;
    }

    setRegLoading(true);
    try {
      const data: RegisterFormData = {
        name: regName,
        email: regEmail,
        password: regPassword,
        role: regRole,
        phone: regPhone || undefined,
        team_id: regRole === 'responder' ? regTeam : undefined,
        department: regRole === 'admin' ? regDept : undefined,
        admin_code: regRole === 'admin' ? regAdminCode : undefined,
      };
      await register(data);
      // Mark first-login so onboarding tour fires
      localStorage.setItem('malemitra_firstlogin', '1');
    } catch (err: any) {
      setRegError(err.message || 'Registration failed.');
    } finally {
      setRegLoading(false);
    }
  };

  const handleForgot = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotError(null);
    setForgotLoading(true);
    try {
      const res = await ApiClient.forgotPassword(forgotEmail.trim());
      setForgotToken(res.debug_token);
      if (res.debug_token) {
        setResetToken(res.debug_token);
        setTab('reset');
      }
    } catch (err: any) {
      setForgotError(err.message || 'Request failed.');
    } finally {
      setForgotLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetError(null);
    if (resetPwd !== resetConfirm) {
      setResetError('Passwords do not match.');
      return;
    }
    const str = evaluatePassword(resetPwd);
    if (str.score < 5) {
      setResetError('Password does not meet all requirements.');
      return;
    }
    setResetLoading(true);
    try {
      await ApiClient.resetPassword(resetToken, resetPwd);
      setResetSuccess(true);
    } catch (err: any) {
      setResetError(err.message || 'Reset failed.');
    } finally {
      setResetLoading(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: '100%', padding: '9px 11px', borderRadius: '6px',
    border: '1px solid #CBD5E1', fontSize: '13px', outline: 'none',
    boxSizing: 'border-box', color: '#1E293B',
  };
  const labelStyle: React.CSSProperties = {
    fontSize: '12px', fontWeight: 700, color: '#475569', display: 'block', marginBottom: '4px',
  };
  const errBox = (msg: string) => (
    <div style={{ padding: '10px 12px', backgroundColor: '#FEF2F2', border: '1px solid #FCA5A5', borderRadius: '6px', fontSize: '12px', color: '#B91C1C', display: 'flex', alignItems: 'center', gap: '6px' }}>
      <AlertCircle size={14} />{msg}
    </div>
  );
  const pwField = (
    val: string, onChange: (v: string) => void, show: boolean, toggle: () => void,
    withMeter = false, placeholder = '••••••••', style?: React.CSSProperties
  ) => (
    <div style={{ position: 'relative' }}>
      <input type={show ? 'text' : 'password'} value={val} onChange={e => onChange(e.target.value)}
        placeholder={placeholder} style={{ ...inputStyle, paddingRight: '36px', ...style }} required />
      <button type="button" onClick={toggle}
        style={{ position: 'absolute', right: '10px', top: '10px', background: 'none', border: 'none', cursor: 'pointer', color: '#64748B' }}>
        {show ? <EyeOff size={15} /> : <Eye size={15} />}
      </button>
      {withMeter && <PasswordStrengthMeter password={val} />}
    </div>
  );

  const DEMO_LOGINS = [
    { email: 'citizen@malemitra.in', label: 'Citizen (Pooja)', role: 'Citizen' },
    { email: 'admin@malemitra.in', label: 'Control Room Admin', role: 'Admin' },
    { email: 'responder1@malemitra.in', label: 'Inspector Ramesh', role: 'Responder' },
    { email: 'responder2@malemitra.in', label: 'Officer Kavitha', role: 'Responder' },
  ];

  const isMainTab = tab === 'login' || tab === 'register';

  return (
    <div style={{
      minHeight: '100vh', backgroundColor: '#0F1E2E',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      padding: '24px',
      backgroundImage: 'radial-gradient(ellipse at top left, rgba(11,139,149,0.15) 0%, transparent 60%), radial-gradient(ellipse at bottom right, rgba(53,118,184,0.1) 0%, transparent 60%)',
    }}>
      {/* Brand */}
      <div style={{ textAlign: 'center', marginBottom: '28px' }}>
        <div style={{
          width: '56px', height: '56px', borderRadius: '14px', backgroundColor: '#0B8B95',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 12px', boxShadow: '0 4px 12px rgba(11,139,149,0.45)',
        }}>
          <CloudRain size={30} color="#FFFFFF" />
        </div>
        <h1 style={{ fontSize: '26px', fontWeight: 800, color: '#FFFFFF', margin: '0 0 4px', letterSpacing: '-0.02em' }}>
          MaleMitra <span style={{ color: '#0B8B95' }}>|</span> <span style={{ fontWeight: 400, color: '#94A3B8' }}>ಮಳೆ ಮಿತ್ರ</span>
        </h1>
        <p style={{ fontSize: '13px', color: '#64748B', margin: 0 }}>
          Connected Monsoon Mobility & Civic Response Platform · Bengaluru
        </p>
      </div>

      {/* Card */}
      <div style={{
        backgroundColor: '#FFFFFF', borderRadius: '14px', width: '100%', maxWidth: '460px',
        boxShadow: '0 24px 48px -12px rgba(0,0,0,0.5)', overflow: 'hidden',
      }}>
        {/* Tabs (only for login/register) */}
        {isMainTab && (
          <div style={{ display: 'flex', borderBottom: '1px solid #E2E8F0', backgroundColor: '#F8FAFC' }}>
            {(['login', 'register'] as Tab[]).map(t => (
              <button key={t} onClick={() => setTab(t)} style={{
                flex: 1, padding: '13px', border: 'none', cursor: 'pointer',
                fontWeight: 700, fontSize: '13px',
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                backgroundColor: tab === t ? '#FFFFFF' : 'transparent',
                color: tab === t ? '#0B8B95' : '#64748B',
                borderBottom: tab === t ? '2px solid #0B8B95' : '2px solid transparent',
                transition: 'all 0.12s ease',
              }}>
                {t === 'login' ? <LogIn size={14} /> : <UserPlus size={14} />}
                {t === 'login' ? 'Sign In' : 'Create Account'}
              </button>
            ))}
          </div>
        )}

        {/* Sub-screen header for forgot/reset */}
        {(tab === 'forgot' || tab === 'reset') && (
          <div style={{ padding: '14px 20px', borderBottom: '1px solid #E2E8F0', backgroundColor: '#F8FAFC', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <button onClick={() => setTab('login')} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#64748B', display: 'flex' }}>
              <ArrowLeft size={18} />
            </button>
            <div>
              <div style={{ fontWeight: 700, fontSize: '14px', color: '#1E293B' }}>
                {tab === 'forgot' ? 'Forgot Password' : 'Reset Password'}
              </div>
              <div style={{ fontSize: '11px', color: '#64748B' }}>
                {tab === 'forgot' ? 'Enter your email to receive a reset token' : 'Enter your new password'}
              </div>
            </div>
          </div>
        )}

        <div style={{ padding: '24px', maxHeight: '72vh', overflowY: 'auto' }}>

          {/* ── LOGIN ── */}
          {tab === 'login' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <p style={{ fontSize: '11px', fontWeight: 700, color: '#94A3B8', textTransform: 'uppercase', margin: '0 0 8px' }}>
                  Quick Demo Access
                </p>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '6px' }}>
                  {DEMO_LOGINS.map(d => (
                    <button key={d.email} onClick={() => { setLoginEmail(d.email); setLoginPassword('demo123'); }} style={{
                      padding: '8px 10px', borderRadius: '6px',
                      border: loginEmail === d.email ? '1.5px solid #0B8B95' : '1px solid #E2E8F0',
                      backgroundColor: loginEmail === d.email ? '#F0FDFA' : '#F8FAFC',
                      cursor: 'pointer', textAlign: 'left', transition: 'all 0.1s',
                    }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: '#1E293B' }}>{d.label}</div>
                      <div style={{ fontSize: '10px', color: '#0B8B95', fontWeight: 600 }}>{d.role}</div>
                    </button>
                  ))}
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{ flex: 1, height: '1px', backgroundColor: '#E2E8F0' }} />
                <span style={{ fontSize: '11px', color: '#94A3B8' }}>OR</span>
                <div style={{ flex: 1, height: '1px', backgroundColor: '#E2E8F0' }} />
              </div>

              {loginError && errBox(loginError)}

              <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Email Address</label>
                  <input type="email" value={loginEmail} onChange={e => setLoginEmail(e.target.value)}
                    placeholder="you@example.com" style={inputStyle} required />
                </div>
                <div>
                  <label style={labelStyle}>Password</label>
                  {pwField(loginPassword, setLoginPassword, loginShowPwd, () => setLoginShowPwd(p => !p))}
                </div>
                <div style={{ textAlign: 'right' }}>
                  <button type="button" onClick={() => { setForgotEmail(loginEmail); setTab('forgot'); }}
                    style={{ background: 'none', border: 'none', color: '#0B8B95', fontSize: '12px', cursor: 'pointer', fontWeight: 600, padding: 0 }}>
                    Forgot password?
                  </button>
                </div>
                <button type="submit" disabled={loginLoading} style={{
                  padding: '10px', borderRadius: '6px', border: 'none',
                  backgroundColor: loginLoading ? '#94A3B8' : '#0B8B95', color: '#FFF',
                  fontWeight: 700, fontSize: '13px', cursor: loginLoading ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                  boxShadow: '0 2px 4px rgba(11,139,149,0.3)',
                }}>
                  <LogIn size={14} />
                  {loginLoading ? 'Signing In…' : 'Sign In to Workspace'}
                </button>
              </form>
            </div>
          )}

          {/* ── REGISTER ── */}
          {tab === 'register' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div>
                <label style={labelStyle}>Account Role</label>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '6px' }}>
                  {[
                    { role: 'citizen' as UserRole, label: 'Citizen', Icon: Navigation },
                    { role: 'responder' as UserRole, label: 'Responder', Icon: Users },
                    { role: 'admin' as UserRole, label: 'Admin', Icon: ShieldAlert },
                  ].map(({ role, label, Icon }) => (
                    <button key={role} type="button" onClick={() => setRegRole(role)} style={{
                      padding: '10px 6px', borderRadius: '6px',
                      border: `1.5px solid ${regRole === role ? '#0B8B95' : '#E2E8F0'}`,
                      backgroundColor: regRole === role ? '#F0FDFA' : '#FAFAFA',
                      cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
                      fontSize: '11px', fontWeight: regRole === role ? 700 : 500,
                      color: regRole === role ? '#0F766E' : '#475569',
                    }}>
                      <Icon size={15} color={regRole === role ? '#0B8B95' : '#64748B'} />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              {regError && errBox(regError)}

              <form onSubmit={handleRegister} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div>
                  <label style={labelStyle}>Full Name</label>
                  <input type="text" value={regName} onChange={e => setRegName(e.target.value)}
                    placeholder="Your name" style={inputStyle} required />
                </div>
                <div>
                  <label style={labelStyle}>Email Address</label>
                  <input type="email" value={regEmail} onChange={e => setRegEmail(e.target.value)}
                    placeholder="you@example.com" style={inputStyle} required />
                </div>
                <div>
                  <label style={labelStyle}>Password</label>
                  {pwField(regPassword, setRegPassword, regShowPwd, () => setRegShowPwd(p => !p), true)}
                </div>
                <div>
                  <label style={labelStyle}>Confirm Password</label>
                  <input type="password" value={regConfirm} onChange={e => setRegConfirm(e.target.value)}
                    placeholder="Re-enter password"
                    style={{ ...inputStyle, borderColor: regConfirm && regConfirm !== regPassword ? '#FCA5A5' : '#CBD5E1' }}
                    required />
                  {regConfirm && regConfirm !== regPassword && (
                    <p style={{ fontSize: '11px', color: '#EF4444', margin: '3px 0 0' }}>Passwords do not match</p>
                  )}
                </div>

                {regRole === 'citizen' && (
                  <div>
                    <label style={labelStyle}>Phone (Optional)</label>
                    <input type="tel" value={regPhone} onChange={e => setRegPhone(e.target.value)}
                      placeholder="+91 98765 43210" style={inputStyle} />
                  </div>
                )}
                {regRole === 'responder' && (
                  <div>
                    <label style={labelStyle}>Response Unit</label>
                    <select value={regTeam} onChange={e => setRegTeam(e.target.value)} style={{ ...inputStyle, fontWeight: 600 }}>
                      <option value="team-alpha">Team Alpha — Stormwater & Dewatering</option>
                      <option value="team-beta">Team Beta — Traffic & Debris</option>
                      <option value="team-gamma">Team Gamma — Quick Drainage & Silt</option>
                    </select>
                  </div>
                )}
                {regRole === 'admin' && (
                  <>
                    <div>
                      <label style={labelStyle}>Municipal Department</label>
                      <input type="text" value={regDept} onChange={e => setRegDept(e.target.value)}
                        placeholder="BBMP Monsoon Control Room" style={inputStyle} />
                    </div>
                    <div>
                      <label style={{ ...labelStyle, color: '#B91C1C' }}>Admin Verification Passcode</label>
                      <input type="password" value={regAdminCode} onChange={e => setRegAdminCode(e.target.value)}
                        placeholder="Enter bbmp2026" style={{ ...inputStyle, borderColor: '#FCA5A5' }} required />
                    </div>
                  </>
                )}

                <button type="submit" disabled={regLoading || pwStrength.score < 5 || regPassword !== regConfirm} style={{
                  padding: '10px', borderRadius: '6px', border: 'none',
                  backgroundColor: (regLoading || pwStrength.score < 5 || regPassword !== regConfirm) ? '#94A3B8' : '#0B8B95',
                  color: '#FFF', fontWeight: 700, fontSize: '13px',
                  cursor: (regLoading || pwStrength.score < 5 || regPassword !== regConfirm) ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                  marginTop: '4px', boxShadow: '0 2px 4px rgba(11,139,149,0.3)',
                }}>
                  <UserPlus size={14} />
                  {regLoading ? 'Creating Account…' : `Register as ${regRole.charAt(0).toUpperCase() + regRole.slice(1)}`}
                </button>
              </form>
            </div>
          )}

          {/* ── FORGOT PASSWORD ── */}
          {tab === 'forgot' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ padding: '12px', backgroundColor: '#F0F9FF', border: '1px solid #BAE6FD', borderRadius: '8px', fontSize: '12px', color: '#0369A1' }}>
                <strong>Demo mode:</strong> In production, a reset link is sent via email. Here the token is returned directly so you can test the flow.
              </div>

              {forgotError && errBox(forgotError)}

              <form onSubmit={handleForgot} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div>
                  <label style={labelStyle}>Email Address</label>
                  <input type="email" value={forgotEmail} onChange={e => setForgotEmail(e.target.value)}
                    placeholder="your-registered@email.com" style={inputStyle} required />
                </div>
                <button type="submit" disabled={forgotLoading} style={{
                  padding: '10px', borderRadius: '6px', border: 'none',
                  backgroundColor: forgotLoading ? '#94A3B8' : '#0B8B95', color: '#FFF',
                  fontWeight: 700, fontSize: '13px', cursor: forgotLoading ? 'not-allowed' : 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                  boxShadow: '0 2px 4px rgba(11,139,149,0.3)',
                }}>
                  <Send size={14} />
                  {forgotLoading ? 'Sending…' : 'Send Reset Token'}
                </button>
              </form>
            </div>
          )}

          {/* ── RESET PASSWORD ── */}
          {tab === 'reset' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {resetSuccess ? (
                <div style={{ textAlign: 'center', padding: '24px 0' }}>
                  <CheckCircle2 size={40} color="#0B8B95" style={{ margin: '0 auto 12px', display: 'block' }} />
                  <div style={{ fontSize: '16px', fontWeight: 700, color: '#1E293B', marginBottom: '6px' }}>Password Updated!</div>
                  <div style={{ fontSize: '13px', color: '#64748B', marginBottom: '20px' }}>Your password has been reset successfully.</div>
                  <button onClick={() => { setTab('login'); setResetSuccess(false); setResetPwd(''); setResetConfirm(''); setResetToken(''); }}
                    style={{ padding: '10px 24px', borderRadius: '6px', border: 'none', backgroundColor: '#0B8B95', color: '#FFF', fontWeight: 700, cursor: 'pointer' }}>
                    Sign In Now
                  </button>
                </div>
              ) : (
                <>
                  {resetError && errBox(resetError)}
                  <form onSubmit={handleReset} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div>
                      <label style={labelStyle}>Reset Token</label>
                      <input type="text" value={resetToken} onChange={e => setResetToken(e.target.value)}
                        placeholder="Paste token here" style={{ ...inputStyle, fontFamily: 'monospace', fontSize: '11px' }} required />
                    </div>
                    <div>
                      <label style={labelStyle}>New Password</label>
                      {pwField(resetPwd, setResetPwd, resetShowPwd, () => setResetShowPwd(p => !p), true)}
                    </div>
                    <div>
                      <label style={labelStyle}>Confirm New Password</label>
                      <input type="password" value={resetConfirm} onChange={e => setResetConfirm(e.target.value)}
                        placeholder="Re-enter new password"
                        style={{ ...inputStyle, borderColor: resetConfirm && resetConfirm !== resetPwd ? '#FCA5A5' : '#CBD5E1' }} required />
                    </div>
                    <button type="submit" disabled={resetLoading} style={{
                      padding: '10px', borderRadius: '6px', border: 'none',
                      backgroundColor: resetLoading ? '#94A3B8' : '#0B8B95', color: '#FFF',
                      fontWeight: 700, fontSize: '13px', cursor: resetLoading ? 'not-allowed' : 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
                    }}>
                      <KeyRound size={14} />
                      {resetLoading ? 'Resetting…' : 'Set New Password'}
                    </button>
                  </form>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      <p style={{ marginTop: '20px', fontSize: '11px', color: '#334155' }}>
        Smarter Streets, Better Living
      </p>
    </div>
  );
};
