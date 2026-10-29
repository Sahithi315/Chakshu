import React, { useState, useEffect } from 'react';
import { Activity, Heart, Thermometer, Droplet, CheckCircle2, User } from 'lucide-react';

export default function NurseStation() {
  const [visits, setVisits] = useState([]);
  const [selectedVisitId, setSelectedVisitId] = useState('');
  const [loading, setLoading] = useState(true);

  // Vitals state
  const [bpSys, setBpSys] = useState(120);
  const [bpDia, setBpDia] = useState(80);
  const [hr, setHr] = useState(74);
  const [temp, setTemp] = useState(98.6);
  const [spo2, setSpo2] = useState(98.5);
  const [bs, setBs] = useState(110);
  const [nurseId, setNurseId] = useState('nurse_anita');

  const [savedSuccess, setSavedSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchVisits = async () => {
    try {
      const res = await fetch('/api/visits');
      const data = await res.json();
      setVisits(data);
      if (data.length > 0 && !selectedVisitId) {
        setSelectedVisitId(data[0].visit_id);
      }
    } catch (e) {
      console.error('Failed to load queue', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchVisits();
  }, []);

  const handleSaveVitals = async (e) => {
    e.preventDefault();
    if (!selectedVisitId) return;
    const selectedVisit = visits.find(v => v.visit_id === selectedVisitId);
    if (!selectedVisit) return;

    setIsSubmitting(true);
    try {
      const res = await fetch('/api/vitals', {
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
          blood_sugar: parseFloat(bs) || null,
          recorded_by: nurseId
        })
      });
      if (res.ok) {
        setSavedSuccess(true);
        setTimeout(() => setSavedSuccess(false), 3000);
      }
    } catch (err) {
      console.error('Failed to save vitals', err);
    } finally {
      setIsSubmitting(false);
    }
  };

  if (loading) {
    return <div style={{ padding: '40px', textAlign: 'center', color: '#64748b' }}>Loading triage queue...</div>;
  }

  const activeV = visits.find(v => v.visit_id === selectedVisitId);

  return (
    <div style={{ maxWidth: '820px', margin: '0 auto' }}>
      <div className="card">
        <div className="card-title">
          <Activity size={22} style={{ color: '#10b981' }} />
          <span>Nurse Station: OPD Vitals Triage</span>
        </div>
        <div className="card-subtitle">
          Record physical measurements for waiting patients before doctor consultation.
        </div>

        {savedSuccess && (
          <div style={{ background: '#ecfdf5', border: '1px solid #a7f3d0', padding: '12px 16px', borderRadius: '12px', color: '#065f46', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '20px' }}>
            <CheckCircle2 size={18} />
            <span>Vitals recorded successfully! Patient's Single Summary Card updated for Dr. Sharma.</span>
          </div>
        )}

        <form onSubmit={handleSaveVitals}>
          {/* Patient Selector */}
          <div className="form-group">
            <label className="form-label">Select Patient from OPD Queue *</label>
            <select
              className="form-select"
              value={selectedVisitId}
              onChange={(e) => setSelectedVisitId(e.target.value)}
              style={{ fontWeight: 700 }}
            >
              {visits.map((v) => (
                <option key={v.visit_id} value={v.visit_id}>
                  {v.token_number} - {v.patient_name} ({v.patient_id}) [{v.status.toUpperCase()}]
                </option>
              ))}
            </select>
          </div>

          {activeV && (
            <div style={{ background: '#f8fafc', padding: '12px 16px', borderRadius: '12px', border: '1px solid #e2e8f0', marginBottom: '20px', fontSize: '0.88rem' }}>
              <strong>Patient:</strong> {activeV.patient_name} ({activeV.patient_age} y/o, {activeV.patient_gender}) · 📞 {activeV.patient_phone}
            </div>
          )}

          {/* Vitals Inputs */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
            <div className="form-group">
              <label className="form-label">Blood Pressure (Systolic / Diastolic)</label>
              <div style={{ display: 'flex', gap: '8px' }}>
                <input
                  type="number"
                  className="form-input"
                  placeholder="Systolic"
                  value={bpSys}
                  onChange={(e) => setBpSys(e.target.value)}
                  required
                />
                <span style={{ alignSelf: 'center', color: '#64748b', fontWeight: 700 }}>/</span>
                <input
                  type="number"
                  className="form-input"
                  placeholder="Diastolic"
                  value={bpDia}
                  onChange={(e) => setBpDia(e.target.value)}
                  required
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Heart Rate (Pulse bpm)</label>
              <input
                type="number"
                className="form-input"
                value={hr}
                onChange={(e) => setHr(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Body Temperature (°F)</label>
              <input
                type="number"
                step="0.1"
                className="form-input"
                value={temp}
                onChange={(e) => setTemp(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">SpO2 Oxygen (%)</label>
              <input
                type="number"
                step="0.5"
                className="form-input"
                value={spo2}
                onChange={(e) => setSpo2(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Random Blood Sugar (mg/dL)</label>
              <input
                type="number"
                step="1"
                className="form-input"
                value={bs}
                onChange={(e) => setBs(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">Triage Nurse Staff ID</label>
              <input
                type="text"
                className="form-input"
                value={nurseId}
                onChange={(e) => setNurseId(e.target.value)}
                required
              />
            </div>
          </div>

          <button
            type="submit"
            className="btn-success"
            style={{ width: '100%', marginTop: '16px' }}
            disabled={isSubmitting}
          >
            <span>{isSubmitting ? 'Recording Vitals...' : 'Save Patient Vitals to Record'}</span>
          </button>
        </form>
      </div>
    </div>
  );
}
