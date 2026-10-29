import React, { useState, useRef, useEffect } from 'react';
import {
  User, ClipboardList, Upload, Camera, CheckCircle2, Sparkles,
  ArrowRight, ShieldCheck, AlertCircle, RefreshCw, X, Plus, FileText,
  Image as ImageIcon, Copy, Check, UserPlus, History, KeyRound, Search
} from 'lucide-react';
import SummaryCard from './SummaryCard';

export default function PatientIntake() {
  const [step, setStep] = useState(1); // 1: Register/Check-in, 2: Questionnaire, 3: Reports, 4: Done
  const [patient, setPatient] = useState(null);
  const [visit, setVisit] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [generatedSummary, setGeneratedSummary] = useState(null);
  const [pastVisits, setPastVisits] = useState([]);
  const [isReturningPatient, setIsReturningPatient] = useState(false);

  // Check-in Tab Mode: 'new' | 'returning'
  const [checkinMode, setCheckinMode] = useState('new');

  // New Patient Form States
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [age, setAge] = useState('35');
  const [gender, setGender] = useState('Male');
  const [newPatientRegistered, setNewPatientRegistered] = useState(false);
  const [copiedMRN, setCopiedMRN] = useState(false);

  // Returning Patient Form States
  const [returningMRN, setReturningMRN] = useState('');
  const [verificationPhone, setVerificationPhone] = useState('');
  const [returningError, setReturningError] = useState('');
  const [isVerifyingReturning, setIsVerifyingReturning] = useState(false);

  // Forgot MRN Lookup States
  const [showForgotMRN, setShowForgotMRN] = useState(false);
  const [lookupPhone, setLookupPhone] = useState('');
  const [lookupName, setLookupName] = useState('');
  const [lookupResults, setLookupResults] = useState([]);
  const [isLookingUp, setIsLookingUp] = useState(false);

  // Identity conflict state
  const [nameConflict, setNameConflict] = useState(null);

  // Step 2 Intake Form States
  const [reason, setReason] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [duration, setDuration] = useState('1 to 3 days');
  const [severity, setSeverity] = useState('Mild (manageable)');
  const [associated, setAssociated] = useState('');
  const [conditions, setConditions] = useState('');
  const [medications, setMedications] = useState('');
  const [allergies, setAllergies] = useState('');

  // Step 3: Reports & Scan state
  const [activeUploadTab, setActiveUploadTab] = useState('camera'); // 'camera' | 'file'
  const [uploadStatus, setUploadStatus] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedPages, setUploadedPages] = useState([]);
  const [groupId] = useState(() => `GRP-${Date.now()}-${Math.random().toString(36).substring(2, 6).toUpperCase()}`);

  // In-browser camera states
  const [isCameraActive, setIsCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState(null);
  const [capturedBlob, setCapturedBlob] = useState(null);
  const [previewUrl, setPreviewUrl] = useState(null);

  const videoRef = useRef(null);
  const streamRef = useRef(null);

  // Stop camera tracks helper
  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
    setIsCameraActive(false);
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, []);

  const copyMRNToClipboard = (mrn) => {
    if (navigator?.clipboard?.writeText && mrn) {
      navigator.clipboard.writeText(mrn);
      setCopiedMRN(true);
      setTimeout(() => setCopiedMRN(false), 2200);
    }
  };

  // 1. In-browser camera start
  const startCamera = async () => {
    setCameraError(null);
    try {
      if (!navigator?.mediaDevices?.getUserMedia) {
        throw new Error('In-browser camera access is not supported by your browser. Please use the Device Camera button below.');
      }
      stopCamera();
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 1920 },
          height: { ideal: 1080 }
        },
        audio: false
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setIsCameraActive(true);
    } catch (err) {
      console.warn('Live camera access error:', err);
      setCameraError(err.message || 'Camera permission was denied or camera is unavailable. Use the device camera app below.');
      setIsCameraActive(false);
    }
  };

  // 2. Capture frame from video to canvas
  const handleCaptureSnapshot = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      if (!blob) return;
      stopCamera();
      setCapturedBlob(blob);
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
    }, 'image/jpeg', 0.92);
  };

  // 3. Discard snapshot / Retake
  const handleDiscardSnapshot = () => {
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setCapturedBlob(null);
    setPreviewUrl(null);
    startCamera();
  };

  // 4. Staged mobile camera file input selection
  const handleMobileCaptureFile = (file) => {
    if (!file) return;
    stopCamera();
    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }
    setCapturedBlob(file);
    setPreviewUrl(URL.createObjectURL(file));
  };

  // 5. Upload staged captured image page
  const handleUploadCapturedPage = async () => {
    if (!capturedBlob || !patient || !visit) return;
    setIsUploading(true);
    setUploadStatus('Uploading photographed document and running OCR extraction...');
    const pageNumber = uploadedPages.length + 1;
    const filename = `paper_report_page_${pageNumber}.jpg`;

    const formData = new FormData();
    formData.append('file', capturedBlob, filename);
    formData.append('patient_id', patient.patient_id);
    formData.append('visit_id', visit.visit_id);
    formData.append('group_id', groupId);

    try {
      const res = await fetch('/api/reports/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        const rowCount = data.extraction?.extracted_rows?.length || 0;
        setUploadStatus(`✅ Page ${pageNumber} uploaded! Extracted ${rowCount} lab results.`);
        setUploadedPages((prev) => [
          ...prev,
          {
            report_id: data.report?.report_id,
            filename,
            pageNumber,
            rowsCount: rowCount,
            preview: previewUrl,
            status: data.extraction?.status || 'success'
          }
        ]);
        if (data.summary) {
          setGeneratedSummary(data.summary);
        }
        setCapturedBlob(null);
        setPreviewUrl(null);
      } else {
        setUploadStatus(`❌ Upload failed: ${data.error || 'Server error'}`);
      }
    } catch (err) {
      setUploadStatus(`❌ Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  // 6. Direct file upload handler (PDF / JPG / PNG)
  const handleDirectFileUpload = async (file) => {
    if (!file || !patient || !visit) return;
    setIsUploading(true);
    setUploadStatus(`Uploading ${file.name} and extracting structured records...`);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('patient_id', patient.patient_id);
    formData.append('visit_id', visit.visit_id);
    formData.append('group_id', groupId);

    try {
      const res = await fetch('/api/reports/upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (res.ok) {
        const rowCount = data.extraction?.extracted_rows?.length || 0;
        setUploadStatus(`✅ ${file.name} uploaded! Extracted ${rowCount} lab results.`);
        setUploadedPages((prev) => [
          ...prev,
          {
            report_id: data.report?.report_id,
            filename: file.name,
            pageNumber: prev.length + 1,
            rowsCount: rowCount,
            status: data.extraction?.status || 'success'
          }
        ]);
        if (data.summary) {
          setGeneratedSummary(data.summary);
        }
      } else {
        setUploadStatus(`❌ Error: ${data.error}`);
      }
    } catch (err) {
      setUploadStatus(`❌ Upload failed: ${err.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  // 7A. NEW PATIENT REGISTRATION
  const handleRegister = async (e, options = {}) => {
    if (e && e.preventDefault) e.preventDefault();
    if (!phone.trim() || !name.trim()) return;
    setIsSubmitting(true);
    setNameConflict(null);

    try {
      const payload = {
        phone: phone.trim(),
        name: name.trim(),
        age: parseInt(age) || null,
        gender,
        force_new: options.force_new || false,
        confirm_existing: options.confirm_existing || false
      };

      const res = await fetch('/api/patients/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      // Handle phone/name conflict
      if (res.status === 409 && data.status === 'name_conflict') {
        setNameConflict(data);
        setIsSubmitting(false);
        return;
      }

      if (!res.ok) {
        alert(data.error || 'Check-in failed');
        setIsSubmitting(false);
        return;
      }

      setPatient(data.patient);
      setVisit(data.visit);
      setIsReturningPatient(!data.is_new);

      if (data.past_visits && data.past_visits.length > 0) {
        setPastVisits(data.past_visits);
        const lastPv = data.past_visits[0];
        if (lastPv.intake?.medical_conditions) setConditions(lastPv.intake.medical_conditions);
        if (lastPv.intake?.current_medications) setMedications(lastPv.intake.current_medications);
        if (lastPv.intake?.known_allergies) setAllergies(lastPv.intake.known_allergies);
      }

      if (data.is_new) {
        // Prominently display newly assigned Short Permanent Patient ID (MRN)
        setNewPatientRegistered(true);
      } else {
        // Recognized returning patient by phone match -> proceed directly
        setStep(2);
      }
    } catch (err) {
      console.error('Registration failed', err);
      alert('Unable to connect to check-in server');
    } finally {
      setIsSubmitting(false);
    }
  };

  // 7B. RETURNING PATIENT CHECK-IN WITH MRN & IDENTITY VERIFICATION
  const handleReturningCheckin = async (e) => {
    e.preventDefault();
    if (!returningMRN.trim()) return;
    setIsVerifyingReturning(true);
    setReturningError('');

    try {
      const res = await fetch('/api/patients/checkin-returning', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: returningMRN.trim(),
          verification_phone: verificationPhone.trim()
        })
      });

      const data = await res.json();
      if (!res.ok) {
        setReturningError(data.error || 'Identity verification failed.');
        setIsVerifyingReturning(false);
        return;
      }

      setPatient(data.patient);
      setVisit(data.visit);
      setIsReturningPatient(true);
      if (data.past_visits) {
        setPastVisits(data.past_visits);
      }
      if (data.prefill) {
        if (data.prefill.medical_conditions) setConditions(data.prefill.medical_conditions);
        if (data.prefill.current_medications) setMedications(data.prefill.current_medications);
        if (data.prefill.known_allergies) setAllergies(data.prefill.known_allergies);
      }

      // Advance to questionnaire
      setStep(2);
    } catch (err) {
      console.error('Returning checkin error:', err);
      setReturningError('Network error connecting to hospital check-in server.');
    } finally {
      setIsVerifyingReturning(false);
    }
  };

  // 7C. LOOKUP MRN BY PHONE (IF FORGOTTEN)
  const handleLookupMRN = async (e) => {
    e.preventDefault();
    if (!lookupPhone.trim()) return;
    setIsLookingUp(true);
    try {
      const res = await fetch('/api/patients/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          phone: lookupPhone.trim(),
          name: lookupName.trim()
        })
      });
      const data = await res.json();
      setLookupResults(data.patients || []);
    } catch (err) {
      console.error('Lookup failed', err);
    } finally {
      setIsLookingUp(false);
    }
  };

  // 8. Submit Intake Questionnaire
  const handleSaveIntake = async (e) => {
    e.preventDefault();
    if (!reason.trim()) return;
    setIsSubmitting(true);
    try {
      const res = await fetch('/api/intake', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: visit.visit_id,
          patient_id: patient.patient_id,
          reason_for_visit: reason,
          symptoms_text: symptoms,
          duration,
          severity,
          associated_symptoms: associated,
          medical_conditions: conditions,
          current_medications: medications,
          known_allergies: allergies
        })
      });
      const data = await res.json();
      if (data.summary) {
        setGeneratedSummary(data.summary);
      }
      setStep(3);
    } catch (err) {
      console.error('Intake failed', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: '840px', margin: '0 auto' }}>
      {/* Step Pills */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '8px', marginBottom: '24px' }}>
        {[
          { num: 1, label: '1. Register / Check-in' },
          { num: 2, label: '2. Intake Questions' },
          { num: 3, label: '3. Reports & Summary' },
        ].map((s) => (
          <div
            key={s.num}
            style={{
              padding: '8px 16px',
              borderRadius: '9999px',
              fontSize: '0.82rem',
              fontWeight: 700,
              background: step === s.num ? '#2563eb' : (step > s.num ? '#dcfce7' : '#ffffff'),
              color: step === s.num ? '#ffffff' : (step > s.num ? '#15803d' : '#64748b'),
              border: '1px solid #e2e8f0',
              boxShadow: '0 2px 6px rgba(0,0,0,0.02)'
            }}
          >
            {s.label}
          </div>
        ))}
      </div>

      {/* STEP 1: CHECK-IN OPTIONS */}
      {step === 1 && (
        <div>
          {/* PROMINENT PERMANENT PATIENT ID ANNOUNCEMENT (When genuinely new registration occurs) */}
          {newPatientRegistered ? (
            <div className="card" style={{ textAlign: 'center', padding: '36px 24px', background: '#eff6ff', border: '2px solid #bfdbfe' }}>
              <div style={{
                width: '56px',
                height: '56px',
                background: '#2563eb',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                margin: '0 auto 16px',
                boxShadow: '0 6px 16px rgba(37,99,235,0.3)'
              }}>
                <CheckCircle2 size={32} />
              </div>

              <h2 style={{ fontSize: '1.35rem', fontWeight: 800, color: '#0f172a', marginBottom: '6px' }}>
                Registration Successful!
              </h2>
              <p style={{ color: '#475569', fontSize: '0.92rem', marginBottom: '18px' }}>
                Your Permanent Patient ID (MRN) has been assigned:
              </p>

              {/* Large MRN Display with Copy Action */}
              <div style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '12px',
                background: '#ffffff',
                border: '2px solid #2563eb',
                padding: '12px 24px',
                borderRadius: '16px',
                boxShadow: '0 4px 14px rgba(37,99,235,0.12)',
                marginBottom: '18px'
              }}>
                <span style={{ fontSize: '1.5rem', fontWeight: 800, color: '#1e3a8a', letterSpacing: '1px' }}>
                  {patient?.patient_id}
                </span>
                <button
                  type="button"
                  onClick={() => copyMRNToClipboard(patient?.patient_id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: copiedMRN ? '#ecfdf5' : '#f1f5f9',
                    border: '1px solid #cbd5e1',
                    padding: '6px 14px',
                    borderRadius: '8px',
                    cursor: 'pointer',
                    fontWeight: 700,
                    fontSize: '0.84rem',
                    color: copiedMRN ? '#065f46' : '#1e293b'
                  }}
                >
                  {copiedMRN ? <Check size={16} /> : <Copy size={16} />}
                  <span>{copiedMRN ? 'Copied!' : 'Copy Patient ID'}</span>
                </button>
              </div>

              <div style={{
                background: '#fffbeb',
                border: '1px solid #fde68a',
                borderRadius: '12px',
                padding: '12px 18px',
                maxWidth: '520px',
                margin: '0 auto 24px',
                fontSize: '0.86rem',
                color: '#92400e',
                textAlign: 'left'
              }}>
                📌 <strong>Please save this ID!</strong> You will use <strong>{patient?.patient_id}</strong> for future check-ins and to access your medical records without registering again.
              </div>

              <button
                type="button"
                className="btn-primary"
                style={{ padding: '12px 32px', fontSize: '0.98rem' }}
                onClick={() => {
                  setNewPatientRegistered(false);
                  setStep(2);
                }}
              >
                <span>Continue to Clinical Intake Questions</span>
                <ArrowRight size={18} />
              </button>
            </div>
          ) : (
            <div className="card">
              {/* TWO CLEAR CHECK-IN OPTIONS: A. NEW PATIENT vs B. RETURNING PATIENT */}
              <div style={{
                display: 'flex',
                background: '#f1f5f9',
                borderRadius: '12px',
                padding: '4px',
                marginBottom: '20px',
                gap: '4px'
              }}>
                <button
                  type="button"
                  onClick={() => setCheckinMode('new')}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '10px 16px',
                    borderRadius: '10px',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    border: 'none',
                    cursor: 'pointer',
                    background: checkinMode === 'new' ? '#ffffff' : 'transparent',
                    color: checkinMode === 'new' ? '#2563eb' : '#64748b',
                    boxShadow: checkinMode === 'new' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <UserPlus size={18} />
                  <span>A. New Patient Registration</span>
                </button>

                <button
                  type="button"
                  onClick={() => setCheckinMode('returning')}
                  style={{
                    flex: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    padding: '10px 16px',
                    borderRadius: '10px',
                    fontWeight: 700,
                    fontSize: '0.88rem',
                    border: 'none',
                    cursor: 'pointer',
                    background: checkinMode === 'returning' ? '#ffffff' : 'transparent',
                    color: checkinMode === 'returning' ? '#2563eb' : '#64748b',
                    boxShadow: checkinMode === 'returning' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                    transition: 'all 0.15s ease'
                  }}
                >
                  <History size={18} />
                  <span>B. Returning Patient Check-in</span>
                </button>
              </div>

              {/* IDENTITY CONFLICT RESOLUTION MODAL / BANNER (Shared) */}
              {nameConflict && (
                <div style={{
                  background: '#fffbeb',
                  border: '1.5px solid #fde68a',
                  borderRadius: '16px',
                  padding: '18px 20px',
                  marginBottom: '20px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px' }}>
                    <AlertCircle size={24} style={{ color: '#d97706', flexShrink: 0, marginTop: '2px' }} />
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 700, color: '#92400e', fontSize: '0.98rem' }}>
                        Identity Verification Needed
                      </div>
                      <div style={{ fontSize: '0.88rem', color: '#78350f', marginTop: '4px', lineHeight: 1.45 }}>
                        Mobile number <strong>{phone}</strong> is already registered under existing patient record:
                        <div style={{
                          background: '#ffffff',
                          border: '1px solid #fef3c7',
                          padding: '8px 12px',
                          borderRadius: '8px',
                          marginTop: '8px',
                          fontWeight: 700,
                          color: '#0f172a'
                        }}>
                          👤 {nameConflict.existing_patient?.name} · MRN: {nameConflict.existing_patient?.patient_id}
                        </div>
                      </div>

                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginTop: '14px' }}>
                        <button
                          type="button"
                          className="btn-primary"
                          style={{ fontSize: '0.84rem', padding: '8px 14px' }}
                          onClick={(e) => {
                            setName(nameConflict.existing_patient?.name || name);
                            handleRegister(e, { confirm_existing: true });
                          }}
                          disabled={isSubmitting}
                        >
                          <CheckCircle2 size={15} />
                          <span>Yes, I am {nameConflict.existing_patient?.name}</span>
                        </button>

                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ fontSize: '0.84rem', padding: '8px 14px' }}
                          onClick={(e) => handleRegister(e, { force_new: true })}
                          disabled={isSubmitting}
                        >
                          <span>Register as new patient / family member</span>
                        </button>

                        <button
                          type="button"
                          style={{
                            background: 'transparent',
                            border: 'none',
                            color: '#64748b',
                            fontSize: '0.84rem',
                            cursor: 'pointer',
                            padding: '8px 12px'
                          }}
                          onClick={() => setNameConflict(null)}
                        >
                          Edit details
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* ---------------- MODE A: NEW PATIENT REGISTRATION ---------------- */}
              {checkinMode === 'new' && (
                <div>
                  <div className="card-title">
                    <UserPlus size={20} style={{ color: '#2563eb' }} />
                    <span>New Patient Registration</span>
                  </div>
                  <div className="card-subtitle">
                    First time visiting our hospital? Register your details to receive your permanent Patient ID (MRN) and OPD token.
                  </div>

                  <form onSubmit={(e) => handleRegister(e)}>
                    <div className="form-group">
                      <label className="form-label">Mobile Phone Number (10 digits) *</label>
                      <input
                        type="tel"
                        className="form-input"
                        placeholder="e.g. 9876543210 or +91 98765 43210"
                        value={phone}
                        onChange={(e) => setPhone(e.target.value)}
                        required
                      />
                    </div>

                    <div className="form-group">
                      <label className="form-label">Full Name *</label>
                      <input
                        type="text"
                        className="form-input"
                        placeholder="e.g. Ramesh Patel"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        required
                      />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                      <div className="form-group">
                        <label className="form-label">Age</label>
                        <input
                          type="number"
                          className="form-input"
                          value={age}
                          onChange={(e) => setAge(e.target.value)}
                        />
                      </div>

                      <div className="form-group">
                        <label className="form-label">Gender</label>
                        <select className="form-select" value={gender} onChange={(e) => setGender(e.target.value)}>
                          <option value="Male">Male</option>
                          <option value="Female">Female</option>
                          <option value="Other">Other</option>
                        </select>
                      </div>
                    </div>

                    <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '12px' }} disabled={isSubmitting}>
                      <span>{isSubmitting ? 'Registering...' : 'Generate Patient ID & Issue OPD Token'}</span>
                      <ArrowRight size={16} />
                    </button>
                  </form>
                </div>
              )}

              {/* ---------------- MODE B: RETURNING PATIENT CHECK-IN ---------------- */}
              {checkinMode === 'returning' && (
                <div>
                  <div className="card-title">
                    <History size={20} style={{ color: '#2563eb' }} />
                    <span>Returning Patient Quick Check-in</span>
                  </div>
                  <div className="card-subtitle">
                    Enter your Permanent Patient ID (MRN) and verify your registered mobile number to check in for today's visit.
                  </div>

                  {returningError && (
                    <div style={{
                      padding: '12px 16px',
                      background: '#fef2f2',
                      border: '1px solid #fecaca',
                      borderRadius: '12px',
                      color: '#991b1b',
                      fontSize: '0.86rem',
                      fontWeight: 600,
                      marginBottom: '16px'
                    }}>
                      ⚠️ {returningError}
                    </div>
                  )}

                  <form onSubmit={handleReturningCheckin}>
                    <div className="form-group">
                      <label className="form-label">Permanent Patient ID (MRN) *</label>
                      <div style={{ position: 'relative' }}>
                        <input
                          type="text"
                          className="form-input"
                          placeholder="e.g. P10482, P10001, or legacy PAT-..."
                          value={returningMRN}
                          onChange={(e) => setReturningMRN(e.target.value)}
                          required
                          style={{ textTransform: 'uppercase', fontWeight: 600, letterSpacing: '0.5px' }}
                        />
                      </div>
                    </div>

                    <div className="form-group">
                      <label className="form-label">Registered Mobile Number (Identity Verification) *</label>
                      <input
                        type="tel"
                        className="form-input"
                        placeholder="e.g. 9876543210 (10 digits)"
                        value={verificationPhone}
                        onChange={(e) => setVerificationPhone(e.target.value)}
                        required
                      />
                      <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '4px' }}>
                        🔒 Required to verify your identity and protect confidential medical history before check-in.
                      </div>
                    </div>

                    <button
                      type="submit"
                      className="btn-primary"
                      style={{ width: '100%', marginTop: '12px' }}
                      disabled={isVerifyingReturning}
                    >
                      <KeyRound size={16} />
                      <span>{isVerifyingReturning ? 'Verifying Identity...' : 'Verify & Continue to Intake Questions'}</span>
                    </button>
                  </form>

                  {/* FORGOT MRN LOOKUP HELPER */}
                  <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid #f1f5f9', textAlign: 'center' }}>
                    <button
                      type="button"
                      onClick={() => setShowForgotMRN(!showForgotMRN)}
                      style={{ background: 'transparent', border: 'none', color: '#2563eb', fontWeight: 700, fontSize: '0.84rem', cursor: 'pointer' }}
                    >
                      {showForgotMRN ? 'Hide Patient ID Finder' : '🔍 Forgot your Patient ID? Find by Registered Mobile Number'}
                    </button>

                    {showForgotMRN && (
                      <div style={{
                        marginTop: '14px',
                        padding: '16px',
                        background: '#f8fafc',
                        borderRadius: '12px',
                        border: '1px solid #e2e8f0',
                        textAlign: 'left'
                      }}>
                        <div style={{ fontWeight: 700, fontSize: '0.86rem', color: '#0f172a', marginBottom: '8px' }}>
                          Find your Permanent Patient ID (MRN)
                        </div>

                        <form onSubmit={handleLookupMRN} style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                          <input
                            type="tel"
                            className="form-input"
                            style={{ flex: 1, minWidth: '180px' }}
                            placeholder="Enter 10-digit phone"
                            value={lookupPhone}
                            onChange={(e) => setLookupPhone(e.target.value)}
                            required
                          />
                          <button
                            type="submit"
                            className="btn-secondary"
                            disabled={isLookingUp}
                            style={{ padding: '8px 16px', fontSize: '0.84rem' }}
                          >
                            <Search size={14} />
                            <span>{isLookingUp ? 'Searching...' : 'Find ID'}</span>
                          </button>
                        </form>

                        {lookupResults.length > 0 && (
                          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                            <div style={{ fontSize: '0.78rem', color: '#64748b' }}>Records found:</div>
                            {lookupResults.map((rec) => (
                              <div
                                key={rec.patient_id}
                                style={{
                                  display: 'flex',
                                  justifyContent: 'space-between',
                                  alignItems: 'center',
                                  padding: '8px 12px',
                                  background: '#ffffff',
                                  borderRadius: '8px',
                                  border: '1px solid #cbd5e1'
                                }}
                              >
                                <div>
                                  <strong style={{ color: '#0f172a' }}>{rec.name}</strong>
                                  <span style={{ fontSize: '0.82rem', color: '#2563eb', marginLeft: '8px', fontWeight: 700 }}>
                                    MRN: {rec.patient_id}
                                  </span>
                                </div>
                                <button
                                  type="button"
                                  className="btn-primary"
                                  style={{ padding: '4px 10px', fontSize: '0.78rem' }}
                                  onClick={() => {
                                    setReturningMRN(rec.patient_id);
                                    setVerificationPhone(lookupPhone);
                                    setShowForgotMRN(false);
                                  }}
                                >
                                  Use this ID
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* STEP 2: INTAKE QUESTIONS */}
      {step === 2 && (
        <div className="card">
          <div className="card-title">
            <ClipboardList size={20} style={{ color: '#2563eb' }} />
            <span>Step 2: Clinical Intake Questionnaire</span>
          </div>
          <div className="card-subtitle">
            Token Issued: <strong style={{ color: '#2563eb' }}>{visit?.token_number}</strong> · Patient: <strong>{patient?.name}</strong> (MRN: <strong style={{ color: '#2563eb' }}>{patient?.patient_id}</strong>)
          </div>

          {/* RETURNING PATIENT RECOGNITION BANNER */}
          {pastVisits.length > 0 && (
            <div style={{
              background: '#f0fdf4',
              border: '1.5px solid #86efac',
              borderRadius: '14px',
              padding: '14px 18px',
              marginBottom: '20px',
              color: '#166534',
              fontSize: '0.9rem'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: 700, fontSize: '0.96rem', marginBottom: '4px' }}>
                <CheckCircle2 size={18} style={{ color: '#16a34a' }} />
                <span>Welcome back, {patient?.name}! We found your previous medical records.</span>
              </div>
              <div>
                We identified <strong>{pastVisits.length} prior consultation(s)</strong> and past doctor notes on file for MRN <strong>{patient?.patient_id}</strong>.
                Your known chronic conditions and routine medications have been pre-filled below. Please update if anything has changed.
              </div>
            </div>
          )}

          <form onSubmit={handleSaveIntake}>
            <div className="form-group">
              <label className="form-label">What is the main reason for your hospital visit today? *</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Chest heaviness while walking, or Diabetes routine check-up"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Describe your current symptoms in detail</label>
              <textarea
                className="form-textarea"
                rows={3}
                placeholder="e.g. Chest heaviness while walking for 2 days. No vomiting. Mild sweating reported."
                value={symptoms}
                onChange={(e) => setSymptoms(e.target.value)}
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              <div className="form-group">
                <label className="form-label">Duration</label>
                <select className="form-select" value={duration} onChange={(e) => setDuration(e.target.value)}>
                  <option value="Less than 1 day">Less than 1 day</option>
                  <option value="1 to 3 days">1 to 3 days</option>
                  <option value="4 to 7 days">4 to 7 days</option>
                  <option value="1 to 2 weeks">1 to 2 weeks</option>
                  <option value="More than 2 weeks">More than 2 weeks</option>
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Severity</label>
                <select className="form-select" value={severity} onChange={(e) => setSeverity(e.target.value)}>
                  <option value="Mild (manageable)">Mild (manageable)</option>
                  <option value="Moderate (interferes with routine)">Moderate (interferes with routine)</option>
                  <option value="Severe (unbearable)">Severe (unbearable)</option>
                </select>
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Existing Chronic Conditions</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Hypertension, diabetes"
                value={conditions}
                onChange={(e) => setConditions(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Current Medications</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. Telma 40, Metformin 500"
                value={medications}
                onChange={(e) => setMedications(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Known Drug Allergies</label>
              <input
                type="text"
                className="form-input"
                placeholder="e.g. No known drug allergies, or Penicillin"
                value={allergies}
                onChange={(e) => setAllergies(e.target.value)}
              />
            </div>

            <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '12px' }} disabled={isSubmitting}>
              <span>{isSubmitting ? 'Saving...' : 'Save & Proceed to Report Upload'}</span>
              <ArrowRight size={16} />
            </button>
          </form>
        </div>
      )}

      {/* STEP 3: REPORT UPLOAD & SUMMARY PREVIEW */}
      {step === 3 && (
        <div>
          <div className="card" style={{ marginBottom: '24px' }}>
            <div className="card-title">
              <Upload size={20} style={{ color: '#2563eb' }} />
              <span>Step 3: Medical Report & Physical Paper Scan</span>
            </div>
            <div className="card-subtitle">
              Photograph paper prescriptions, lab printouts, or upload existing electronic documents.
            </div>

            {/* TWO CLEAR OPTIONS SELECTOR TABS */}
            <div style={{
              display: 'flex',
              background: '#f1f5f9',
              borderRadius: '12px',
              padding: '4px',
              marginBottom: '20px',
              gap: '4px'
            }}>
              <button
                type="button"
                onClick={() => {
                  setActiveUploadTab('camera');
                }}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '10px 16px',
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  border: 'none',
                  cursor: 'pointer',
                  background: activeUploadTab === 'camera' ? '#ffffff' : 'transparent',
                  color: activeUploadTab === 'camera' ? '#2563eb' : '#64748b',
                  boxShadow: activeUploadTab === 'camera' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                <Camera size={18} />
                <span>Take Photo of Report</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  stopCamera();
                  setActiveUploadTab('file');
                }}
                style={{
                  flex: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: '8px',
                  padding: '10px 16px',
                  borderRadius: '10px',
                  fontWeight: 700,
                  fontSize: '0.88rem',
                  border: 'none',
                  cursor: 'pointer',
                  background: activeUploadTab === 'file' ? '#ffffff' : 'transparent',
                  color: activeUploadTab === 'file' ? '#2563eb' : '#64748b',
                  boxShadow: activeUploadTab === 'file' ? '0 2px 6px rgba(0,0,0,0.06)' : 'none',
                  transition: 'all 0.15s ease'
                }}
              >
                <Upload size={18} />
                <span>Upload Existing File</span>
              </button>
            </div>

            {/* TAB 1: CAMERA SCAN WORKFLOW */}
            {activeUploadTab === 'camera' && (
              <div>
                {/* 1. Live Viewfinder View */}
                {isCameraActive && (
                  <div style={{
                    position: 'relative',
                    background: '#000000',
                    borderRadius: '16px',
                    overflow: 'hidden',
                    marginBottom: '16px',
                    textAlign: 'center'
                  }}>
                    <video
                      ref={videoRef}
                      autoPlay
                      playsInline
                      muted
                      style={{
                        width: '100%',
                        maxHeight: '420px',
                        objectFit: 'contain',
                        display: 'block'
                      }}
                    />

                    {/* Framing Guide Overlay */}
                    <div style={{
                      position: 'absolute',
                      top: '15px',
                      bottom: '15px',
                      left: '20px',
                      right: '20px',
                      border: '2px dashed rgba(255,255,255,0.7)',
                      borderRadius: '12px',
                      pointerEvents: 'none',
                      boxShadow: '0 0 0 9999px rgba(0, 0, 0, 0.35)',
                      display: 'flex',
                      flexDirection: 'column',
                      justifyContent: 'space-between',
                      padding: '12px'
                    }}>
                      <div style={{ color: '#ffffff', fontSize: '0.8rem', background: 'rgba(0,0,0,0.6)', padding: '4px 8px', borderRadius: '6px', alignSelf: 'flex-start' }}>
                        Align paper report page within frame
                      </div>
                      <div style={{ color: '#ffffff', fontSize: '0.75rem', background: 'rgba(0,0,0,0.6)', padding: '4px 8px', borderRadius: '6px', alignSelf: 'center' }}>
                        Hold still for best sharpness
                      </div>
                    </div>

                    {/* Camera Control Action Bar */}
                    <div style={{
                      position: 'absolute',
                      bottom: '24px',
                      left: 0,
                      right: 0,
                      display: 'flex',
                      justifyContent: 'center',
                      gap: '16px',
                      zIndex: 10
                    }}>
                      <button
                        type="button"
                        onClick={stopCamera}
                        style={{
                          background: 'rgba(15, 23, 42, 0.8)',
                          color: '#ffffff',
                          border: 'none',
                          padding: '10px 18px',
                          borderRadius: '9999px',
                          cursor: 'pointer',
                          fontWeight: 600,
                          fontSize: '0.84rem'
                        }}
                      >
                        Cancel
                      </button>

                      <button
                        type="button"
                        onClick={handleCaptureSnapshot}
                        style={{
                          background: '#2563eb',
                          color: '#ffffff',
                          border: '3px solid #ffffff',
                          padding: '10px 24px',
                          borderRadius: '9999px',
                          cursor: 'pointer',
                          fontWeight: 700,
                          fontSize: '0.92rem',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          boxShadow: '0 4px 14px rgba(0,0,0,0.3)'
                        }}
                      >
                        <Camera size={18} />
                        <span>Capture Page {uploadedPages.length + 1}</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* 2. Photo Staged Preview Before Upload */}
                {previewUrl && (
                  <div style={{
                    background: '#f8fafc',
                    border: '1.5px solid #cbd5e1',
                    borderRadius: '16px',
                    padding: '20px',
                    marginBottom: '18px',
                    textAlign: 'center'
                  }}>
                    <div style={{ fontWeight: 700, color: '#0f172a', marginBottom: '8px', fontSize: '0.94rem' }}>
                      📸 Preview: Page {uploadedPages.length + 1}
                    </div>
                    <div style={{ fontSize: '0.8rem', color: '#64748b', marginBottom: '14px' }}>
                      Check if the text, tests, and numerical values are clearly legible before uploading.
                    </div>

                    <div style={{
                      maxWidth: '380px',
                      margin: '0 auto 16px',
                      borderRadius: '12px',
                      overflow: 'hidden',
                      boxShadow: '0 6px 18px rgba(0,0,0,0.08)',
                      border: '1px solid #e2e8f0'
                    }}>
                      <img
                        src={previewUrl}
                        alt="Captured report preview"
                        style={{ width: '100%', maxHeight: '360px', objectFit: 'contain', display: 'block', background: '#000' }}
                      />
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn-secondary"
                        onClick={handleDiscardSnapshot}
                        disabled={isUploading}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <RefreshCw size={15} />
                        <span>Retake Photo</span>
                      </button>

                      <button
                        type="button"
                        className="btn-primary"
                        onClick={handleUploadCapturedPage}
                        disabled={isUploading}
                        style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                      >
                        <Upload size={15} />
                        <span>{isUploading ? 'Uploading & Processing...' : `Upload Page ${uploadedPages.length + 1}`}</span>
                      </button>
                    </div>
                  </div>
                )}

                {/* 3. Launch In-Browser or Native Camera Options */}
                {!isCameraActive && !previewUrl && (
                  <div style={{
                    border: '2px dashed #93c5fd',
                    borderRadius: '16px',
                    padding: '28px 20px',
                    textAlign: 'center',
                    background: '#eff6ff',
                    marginBottom: '16px'
                  }}>
                    <Camera size={38} style={{ color: '#2563eb', margin: '0 auto 10px' }} />
                    <div style={{ fontWeight: 700, fontSize: '1rem', color: '#1e3a8a' }}>
                      Photograph Paper Report Page {uploadedPages.length + 1}
                    </div>
                    <div style={{ fontSize: '0.82rem', color: '#3b82f6', maxWidth: '440px', margin: '6px auto 18px' }}>
                      Position your phone camera over the paper lab report or prescription to extract lab findings.
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'center', gap: '12px', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        className="btn-primary"
                        onClick={startCamera}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                      >
                        <Camera size={16} />
                        <span>Launch Camera Viewfinder</span>
                      </button>

                      <label
                        className="btn-secondary"
                        style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '8px' }}
                      >
                        <ImageIcon size={16} />
                        <span>Use Device Camera App</span>
                        <input
                          type="file"
                          accept="image/*"
                          capture="environment"
                          style={{ display: 'none' }}
                          onChange={(e) => {
                            if (e.target.files?.[0]) handleMobileCaptureFile(e.target.files[0]);
                          }}
                        />
                      </label>
                    </div>

                    {cameraError && (
                      <div style={{
                        marginTop: '16px',
                        padding: '10px 14px',
                        background: '#fef2f2',
                        border: '1px solid #fecaca',
                        borderRadius: '10px',
                        color: '#991b1b',
                        fontSize: '0.82rem',
                        textAlign: 'left'
                      }}>
                        ⚠️ {cameraError}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: UPLOAD EXISTING FILE (PDF / JPG / PNG) */}
            {activeUploadTab === 'file' && (
              <div style={{
                border: '2px dashed #cbd5e1',
                borderRadius: '16px',
                padding: '32px 20px',
                textAlign: 'center',
                background: '#f8fafc',
                marginBottom: '16px'
              }}>
                <Upload size={38} style={{ color: '#64748b', margin: '0 auto 10px' }} />
                <div style={{ fontWeight: 700, fontSize: '1rem', color: '#0f172a' }}>
                  Select Medical Report Document
                </div>
                <div style={{ fontSize: '0.82rem', color: '#64748b', marginBottom: '18px' }}>
                  PDF, JPG, JPEG, PNG (Single or Multi-page documents up to 15MB)
                </div>

                <label className="btn-primary" style={{ cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                  <FileText size={16} />
                  <span>Browse Device Files</span>
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg"
                    style={{ display: 'none' }}
                    onChange={(e) => {
                      if (e.target.files?.[0]) handleDirectFileUpload(e.target.files[0]);
                    }}
                  />
                </label>
              </div>
            )}

            {/* STATUS NOTIFICATION BAR */}
            {uploadStatus && (
              <div style={{
                padding: '12px 16px',
                background: uploadStatus.startsWith('❌') ? '#fef2f2' : (uploadStatus.startsWith('✅') ? '#f0fdf4' : '#f1f5f9'),
                border: uploadStatus.startsWith('❌') ? '1px solid #fecaca' : (uploadStatus.startsWith('✅') ? '1px solid #bbf7d0' : '1px solid #e2e8f0'),
                borderRadius: '12px',
                fontSize: '0.88rem',
                fontWeight: 600,
                color: uploadStatus.startsWith('❌') ? '#991b1b' : (uploadStatus.startsWith('✅') ? '#166534' : '#1e293b'),
                marginBottom: '16px'
              }}>
                {uploadStatus}
              </div>
            )}

            {/* MULTI-PAGE CAPTURED PAGES GALLERY / LIST */}
            {uploadedPages.length > 0 && (
              <div style={{
                background: '#ffffff',
                border: '1px solid #e2e8f0',
                borderRadius: '14px',
                padding: '14px 18px',
                marginTop: '16px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                  <div style={{ fontSize: '0.86rem', fontWeight: 700, color: '#0f172a' }}>
                    📑 Document Pages Attached ({uploadedPages.length})
                  </div>
                  <div style={{ fontSize: '0.78rem', color: '#2563eb', fontWeight: 600 }}>
                    Group ID: {groupId.slice(0, 14)}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {uploadedPages.map((page, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '8px 12px',
                        background: '#f8fafc',
                        borderRadius: '8px',
                        fontSize: '0.84rem'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <CheckCircle2 size={16} style={{ color: '#16a34a' }} />
                        <span style={{ fontWeight: 600, color: '#1e293b' }}>
                          Page {page.pageNumber}: {page.filename}
                        </span>
                      </div>
                      <div style={{ color: '#64748b', fontSize: '0.8rem' }}>
                        {page.rowsCount} lab results extracted
                      </div>
                    </div>
                  ))}
                </div>

                {/* Additional Page Call-to-action */}
                <div style={{ marginTop: '12px', textAlign: 'center' }}>
                  <button
                    type="button"
                    onClick={() => {
                      setActiveUploadTab('camera');
                      startCamera();
                    }}
                    style={{
                      background: 'transparent',
                      border: '1.5px dashed #3b82f6',
                      borderRadius: '8px',
                      color: '#2563eb',
                      padding: '8px 16px',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '6px'
                    }}
                  >
                    <Plus size={15} />
                    <span>Photograph Page {uploadedPages.length + 1}</span>
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* GENERATED 10-15s SUMMARY CARD PREVIEW */}
          {generatedSummary && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
                <Sparkles size={18} style={{ color: '#2563eb' }} />
                <h3 style={{ fontSize: '1rem', fontWeight: 700, color: '#0f172a' }}>
                  Generated Summary Card (Ready for Doctor)
                </h3>
              </div>
              <SummaryCard summary={generatedSummary} patient={patient} visit={visit} />
            </div>
          )}

          <div style={{ textAlign: 'center', marginTop: '24px' }}>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              background: '#ecfdf5',
              padding: '12px 24px',
              borderRadius: '9999px',
              color: '#065f46',
              fontWeight: 700,
              boxShadow: '0 2px 8px rgba(0,0,0,0.04)'
            }}>
              <CheckCircle2 size={18} />
              <span>Check-in Complete! Your Token is {visit?.token_number}. Please wait in OPD lounge.</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
