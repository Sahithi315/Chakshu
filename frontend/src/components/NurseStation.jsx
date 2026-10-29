import React, { useEffect, useState } from 'react';
import { Activity, AlertTriangle, CheckCircle2, Search, UserRound } from 'lucide-react';
import AnimatedList from './AnimatedList';

export default function NurseStation({ apiFetch = fetch, user }) {
  const [visits, setVisits] = useState([]);
  const [selectedVisitId, setSelectedVisitId] = useState('');
  const [queueFilter, setQueueFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [bpSys, setBpSys] = useState(120);
  const [bpDia, setBpDia] = useState(80);
  const [hr, setHr] = useState(74);
  const [temp, setTemp] = useState(98.6);
  const [spo2, setSpo2] = useState(98.5);
  const [bs, setBs] = useState(110);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSaveConfirmation, setShowSaveConfirmation] = useState(false);

  const fetchVisits = async () => {
    try {
      const response = await apiFetch('/api/visits?needs_vitals=1');
      const data = await response.json();
      setVisits(data);
      setSelectedVisitId(current => data.some(visit => visit.visit_id === current) ? current : (data[0]?.visit_id || ''));
    } catch (error) {
      console.error('Failed to load queue', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchVisits(); }, []);

  const handleSaveVitals = event => {
    event.preventDefault();
    if (activeVisit) setShowSaveConfirmation(true);
  };

  const confirmSaveVitals = async () => {
    const selectedVisit = visits.find(visit => visit.visit_id === selectedVisitId);
    if (!selectedVisit) return;
    setIsSubmitting(true);
    try {
      const response = await apiFetch('/api/vitals', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          visit_id: selectedVisit.visit_id,
          patient_id: selectedVisit.patient_id,
          bp_systolic: parseInt(bpSys) || null,
          bp_diastolic: parseInt(bpDia) || null,
          heart_rate: parseInt(hr) || null,
          temperature: parseFloat(temp) || null,
          spo2: parseFloat(spo2) || null,
          blood_sugar: parseFloat(bs) || null
        })
      });
      if (response.ok) {
        setShowSaveConfirmation(false);
        setSavedSuccess(true);
        setBpSys(120);
        setBpDia(80);
        setHr(74);
        setTemp(98.6);
        setSpo2(98.5);
        setBs(110);
        await fetchVisits();
        setTimeout(() => setSavedSuccess(false), 3000);
      }
    } catch (error) {
      console.error('Failed to save vitals', error);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) return <div className="route-loading">Loading allotted patients...</div>;

  const activeVisit = visits.find(visit => visit.visit_id === selectedVisitId);
  const filter = queueFilter.trim().toLowerCase();
  const filteredVisits = visits.filter(visit => !filter || [
    visit.patient_name, visit.patient_id, visit.token_number
  ].some(value => String(value || '').toLowerCase().includes(filter)));
  const animatedPatients = filteredVisits.map((visit, index) => ({
    ...visit,
    id: visit.visit_id,
    title: visit.patient_name,
    description: `${visit.patient_id} · ${visit.patient_age} yrs${index === 0 && !filter ? ' · Newest' : ''}`,
    meta: visit.token_number
  }));
  const selectedPatientIndex = animatedPatients.findIndex(visit => visit.visit_id === selectedVisitId);

  return <div className="nurse-workspace">
    <section className="card nurse-queue-panel">
      <div className="card-title"><UserRound size={22} style={{ color: '#2563eb' }} /><span>Newly allotted patients</span></div>
      <div className="card-subtitle">Newest check-ins appear first. Type a name, patient ID, or token to narrow the list instantly.</div>
      <div className="nurse-queue-filter"><Search size={18} /><input value={queueFilter} onChange={event => setQueueFilter(event.target.value)} placeholder="Name, patient ID, or token" aria-label="Filter allotted patients" /></div>
      {animatedPatients.length === 0 ? <div className="nurse-queue-empty">No allotted patient matches this entry.</div> : <AnimatedList
        items={animatedPatients}
        selectedIndex={selectedPatientIndex}
        onItemSelect={visit => setSelectedVisitId(visit.visit_id)}
        animation="pop"
        theme="light"
        selectOnHover={false}
        maxHeight={500}
        width="100%"
      />}
    </section>

    <section className="card nurse-vitals-panel">
      <div className="card-title"><Activity size={22} style={{ color: '#10b981' }} /><span>Record patient vitals</span></div>
      <div className="card-subtitle">Select an allotted patient from the list and record their measurements.</div>
      {savedSuccess && <div className="nurse-save-success"><CheckCircle2 size={18} /><span>Vitals recorded successfully. The doctor brief has been updated.</span></div>}
      {!activeVisit && <div className="nurse-queue-empty">Choose a patient from the allotted list to record vitals.</div>}
      {activeVisit && <form onSubmit={handleSaveVitals}>
        <div className="selected-nurse-patient"><strong>{activeVisit.token_number} · {activeVisit.patient_name}</strong><span>{activeVisit.patient_id} · {activeVisit.patient_age} y/o · {activeVisit.patient_gender}</span></div>
        <div className="nurse-vitals-grid">
          <div className="form-group"><label className="form-label">Blood Pressure</label><div className="bp-inputs"><input type="number" className="form-input" placeholder="Systolic" value={bpSys} onChange={event => setBpSys(event.target.value)} required /><span>/</span><input type="number" className="form-input" placeholder="Diastolic" value={bpDia} onChange={event => setBpDia(event.target.value)} required /></div></div>
          <div className="form-group"><label className="form-label">Heart Rate (bpm)</label><input type="number" className="form-input" value={hr} onChange={event => setHr(event.target.value)} required /></div>
          <div className="form-group"><label className="form-label">Temperature (°F)</label><input type="number" step="0.1" className="form-input" value={temp} onChange={event => setTemp(event.target.value)} required /></div>
          <div className="form-group"><label className="form-label">SpO₂ (%)</label><input type="number" step="0.5" className="form-input" value={spo2} onChange={event => setSpo2(event.target.value)} required /></div>
          <div className="form-group"><label className="form-label">Blood Sugar (mg/dL)</label><input type="number" className="form-input" value={bs} onChange={event => setBs(event.target.value)} required /></div>
          <div className="form-group"><label className="form-label">Recorded by</label><input className="form-input" value={`${user?.display_name || 'Authenticated nurse'} (${user?.staff_id || ''})`} readOnly /></div>
        </div>
        <button type="submit" className="btn-success nurse-save-button" disabled={isSubmitting}>Review & Save Patient Vitals</button>
      </form>}
    </section>
    {showSaveConfirmation && activeVisit && <div className="nurse-confirm-backdrop" role="presentation">
      <div className="nurse-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="nurse-confirm-title">
        <div className="nurse-confirm-icon"><AlertTriangle size={24} /></div>
        <h3 id="nurse-confirm-title">Confirm vitals submission</h3>
        <p>You are about to save these measurements for <strong>{activeVisit.patient_name}</strong> ({activeVisit.patient_id}), token <strong>{activeVisit.token_number}</strong>.</p>
        <div className="nurse-confirm-values">
          <span>BP <strong>{bpSys}/{bpDia}</strong></span>
          <span>Pulse <strong>{hr} bpm</strong></span>
          <span>Temperature <strong>{temp} °F</strong></span>
          <span>SpO₂ <strong>{spo2}%</strong></span>
          <span>Blood sugar <strong>{bs} mg/dL</strong></span>
        </div>
        <p className="nurse-confirm-note">After confirmation, this patient will be removed from the nurse queue and the next patient will load automatically.</p>
        <div className="nurse-confirm-actions">
          <button type="button" className="btn-secondary" onClick={() => setShowSaveConfirmation(false)} disabled={isSubmitting}>Go Back</button>
          <button type="button" className="btn-success" onClick={confirmSaveVitals} disabled={isSubmitting}>{isSubmitting ? 'Saving...' : 'Confirm & Save'}</button>
        </div>
      </div>
    </div>}
  </div>;
}
