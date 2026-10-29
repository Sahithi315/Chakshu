import React, { useState, useEffect } from 'react';
import { Search, User, FileText, Activity, Save, CheckCircle2, AlertCircle, Sparkles, Clock, Calendar, FolderArchive } from 'lucide-react';
import SummaryCard from './SummaryCard';

export default function DoctorDashboard({ onOpenPatientRecords }) {
  const [visits, setVisits] = useState([]);
  const [selectedVisitId, setSelectedVisitId] = useState(null);
  const [visitData, setVisitData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // Doctor consultation notes form state
  const [clinicalNotes, setClinicalNotes] = useState('');
  const [clinicalPlan, setClinicalPlan] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [notesSavedSuccess, setNotesSavedSuccess] = useState(false);

  // Fetch active queue
  const fetchVisits = async () => {
    try {
      const res = await fetch('/api/visits');
      const data = await res.json();
      setVisits(data);
      if (data.length > 0 && !selectedVisitId) {
        setSelectedVisitId(data[0].visit_id);
      }
    } catch (err) {
      console.error('Failed to fetch visits', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVisits();
  }, []);

  // Fetch selected visit details
  useEffect(() => {
    if (!selectedVisitId) return;
    const fetchDetails = async () => {
      try {
        const res = await fetch(`/api/visits/${selectedVisitId}`);
        const data = await res.json();
        setVisitData(data);
        if (data.doctor_notes) {
          setClinicalNotes(data.doctor_notes.clinical_notes || '');
          setClinicalPlan(data.doctor_notes.plan || '');
        } else {
          setClinicalNotes('');
          setClinicalPlan('');
        }
        setNotesSavedSuccess(false);
      } catch (err) {
        console.error('Failed to fetch visit details', err);
      }
    };
    fetchDetails();
  }, [selectedVisitId]);

  // Live patient search handler
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await fetch(`/api/patients?q=${encodeURIComponent(searchQuery)}`);
        const data = await res.json();
        setSearchResults(data);
      } catch (err) {
        console.error('Search error', err);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Handle selecting a searched patient
  const handleSelectPatientSearchResult = async (patient) => {
    setSearchQuery('');
    setSearchResults([]);
    // Find if patient has a visit in the queue
    const match = visits.find(v => v.patient_id === patient.patient_id);
    if (match) {
      setSelectedVisitId(match.visit_id);
    } else {
      // Create a new visit for this patient if not in current queue
      try {
        const res = await fetch('/api/patients/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ phone: patient.phone, name: patient.name, age: patient.age, gender: patient.gender })
        });
        const created = await res.json();
        await fetchVisits();
        setSelectedVisitId(created.visit.visit_id);
      } catch (e) {
        console.error('Failed to open patient', e);
      }
    }
  };

  // Save consultation notes
  const handleSaveNotes = async (e) => {
    e.preventDefault();
    if (!visitData || !clinicalNotes.trim()) return;
    setSavingNotes(true);
    try {
      const res = await fetch('/api/doctor/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visitData.visit_id,
          patient_id: visitData.patient_id,
          clinical_notes: clinicalNotes.trim(),
          plan: clinicalPlan.trim(),
          doctor_id: 'DR-SHARMA'
        })
      });
      if (res.ok) {
        setNotesSavedSuccess(true);
        await fetchVisits();
        const updatedRes = await fetch(`/api/visits/${visitData.visit_id}`);
        if (updatedRes.ok) {
          const updatedData = await updatedRes.json();
          setVisitData(updatedData);
        }
      }
    } catch (err) {
      console.error('Failed to save notes', err);
    } finally {
      setSavingNotes(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '60px 20px', textAlign: 'center', color: '#64748b' }}>Loading Doctor Dashboard...</div>;
  }

  const patient = visitData ? {
    name: visitData.patient_name,
    age: visitData.patient_age,
    gender: visitData.patient_gender,
    patient_id: visitData.patient_id,
    phone: visitData.patient_phone
  } : null;

  const intake = visitData?.intake || {};
  const vitals = visitData?.vitals || {};
  const labRows = visitData?.extracted_results || [];

  return (
    <div>
      {/* SEARCH BAR (Image 5 style) */}
      <div className="search-wrapper">
        <Search className="search-icon" size={20} />
        <input
          type="text"
          className="search-input"
          placeholder="Search patient by Name, Phone, MRN/Patient ID, or Token (e.g. Ramesh, 9876543210, T-101)..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
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
            overflow: 'hidden'
          }}>
            {searchResults.map((p) => (
              <div
                key={p.patient_id}
                onClick={() => handleSelectPatientSearchResult(p)}
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
                <div style={{ fontSize: '0.82rem', color: '#2563eb', fontWeight: 600 }}>
                  MRN: {p.patient_id} · 📞 {p.phone}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* OPD TOKEN QUEUE CHIPS */}
      <div className="queue-chips">
        {visits.map((v) => {
          const isActive = v.visit_id === selectedVisitId;
          return (
            <button
              key={v.visit_id}
              className={`queue-chip ${isActive ? 'active' : ''}`}
              onClick={() => setSelectedVisitId(v.visit_id)}
            >
              <span className="token-pill">{v.token_number}</span>
              <span>{v.patient_name}</span>
              <span style={{ fontSize: '0.74rem', opacity: 0.8 }}>({v.status})</span>
            </button>
          );
        })}
      </div>

      {visitData ? (
        <div className="doctor-layout-grid">
          {/* LEFT / CENTER COLUMN */}
          <div>
            {/* 1. THE 10-15s SINGLE SUMMARY CARD (Exact Image 4 format) */}
            <SummaryCard summary={visitData.summary} patient={patient} visit={visitData} />

            {/* 2. REASON FOR CURRENT VISIT & INTAKE DETAILS */}
            <div className="card" style={{ marginBottom: '24px' }}>
              <div className="card-title">
                <FileText size={18} style={{ color: '#2563eb' }} />
                <span>Current Visit & Patient-Reported Intake</span>
              </div>
              <div className="card-subtitle">
                Recorded during check-in · Token: <strong>{visitData.token_number}</strong>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
                <div style={{ background: '#f8fafc', padding: '12px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Main Reason for Visit</div>
                  <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                    {intake.reason_for_visit || 'Not specified'}
                  </div>
                </div>

                <div style={{ background: '#f8fafc', padding: '12px 16px', borderRadius: '12px', border: '1px solid #e2e8f0' }}>
                  <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>Duration & Severity</div>
                  <div style={{ fontSize: '0.98rem', fontWeight: 700, color: '#0f172a', marginTop: '2px' }}>
                    {intake.duration || 'Unspecified'} · {intake.severity || 'Unspecified'}
                  </div>
                </div>
              </div>

              <div style={{ marginBottom: '12px' }}>
                <div style={{ fontSize: '0.8rem', fontWeight: 700, color: '#475569', marginBottom: '4px' }}>Patient's Own Words:</div>
                <div style={{ fontSize: '0.94rem', color: '#1e293b', background: '#eff6ff', padding: '10px 14px', borderRadius: '10px', borderLeft: '4px solid #2563eb' }}>
                  "{intake.symptoms_text || 'No additional narrative provided.'}"
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '10px', marginTop: '14px', fontSize: '0.88rem' }}>
                <div><strong>Comorbidities:</strong> {intake.medical_conditions || 'None declared'}</div>
                <div><strong>Current Medicines:</strong> {intake.current_medications || 'None declared'}</div>
                <div><strong>Known Allergies:</strong> <span style={{ color: intake.known_allergies?.toLowerCase().includes('allergy') || intake.known_allergies?.toLowerCase().includes('penicillin') ? '#dc2626' : 'inherit', fontWeight: 600 }}>{intake.known_allergies || 'Not recorded'}</span></div>
              </div>
            </div>

            {/* 3. MEDICAL REPORTS & LABORATORY FINDINGS (CLEAN DISPLAY - NO INSPECT OPTION!) */}
            <div className="card" style={{ marginBottom: '24px' }}>
              <div className="card-title">
                <Activity size={18} style={{ color: '#2563eb' }} />
                <span>Medical Reports & Laboratory Findings</span>
              </div>
              <div className="card-subtitle">
                Extracted from patient's uploaded PDF reports and physical scans. Clean tabular review (no inspect viewer).
              </div>

              {labRows.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                  No laboratory records extracted for this visit yet. Upload a report via Patient Check-in.
                </div>
              ) : (
                <div className="lab-table-container">
                  <table className="lab-table">
                    <thead>
                      <tr>
                        <th>Investigation / Test Name</th>
                        <th>Observed Result</th>
                        <th>Reference Range</th>
                        <th>Clinical Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {labRows.map((row, idx) => {
                        const isHigh = row.range_note || row.source_line?.toLowerCase().includes('high') || row.source_line?.toLowerCase().includes('outside');
                        const isLow = row.source_line?.toLowerCase().includes('low');
                        return (
                          <tr key={idx}>
                            <td style={{ fontWeight: 600 }}>{row.test_name}</td>
                            <td style={{ fontWeight: 700, color: isHigh ? '#dc2626' : (isLow ? '#b45309' : '#0f172a') }}>
                              {row.test_value} <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{row.unit}</span>
                            </td>
                            <td style={{ color: '#64748b' }}>{row.reference_range || '-'}</td>
                            <td>
                              {isHigh ? (
                                <span className="badge-status badge-high">OUTSIDE RANGE</span>
                              ) : isLow ? (
                                <span className="badge-status badge-low">LOW</span>
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
              )}
            </div>

            {/* 4. PAST CONSULTATIONS & DOCTOR NOTES HISTORY */}
            <div className="card" style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
                <div className="card-title" style={{ margin: 0 }}>
                  <Clock size={18} style={{ color: '#2563eb' }} />
                  <span>Past Consultations & Doctor Notes History</span>
                </div>

                {onOpenPatientRecords && visitData.patient_id && (
                  <button
                    type="button"
                    onClick={() => onOpenPatientRecords(visitData.patient_id)}
                    className="btn-secondary"
                    style={{ fontSize: '0.8rem', padding: '6px 12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                  >
                    <FolderArchive size={14} />
                    <span>View Full History in Patient Records</span>
                  </button>
                )}
              </div>
              <div className="card-subtitle">
                Historical doctor writings, diagnosed problems, and previous treatment plans on record for this patient.
              </div>

              {(!visitData.past_visits || visitData.past_visits.length === 0) ? (
                <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                  First recorded visit for this patient at this hospital. Future visits will display longitudinal history and doctor notes here.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  {visitData.past_visits.map((pv, idx) => {
                    const pDate = pv.created_at ? pv.created_at.slice(0, 10) : 'Previous Date';
                    const pIn = pv.intake || {};
                    const pNotes = pv.doctor_notes || {};
                    const pVits = pv.vitals || {};
                    const pLabs = pv.extracted_results || [];

                    return (
                      <div
                        key={pv.visit_id || idx}
                        style={{
                          background: '#f8fafc',
                          border: '1px solid #e2e8f0',
                          borderRadius: '16px',
                          padding: '16px 20px',
                          display: 'flex',
                          flexDirection: 'column',
                          gap: '10px'
                        }}
                      >
                        {/* Visit header bar */}
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px', borderBottom: '1px solid #e2e8f0', paddingBottom: '10px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <span style={{ fontWeight: 700, color: '#0f172a', fontSize: '0.98rem' }}>
                              📅 Consultation on {pDate}
                            </span>
                            <span className="token-pill" style={{ background: '#e0f2fe', color: '#0369a1', fontSize: '0.78rem' }}>
                              Token {pv.token_number || '-'}
                            </span>
                            <span style={{ fontSize: '0.76rem', background: '#ecfdf5', color: '#065f46', padding: '2px 8px', borderRadius: '9999px', fontWeight: 600 }}>
                              {pv.status?.toUpperCase() || 'COMPLETED'}
                            </span>
                          </div>
                          <div style={{ fontSize: '0.82rem', color: '#64748b' }}>
                            Physician: <strong>{pNotes.doctor_id || 'Attending Doctor'}</strong>
                          </div>
                        </div>

                        {/* Patient's Reported Problem at that time */}
                        <div>
                          <div style={{ fontSize: '0.78rem', fontWeight: 700, color: '#64748b', textTransform: 'uppercase' }}>
                            Patient Problem / Chief Complaint at that visit:
                          </div>
                          <div style={{ fontSize: '0.92rem', color: '#1e293b', marginTop: '2px', fontWeight: 600 }}>
                            "{pIn.reason_for_visit || pIn.symptoms_text || 'Routine follow-up'}"
                            {pIn.duration ? <span style={{ color: '#64748b', fontWeight: 400, marginLeft: '6px' }}>({pIn.duration})</span> : null}
                          </div>
                        </div>

                        {/* DOCTOR CLINICAL WRITINGS: Examination & Observations */}
                        {pNotes.clinical_notes && (
                          <div style={{ background: '#ffffff', padding: '12px 14px', borderRadius: '12px', borderLeft: '4px solid #3b82f6', border: '1px solid #e2e8f0' }}>
                            <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#1d4ed8', textTransform: 'uppercase' }}>
                              👨‍⚕️ Doctor Clinical Examination & Observations:
                            </div>
                            <div style={{ fontSize: '0.92rem', color: '#0f172a', marginTop: '4px', lineHeight: 1.45 }}>
                              {pNotes.clinical_notes}
                            </div>
                          </div>
                        )}

                        {/* DOCTOR CLINICAL WRITINGS: Diagnosis, Advice & Prescription Plan */}
                        {pNotes.plan && (
                          <div style={{ background: '#f0fdf4', padding: '12px 14px', borderRadius: '12px', borderLeft: '4px solid #10b981', border: '1px solid #bbf7d0' }}>
                            <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#065f46', textTransform: 'uppercase' }}>
                              💊 Doctor Diagnosis, Advice & Prescription Plan:
                            </div>
                            <div style={{ fontSize: '0.92rem', color: '#064e3b', marginTop: '4px', lineHeight: 1.45, fontWeight: 500 }}>
                              {pNotes.plan}
                            </div>
                          </div>
                        )}

                        {/* Past Lab Findings from uploaded reports */}
                        {pLabs.length > 0 && (
                          <div style={{ fontSize: '0.84rem', color: '#475569', background: '#ffffff', padding: '8px 12px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                            <strong style={{ color: '#0f172a' }}>🧪 Previous Lab Results: </strong>
                            {pLabs.map((l, lidx) => (
                              <span key={lidx} style={{ marginRight: '8px', display: 'inline-block' }}>
                                {l.test_name}: <strong>{l.test_value} {l.unit || ''}</strong>
                                {lidx < pLabs.length - 1 ? ' · ' : ''}
                              </span>
                            ))}
                          </div>
                        )}

                        {/* Past Vitals */}
                        {pVits.bp_systolic && (
                          <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                            <strong>Prior Vitals:</strong> BP {pVits.bp_systolic}/{pVits.bp_diastolic} mmHg · HR {pVits.heart_rate} bpm · SpO2 {pVits.spo2}% · Sugar {pVits.blood_sugar} mg/dL
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          {/* RIGHT COLUMN: DOCTOR CONSULTATION NOTES & VITALS */}
          <div>
            {/* VITALS CARD */}
            <div className="card" style={{ marginBottom: '24px' }}>
              <div className="card-title">
                <Activity size={18} style={{ color: '#10b981' }} />
                <span>Nurse Vitals Measurement</span>
              </div>
              <div className="card-subtitle">Recorded by triage nursing staff</div>

              <div className="vitals-grid">
                <div className="vital-box">
                  <div className="vital-label">Blood Pressure</div>
                  <div className="vital-val" style={{ color: (vitals.bp_systolic >= 140 || vitals.bp_diastolic >= 90) ? '#dc2626' : '#0f172a' }}>
                    {vitals.bp_systolic ? `${vitals.bp_systolic}/${vitals.bp_diastolic}` : '-'}
                  </div>
                  <div className="vital-unit">mmHg</div>
                </div>

                <div className="vital-box">
                  <div className="vital-label">Heart Rate</div>
                  <div className="vital-val">{vitals.heart_rate || '-'}</div>
                  <div className="vital-unit">bpm</div>
                </div>

                <div className="vital-box">
                  <div className="vital-label">Temperature</div>
                  <div className="vital-val" style={{ color: vitals.temperature >= 100.4 ? '#dc2626' : '#0f172a' }}>
                    {vitals.temperature || '-'}
                  </div>
                  <div className="vital-unit">°F</div>
                </div>

                <div className="vital-box">
                  <div className="vital-label">SpO2</div>
                  <div className="vital-val" style={{ color: vitals.spo2 < 95 ? '#dc2626' : '#0f172a' }}>
                    {vitals.spo2 ? `${vitals.spo2}%` : '-'}
                  </div>
                  <div className="vital-unit">Oxygen</div>
                </div>

                <div className="vital-box">
                  <div className="vital-label">Blood Sugar</div>
                  <div className="vital-val">{vitals.blood_sugar || '-'}</div>
                  <div className="vital-unit">mg/dL</div>
                </div>
              </div>
            </div>

            {/* DOCTOR CONSULTATION NOTES & CLINICAL PLAN (Retained as requested) */}
            <div className="card">
              <div className="card-title">
                <span>✍️ Doctor Consultation Notes & Plan</span>
              </div>
              <div className="card-subtitle">
                Record findings and advice. Saved to the patient's permanent hospital record.
              </div>

              {notesSavedSuccess && (
                <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '10px 14px', borderRadius: '10px', color: '#065f46', fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
                  <CheckCircle2 size={16} />
                  <span>Consultation notes saved successfully! Visit marked completed.</span>
                </div>
              )}

              <form onSubmit={handleSaveNotes}>
                <div className="form-group">
                  <label className="form-label">Clinical Examination & Observations *</label>
                  <textarea
                    className="form-textarea"
                    rows={4}
                    placeholder="e.g. Chest clear on auscultation. Normal S1/S2. Mild bilateral pedal edema noted. Abdomen soft..."
                    value={clinicalNotes}
                    onChange={(e) => setClinicalNotes(e.target.value)}
                    required
                  />
                </div>

                <div className="form-group">
                  <label className="form-label">Diagnosis, Advice & Prescription Plan</label>
                  <textarea
                    className="form-textarea"
                    rows={3}
                    placeholder="e.g. Continue Metformin 500mg BD. Add Telmisartan 40mg OD. Order Repeat HbA1c in 3 months. Low salt diet..."
                    value={clinicalPlan}
                    onChange={(e) => setClinicalPlan(e.target.value)}
                  />
                </div>

                <button
                  type="submit"
                  className="btn-primary"
                  style={{ width: '100%' }}
                  disabled={savingNotes}
                >
                  <Save size={16} />
                  <span>{savingNotes ? 'Saving Notes...' : 'Save Notes & Complete Consultation'}</span>
                </button>
              </form>
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '60px 20px', color: '#64748b' }}>
          No patient selected. Choose a patient from the queue or search above.
        </div>
      )}
    </div>
  );
}
