import React, { createContext, useContext, useEffect, useMemo, useState } from 'react';

const AuthContext = createContext(null);
const STORAGE_KEY = 'chakshu_staff_session';

export function AuthProvider({ children }) {
  const stored = (() => { try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null'); } catch { return null; } })();
  const [token, setToken] = useState(stored?.token || null);
  const [user, setUser] = useState(stored?.user || null);
  const [loading, setLoading] = useState(Boolean(stored?.token));
  const clearSession = () => { localStorage.removeItem(STORAGE_KEY); setToken(null); setUser(null); };
  const apiFetch = async (url, options = {}) => {
    const headers = new Headers(options.headers || {});
    if (token) headers.set('Authorization', `Bearer ${token}`);
    const response = await fetch(url, { ...options, headers });
    if (response.status === 401 && token) clearSession();
    return response;
  };
  useEffect(() => {
    if (!token) { setLoading(false); return; }
    fetch('/api/auth/staff/me', { headers: { Authorization: `Bearer ${token}` } })
      .then(async (response) => { if (!response.ok) throw new Error('Expired session'); const data = await response.json(); setUser(data.user); localStorage.setItem(STORAGE_KEY, JSON.stringify({ token, user: data.user })); })
      .catch(clearSession).finally(() => setLoading(false));
  }, [token]);
  const login = async (username, password) => {
    const response = await fetch('/api/auth/staff/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, password }) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Sign-in failed');
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ token: data.token, user: data.user })); setToken(data.token); setUser(data.user); return data.user;
  };
  const logout = async () => { if (token) await fetch('/api/auth/staff/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => {}); clearSession(); };
  const value = useMemo(() => ({ token, user, loading, login, logout, apiFetch }), [token, user, loading]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() { return useContext(AuthContext); }
