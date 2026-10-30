import React, { useState, useEffect, useRef } from 'react';
import { Search, User, FileText, Activity, Save, CheckCircle2, AlertCircle, Sparkles, Clock, Calendar, FolderArchive, Plus, Trash2, ShieldAlert, ShieldCheck, Pill, Eye } from 'lucide-react';
import SummaryCard from './SummaryCard';

const orderedActiveQueue = queue => [...queue]
  .filter(visit => String(visit.status || '').toLowerCase() !== 'completed')
  .sort((left, right) => {
    const timeOrder = String(left.created_at || '').localeCompare(String(right.created_at || ''));
    if (timeOrder !== 0) return timeOrder;
    const leftToken = Number(String(left.token_number || '').replace(/\D/g, '')) || Number.MAX_SAFE_INTEGER;
    const rightToken = Number(String(right.token_number || '').replace(/\D/g, '')) || Number.MAX_SAFE_INTEGER;
    return leftToken - rightToken;
  });

export default function DoctorDashboard({ onOpenPatientRecords, apiFetch = fetch }) {
  const [visits, setVisits] = useState([]);
  const [selectedVisitId, setSelectedVisitId] = useState(null);
  const [visitData, setVisitData] = useState(null);
  const [visitLoading, setVisitLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);

  // Doctor consultation notes form state
  const [clinicalNotes, setClinicalNotes] = useState('');
  const [clinicalPlan, setClinicalPlan] = useState('');
  const [savingNotes, setSavingNotes] = useState(false);
  const [completionNotice, setCompletionNotice] = useState('');
  const [medications, setMedications] = useState([{ name: '', strength: '', dose: '', frequency: '', duration: '' }]);
  const [safetyResult, setSafetyResult] = useState(null);
  const visitCacheRef = useRef(new Map());
  const visitRequestsRef = useRef(new Map());
  const detailRequestRef = useRef(0);

  const requestVisitDetails = visitId => {
    if (visitCacheRef.current.has(visitId)) return Promise.resolve(visitCacheRef.current.get(visitId));
    if (visitRequestsRef.current.has(visitId)) return visitRequestsRef.current.get(visitId);
    const request = apiFetch(`/api/visits/${visitId}`)
      .then(async response => {
        if (!response.ok) throw new Error('Unable to load patient details');
        const data = await response.json();
        visitCacheRef.current.set(visitId, data);
        return data;
      })
      .finally(() => visitRequestsRef.current.delete(visitId));
    visitRequestsRef.current.set(visitId, request);
    return request;
  };

  const prefetchVisit = visitId => {
    requestVisitDetails(visitId).catch(error => console.error('Patient prefetch failed', error));
  };

  // Fetch active queue
  const fetchVisits = async () => {
    try {
      const res = await apiFetch('/api/visits');
      const data = await res.json();
      const queue = orderedActiveQueue(Array.isArray(data) ? data : []);
      setVisits(queue);
      setSelectedVisitId(current => queue.some(visit => visit.visit_id === current) ? current : (queue[0]?.visit_id || null));
      window.setTimeout(() => queue.slice(0, 3).forEach(visit => prefetchVisit(visit.visit_id)), 120);
      return queue;
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
    if (!selectedVisitId) {
      setVisitData(null);
      setVisitLoading(false);
      return;
    }
    setMedications([{ name: '', strength: '', dose: '', frequency: '', duration: '' }]);
    setSafetyResult(null);
    const requestId = ++detailRequestRef.current;
    const cached = visitCacheRef.current.get(selectedVisitId);
    const queuePatient = visits.find(visit => visit.visit_id === selectedVisitId);

    if (cached) {
      setVisitData(cached);
      setClinicalNotes(cached.doctor_notes?.clinical_notes || '');
      setClinicalPlan(cached.doctor_notes?.plan || '');
      setVisitLoading(false);
      return;
    }

    setVisitData(queuePatient ? {
      ...queuePatient,
      intake: null,
      vitals: null,
      reports: [],
      extracted_results: [],
      extracted_medications: [],
      document_findings: [],
      past_visits: [],
      summary: null,
      symptom_extraction: null
    } : null);
    setClinicalNotes('');
    setClinicalPlan('');
    setVisitLoading(true);
    const fetchDetails = async () => {
      try {
        const data = await requestVisitDetails(selectedVisitId);
        if (requestId !== detailRequestRef.current) return;
        setVisitData(data);
        if (data.doctor_notes) {
          setClinicalNotes(data.doctor_notes.clinical_notes || '');
          setClinicalPlan(data.doctor_notes.plan || '');
        } else {
          setClinicalNotes('');
          setClinicalPlan('');
        }
      } catch (err) {
        console.error('Failed to fetch visit details', err);
      } finally {
        if (requestId === detailRequestRef.current) setVisitLoading(false);
      }
    };
    fetchDetails();
  }, [selectedVisitId]);

  useEffect(() => {
    const hasMedicineInput = medications.some(medicine => Object.values(medicine).some(value => String(value || '').trim()));
    if (!hasMedicineInput || !visitData) {
      setSafetyResult(null);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const response = await apiFetch('/api/doctor/prescription-safety', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ medications, allergies: visitData.intake?.known_allergies || '' })
        });
        if (response.ok) setSafetyResult(await response.json());
      } catch (error) {
        console.error('Prescription safety check failed', error);
      }
    }, 350);
    return () => clearTimeout(timer);
  }, [medications, visitData]);

  const updateMedication = (index, field, value) => setMedications(current => current.map((medicine, itemIndex) => itemIndex === index ? { ...medicine, [field]: value } : medicine));
  const addMedication = () => setMedications(current => [...current, { name: '', strength: '', dose: '', frequency: '', duration: '' }]);
  const removeMedication = index => setMedications(current => current.length === 1 ? [{ name: '', strength: '', dose: '', frequency: '', duration: '' }] : current.filter((_, itemIndex) => itemIndex !== index));

  // Live patient search handler
  useEffect(() => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      try {
        const res = await apiFetch(`/api/patients?q=${encodeURIComponent(searchQuery)}`);
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
      // Searching records must not silently create a new clinical encounter.
      if (onOpenPatientRecords) onOpenPatientRecords(patient.patient_id);
    }
  };

  // Save consultation notes
  const handleSaveNotes = async (e) => {
    e.preventDefault();
    if (!visitData || !clinicalNotes.trim()) return;
    setSavingNotes(true);
    try {
      const res = await apiFetch('/api/doctor/notes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visitData.visit_id,
          patient_id: visitData.patient_id,
          clinical_notes: clinicalNotes.trim(),
          plan: clinicalPlan.trim(),
          medications: medications.filter(medicine => medicine.name.trim()),
        })
      });
      if (res.ok) {
        const completedVisitId = visitData.visit_id;
        const completedPatientName = visitData.patient_name;
        const remainingQueue = orderedActiveQueue(visits.filter(visit => visit.visit_id !== completedVisitId));
        setVisits(remainingQueue);
        setVisitData(null);
        setCompletionNotice(`${completedPatientName} was completed and removed from the consultation queue.`);
        setSelectedVisitId(remainingQueue[0]?.visit_id || null);
        await fetchVisits();
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
  const extractedMeds = visitData?.extracted_medications || [];
  const docFindings = visitData?.document_findings || [];
  const uploadedDocs = visitData?.reports || [];

  return (
    <div className="doctor-dashboard-page">
      <div className="doctor-patient-switcher">
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
                className="search-result-row"
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

      {/* ORDERED OPD CONSULTATION QUEUE */}
      <div className="doctor-queue-panel">
        <div className="doctor-queue-heading">
          <div><Clock size={16} /><strong>Consultation queue</strong></div>
          <span>{visits.length} {visits.length === 1 ? 'patient' : 'patients'} waiting</span>
        </div>
        <div className="queue-chips">
        {visits.map((v, index) => {
          const isActive = v.visit_id === selectedVisitId;
          return (
            <button
              key={v.visit_id}
              className={`queue-chip ${isActive ? 'active' : ''}`}
              onClick={() => setSelectedVisitId(v.visit_id)}
              onPointerEnter={() => prefetchVisit(v.visit_id)}
              onFocus={() => prefetchVisit(v.visit_id)}
            >
              <span className="queue-order">{String(index + 1).padStart(2, '0')}</span>
              <span className="token-pill">{v.token_number}</span>
              <span className="queue-patient-name">{v.patient_name}</span>
              <span className="queue-status">{v.status || 'waiting'}</span>
            </button>
          );
        })}
        {visits.length === 0 && <div className="doctor-queue-empty">Queue clear</div>}
        </div>
      </div>
      </div>

      {completionNotice && <div className="doctor-completion-notice" role="status">
        <CheckCircle2 size={17} />
        <span>{completionNotice}</span>
        <button type="button" onClick={() => setCompletionNotice('')} aria-label="Dismiss completion message">×</button>
      </div>}

      {visitLoading && visitData && <div className="doctor-data-loading" role="status" aria-live="polite">
        <span className="doctor-data-loading-spinner" />
        <span><strong>{visitData.patient_name}</strong> selected · loading clinical details</span>
      </div>}

      {visitData ? (
        <div className="doctor-consultation-view">
          <SummaryCard summary={visitData.summary} patient={patient} visit={visitData} symptomExtraction={visitData.symptom_extraction} />
        <div className="doctor-layout-grid">
          {/* LEFT / CENTER COLUMN */}
          <div className="doctor-support-column">

            {/* 2. REASON FOR CURRENT VISIT & INTAKE DETAILS */}
            <details className="doctor-detail-section">
              <summary className="doctor-detail-summary">
                <FileText size={18} style={{ color: '#2563eb' }} />
                <span><strong>Patient-reported intake details</strong><small>Original check-in responses</small></span>
              </summary>
              <div className="doctor-detail-body">
              <div className="card-subtitle">
                Recorded during check-in · Token: <strong>{visitData.token_number}</strong>
              </div>

              <div className="responsive-two-column" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '16px' }}>
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
            </details>

            {/* B. REPORTS AND LABORATORY FINDINGS */}
            <details className="doctor-detail-section" open={labRows.length > 0}>
              <summary className="doctor-detail-summary">
                <Activity size={18} style={{ color: '#2563eb' }} />
                <span><strong>Reports and laboratory findings</strong><small>{labRows.length} extracted result{labRows.length === 1 ? '' : 's'}</small></span>
              </summary>
              <div className="doctor-detail-body">
              {labRows.length === 0 ? (
                <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                  No laboratory results available for this visit.
                </div>
              ) : (
                <div className="lab-table-container">
                  <table className="lab-table">
                    <thead>
                      <tr>
                        <th>Investigation / Test Name</th>
                        <th>Observed Result</th>
                        <th>Reference Range</th>
                        <th>Abnormality Status</th>
                        <th>Source Document</th>
                      </tr>
                    </thead>
                    <tbody>
                      {labRows.map((row, idx) => {
                        const flagText = `${row.range_note || ''} ${row.status || ''} ${row.source_line || ''}`.toLowerCase();
                        const isLow = (row.status && row.status.toLowerCase() === 'low') || flagText.includes('low') || flagText.includes('below');
                        const isHigh = (row.status && row.status.toLowerCase() === 'high') || flagText.includes('high') || flagText.includes('above') || flagText.includes('significant');
                        const needsReview = Boolean(row.range_note) && !isLow && !isHigh;
                        return (
                          <tr key={idx} style={{ background: isHigh ? '#fff5f5' : isLow ? '#fffbeb' : 'inherit' }}>
                            <td style={{ fontWeight: 600 }}>{row.test_name}</td>
                            <td style={{ fontWeight: 700, color: (isHigh || needsReview) ? '#dc2626' : (isLow ? '#b45309' : '#0f172a') }}>
                              {row.test_value} <span style={{ fontSize: '0.8rem', color: '#64748b' }}>{row.unit}</span>
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
                                <span className="badge-status badge-normal">NORMAL</span>
                              )}
                            </td>
                            <td style={{ fontSize: '0.78rem', color: '#64748b' }}>
                              {row.source_document || 'Uploaded Report'}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
              </div>
            </details>

            {/* C. MEDICATIONS EXTRACTED FROM REPORTS */}
            <details className="doctor-detail-section" open={extractedMeds.length > 0}>
              <summary className="doctor-detail-summary">
                <Pill size={18} style={{ color: '#2563eb' }} />
                <span><strong>Medications Extracted from Reports</strong><small>{extractedMeds.length} prescription item{extractedMeds.length === 1 ? '' : 's'}</small></span>
              </summary>
              <div className="doctor-detail-body">
                <div className="card-subtitle" style={{ marginBottom: '12px' }}>
                  Prescription medicines identified from uploaded documents. Clearly distinguished from patient-reported current medications.
                </div>

                {extractedMeds.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                    No prescription medications extracted from uploaded documents for this visit.
                  </div>
                ) : (
                  <div className="lab-table-container">
                    <table className="lab-table">
                      <thead>
                        <tr>
                          <th>Medicine Name</th>
                          <th>Dosage &amp; Strength</th>
                          <th>Frequency</th>
                          <th>Timing</th>
                          <th>Duration</th>
                          <th>Route</th>
                          <th>Instructions</th>
                          <th>Source Document</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extractedMeds.map((med, mIdx) => (
                          <tr key={med.med_id || mIdx}>
                            <td style={{ fontWeight: 700, color: '#0f172a' }}>{med.medicine_name}</td>
                            <td style={{ fontWeight: 600, color: med.dosage !== 'Not specified' ? '#2563eb' : '#94a3b8' }}>
                              {med.dosage || 'Not specified'}
                            </td>
                            <td style={{ color: med.frequency !== 'Not specified' ? '#0f172a' : '#94a3b8' }}>
                              {med.frequency || 'Not specified'}
                            </td>
                            <td style={{ color: med.timing !== 'Not specified' ? '#0f172a' : '#94a3b8' }}>
                              {med.timing || 'Not specified'}
                            </td>
                            <td style={{ color: med.duration !== 'Not specified' ? '#0f172a' : '#94a3b8' }}>
                              {med.duration || 'Not specified'}
                            </td>
                            <td style={{ color: med.route !== 'Not specified' ? '#0f172a' : '#94a3b8' }}>
                              {med.route || 'Not specified'}
                            </td>
                            <td style={{ fontSize: '0.82rem', color: med.instructions !== 'Not specified' ? '#475569' : '#94a3b8' }}>
                              {med.instructions || 'Not specified'}
                            </td>
                            <td style={{ fontSize: '0.78rem', color: '#64748b' }}>
                              {med.source_document || 'Prescription Upload'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </details>

            {/* D. IMPORTANT MEDICAL FINDINGS & CLINICAL INSIGHTS */}
            <details className="doctor-detail-section" open={docFindings.length > 0}>
              <summary className="doctor-detail-summary">
                <AlertCircle size={18} style={{ color: '#2563eb' }} />
                <span><strong>Important Medical Findings</strong><small>{docFindings.length} observation{docFindings.length === 1 ? '' : 's'}</small></span>
              </summary>
              <div className="doctor-detail-body">
                <div className="card-subtitle" style={{ marginBottom: '12px' }}>
                  Critical observations and preliminary automated findings. Automated insights require clinician verification and are not confirmed diagnoses.
                </div>

                {docFindings.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                    No abnormal findings or explicit diagnostic remarks detected in uploaded documents for this visit.
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {docFindings.map((f, fIdx) => {
                      const isInsight = f.category === 'insight' || Boolean(f.is_automated);
                      const isHigh = f.severity === 'high';
                      const isWarning = f.severity === 'warning';
                      return (
                        <div
                          key={f.finding_id || fIdx}
                          style={{
                            background: isHigh ? '#fef2f2' : isWarning ? '#fffbeb' : '#f8fafc',
                            border: isHigh ? '1px solid #fecaca' : isWarning ? '1px solid #fde68a' : '1px solid #e2e8f0',
                            borderLeft: isHigh ? '4px solid #dc2626' : isWarning ? '4px solid #f59e0b' : '4px solid #3b82f6',
                            borderRadius: '12px',
                            padding: '12px 16px'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px', flexWrap: 'wrap', gap: '6px' }}>
                            <span style={{ fontWeight: 700, fontSize: '0.9rem', color: isHigh ? '#991b1b' : isWarning ? '#92400e' : '#0f172a' }}>
                              {f.title}
                            </span>
                            {isInsight ? (
                              <span style={{ fontSize: '0.7rem', background: '#eff6ff', color: '#1d4ed8', padding: '2px 8px', borderRadius: '9999px', fontWeight: 600 }}>
                                Automated Insight · Requires Verification
                              </span>
                            ) : (
                              <span style={{ fontSize: '0.7rem', background: '#f1f5f9', color: '#475569', padding: '2px 8px', borderRadius: '9999px', fontWeight: 600 }}>
                                Document Text Finding
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: '0.88rem', color: '#334155', lineHeight: 1.45 }}>
                            {f.detail}
                          </div>
                          {f.source_document && (
                            <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '6px' }}>
                              Source: <strong>{f.source_document}</strong>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </details>

            {/* E. UPLOADED DOCUMENTS AND EXTRACTION STATUS */}
            <details className="doctor-detail-section">
              <summary className="doctor-detail-summary">
                <FolderArchive size={18} style={{ color: '#2563eb' }} />
                <span><strong>Uploaded Documents &amp; Extraction Status</strong><small>{uploadedDocs.length} file{uploadedDocs.length === 1 ? '' : 's'}</small></span>
              </summary>
              <div className="doctor-detail-body">
                <div className="card-subtitle" style={{ marginBottom: '12px' }}>
                  All medical reports, prescriptions, and laboratory files uploaded for this patient encounter.
                </div>

                {uploadedDocs.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                    No medical documents uploaded for this visit yet.
                  </div>
                ) : (
                  <div className="lab-table-container">
                    <table className="lab-table">
                      <thead>
                        <tr>
                          <th>Document Name</th>
                          <th>Detected Type</th>
                          <th>Extraction Status</th>
                          <th>Extracted Findings</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {uploadedDocs.map((doc, dIdx) => {
                          const status = (doc.extraction_status || 'Completed').toLowerCase();
                          const isCompleted = status === 'completed' || status === 'success';
                          const isFailed = status === 'failed' || status === 'error';
                          return (
                            <tr key={doc.report_id || dIdx}>
                              <td style={{ fontWeight: 600, color: '#0f172a' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                  <FileText size={16} style={{ color: '#2563eb' }} />
                                  <span>{doc.filename}</span>
                                </div>
                              </td>
                              <td style={{ color: '#334155' }}>
                                <span style={{ background: '#f1f5f9', padding: '3px 8px', borderRadius: '6px', fontSize: '0.8rem', fontWeight: 600 }}>
                                  {doc.doc_type || (doc.file_type === 'pdf' ? 'Laboratory Report' : 'Medical Image')}
                                </span>
                              </td>
                              <td>
                                {isCompleted ? (
                                  <span className="badge-status badge-normal">COMPLETED</span>
                                ) : isFailed ? (
                                  <span className="badge-status badge-high">FAILED</span>
                                ) : (
                                  <span className="badge-status badge-low">PROCESSING</span>
                                )}
                              </td>
                              <td style={{ fontWeight: 700, color: '#0f172a' }}>
                                {doc.findings_count != null ? doc.findings_count : (labRows.length + extractedMeds.length)} items
                              </td>
                              <td>
                                <a
                                  href={`/api/reports/${doc.report_id}/file`}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="btn-secondary"
                                  style={{ fontSize: '0.78rem', padding: '5px 12px', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                                >
                                  <Eye size={13} />
                                  <span>View Document</span>
                                </a>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </details>

            {/* 4. PAST CONSULTATIONS & DOCTOR NOTES HISTORY */}
            <details className="doctor-detail-section">
              <summary className="doctor-detail-summary">
                <Clock size={18} style={{ color: '#2563eb' }} />
                <span><strong>Past consultations</strong><small>{visitData.past_visits?.length || 0} earlier visit{visitData.past_visits?.length === 1 ? '' : 's'}</small></span>
              </summary>
              <div className="doctor-detail-body">
              <div className="doctor-history-actions">

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
            </details>
          </div>

          {/* RIGHT COLUMN: DOCTOR CONSULTATION NOTES & VITALS */}
          <div>
            {/* VITALS CARD */}
            <div className="card doctor-vitals-card" style={{ marginBottom: '24px' }}>
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

            {/* DOCTOR CONSULTATION NOTES & CLINICAL PLAN */}
            <div className="card doctor-prescription-card">
              <div className="card-title">
                <Save size={19} style={{ color: '#2563eb' }} />
                <span>Doctor Assessment &amp; Prescription</span>
              </div>
              <div className="card-subtitle">
                Enter examination findings first, followed by the prescription, advice, and follow-up plan.
              </div>

              <form onSubmit={handleSaveNotes}>
                <div className="form-group">
                  <label className="form-label">Examination findings and clinical assessment *</label>
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
                  <div className="prescription-builder-header">
                    <div><label className="form-label">Medicines</label><span>Enter each medicine separately for safety review.</span></div>
                    <button type="button" className="btn-secondary" onClick={addMedication}><Plus size={15} />Add medicine</button>
                  </div>
                  <div className="prescription-medicine-list">
                    {medications.map((medicine, index) => <div className="prescription-medicine-row" key={index}>
                      <div className="prescription-medicine-number">{index + 1}</div>
                      <input className="form-input" placeholder="Medicine name" value={medicine.name} onChange={event => updateMedication(index, 'name', event.target.value)} />
                      <input className="form-input" placeholder="Strength" value={medicine.strength} onChange={event => updateMedication(index, 'strength', event.target.value)} />
                      <input className="form-input" placeholder="Dose" value={medicine.dose} onChange={event => updateMedication(index, 'dose', event.target.value)} />
                      <input className="form-input" placeholder="Frequency" value={medicine.frequency} onChange={event => updateMedication(index, 'frequency', event.target.value)} />
                      <input className="form-input" placeholder="Duration" value={medicine.duration} onChange={event => updateMedication(index, 'duration', event.target.value)} />
                      <button type="button" className="prescription-remove" onClick={() => removeMedication(index)} aria-label={`Remove medicine ${index + 1}`}><Trash2 size={16} /></button>
                    </div>)}
                  </div>

                  {safetyResult && <div className={`prescription-safety-panel ${safetyResult.issues.length ? 'has-issues' : 'is-clear'}`}>
                    <div className="prescription-safety-title">{safetyResult.issues.length ? <ShieldAlert size={18} /> : <ShieldCheck size={18} />}<strong>{safetyResult.issues.length ? 'Safety review needed' : 'No issues found by the limited checks'}</strong></div>
                    {safetyResult.issues.map(issue => <div className="prescription-safety-issue" key={issue.id}><strong>{issue.title}</strong><span>{issue.message}</span></div>)}
                    <p>{safetyResult.coverage_note}</p>
                  </div>}
                </div>

                <div className="form-group">
                  <label className="form-label">Additional prescription, advice, and follow-up plan</label>
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
                  <span>{savingNotes ? 'Saving consultation...' : 'Save Prescription & Complete Consultation'}</span>
                </button>
              </form>
            </div>
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
