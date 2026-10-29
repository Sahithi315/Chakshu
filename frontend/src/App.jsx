import React, { useState } from 'react';
import Navbar from './components/Navbar';
import DoctorDashboard from './components/DoctorDashboard';
import PatientRecords from './components/PatientRecords';
import PatientIntake from './components/PatientIntake';
import NurseStation from './components/NurseStation';
import { Stethoscope, FolderArchive, ClipboardList, Activity, AlertTriangle } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState('doctor');
  const [recordsPatientId, setRecordsPatientId] = useState(null);

  const handleOpenPatientRecords = (patientId) => {
    setRecordsPatientId(patientId);
    setActiveTab('records');
  };

  return (
    <div className="app-container">
      {/* Top Navbar */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Prototype Clinical Disclaimer Banner */}
      <div className="disclaimer-banner">
        <AlertTriangle size={16} />
        <span>
          <strong>Prototype. Synthetic data only.</strong> For clinical documentation assistance. It must never independently diagnose patients or prescribe medication.
        </span>
      </div>

      {/* Dynamic View Tab */}
      <main>
        {activeTab === 'doctor' && (
          <DoctorDashboard onOpenPatientRecords={handleOpenPatientRecords} />
        )}
        {activeTab === 'records' && (
          <PatientRecords
            initialPatientId={recordsPatientId}
            onBackToDoctor={() => setActiveTab('doctor')}
          />
        )}
        {activeTab === 'patient' && <PatientIntake />}
        {activeTab === 'nurse' && <NurseStation />}
      </main>

      {/* Mobile Bottom Navigation Bar (4 Tabs) */}
      <nav className="mobile-bottom-bar">
        <button
          className={`mobile-nav-item ${activeTab === 'doctor' ? 'active' : ''}`}
          onClick={() => setActiveTab('doctor')}
        >
          <Stethoscope size={20} />
          <span>Doctor Brief</span>
        </button>

        <button
          className={`mobile-nav-item ${activeTab === 'records' ? 'active' : ''}`}
          onClick={() => setActiveTab('records')}
        >
          <FolderArchive size={20} />
          <span>Records</span>
        </button>

        <button
          className={`mobile-nav-item ${activeTab === 'patient' ? 'active' : ''}`}
          onClick={() => setActiveTab('patient')}
        >
          <ClipboardList size={20} />
          <span>Check-in</span>
        </button>

        <button
          className={`mobile-nav-item ${activeTab === 'nurse' ? 'active' : ''}`}
          onClick={() => setActiveTab('nurse')}
        >
          <Activity size={20} />
          <span>Vitals</span>
        </button>
      </nav>
    </div>
  );
}
