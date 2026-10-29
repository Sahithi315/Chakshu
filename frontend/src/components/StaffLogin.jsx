import React, { useState } from 'react';
import { LockKeyhole, Stethoscope } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';

export default function StaffLogin() {
  const [params] = useSearchParams(); const requestedRole = params.get('role');
  const [username, setUsername] = useState(requestedRole === 'nurse' ? 'nurse.demo' : 'doctor.demo');
  const [password, setPassword] = useState(requestedRole === 'nurse' ? 'Nurse123!' : 'Doctor123!');
  const [error, setError] = useState(''); const [submitting, setSubmitting] = useState(false);
  const { login } = useAuth(); const navigate = useNavigate();
  const submit = async (event) => { event.preventDefault(); setError(''); setSubmitting(true); try { const user = await login(username, password); navigate(user.role === 'doctor' ? '/doctor/queue' : '/nurse/queue', { replace: true }); } catch (err) { setError(err.message); } finally { setSubmitting(false); } };
  return <div className="login-shell"><form className="card login-card" onSubmit={submit}><div className="login-icon"><LockKeyhole size={26} /></div><h2>Staff sign-in</h2><p>Authorized doctor and nurse accounts only.</p>{error && <div className="auth-error">{error}</div>}<label className="form-label">Username</label><input className="form-input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" required /><label className="form-label" style={{ marginTop: 16 }}>Password</label><input type="password" className="form-input" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required /><button className="btn-primary login-submit" disabled={submitting}><Stethoscope size={17} />{submitting ? 'Signing in...' : 'Sign in securely'}</button><div className="demo-credentials"><strong>Synthetic demo accounts</strong><span>Doctor: doctor.demo / Doctor123!</span><span>Nurse: nurse.demo / Nurse123!</span></div></form></div>;
}
