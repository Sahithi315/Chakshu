import React, { useState, useEffect } from 'react';
import {
  Search, User, Calendar, Clock, FileText, Activity, Download,
  ExternalLink, ChevronDown, ChevronUp, Copy, Check, AlertCircle,
  FolderArchive, ArrowLeft, ShieldCheck, CheckCircle2, Sparkles, Filter,
  RefreshCw
} from 'lucide-react';
import SummaryCard from './SummaryCard';

export default function PatientRecords({ initialPatientId, onBackToDoctor, apiFetch = fetch }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedPatientId, setSelectedPatientId] = useState(initialPatientId || null);
  const [patientRecord, setPatientRecord] = useState(null);
  const [isLoadingRecord, setIsLoadingRecord] = useState(false);
  const [recordError, setRecordError] = useState(null);
  const [expandedVisits, setExpandedVisits] = useState({});
  const [copiedMRN, setCopiedMRN] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState('timeline'); // 'timeline' | 'reports'

  // Pre-load if initialPatientId provided
  useEffect(() => {
    if (initialPatientId) {
      setSelectedPatientId(initialPatientId);
      loadPatientRecord(initialPatientId);
    }
  }, [initialPatientId]);

  // Live search debounced
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await apiFetch(`/api/patients?q=${encodeURIComponent(searchQuery.trim())}`);
        const data = await res.json();
        setSearchResults(data);
      } catch (err) {
        console.error('Patient search error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Load complete patient records timeline
  const loadPatientRecord = async (pid) => {
    if (!pid || !String(pid).trim()) return;
    const cleanId = String(pid).trim().replace(/^["'`\s]+|["'`\s]+$/g, '');
    if (!cleanId) return;
    setSelectedPatientId(cleanId);
    setIsLoadingRecord(true);
    setRecordError(null);
    try {
      const res = await apiFetch(`/api/patients/${encodeURIComponent(cleanId)}/records`);
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        if (res.status === 404) {
          throw new Error(errData.error || `Patient record "${cleanId}" was not found in the hospital system.`);
        } else {
          throw new Error(errData.error || `Failed to retrieve records for patient ${cleanId}. Please check the server connection and try again.`);
        }
      }
      const data = await res.json();
      setPatientRecord(data);
      // Auto-expand the most recent visit
      if (data.visits && data.visits.length > 0) {
        setExpandedVisits({ [data.visits[0].visit_id]: true });
      }
    } catch (err) {
      console.error('Load record error:', err);
      setRecordError(err.message || `An error occurred while loading records for ${cleanId}.`);
    } finally {
      setIsLoadingRecord(false);
    }
  };

  const handleSelectPatient = (p) => {
    setSearchQuery('');
    setSearchResults([]);
    loadPatientRecord(p.patient_id);
  };

  const handleSearchKeyDown = (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      if (searchResults.length > 0) {
        handleSelectPatient(searchResults[0]);
      } else if (searchQuery.trim()) {
        const q = searchQuery.trim();
        setSearchResults([]);
        loadPatientRecord(q);
      }
    }
  };

  const toggleVisitExpand = (vid) => {
    setExpandedVisits((prev) => ({
      ...prev,
      [vid]: !prev[vid]
    }));
  };

  const copyToClipboard = (text) => {
    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(text);
      setCopiedMRN(true);
      setTimeout(() => setCopiedMRN(false), 2000);
    }
  };

  const downloadReport = async (report) => {
    try {
      const response = await apiFetch(report.download_url);
      if (!response.ok) throw new Error('Document download was denied');
      const blobUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = blobUrl;
      link.download = report.filename || 'medical-report';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(blobUrl);
    } catch (error) {
      setRecordError(error.message);
    }
  };

  const patient = patientRecord?.patient;
  const visits = patientRecord?.visits || [];
  const allReports = patientRecord?.all_reports || [];

  return (
    <div className="patient-records-page">
      {/* Top Action Bar with Search and Return button */}
      <div className="records-top-bar" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '18px', gap: '12px', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {onBackToDoctor && (
            <button
              onClick={onBackToDoctor}
              className="btn-secondary"
              style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', fontSize: '0.84rem', padding: '8px 14px' }}
            >
              <ArrowLeft size={16} />
              <span>Back to Doctor Brief</span>
            </button>
          )}
          <h2 style={{ fontSize: '1.25rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
            Patient Records & Medical History Archive
          </h2>
        </div>

        <div style={{ fontSize: '0.8rem', color: '#64748b', background: '#ffffff', padding: '6px 14px', borderRadius: '9999px', border: '1px solid #e2e8f0', fontWeight: 600 }}>
          🔒 Clinical Staff View · Read-Only Patient History
        </div>
      </div>

      {/* SEARCH BAR FOR PATIENT RECORDS */}
      <div className="search-wrapper" style={{ marginBottom: '22px' }}>
        <Search className="search-icon" size={20} />
        <input
          type="text"
          className="search-input"
          placeholder="Search by Permanent MRN (e.g. P10482, PAT-...), Patient Name, or Registered Phone Number..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onKeyDown={handleSearchKeyDown}
        />

        {/* Autocomplete dropdown */}
        {searchResults.length > 0 && (
          <div style={{
            position: 'absolute',
            top: '100%',
            left: 0,
            right: 0,
            background: '#ffffff',
            borderRadius: '16px',
            boxShadow: '0 12px 30px rgba(0,0,0,0.12)',
            border: '1px solid #e2e8f0',
            marginTop: '8px',
            zIndex: 100,
            overflow: 'hidden',
            maxHeight: '340px',
            overflowY: 'auto'
          }}>
            {searchResults.map((p) => (
              <div
                className="search-result-row"
                key={p.patient_id}
                onClick={() => handleSelectPatient(p)}
                style={{
                  padding: '12px 20px',
                  borderBottom: '1px solid #f1f5f9',
                  cursor: 'pointer',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  transition: 'background 0.15s ease'
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = '#f8fafc'}
                onMouseLeave={(e) => e.currentTarget.style.background = '#ffffff'}
              >
                <div>
                  <span style={{ fontWeight: 700, color: '#0f172a' }}>{p.name}</span>
                  <span style={{ color: '#64748b', fontSize: '0.85rem', marginLeft: '8px' }}>
                    ({p.age || '-'} y/o, {p.gender || '-'})
                  </span>
                </div>
                <div style={{ fontSize: '0.82rem', color: '#2563eb', fontWeight: 700 }}>
                  MRN: {p.patient_id} · 📞 {p.phone}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* LOADING STATE */}
      {isLoadingRecord && (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
          <Activity size={32} style={{ animation: 'spin 1s linear infinite', margin: '0 auto 12px', color: '#2563eb' }} />
          <div style={{ fontWeight: 700 }}>Loading comprehensive medical history...</div>
        </div>
      )}

      {/* ERROR STATE WITH RETRY ACTION */}
      {recordError && !isLoadingRecord && (
        <div className="card" style={{ background: '#fef2f2', border: '1.5px solid #fecaca', padding: '24px', textAlign: 'center', marginBottom: '20px' }}>
          <AlertCircle size={36} style={{ color: '#dc2626', margin: '0 auto 10px' }} />
          <h3 style={{ color: '#991b1b', fontWeight: 700, fontSize: '1.1rem' }}>Record Retrieval Notice</h3>
          <p style={{ color: '#7f1d1d', marginTop: '6px', fontSize: '0.92rem', maxWidth: '540px', margin: '6px auto 16px' }}>
            {recordError}
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
            {selectedPatientId && (
              <button
                type="button"
                onClick={() => loadPatientRecord(selectedPatientId)}
                className="btn-primary"
                style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', fontSize: '0.86rem', padding: '8px 18px' }}
              >
                <RefreshCw size={15} />
                <span>Retry Loading Records</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => { setRecordError(null); setSelectedPatientId(null); setPatientRecord(null); }}
              className="btn-secondary"
              style={{ fontSize: '0.86rem', padding: '8px 18px' }}
            >
              Clear Notice
            </button>
          </div>
        </div>
      )}

      {/* EMPTY STATE (No patient selected yet) */}
      {!patient && !isLoadingRecord && !recordError && (
        <div className="card" style={{ textAlign: 'center', padding: '70px 20px', background: '#f8fafc' }}>
          <FolderArchive size={48} style={{ color: '#94a3b8', margin: '0 auto 14px' }} />
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, color: '#1e293b' }}>
            No Patient Record Selected
          </h3>
          <p style={{ color: '#64748b', fontSize: '0.88rem', maxWidth: '480px', margin: '8px auto 20px' }}>
            Search for a patient above using their <strong>Permanent Patient ID (MRN)</strong>, full name, or registered mobile phone number to inspect their full longitudinal visits timeline.
          </p>
        </div>
      )}

      {/* PATIENT RECORD PROFILE & TIMELINE */}
      {patient && !isLoadingRecord && (
        <div>
          {/* 1. PATIENT DEMOGRAPHICS HEADER CARD */}
          <div className="card" style={{ marginBottom: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '14px' }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                  <h1 style={{ fontSize: '1.4rem', fontWeight: 800, color: '#0f172a', margin: 0 }}>
                    {patient.name}
                  </h1>
                  <span style={{ fontSize: '0.88rem', color: '#64748b', fontWeight: 600 }}>
                    {patient.age || '-'} y/o · {patient.gender || 'Unspecified'}
                  </span>
                  <div style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: '#eff6ff',
                    border: '1.5px solid #bfdbfe',
                    padding: '3px 10px',
                    borderRadius: '9999px',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    color: '#1d4ed8'
                  }}>
                    <span>MRN: {patient.patient_id}</span>
                    <button
                      type="button"
                      onClick={() => copyToClipboard(patient.patient_id)}
                      title="Copy Permanent MRN"
                      style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#2563eb', padding: '2px', display: 'flex' }}
                    >
                      {copiedMRN ? <Check size={14} style={{ color: '#16a34a' }} /> : <Copy size={14} />}
                    </button>
                  </div>
                </div>

                <div style={{ display: 'flex', gap: '16px', marginTop: '8px', fontSize: '0.84rem', color: '#64748b', flexWrap: 'wrap' }}>
                  <span>📞 <strong>Mobile:</strong> {patient.phone}</span>
                  <span>🗓️ <strong>First Registered:</strong> {patient.registered_at ? patient.registered_at.slice(0, 10) : 'Recorded'}</span>
                  <span>🏥 <strong>Total Recorded Visits:</strong> <strong style={{ color: '#0f172a' }}>{patientRecord.visits_count}</strong></span>
                </div>
              </div>

              {/* View Switcher Pills */}
              <div style={{ display: 'flex', background: '#f1f5f9', borderRadius: '10px', padding: '3px', gap: '4px' }}>
                <button
                  type="button"
                  onClick={() => setActiveSubTab('timeline')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: activeSubTab === 'timeline' ? '#ffffff' : 'transparent',
                    color: activeSubTab === 'timeline' ? '#2563eb' : '#64748b',
                    boxShadow: activeSubTab === 'timeline' ? '0 2px 4px rgba(0,0,0,0.06)' : 'none'
                  }}
                >
                  Chronological Timeline ({visits.length})
                </button>

                <button
                  type="button"
                  onClick={() => setActiveSubTab('reports')}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '8px',
                    fontSize: '0.82rem',
                    fontWeight: 700,
                    border: 'none',
                    cursor: 'pointer',
                    background: activeSubTab === 'reports' ? '#ffffff' : 'transparent',
                    color: activeSubTab === 'reports' ? '#2563eb' : '#64748b',
                    boxShadow: activeSubTab === 'reports' ? '0 2px 4px rgba(0,0,0,0.06)' : 'none'
                  }}
                >
                  Reports Archive ({allReports.length})
                </button>
              </div>
            </div>

            {/* Baseline Medical Profile Bar */}
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: '12px',
              marginTop: '18px',
              padding: '14px 16px',
              background: '#f8fafc',
              borderRadius: '14px',
              border: '1px solid #e2e8f0',
              fontSize: '0.86rem'
            }}>
              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Known Chronic Conditions</div>
                <div style={{ fontWeight: 600, color: '#0f172a', marginTop: '2px' }}>{patientRecord.chronic_conditions}</div>
              </div>

              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Active Medications</div>
                <div style={{ fontWeight: 600, color: '#0f172a', marginTop: '2px' }}>{patientRecord.current_medications}</div>
              </div>

              <div>
                <div style={{ fontSize: '0.72rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Known Drug Allergies</div>
                <div style={{
                  fontWeight: 700,
                  color: patientRecord.known_allergies?.toLowerCase().includes('penicillin') || patientRecord.known_allergies?.toLowerCase().includes('allergy') ? '#dc2626' : '#0f172a',
                  marginTop: '2px'
                }}>
                  {patientRecord.known_allergies}
                </div>
              </div>
            </div>
          </div>

          {/* 2. CHRONOLOGICAL VISITS TIMELINE SUB-TAB */}
          {activeSubTab === 'timeline' && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {visits.length === 0 ? (
                <div className="card" style={{ textAlign: 'center', padding: '40px', color: '#64748b' }}>
                  No visit history recorded for this patient yet.
                </div>
              ) : (
                visits.map((v, index) => {
                  const isExpanded = !!expandedVisits[v.visit_id];
                  const isCurrent = index === 0;
                  const vDate = v.created_at ? v.created_at.slice(0, 16).replace('T', ' ') : 'Date recorded';
                  const inData = v.intake || {};
                  const vitData = v.vitals || {};
                  const docNotes = v.doctor_notes || {};
                  const repList = v.reports || [];
                  const labRows = v.extracted_results || [];

                  return (
                    <div
                      key={v.visit_id}
                      className="card"
                      style={{
                        borderLeft: isCurrent ? '5px solid #2563eb' : '5px solid #94a3b8',
                        padding: '18px 22px'
                      }}
                    >
                      {/* Visit Header */}
                      <div
                        onClick={() => toggleVisitExpand(v.visit_id)}
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          cursor: 'pointer',
                          userSelect: 'none',
                          flexWrap: 'wrap',
                          gap: '10px'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                          <span style={{ fontWeight: 800, fontSize: '1.02rem', color: '#0f172a' }}>
                            🗓️ Consultation on {vDate}
                          </span>

                          <span className="token-pill" style={{ background: '#e0f2fe', color: '#0369a1', fontSize: '0.8rem' }}>
                            Token {v.token_number}
                          </span>

                          <span style={{
                            fontSize: '0.74rem',
                            fontWeight: 700,
                            padding: '3px 10px',
                            borderRadius: '9999px',
                            background: v.status === 'completed' ? '#ecfdf5' : '#fffbeb',
                            color: v.status === 'completed' ? '#065f46' : '#92400e',
                            textTransform: 'uppercase'
                          }}>
                            {v.status || 'WAITING'}
                          </span>

                          {isCurrent && (
                            <span style={{ fontSize: '0.72rem', background: '#2563eb', color: '#fff', padding: '2px 8px', borderRadius: '9999px', fontWeight: 700 }}>
                              CURRENT VISIT
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ fontSize: '0.82rem', color: '#64748b' }}>
                            Visit ID: <code>{v.visit_id}</code>
                          </span>
                          {isExpanded ? <ChevronUp size={18} style={{ color: '#64748b' }} /> : <ChevronDown size={18} style={{ color: '#64748b' }} />}
                        </div>
                      </div>

                      {/* Summary quick-line even when collapsed */}
                      <div style={{ marginTop: '8px', fontSize: '0.88rem', color: '#475569' }}>
                        <strong>Complaint:</strong> "{inData.reason_for_visit || inData.symptoms_text || 'Routine follow-up'}"
                        {docNotes.clinical_notes && (
                          <span style={{ marginLeft: '12px', color: '#2563eb', fontWeight: 600 }}>
                            · Notes recorded by {docNotes.doctor_id || 'Physician'}
                          </span>
                        )}
                      </div>

                      {/* EXPANDED VISIT DETAILS */}
                      {isExpanded && (
                        <div style={{ marginTop: '18px', paddingTop: '16px', borderTop: '1px solid #f1f5f9', display: 'flex', flexDirection: 'column', gap: '18px' }}>
                          {/* 1. Patient-Reported Intake */}
                          <div style={{ background: '#f8fafc', padding: '14px 18px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                            <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#2563eb', textTransform: 'uppercase', marginBottom: '6px' }}>
                              📋 Patient Check-In Intake Details
                            </div>
                            <div className="responsive-two-column" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', fontSize: '0.88rem', marginBottom: '8px' }}>
                              <div><strong>Chief Complaint:</strong> {inData.reason_for_visit || 'Not specified'}</div>
                              <div><strong>Timeline:</strong> {inData.duration || 'Unspecified'} ({inData.severity || 'Unspecified'})</div>
                            </div>
                            {inData.symptoms_text && (
                              <div style={{ fontSize: '0.88rem', color: '#1e293b', background: '#ffffff', padding: '8px 12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                                <em>"{inData.symptoms_text}"</em>
                              </div>
                            )}
                          </div>

                          {/* 2. Nurse Vitals */}
                          {vitData.bp_systolic && (
                            <div style={{ background: '#f8fafc', padding: '14px 18px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#10b981', textTransform: 'uppercase', marginBottom: '8px' }}>
                                🩺 Nurse-Recorded Vital Signs
                              </div>
                              <div style={{ display: 'flex', gap: '20px', flexWrap: 'wrap', fontSize: '0.86rem' }}>
                                <div><strong>Blood Pressure:</strong> {vitData.bp_systolic}/{vitData.bp_diastolic} mmHg</div>
                                <div><strong>Heart Rate:</strong> {vitData.heart_rate} bpm</div>
                                <div><strong>Temperature:</strong> {vitData.temperature} °F</div>
                                <div><strong>SpO2:</strong> {vitData.spo2}%</div>
                                <div><strong>Blood Sugar:</strong> {vitData.blood_sugar} mg/dL</div>
                              </div>
                            </div>
                          )}

                          {/* 3. Doctor Consultation Notes & Plan */}
                          {docNotes.clinical_notes && (
                            <div style={{ background: '#eff6ff', padding: '16px 18px', borderRadius: '12px', borderLeft: '4px solid #3b82f6', border: '1px solid #bfdbfe' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                                <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#1d4ed8', textTransform: 'uppercase' }}>
                                  👨‍⚕️ Attending Doctor Clinical Examination & Findings
                                </div>
                                <span style={{ fontSize: '0.76rem', color: '#64748b' }}>Physician: <strong>{docNotes.doctor_id || 'Doctor'}</strong></span>
                              </div>
                              <div style={{ fontSize: '0.92rem', color: '#0f172a', lineHeight: 1.5, marginBottom: '10px' }}>
                                {docNotes.clinical_notes}
                              </div>
                              {docNotes.plan && (
                                <div style={{ background: '#ffffff', padding: '10px 14px', borderRadius: '8px', border: '1px solid #bbf7d0', borderLeft: '4px solid #10b981' }}>
                                  <div style={{ fontSize: '0.74rem', fontWeight: 700, color: '#065f46', textTransform: 'uppercase', marginBottom: '3px' }}>
                                    💊 Diagnosis & Prescription Plan:
                                  </div>
                                  <div style={{ fontSize: '0.88rem', color: '#064e3b', fontWeight: 500 }}>
                                    {docNotes.plan}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          {/* 4. Uploaded Reports & Extracted Results */}
                          {repList.length > 0 && (
                            <div style={{ background: '#f8fafc', padding: '14px 18px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase', marginBottom: '10px' }}>
                                📑 Uploaded Medical Reports in this Visit ({repList.length})
                              </div>
                              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {repList.map((r, ridx) => (
                                  <div
                                    key={ridx}
                                    style={{
                                      display: 'flex',
                                      justifyContent: 'space-between',
                                      alignItems: 'center',
                                      background: '#ffffff',
                                      padding: '8px 14px',
                                      borderRadius: '8px',
                                      border: '1px solid #e2e8f0',
                                      fontSize: '0.84rem'
                                    }}
                                  >
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                      <FileText size={16} style={{ color: '#2563eb' }} />
                                      <span style={{ fontWeight: 600, color: '#0f172a' }}>{r.filename}</span>
                                      <span style={{ fontSize: '0.74rem', color: '#64748b', background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px' }}>
                                        {r.file_type?.toUpperCase()}
                                      </span>
                                    </div>

                                    <button
                                      type="button"
                                      onClick={() => downloadReport(r)}
                                      className="btn-secondary"
                                      style={{ padding: '4px 10px', fontSize: '0.78rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                                    >
                                      <Download size={13} />
                                      <span>Download Original</span>
                                    </button>
                                  </div>
                                ))}
                              </div>

                              {/* Lab rows if available */}
                              {labRows.length > 0 && (
                                <div style={{ marginTop: '12px' }}>
                                  <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#475569', marginBottom: '6px' }}>Extracted Laboratory Findings:</div>
                                  <div className="lab-table-container">
                                    <table className="lab-table">
                                      <thead>
                                        <tr>
                                          <th>Test Name</th>
                                          <th>Observed Result</th>
                                          <th>Reference Range</th>
                                          <th>Status</th>
                                        </tr>
                                      </thead>
                                      <tbody>
                                        {labRows.map((row, lidx) => {
                                          const flagText = `${row.range_note || ''} ${row.source_line || ''}`.toLowerCase();
                                          const isLow = flagText.includes('low') || flagText.includes('below');
                                          const isHigh = flagText.includes('high') || flagText.includes('above');
                                          const needsReview = Boolean(row.range_note) && !isLow && !isHigh;
                                          return (
                                            <tr key={lidx}>
                                              <td style={{ fontWeight: 600 }}>{row.test_name}</td>
                                              <td style={{ fontWeight: 700, color: (isHigh || needsReview) ? '#dc2626' : (isLow ? '#b45309' : '#0f172a') }}>
                                                {row.test_value} {row.unit}
                                              </td>
                                              <td style={{ color: '#64748b' }}>{row.reference_range || '-'}</td>
                                              <td>
                                                {isHigh ? (
                                                  <span className="badge-status badge-high">HIGH</span>
                                                ) : isLow ? (
                                                  <span className="badge-status badge-low">LOW</span>
                                                ) : needsReview ? (
                                                  <span className="badge-status badge-high">REVIEW</span>
                                                ) : (
                                                  <span className="badge-status badge-normal">IN RANGE</span>
                                                )}
                                              </td>
                                            </tr>
                                          );
                                        })}
                                      </tbody>
                                    </table>
                                  </div>
                                </div>
                              )}
                            </div>
                          )}

                          {/* 5. Visit Clinical Summary Card */}
                          {v.summary && (
                            <div>
                              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#2563eb', textTransform: 'uppercase', marginBottom: '6px' }}>
                                ✨ Generated Summary Card for this Visit
                              </div>
                              <SummaryCard summary={v.summary} patient={patient} visit={v} compact />
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          )}

          {/* 3. ALL REPORTS ARCHIVE SUB-TAB */}
          {activeSubTab === 'reports' && (
            <div className="card">
              <div className="card-title">
                <FolderArchive size={20} style={{ color: '#2563eb' }} />
                <span>Uploaded Medical Reports & Document Archive</span>
              </div>
              <div className="card-subtitle">
                Complete longitudinal archive of lab reports, blood panels, and prescriptions uploaded for MRN {patient.patient_id}.
              </div>

              {allReports.length === 0 ? (
                <div style={{ padding: '36px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '12px', marginTop: '14px' }}>
                  No medical reports have been uploaded for this patient across any visits.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '16px' }}>
                  {allReports.map((r, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        padding: '14px 18px',
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderRadius: '12px',
                        flexWrap: 'wrap',
                        gap: '12px'
                      }}
                    >
                      <div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <FileText size={18} style={{ color: '#2563eb' }} />
                          <span style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.94rem' }}>{r.filename}</span>
                          <span style={{ fontSize: '0.74rem', fontWeight: 700, color: '#1d4ed8', background: '#eff6ff', padding: '2px 8px', borderRadius: '6px' }}>
                            {r.file_type?.toUpperCase()}
                          </span>
                        </div>
                        <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px' }}>
                          Uploaded: {r.created_at ? r.created_at.slice(0, 16) : 'Recorded'} · Attached to Visit: <code>{r.visit_id}</code>
                        </div>
                      </div>

                      <button
                        type="button"
                        onClick={() => downloadReport(r)}
                        className="btn-primary"
                        style={{ fontSize: '0.84rem', padding: '8px 16px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                      >
                        <Download size={15} />
                        <span>Download / View Document</span>
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
