import React from 'react';
import { BrowserRouter, Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './auth/AuthContext';
import Navbar from './components/Navbar';
import RoleSelection from './components/RoleSelection';
import StaffLogin from './components/StaffLogin';
import DoctorDashboard from './components/DoctorDashboard';
import PatientRecords from './components/PatientRecords';
import PatientIntake from './components/PatientIntake';
import NurseStation from './components/NurseStation';
import AnimatedContent from './components/AnimatedContent';

function ProtectedRoute({ role, children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="route-loading">Checking staff session...</div>;
  if (!user) return <Navigate to="/staff/login" replace />;
  if (user.role !== role) return <Navigate to={user.role === 'doctor' ? '/doctor/queue' : '/nurse/queue'} replace />;
  return children;
}

function PatientFlow() {
  const location = useLocation();
  const navigate = useNavigate();
  const step = location.pathname.endsWith('/intake') ? 2 : location.pathname.endsWith('/reports') ? 3 : location.pathname.endsWith('/complete') ? 4 : 1;
  const paths = { 1: '/patient/check-in', 2: '/patient/intake', 3: '/patient/reports', 4: '/patient/complete' };
  return <PatientIntake activeStep={step} onStepChange={(next) => navigate(paths[next] || paths[1])} />;
}

function RecordsFromRoute({ apiFetch, onBack }) {
  const location = useLocation();
  const patientId = decodeURIComponent(location.pathname.split('/').pop() || '');
  return <PatientRecords initialPatientId={patientId} apiFetch={apiFetch} onBackToDoctor={onBack} />;
}

function AppRoutes() {
  const { user, apiFetch } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  return <div className="app-container">
    <Navbar />
    <main><AnimatedContent
      key={location.pathname}
      distance={34}
      direction="vertical"
      duration={0.62}
      ease="power3.out"
      blur={0}
      stagger={0.07}
      threshold={0.1}
      trigger="mount"
      className="route-animated-content"
    ><Routes location={location}>
      <Route path="/" element={<RoleSelection />} />
      <Route path="/staff/login" element={user ? <Navigate to={user.role === 'doctor' ? '/doctor/queue' : '/nurse/queue'} replace /> : <StaffLogin />} />
      <Route path="/patient/*" element={<PatientFlow />} />
      <Route path="/doctor/queue" element={<ProtectedRoute role="doctor"><DoctorDashboard apiFetch={apiFetch} onOpenPatientRecords={(id) => navigate(`/doctor/records/${encodeURIComponent(id)}`)} /></ProtectedRoute>} />
      <Route path="/doctor/visit/:visitId" element={<Navigate to="/doctor/queue" replace />} />
      <Route path="/doctor/records" element={<ProtectedRoute role="doctor"><PatientRecords apiFetch={apiFetch} onBackToDoctor={() => navigate('/doctor/queue')} /></ProtectedRoute>} />
      <Route path="/doctor/records/:patientId" element={<ProtectedRoute role="doctor"><RecordsFromRoute apiFetch={apiFetch} onBack={() => navigate('/doctor/queue')} /></ProtectedRoute>} />
      <Route path="/nurse/queue" element={<ProtectedRoute role="nurse"><NurseStation apiFetch={apiFetch} user={user} /></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes></AnimatedContent></main>
  </div>;
}

export default function App() {
  return <BrowserRouter><AuthProvider><AppRoutes /></AuthProvider></BrowserRouter>;
}
