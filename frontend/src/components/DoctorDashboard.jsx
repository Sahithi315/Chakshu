import React, { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { Search, User, FileText, Activity, Save, CheckCircle2, AlertCircle, Sparkles, Clock, Calendar, FolderArchive, Plus, Trash2, ShieldAlert, ShieldCheck, Pill, Eye, Check, X, Edit3, Image as ImageIcon, ExternalLink, AlertTriangle, ZoomIn, ZoomOut, RotateCcw, Download, Maximize2 } from 'lucide-react';
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

  // Handwritten prescription viewer & doctor verification modal states
  const [viewingDoc, setViewingDoc] = useState(null);
  const [docPreviewUrl, setDocPreviewUrl] = useState(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState(null);
  const [docZoom, setDocZoom] = useState(1);
  const [editingMed, setEditingMed] = useState(null);
  const [editRegionUrl, setEditRegionUrl] = useState(null);
  const [regionModal, setRegionModal] = useState(null); // { title, ocrText, url, loading, error }

  const fetchRegionBlobUrl = async (reportId, region) => {
    if (!reportId || !region) return null;
    const qs = new URLSearchParams({
      x: String(region.x ?? 0),
      y: String(region.y ?? 0),
      w: String(region.w ?? 1),
      h: String(region.h ?? 1)
    });
    const res = await apiFetch(`/api/reports/${reportId}/region?${qs.toString()}`);
    if (!res.ok) throw new Error(`Unable to load region (${res.status})`);
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  };

  const handleInspectRegion = async (reportId, region, ocrText, title) => {
    if (regionModal?.url) {
      URL.revokeObjectURL(regionModal.url);
    }
    setRegionModal({ title: title || region?.label || 'Source Region', ocrText: ocrText || '', url: null, loading: true, error: null });
    try {
      const url = await fetchRegionBlobUrl(reportId, region);
      setRegionModal({ title: title || region?.label || 'Source Region', ocrText: ocrText || '', url, loading: false, error: null });
    } catch (err) {
      setRegionModal({ title: title || region?.label || 'Source Region', ocrText: ocrText || '', url: null, loading: false, error: err.message || 'Failed to load region preview' });
    }
  };

  const handleCloseRegionModal = () => {
    if (regionModal?.url) {
      URL.revokeObjectURL(regionModal.url);
    }
    setRegionModal(null);
  };

  // Authenticated file fetching for View Document
  const handleOpenDocumentViewer = async (doc) => {
    if (!doc) return;
    if (docPreviewUrl) {
      URL.revokeObjectURL(docPreviewUrl);
      setDocPreviewUrl(null);
    }
    setViewingDoc(doc);
    setDocLoading(true);
    setDocError(null);
    setDocZoom(1);

    try {
      const response = await apiFetch(`/api/reports/${doc.report_id}/file`);
      if (!response.ok) {
        let errMsg = `Failed to load document (${response.status}: ${response.statusText || 'Staff Authentication Required'})`;
        try {
          const errData = await response.json();
          if (errData && errData.error) errMsg = errData.error;
        } catch (_) {}
        throw new Error(errMsg);
      }
      const blob = await response.blob();
      if (!blob || blob.size === 0) {
        throw new Error('Received empty document content from server.');
      }
      const url = URL.createObjectURL(blob);
      setDocPreviewUrl(url);
    } catch (err) {
      console.error('Error fetching document:', err);
      setDocError(err.message || 'Failed to securely load document preview');
    } finally {
      setDocLoading(false);
    }
  };

  const handleCloseDocumentViewer = () => {
    if (docPreviewUrl) {
      URL.revokeObjectURL(docPreviewUrl);
      setDocPreviewUrl(null);
    }
    setViewingDoc(null);
    setDocError(null);
    setDocLoading(false);
  };

  // Prevent background scrolling and enable Escape to close when viewing document modal
  useEffect(() => {
    if (viewingDoc) {
      const originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
      const handleKeyDown = (e) => {
        if (e.key === 'Escape') {
          handleCloseDocumentViewer();
        }
      };
      window.addEventListener('keydown', handleKeyDown);
      return () => {
        document.body.style.overflow = originalOverflow;
        window.removeEventListener('keydown', handleKeyDown);
      };
    }
  }, [viewingDoc]);

  // Clean up object URL on unmount
  useEffect(() => {
    return () => {
      if (docPreviewUrl) {
        URL.revokeObjectURL(docPreviewUrl);
      }
    };
  }, [docPreviewUrl]);

  // Format frequency to concise standard medical representation
  const formatFrequency = (freq) => {
    if (!freq || freq === 'Not specified') return 'Not specified';
    const lower = freq.toLowerCase();
    if (lower.includes('sos') || lower.includes('as needed') || lower.includes('prn')) {
      return 'SOS (As needed)';
    }
    if (lower.includes('tds') || lower.includes('tid') || lower.includes('thrice')) {
      if (lower.includes('1-1-1')) return 'TDS (1-1-1)';
      return 'TDS (Three times daily)';
    }
    if (lower.includes('bd') || lower.includes('bid') || lower.includes('twice')) {
      if (lower.includes('1-0-1')) return 'BD (1-0-1)';
      return 'BD (Twice daily)';
    }
    if (lower.includes('od') || lower.includes('qd') || lower.includes('once daily')) {
      if (lower.includes('1-0-0')) return 'OD (1-0-0)';
      return 'OD (Once daily)';
    }
    if (lower.includes('hs') || lower.includes('bedtime')) {
      return 'HS (At bedtime)';
    }
    const match = freq.match(/(\d+[-–—]\d+[-–—]\d+|\d+[-–—]\d+)/);
    if (match) return match[1].replace(/[–—]/g, '-');
    return freq;
  };

  const handleDownloadDoc = () => {
    if (!docPreviewUrl || !viewingDoc) return;
    const a = document.createElement('a');
    a.href = docPreviewUrl;
    a.download = viewingDoc.filename || 'prescription-document';
    document.body.appendChild(a);
    a.click();
    a.remove();
  };

  // Handle doctor confirming, correcting, or rejecting extracted medications
  const handleVerifyMedication = async (medId, decision, correctedValue = null) => {
    if (!visitData) return;
    try {
      const response = await apiFetch('/api/doctor/decision', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visitData.visit_id,
          patient_id: visitData.patient_id,
          item_id: medId,
          part_type: 'medication',
          decision,
          corrected_value: correctedValue
        })
      });
      if (response.ok) {
        setVisitData(prev => {
          if (!prev) return prev;
          const updatedMeds = (prev.extracted_medications || []).map(m => {
            if (m.med_id === medId) {
              const updated = { ...m, verification_status: decision };
              if (correctedValue && typeof correctedValue === 'object') {
                Object.assign(updated, correctedValue);
                updated.corrected_data = correctedValue;
              }
              return updated;
            }
            return m;
          });
          const next = { ...prev, extracted_medications: updatedMeds };
          visitCacheRef.current.set(prev.visit_id, next);
          return next;
        });
      }
    } catch (err) {
      console.error('Failed to save medication decision', err);
    }
  };

  const handleStartEditMed = async (med) => {
    if (editRegionUrl) {
      URL.revokeObjectURL(editRegionUrl);
      setEditRegionUrl(null);
    }
    const isUnclearName = (med.medicine_name || '').toLowerCase().includes('unclear');
    setEditingMed({
      med_id: med.med_id,
      report_id: med.report_id,
      raw_text: med.raw_text || med.source_line || '',
      source_region: med.source_region || null,
      medicine_name: isUnclearName ? '' : (med.medicine_name || ''),
      medicine_type: med.medicine_type && med.medicine_type !== 'Not specified' ? med.medicine_type : 'Not specified',
      strength: med.strength && med.strength !== 'Not specified' ? med.strength : '',
      dosage: med.dosage && med.dosage !== 'Not specified' ? med.dosage : '',
      frequency: med.frequency && med.frequency !== 'Not specified' ? med.frequency : '',
      timing: med.timing && med.timing !== 'Not specified' ? med.timing : '',
      duration: med.duration && med.duration !== 'Not specified' ? med.duration : '',
      quantity: med.quantity && med.quantity !== 'Not specified' ? med.quantity : '',
      route: med.route && med.route !== 'Not specified' ? med.route : '',
      instructions: med.instructions && med.instructions !== 'Not specified' ? med.instructions : ''
    });
    if (med.report_id && med.source_region) {
      try {
        const url = await fetchRegionBlobUrl(med.report_id, med.source_region);
        setEditRegionUrl(url);
      } catch (_) {}
    }
  };

  const handleCloseEditMed = () => {
    if (editRegionUrl) {
      URL.revokeObjectURL(editRegionUrl);
      setEditRegionUrl(null);
    }
    setEditingMed(null);
  };

  const handleSaveMedEdit = async (e) => {
    e.preventDefault();
    if (!editingMed) return;
    const { med_id, report_id, raw_text, source_region, ...corrections } = editingMed;
    await handleVerifyMedication(med_id, 'corrected', corrections);
    handleCloseEditMed();
  };

  const handleAddExtractedToPrescription = (med) => {
    const isCancelled = med.is_cancelled || (med.instructions && med.instructions.toLowerCase().includes('cancelled'));
    if (isCancelled) {
      alert('This item was crossed out / cancelled on the prescription note and cannot be added to active consultation.');
      return;
    }
    const medName = med.medicine_name && !med.medicine_name.includes('Unclear') ? med.medicine_name : '';
    const medStrength = med.strength && med.strength !== 'Not specified' ? med.strength : (med.dosage && med.dosage !== 'Not specified' && med.dosage !== 'Unclear' ? med.dosage : '');
    const medFreq = med.frequency && med.frequency !== 'Not specified' && med.frequency !== 'Unclear' ? med.frequency : '';
    const medDur = med.duration && med.duration !== 'Not specified' && med.duration !== 'Unclear' ? med.duration : '';

    setMedications(prev => {
      const hasEmptyOnly = prev.length === 1 && !prev[0].name.trim();
      const newRow = {
        name: medName,
        strength: medStrength,
        dose: '1',
        frequency: medFreq,
        duration: medDur
      };
      if (hasEmptyOnly) {
        return [newRow];
      }
      return [...prev, newRow];
    });
  };
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

            {/* C. MEDICATIONS & HANDWRITTEN PRESCRIPTIONS (OCR PIPELINE) */}
            <details className="doctor-detail-section" open={extractedMeds.length > 0}>
              <summary className="doctor-detail-summary">
                <Pill size={18} style={{ color: '#2563eb' }} />
                <span>
                  <strong>Handwritten &amp; Document Prescriptions</strong>
                  <small>{extractedMeds.length} prescription item{extractedMeds.length === 1 ? '' : 's'}</small>
                </span>
              </summary>
              <div className="doctor-detail-body">
                <div className="card-subtitle" style={{ marginBottom: '12px' }}>
                  Review extracted items against the original prescription before confirming or prescribing.
                </div>

                {/* Detected vs Reliably Identified Summary Banner */}
                {(() => {
                  const isCancelledMed = (m) =>
                    Boolean(
                      m.is_cancelled ||
                      (m.instructions && m.instructions.toLowerCase().includes('cancelled')) ||
                      m.review_status === 'cancelled_by_prescriber' ||
                      (m.medicine_name && m.medicine_name.toLowerCase().includes('cancelled'))
                    );
                  const detectedCount = extractedMeds.length;
                  const activeMeds = extractedMeds.filter(m => !isCancelledMed(m) && (m.verification_status || '').toLowerCase() !== 'rejected');
                  const identifiedCount = activeMeds.filter(
                    m => m.medicine_name && !m.medicine_name.toLowerCase().includes('unclear')
                  ).length;

                  if (detectedCount > 0 && identifiedCount === 0) {
                    return (
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '10px',
                        background: '#fffbeb', border: '1px solid #fde68a',
                        borderRadius: '12px', padding: '10px 14px', marginBottom: '14px',
                        fontSize: '0.88rem', color: '#92400e', fontWeight: 600
                      }}>
                        <AlertTriangle size={17} style={{ color: '#d97706', flexShrink: 0 }} />
                        <span>
                          {detectedCount} possible {detectedCount === 1 ? 'entry' : 'entries'} detected. 0 medicines reliably identified. Doctor verification required.
                        </span>
                      </div>
                    );
                  }
                  if (detectedCount > 0 && identifiedCount < activeMeds.length) {
                    return (
                      <div style={{
                        display: 'flex', alignItems: 'center', gap: '10px',
                        background: '#fffbeb', border: '1px solid #fde68a',
                        borderRadius: '12px', padding: '10px 14px', marginBottom: '14px',
                        fontSize: '0.86rem', color: '#92400e'
                      }}>
                        <AlertTriangle size={17} style={{ color: '#d97706', flexShrink: 0 }} />
                        <span>
                          <strong>{detectedCount} possible entries detected.</strong> {identifiedCount} medicine{identifiedCount === 1 ? '' : 's'} reliably identified; {activeMeds.length - identifiedCount} require doctor verification.
                        </span>
                      </div>
                    );
                  }
                  return null;
                })()}

                {extractedMeds.length === 0 ? (
                  <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                    {uploadedDocs.length > 0 ? (
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', color: '#b45309' }}>
                        <AlertTriangle size={24} style={{ color: '#d97706' }} />
                        <strong>0 medicines reliably identified. Doctor verification required.</strong>
                        <span style={{ fontSize: '0.85rem', color: '#78350f' }}>
                          Please inspect the original document in Uploaded Documents below.
                        </span>
                      </div>
                    ) : (
                      'No prescription medications extracted from uploaded documents for this visit.'
                    )}
                  </div>
                ) : (
                  <div className="lab-table-container">
                    <table className="lab-table">
                      <thead>
                        <tr>
                          <th>Medicine Name</th>
                          <th>Type</th>
                          <th>Strength</th>
                          <th>Dosage</th>
                          <th>Frequency</th>
                          <th>Timing</th>
                          <th>Duration</th>
                          <th>Route</th>
                          <th>Review Status</th>
                          <th>Actions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {extractedMeds.map((med, mIdx) => {
                          const status = (med.verification_status || 'unverified').toLowerCase();
                          const isConfirmed = status === 'confirmed';
                          const isCorrected = status === 'corrected';
                          const isRejected = status === 'rejected';
                          const isCancelled = med.is_cancelled ||
                                              (med.instructions && med.instructions.toLowerCase().includes('cancelled')) ||
                                              (med.review_status === 'cancelled_by_prescriber') ||
                                              (med.medicine_name && med.medicine_name.toLowerCase().includes('cancelled'));
                          const isUnclearName = Boolean(med.medicine_name && med.medicine_name.toLowerCase().includes('unclear'));
                          const isUnclear = !isCancelled && (isUnclearName || med.is_uncertain || med.confidence_level === 'unclear');
                          const conf = med.confidence != null ? med.confidence : 0.0;
                          const fc = med.field_confidences || {};
                          const fieldTitle = (key, fallbackVal) =>
                            fc[key] ? `${fallbackVal || ''} (Field confidence: ${Math.round(fc[key])}%)`.trim() : (fallbackVal || '');

                          return (
                            <tr
                              key={med.med_id || mIdx}
                              style={{
                                background: isCancelled ? '#fff1f2' : isRejected ? '#fef2f2' : isConfirmed ? '#f0fdf4' : isCorrected ? '#eff6ff' : isUnclear ? '#fffbeb' : 'inherit',
                                opacity: isRejected ? 0.55 : 1
                              }}
                            >
                              {/* 1. Medicine Name */}
                              <td title={fieldTitle('medicine_name', med.medicine_name)}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                                  <span style={{
                                    fontWeight: 600,
                                    color: isCancelled ? '#991b1b' : isUnclear ? '#b45309' : '#0f172a',
                                    fontSize: '0.9rem',
                                    textDecoration: isCancelled ? 'line-through' : 'none'
                                  }}>
                                    {med.medicine_name}
                                  </span>
                                  {med.source_region && med.report_id && (
                                    <button
                                      type="button"
                                      onClick={() => handleInspectRegion(med.report_id, med.source_region, '', `${med.source_region.label || 'Prescription Entry'} — Handwriting Crop`)}
                                      title="Inspect original handwriting crop"
                                      style={{ background: '#eff6ff', border: '1px solid #bfdbfe', color: '#1d4ed8', fontSize: '0.7rem', padding: '1px 6px', borderRadius: '5px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '3px', fontWeight: 600 }}
                                    >
                                      <Eye size={10} />
                                      <span>Crop</span>
                                    </button>
                                  )}
                                </div>
                              </td>

                              {/* 2. Type */}
                              <td title={fieldTitle('medicine_type', med.medicine_type)}>
                                <span style={{ fontWeight: 500, color: med.medicine_type && med.medicine_type !== 'Not specified' ? '#334155' : '#94a3b8', fontSize: '0.82rem' }}>
                                  {med.medicine_type && med.medicine_type !== 'Not specified' ? med.medicine_type : 'Not specified'}
                                </span>
                              </td>

                              {/* 3. Strength */}
                              <td title={fieldTitle('strength', med.strength)} style={{ fontWeight: 600, color: med.strength && med.strength !== 'Not specified' ? '#2563eb' : '#94a3b8', fontSize: '0.83rem' }}>
                                {med.strength && med.strength !== 'Not specified' ? med.strength : 'Not specified'}
                              </td>

                              {/* 4. Dosage */}
                              <td title={fieldTitle('dosage', med.dosage)} style={{ color: med.dosage && med.dosage !== 'Not specified' ? '#0f172a' : '#94a3b8', fontSize: '0.83rem' }}>
                                {med.dosage && med.dosage !== 'Not specified' ? med.dosage : 'Not specified'}
                              </td>

                              {/* 5. Frequency */}
                              <td title={fieldTitle('frequency', med.frequency)} style={{ fontWeight: 600, color: med.frequency && med.frequency !== 'Not specified' ? '#0f172a' : '#94a3b8', fontSize: '0.83rem' }}>
                                {formatFrequency(med.frequency)}
                              </td>

                              {/* 6. Timing */}
                              <td title={fieldTitle('timing', med.timing)} style={{ color: med.timing && med.timing !== 'Not specified' ? '#0f172a' : '#94a3b8', fontSize: '0.83rem' }}>
                                {med.timing || 'Not specified'}
                              </td>

                              {/* 7. Duration */}
                              <td title={fieldTitle('duration', med.duration)} style={{ color: med.duration && med.duration !== 'Not specified' ? '#0f172a' : '#94a3b8', fontSize: '0.83rem' }}>
                                {med.duration || 'Not specified'}
                              </td>

                              {/* 8. Route */}
                              <td title={fieldTitle('route', med.route)} style={{ color: med.route && med.route !== 'Not specified' ? '#0f172a' : '#94a3b8', fontSize: '0.83rem' }}>
                                {med.route && med.route !== 'Not specified' ? med.route : 'Not specified'}
                              </td>

                              {/* 9. Review Status */}
                              <td>
                                {isCancelled ? (
                                  <span style={{ background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca', borderRadius: '6px', fontSize: '0.72rem', padding: '2px 7px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                    <X size={11} /> Cancelled
                                  </span>
                                ) : isConfirmed ? (
                                  <span className="badge-status badge-normal" style={{ fontSize: '0.72rem', padding: '2px 7px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                    <Check size={11} /> Confirmed
                                  </span>
                                ) : isCorrected ? (
                                  <span className="badge-status badge-low" style={{ fontSize: '0.72rem', padding: '2px 7px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                    <Edit3 size={11} /> Corrected
                                  </span>
                                ) : isRejected ? (
                                  <span className="badge-status badge-high" style={{ fontSize: '0.72rem', padding: '2px 7px', display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                    <X size={11} /> Rejected
                                  </span>
                                ) : isUnclear ? (
                                  <span style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a', borderRadius: '6px', fontSize: '0.72rem', padding: '2px 7px', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
                                    <AlertTriangle size={11} /> Review ({Math.round(conf)}%)
                                  </span>
                                ) : (
                                  <span style={{ background: '#f1f5f9', color: '#475569', border: '1px solid #e2e8f0', borderRadius: '6px', fontSize: '0.72rem', padding: '2px 7px', fontWeight: 600 }}>
                                    Unverified ({Math.round(conf)}%)
                                  </span>
                                )}
                              </td>

                              {/* 10. Actions */}
                              <td>
                                <div style={{ display: 'flex', gap: '5px', flexWrap: 'wrap', alignItems: 'center' }}>
                                  {!isConfirmed && !isCancelled && !isRejected && !isUnclearName && (
                                    <button
                                      type="button"
                                      className="btn-primary"
                                      onClick={() => handleVerifyMedication(med.med_id, 'confirmed')}
                                      title="Confirm extracted medicine"
                                      style={{ padding: '3px 7px', fontSize: '0.74rem', background: '#059669', borderColor: '#059669', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                                    >
                                      <Check size={11} />
                                      <span>Confirm</span>
                                    </button>
                                  )}

                                  {!isCancelled && (
                                    <button
                                      type="button"
                                      className="btn-secondary"
                                      onClick={() => handleStartEditMed(med)}
                                      title="Edit and verify against original handwriting crop"
                                      style={{ padding: '3px 7px', fontSize: '0.74rem', display: 'inline-flex', alignItems: 'center', gap: '3px', ...(isUnclearName ? { background: '#fef3c7', borderColor: '#f59e0b', color: '#92400e', fontWeight: 700 } : {}) }}
                                    >
                                      <Edit3 size={11} />
                                      <span>Edit</span>
                                    </button>
                                  )}

                                  {!isRejected && (
                                    <button
                                      type="button"
                                      className="btn-secondary"
                                      onClick={() => handleVerifyMedication(med.med_id, 'rejected')}
                                      title={isCancelled ? 'Dismiss cancelled item' : 'Reject incorrect extraction'}
                                      style={{ padding: '3px 7px', fontSize: '0.74rem', color: '#dc2626', borderColor: '#fca5a5', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                                    >
                                      <X size={11} />
                                      <span>{isCancelled ? 'Dismiss' : 'Reject'}</span>
                                    </button>
                                  )}

                                  {(isConfirmed || isCorrected) && !isCancelled && !isRejected && !isUnclearName && (
                                    <button
                                      type="button"
                                      className="btn-secondary"
                                      onClick={() => handleAddExtractedToPrescription(med)}
                                      title="Add verified medicine to consultation prescription"
                                      style={{ padding: '3px 7px', fontSize: '0.74rem', color: '#2563eb', borderColor: '#bfdbfe', background: '#eff6ff', display: 'inline-flex', alignItems: 'center', gap: '3px' }}
                                    >
                                      <Plus size={11} />
                                      <span>Prescribe</span>
                                    </button>
                                  )}
                                </div>
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

            {/* D. IMPORTANT MEDICAL FINDINGS (4 CLEAR SECTIONS) */}
            <details className="doctor-detail-section" open={docFindings.length > 0}>
              <summary className="doctor-detail-summary">
                <AlertCircle size={18} style={{ color: '#2563eb' }} />
                <span><strong>Important Medical Findings</strong><small>Symptoms, vitals, diagnosis &amp; doctor summary</small></span>
              </summary>
              <div className="doctor-detail-body">
                {(() => {
                  const symptomFindings = docFindings.filter(f => f.category === 'symptoms_observations');
                  const vitalFindings = docFindings.filter(f => f.category === 'vitals');
                  const conditionFinding = docFindings.find(f => f.category === 'condition' || f.category === 'clinical_impression');
                  const adviceFindings = docFindings.filter(f => f.category === 'advice');
                  const summaryFinding = docFindings.find(f => f.category === 'insight');
                  const abnormalLabs = docFindings.filter(f => f.category === 'abnormal_lab');

                  if (docFindings.length === 0) {
                    return (
                      <div style={{ padding: '24px', textAlign: 'center', color: '#64748b', background: '#f8fafc', borderRadius: '14px' }}>
                        No clinical findings extracted from uploaded documents for this visit.
                      </div>
                    );
                  }

                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                      {/* 1. Symptoms / Observations */}
                      <div style={{
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderLeft: '4px solid #7c3aed',
                        borderRadius: '12px',
                        padding: '12px 16px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#5b21b6', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            1. Symptoms / Observations
                          </div>
                          {symptomFindings[0]?.source_region && symptomFindings[0]?.report_id && (
                            <button
                              type="button"
                              onClick={() => handleInspectRegion(symptomFindings[0].report_id, symptomFindings[0].source_region, '', 'Symptoms / Observations — Handwriting Crop')}
                              style={{ background: '#f5f3ff', border: '1px solid #ddd6fe', color: '#6d28d9', fontSize: '0.7rem', padding: '2px 7px', borderRadius: '6px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
                            >
                              <Eye size={10} />
                              <span>View Handwriting</span>
                            </button>
                          )}
                        </div>
                        {symptomFindings.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {symptomFindings.map((sf, sIdx) => (
                              <div key={sf.finding_id || sIdx} style={{ fontSize: '0.9rem', color: '#1e293b', lineHeight: 1.45, whiteSpace: 'pre-line' }}>
                                {sf.detail}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: '0.86rem', color: '#64748b' }}>
                            No symptoms or observations noted.
                          </div>
                        )}
                      </div>

                      {/* 2. Vital Signs */}
                      <div style={{
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderLeft: '4px solid #0891b2',
                        borderRadius: '12px',
                        padding: '12px 16px'
                      }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                          <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#155e75', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                            2. Vital Signs
                          </div>
                          {vitalFindings[0]?.source_region && vitalFindings[0]?.report_id && (
                            <button
                              type="button"
                              onClick={() => handleInspectRegion(vitalFindings[0].report_id, vitalFindings[0].source_region, '', 'Vital Signs — Handwriting Crop')}
                              style={{ background: '#ecfeff', border: '1px solid #a5f3fc', color: '#0e7490', fontSize: '0.7rem', padding: '2px 7px', borderRadius: '6px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}
                            >
                              <Eye size={10} />
                              <span>View Handwriting</span>
                            </button>
                          )}
                        </div>
                        {vitalFindings.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {vitalFindings.map((vf, vIdx) => (
                              <div key={vf.finding_id || vIdx} style={{ fontSize: '0.9rem', fontWeight: vf.detail?.toLowerCase().includes('could not be reliably') ? 400 : 600, color: vf.detail?.toLowerCase().includes('could not be reliably') ? '#64748b' : '#0f172a', lineHeight: 1.45 }}>
                                {vf.detail}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: '0.86rem', color: '#64748b' }}>
                            Vital signs could not be reliably identified.
                          </div>
                        )}
                      </div>

                      {/* 3. Diagnosis */}
                      <div style={{
                        background: '#f8fafc',
                        border: '1px solid #e2e8f0',
                        borderLeft: '4px solid #2563eb',
                        borderRadius: '12px',
                        padding: '12px 16px'
                      }}>
                        <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#1e40af', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '4px' }}>
                          3. Diagnosis
                        </div>
                        <div style={{ fontSize: '0.98rem', fontWeight: conditionFinding && !conditionFinding.detail?.toLowerCase().includes('no explicit diagnosis') ? 700 : 500, color: conditionFinding && !conditionFinding.detail?.toLowerCase().includes('no explicit diagnosis') ? '#0f172a' : '#64748b' }}>
                          {conditionFinding ? conditionFinding.detail : 'No explicit diagnosis identified.'}
                        </div>
                      </div>

                      {/* 4. Doctor Instructions & AI Summary */}
                      <div style={{
                        background: '#f0f9ff',
                        border: '1px solid #bae6fd',
                        borderLeft: '4px solid #0284c7',
                        borderRadius: '12px',
                        padding: '12px 16px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '10px'
                      }}>
                        <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#0369a1', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                          4. Doctor Instructions &amp; AI Summary
                        </div>

                        <div>
                          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#065f46', marginBottom: '4px' }}>
                            Doctor Instructions
                          </div>
                          {adviceFindings.length > 0 ? (
                            <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                              {adviceFindings.map((adv, aIdx) => (
                                <li key={adv.finding_id || aIdx} style={{ fontSize: '0.88rem', color: '#1e293b', lineHeight: 1.45, whiteSpace: 'pre-line' }}>
                                  <span>{adv.detail}</span>
                                  {adv.source_region && adv.report_id && (
                                    <button
                                      type="button"
                                      onClick={() => handleInspectRegion(adv.report_id, adv.source_region, '', 'Doctor Instructions — Handwriting Crop')}
                                      style={{ marginLeft: '8px', background: '#ecfdf5', border: '1px solid #a7f3d0', color: '#047857', fontSize: '0.68rem', padding: '1px 6px', borderRadius: '5px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '3px', fontWeight: 600 }}
                                    >
                                      <Eye size={10} />
                                      <span>View Handwriting</span>
                                    </button>
                                  )}
                                </li>
                              ))}
                            </ul>
                          ) : (
                            <div style={{ fontSize: '0.86rem', color: '#64748b' }}>
                              No explicit doctor instructions recorded.
                            </div>
                          )}
                        </div>

                        <div style={{ borderTop: '1px solid #bae6fd', paddingTop: '8px' }}>
                          <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#0369a1', marginBottom: '3px' }}>
                            Clinical Summary
                          </div>
                          <div style={{ fontSize: '0.89rem', color: '#0c4a6e', lineHeight: 1.48 }}>
                            {summaryFinding
                              ? summaryFinding.detail
                              : `${extractedMeds.length} possible entries detected. Doctor verification required.`}
                          </div>
                        </div>
                      </div>

                      {/* Optional Out-of-Range Laboratory Observations (only when lab reports have abnormal rows) */}
                      {abnormalLabs.length > 0 && (
                        <div style={{
                          background: '#fef2f2',
                          border: '1px solid #fecaca',
                          borderLeft: '4px solid #dc2626',
                          borderRadius: '12px',
                          padding: '12px 16px'
                        }}>
                          <div style={{ fontSize: '0.76rem', fontWeight: 700, color: '#991b1b', textTransform: 'uppercase', letterSpacing: '0.04em', marginBottom: '6px' }}>
                            Out-of-Range Laboratory Results
                          </div>
                          <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {abnormalLabs.map((lab, lIdx) => (
                              <li key={lab.finding_id || lIdx} style={{ fontSize: '0.88rem', color: '#7f1d1d' }}>
                                <strong>{lab.title}</strong>: {lab.detail}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  );
                })()}
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
                          const isCompleted = status === 'completed' || status === 'success' || status === 'warning';
                          const isFailed = status === 'failed' || status === 'error';
                          const isPrescription = (doc.doc_type || '').toLowerCase().includes('prescription');
                          const totalItems = doc.findings_count != null ? doc.findings_count : (labRows.length + extractedMeds.length);
                          const needsReview = isPrescription && extractedMeds.length === 0;
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
                                  needsReview ? (
                                    <span className="badge-status badge-high" style={{ background: '#fef3c7', color: '#92400e', borderColor: '#fde68a' }}>NEEDS REVIEW</span>
                                  ) : (
                                    <span className="badge-status badge-normal">COMPLETED</span>
                                  )
                                ) : isFailed ? (
                                  <span className="badge-status badge-high">FAILED</span>
                                ) : (
                                  <span className="badge-status badge-low">PROCESSING</span>
                                )}
                              </td>
                              <td style={{ fontWeight: 700, color: '#0f172a' }}>
                                {totalItems} items
                              </td>
                              <td>
                                <button
                                  type="button"
                                  onClick={() => handleOpenDocumentViewer(doc)}
                                  className="btn-secondary"
                                  style={{ fontSize: '0.78rem', padding: '5px 12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                                >
                                  <Eye size={13} />
                                  <span>View Document</span>
                                </button>
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
      {/* MODAL 1: AUTHENTICATED ORIGINAL UPLOADED PRESCRIPTION DOCUMENT VIEWER */}
      {viewingDoc && typeof document !== 'undefined' && createPortal(
        <div className="document-viewer-portal">
          {/* Layer 1: Dark Backdrop */}
          <div
            className="document-viewer-backdrop"
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              width: '100vw',
              height: '100vh',
              background: 'rgba(15, 23, 42, 0.85)',
              backdropFilter: 'blur(5px)',
              WebkitBackdropFilter: 'blur(5px)',
              zIndex: 99998,
              cursor: 'pointer'
            }}
            onClick={handleCloseDocumentViewer}
            aria-hidden="true"
          />

          {/* Layer 2: Modal Centering Container */}
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Document Viewer: ${viewingDoc.filename}`}
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              width: '100vw',
              height: '100vh',
              zIndex: 99999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '2vh 2vw',
              pointerEvents: 'none',
              overflow: 'hidden'
            }}
          >
            {/* Layer 3: Modal Card */}
            <div
              className="document-viewer-card"
              style={{
                pointerEvents: 'auto',
                background: '#ffffff',
                borderRadius: '14px',
                width: '92vw',
                maxWidth: '1600px',
                height: '88vh',
                maxHeight: '90vh',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '0 25px 60px -15px rgba(0, 0, 0, 0.6), 0 0 0 1px rgba(255, 255, 255, 0.15)',
                overflow: 'hidden',
                position: 'relative'
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Header Toolbar */}
              <div style={{
                padding: '10px 18px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: '#f8fafc',
                flexShrink: 0,
                gap: '12px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, overflow: 'hidden' }}>
                  <FileText size={18} style={{ color: '#2563eb', flexShrink: 0 }} />
                  <span style={{ fontWeight: 700, fontSize: '0.92rem', color: '#0f172a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {viewingDoc.filename}
                  </span>
                  <span style={{ fontSize: '0.72rem', background: '#e0f2fe', color: '#0369a1', padding: '2px 8px', borderRadius: '9999px', fontWeight: 600, flexShrink: 0 }}>
                    {viewingDoc.doc_type || 'Prescription Document'}
                  </span>
                </div>

                {/* Viewer Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                  {/* Zoom Controls for images */}
                  {!viewingDoc.filename?.toLowerCase().endsWith('.pdf') && viewingDoc.file_type !== 'pdf' && (
                    <div style={{ display: 'flex', alignItems: 'center', background: '#e2e8f0', borderRadius: '8px', padding: '2px 4px', gap: '2px' }}>
                      <button
                        type="button"
                        onClick={() => setDocZoom(z => Math.max(0.5, Number((z - 0.25).toFixed(2))))}
                        title="Zoom Out"
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px 6px', display: 'flex', alignItems: 'center', color: '#334155' }}
                      >
                        <ZoomOut size={15} />
                      </button>
                      <span style={{ fontSize: '0.75rem', fontWeight: 700, minWidth: '44px', textAlign: 'center', color: '#1e293b' }}>
                        {Math.round(docZoom * 100)}%
                      </span>
                      <button
                        type="button"
                        onClick={() => setDocZoom(z => Math.min(3.0, Number((z + 0.25).toFixed(2))))}
                        title="Zoom In"
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px 6px', display: 'flex', alignItems: 'center', color: '#334155' }}
                      >
                        <ZoomIn size={15} />
                      </button>
                      <button
                        type="button"
                        onClick={() => setDocZoom(1)}
                        title="Fit to Screen (100%)"
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer', padding: '4px 6px', display: 'flex', alignItems: 'center', color: '#334155', borderLeft: '1px solid #cbd5e1', marginLeft: '2px' }}
                      >
                        <Maximize2 size={14} />
                      </button>
                    </div>
                  )}

                  {/* Download Authenticated Document Blob */}
                  {docPreviewUrl && (
                    <button
                      type="button"
                      onClick={handleDownloadDoc}
                      className="btn-secondary"
                      title="Download original document"
                      style={{ fontSize: '0.78rem', padding: '5px 10px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                    >
                      <Download size={13} />
                      <span>Download</span>
                    </button>
                  )}

                  {/* Close Button */}
                  <button
                    type="button"
                    onClick={handleCloseDocumentViewer}
                    style={{ background: 'transparent', border: 'none', padding: '4px', cursor: 'pointer', color: '#64748b', display: 'flex', alignItems: 'center' }}
                    title="Close Preview (Esc)"
                  >
                    <X size={20} />
                  </button>
                </div>
              </div>

              {/* Viewer Body */}
              <div style={{
                flex: 1,
                background: '#0f172a',
                overflow: 'auto',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '16px',
                position: 'relative'
              }}>
                {docLoading ? (
                  <div style={{ color: '#f8fafc', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '14px', height: '100%', minHeight: '300px' }}>
                    <div className="spinner" style={{ width: '38px', height: '38px', border: '3px solid rgba(255,255,255,0.2)', borderTopColor: '#38bdf8', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
                    <span style={{ fontSize: '0.92rem', fontWeight: 600 }}>Loading document preview...</span>
                  </div>
                ) : docError ? (
                  <div style={{ background: '#451a1a', border: '1px solid #7f1d1d', borderRadius: '12px', padding: '28px', maxWidth: '480px', textAlign: 'center', color: '#fca5a5', margin: 'auto' }}>
                    <AlertCircle size={36} style={{ color: '#ef4444', margin: '0 auto 12px' }} />
                    <div style={{ fontWeight: 700, fontSize: '1.05rem', marginBottom: '8px', color: '#fecaca' }}>Unable to Display Document</div>
                    <div style={{ fontSize: '0.88rem', marginBottom: '18px', color: '#fca5a5', lineHeight: 1.4 }}>{docError}</div>
                    <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
                      <button
                        type="button"
                        onClick={() => handleOpenDocumentViewer(viewingDoc)}
                        className="btn-primary"
                        style={{ fontSize: '0.82rem', padding: '6px 18px' }}
                      >
                        Retry Loading
                      </button>
                      <button
                        type="button"
                        onClick={handleCloseDocumentViewer}
                        className="btn-secondary"
                        style={{ fontSize: '0.82rem', padding: '6px 18px', color: '#f8fafc', borderColor: '#7f1d1d' }}
                      >
                        Close Preview
                      </button>
                    </div>
                  </div>
                ) : docPreviewUrl ? (
                  viewingDoc.file_type === 'pdf' || viewingDoc.filename?.toLowerCase().endsWith('.pdf') ? (
                    <iframe
                      src={`${docPreviewUrl}#toolbar=1&navpanes=1`}
                      title={viewingDoc.filename}
                      style={{ width: '100%', height: '100%', minHeight: '500px', border: 'none', borderRadius: '6px', background: '#fff' }}
                    />
                  ) : (
                    <div style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      minWidth: '100%',
                      minHeight: '100%',
                      overflow: 'auto',
                      padding: '8px'
                    }}>
                      <img
                        src={docPreviewUrl}
                        alt={viewingDoc.filename}
                        style={{
                          maxHeight: docZoom === 1 ? 'calc(88vh - 120px)' : 'none',
                          maxWidth: docZoom === 1 ? 'calc(92vw - 60px)' : 'none',
                          height: docZoom === 1 ? 'auto' : `${docZoom * 76}vh`,
                          width: 'auto',
                          objectFit: 'contain',
                          borderRadius: '6px',
                          boxShadow: '0 12px 40px rgba(0, 0, 0, 0.75)',
                          transition: 'height 0.15s ease-out',
                          userSelect: 'none'
                        }}
                      />
                    </div>
                  )
                ) : null}
              </div>

              {/* Modal Footer */}
              <div style={{
                padding: '8px 18px',
                background: '#f8fafc',
                borderTop: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'flex-end',
                alignItems: 'center',
                flexShrink: 0
              }}>
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={handleCloseDocumentViewer}
                  style={{ padding: '4px 14px', fontSize: '0.78rem' }}
                >
                  Close Preview
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* MODAL 2: EDIT EXTRACTED PRESCRIPTION MEDICATION */}
      {editingMed && typeof document !== 'undefined' && createPortal(
        <div className="med-editor-portal">
          <div
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              width: '100vw',
              height: '100vh',
              background: 'rgba(15, 23, 42, 0.75)',
              backdropFilter: 'blur(4px)',
              WebkitBackdropFilter: 'blur(4px)',
              zIndex: 99998,
              cursor: 'pointer'
            }}
            onClick={handleCloseEditMed}
            aria-hidden="true"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Edit Medicine"
            style={{
              position: 'fixed',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              width: '100vw',
              height: '100vh',
              zIndex: 99999,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '20px',
              pointerEvents: 'none',
              overflow: 'auto'
            }}
          >
            <div
              style={{
                pointerEvents: 'auto',
                background: '#ffffff',
                borderRadius: '16px',
                width: '90%',
                maxWidth: '680px',
                maxHeight: '90vh',
                display: 'flex',
                flexDirection: 'column',
                boxShadow: '0 20px 40px rgba(0,0,0,0.3)',
                overflow: 'hidden',
                position: 'relative'
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{
                padding: '16px 20px',
                borderBottom: '1px solid #e2e8f0',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                background: '#f8fafc'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Edit3 size={18} style={{ color: '#2563eb' }} />
                  <strong style={{ fontSize: '1rem', color: '#0f172a' }}>Verify &amp; Correct Extracted Medicine Details</strong>
                </div>
                <button
                  type="button"
                  onClick={handleCloseEditMed}
                  style={{ background: 'transparent', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: '#64748b' }}
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleSaveMedEdit} style={{ padding: '20px', overflowY: 'auto' }}>
                {editRegionUrl && (
                  <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: '10px', padding: '12px', marginBottom: '16px' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: '#334155', textTransform: 'uppercase', marginBottom: '6px' }}>
                      Original Handwriting Crop
                    </div>
                    <div style={{ textAlign: 'center', background: '#ffffff', padding: '8px', borderRadius: '8px', border: '1px solid #e2e8f0' }}>
                      <img src={editRegionUrl} alt="Original handwritten prescription region" style={{ maxWidth: '100%', maxHeight: '160px', objectFit: 'contain' }} />
                    </div>
                  </div>
                )}
                <div style={{ display: 'grid', gridTemplateColumns: '1.6fr 1.2fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Medicine Name *</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.medicine_name}
                      onChange={(e) => setEditingMed({ ...editingMed, medicine_name: e.target.value })}
                      placeholder="e.g. Rockcef, Paracetamol, Amoxicillin"
                      required
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Dosage Form / Type</label>
                    <select
                      className="form-input"
                      value={editingMed.medicine_type || 'Tablet'}
                      onChange={(e) => setEditingMed({ ...editingMed, medicine_type: e.target.value })}
                    >
                      <option value="Tablet">Tablet</option>
                      <option value="Capsule">Capsule</option>
                      <option value="Syrup / Suspension">Syrup / Suspension</option>
                      <option value="Ointment">Ointment</option>
                      <option value="Cream">Cream</option>
                      <option value="Gel">Gel</option>
                      <option value="Injection">Injection</option>
                      <option value="Drops">Drops</option>
                      <option value="Inhaler / Spray">Inhaler / Spray</option>
                      <option value="Sachet">Sachet</option>
                      <option value="Shampoo">Shampoo</option>
                      <option value="Lotion">Lotion</option>
                      <option value="Not specified">Not specified</option>
                    </select>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Strength</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.strength || ''}
                      onChange={(e) => setEditingMed({ ...editingMed, strength: e.target.value })}
                      placeholder="e.g. 200 mg, 500 mg, 2%"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Dosage (per dose)</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.dosage}
                      onChange={(e) => setEditingMed({ ...editingMed, dosage: e.target.value })}
                      placeholder="e.g. 1 tablet, 5 ml, 200 mg"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Frequency</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.frequency}
                      onChange={(e) => setEditingMed({ ...editingMed, frequency: e.target.value })}
                      placeholder="e.g. Twice daily (1-0-1), Once daily, TDS, SOS"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Timing</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.timing}
                      onChange={(e) => setEditingMed({ ...editingMed, timing: e.target.value })}
                      placeholder="e.g. After food, Before food, Bedtime"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Duration</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.duration}
                      onChange={(e) => setEditingMed({ ...editingMed, duration: e.target.value })}
                      placeholder="e.g. 5 days, 10 tablets (5 days), 1 week"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Quantity</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.quantity || ''}
                      onChange={(e) => setEditingMed({ ...editingMed, quantity: e.target.value })}
                      placeholder="e.g. 10 tablets, 1 bottle, 1 tube"
                    />
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Route</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.route}
                      onChange={(e) => setEditingMed({ ...editingMed, route: e.target.value })}
                      placeholder="e.g. Oral, Topical, Inhalation"
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Instructions / Advice</label>
                    <input
                      type="text"
                      className="form-input"
                      value={editingMed.instructions}
                      onChange={(e) => setEditingMed({ ...editingMed, instructions: e.target.value })}
                      placeholder="e.g. Dispense as prescribed, Take after food"
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '16px' }}>
                  <button type="button" className="btn-secondary" onClick={handleCloseEditMed}>
                    Cancel
                  </button>
                  <button type="submit" className="btn-primary">
                    Save Doctor Corrections
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* MODAL 3: SOURCE REGION HANDWRITING VERIFICATION VIEWER */}
      {regionModal && typeof document !== 'undefined' && createPortal(
        <div className="region-viewer-portal">
          <div
            style={{
              position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
              background: 'rgba(15, 23, 42, 0.78)', backdropFilter: 'blur(4px)',
              zIndex: 99998, cursor: 'pointer'
            }}
            onClick={handleCloseRegionModal}
            aria-hidden="true"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label={regionModal.title}
            style={{
              position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
              zIndex: 99999, display: 'flex', alignItems: 'center', justifyContent: 'center',
              padding: '20px', pointerEvents: 'none'
            }}
          >
            <div
              style={{
                pointerEvents: 'auto', background: '#ffffff', borderRadius: '14px',
                width: '92%', maxWidth: '760px', maxHeight: '85vh',
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
                boxShadow: '0 22px 50px rgba(0,0,0,0.4)'
              }}
              onClick={(e) => e.stopPropagation()}
            >
              <div style={{ padding: '12px 18px', borderBottom: '1px solid #e2e8f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#f8fafc' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Eye size={17} style={{ color: '#2563eb' }} />
                  <strong style={{ fontSize: '0.96rem', color: '#0f172a' }}>{regionModal.title}</strong>
                </div>
                <button type="button" onClick={handleCloseRegionModal} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: '#64748b' }}>
                  <X size={19} />
                </button>
              </div>
              <div style={{ padding: '18px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ background: '#0f172a', borderRadius: '10px', padding: '16px', minHeight: '160px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  {regionModal.loading ? (
                    <span style={{ color: '#e2e8f0', fontSize: '0.9rem' }}>Loading original handwriting crop...</span>
                  ) : regionModal.error ? (
                    <span style={{ color: '#fca5a5', fontSize: '0.9rem' }}>{regionModal.error}</span>
                  ) : regionModal.url ? (
                    <img src={regionModal.url} alt={regionModal.title} style={{ maxWidth: '100%', maxHeight: '420px', objectFit: 'contain', borderRadius: '6px', background: '#fff' }} />
                  ) : null}
                </div>
              </div>
              <div style={{ padding: '10px 18px', borderTop: '1px solid #e2e8f0', display: 'flex', justifyContent: 'flex-end', background: '#f8fafc' }}>
                <button type="button" className="btn-secondary" onClick={handleCloseRegionModal} style={{ fontSize: '0.8rem', padding: '5px 14px' }}>
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
}
