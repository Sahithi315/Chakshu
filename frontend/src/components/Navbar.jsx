import React from 'react';
import { Stethoscope, FolderArchive, ClipboardList, Activity } from 'lucide-react';

export default function Navbar({ activeTab, setActiveTab }) {
  const tabs = [
    { id: 'doctor', label: 'Doctor Brief', icon: Stethoscope },
    { id: 'records', label: 'Patient Records', icon: FolderArchive },
    { id: 'patient', label: 'Patient Check-in', icon: ClipboardList },
    { id: 'nurse', label: 'Nurse Station', icon: Activity },
  ];

  return (
    <header className="top-nav">
      <div className="brand-section">
        <div className="brand-logo">
          <Stethoscope size={24} />
        </div>
        <div className="brand-text">
          <h1>Clinical Context Platform</h1>
          <p>AI-Assisted Hospital OPD Pre-Consultation</p>
        </div>
      </div>

      <nav className="nav-tabs" style={{ display: window.innerWidth < 768 ? 'none' : 'flex' }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              className={`nav-tab-btn ${isActive ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>

      <div className="doctor-badge-profile">
        <div className="doc-avatar">DS</div>
        <div style={{ display: window.innerWidth < 640 ? 'none' : 'block' }}>
          <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#0f172a' }}>Dr. Sharma</div>
          <div style={{ fontSize: '0.74rem', color: '#64748b' }}>General Medicine OPD</div>
        </div>
      </div>
    </header>
  );
}
