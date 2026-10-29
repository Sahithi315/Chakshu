import React, { useState } from 'react';
import {
  Activity, AlertTriangle, Check, ClipboardCheck, Copy, FlaskConical,
  History, Sparkles, UserRound
} from 'lucide-react';

const cleanItems = items => (Array.isArray(items) ? items : [items])
  .map(item => String(item || '').trim())
  .filter(Boolean);

export default function SummaryCard({ summary, patient, visit, symptomExtraction, compact = false }) {
  const [copied, setCopied] = useState(false);

  if (!summary) {
    return (
      <div className="clinical-brief clinical-brief-empty">
        <Sparkles size={30} />
        <strong>Preparing the clinical brief…</strong>
        <span>It will update when intake, vitals, or report evidence becomes available.</span>
      </div>
    );
  }

  const card = summary.single_card || {};
  const reported = summary.patient_reported || {};
  const vitals = visit?.vitals || {};
  const today = card.today || summary.concise_brief || reported.reason_for_visit || 'No chief complaint recorded.';
  const narrative = reported.symptoms_description && reported.symptoms_description !== today
    ? reported.symptoms_description
    : '';
  const historyItems = cleanItems(card.relevant_history || reported.chronic_conditions || 'No relevant history recorded.');
  const priorItems = cleanItems(card.same_complaint_before || 'First recorded presentation in this hospital.');
  const checks = cleanItems(card.confirm_in_room || summary.information_gaps || 'Confirm current symptoms and medication history.');
  const temporal = summary.temporal_reasoning || {};
  const redFlag = card.red_flag;
  const abnormalLabs = summary.lab_evidence?.abnormal_results?.length || 0;
  const extractedSymptoms = (symptomExtraction?.symptoms || []).filter((item, index, items) => {
    const key = `${String(item.text || '').trim().toLowerCase()}-${Boolean(item.negated)}`;
    return item.text && items.findIndex(candidate => `${String(candidate.text || '').trim().toLowerCase()}-${Boolean(candidate.negated)}` === key) === index;
  });
  const reportedSymptoms = extractedSymptoms.filter(item => !item.negated);
  const deniedSymptoms = extractedSymptoms.filter(item => item.negated);
  const extractedDurations = cleanItems((symptomExtraction?.durations || []).map(item => item.text));
  const extractedSeverities = cleanItems((symptomExtraction?.severities || []).map(item => item.text));
  const durationText = reported.duration && reported.duration !== 'Unspecified'
    ? reported.duration
    : extractedDurations.join(', ') || 'Not stated';
  const severityText = reported.severity && reported.severity !== 'Unspecified'
    ? reported.severity
    : extractedSeverities.join(', ') || 'Not stated';

  const vitalItems = [
    { label: 'BP', value: vitals.bp_systolic ? `${vitals.bp_systolic}/${vitals.bp_diastolic}` : '—', unit: 'mmHg', alert: vitals.bp_systolic >= 140 || vitals.bp_diastolic >= 90 },
    { label: 'Pulse', value: vitals.heart_rate || '—', unit: 'bpm' },
    { label: 'Temp', value: vitals.temperature || '—', unit: '°F', alert: vitals.temperature >= 100.4 },
    { label: 'SpO₂', value: vitals.spo2 ? `${vitals.spo2}%` : '—', unit: '', alert: vitals.spo2 && vitals.spo2 < 95 },
    { label: 'Sugar', value: vitals.blood_sugar || '—', unit: 'mg/dL' }
  ];

  const handleCopy = async () => {
    const text = card.raw_text || [
      `${patient?.name || 'Patient'} | MRN ${patient?.patient_id || '—'} | ${visit?.token_number || '—'}`,
      `TODAY: ${today}`,
      narrative && `PATIENT WORDS: ${narrative}`,
      redFlag && `FLAGGED RISK: ${redFlag}`,
      `RELEVANT HISTORY:\n${historyItems.map(item => `- ${item}`).join('\n')}`,
      `VERIFY IN ROOM:\n${checks.map(item => `- ${item}`).join('\n')}`
    ].filter(Boolean).join('\n\n');
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <section className={`clinical-brief ${redFlag ? 'clinical-brief-flagged' : ''} ${compact ? 'clinical-brief-compact' : 'clinical-brief-dashboard'}`} aria-labelledby="clinical-brief-title">
      <header className="clinical-brief-header">
        <div className="clinical-brief-patient">
          <div className="clinical-brief-avatar"><UserRound size={22} /></div>
          <div>
            <div className="clinical-brief-kicker">Symptoms &amp; vitals</div>
            <h2 id="clinical-brief-title">{patient?.name || 'Patient'}</h2>
            <p>{patient?.age || '—'} yrs · {patient?.gender || 'Unspecified'} · MRN {patient?.patient_id || '—'}</p>
          </div>
        </div>
        <div className="clinical-brief-actions">
          <span className="clinical-token">{visit?.token_number || 'No token'}</span>
          <button type="button" className="clinical-copy-button" onClick={handleCopy} title="Copy clinical brief">
            {copied ? <Check size={15} /> : <Copy size={15} />}
            {copied ? 'Copied' : 'Copy brief'}
          </button>
        </div>
      </header>

      <div className="clinical-chief-complaint">
        <div className="clinical-section-label">Symptoms</div>
        {extractedSymptoms.length > 0 ? <div className="clinical-symptom-chips clinical-symptom-keywords">
            {reportedSymptoms.map((item, index) => <span key={`reported-${index}`} className="clinical-symptom-chip">{item.text}</span>)}
            {deniedSymptoms.map((item, index) => <span key={`denied-${index}`} className="clinical-symptom-chip clinical-symptom-denied">No {item.text}</span>)}
          </div> : <div className="clinical-chief-text">{reported.reason_for_visit || narrative || today}</div>}
        <div className="clinical-context-chips">
          <span><strong>Duration</strong>{durationText}</span>
          <span><strong>Severity</strong>{severityText}</span>
          <span><strong>Reports</strong>{summary.lab_evidence?.total_extracted || 0} results · {abnormalLabs} flagged</span>
        </div>
      </div>

      {redFlag && <div className="clinical-risk-banner" role="note">
        <AlertTriangle size={20} />
        <div><strong>Flagged for priority review</strong><span>{redFlag}</span></div>
      </div>}

      <div className="clinical-vitals-strip" aria-label="Nurse-recorded vitals">
        <div className="clinical-vitals-source"><Activity size={16} /><span>Nurse vitals</span></div>
        {vitalItems.map(item => <div key={item.label} className={`clinical-vital ${item.alert ? 'clinical-vital-alert' : ''}`}>
          <span>{item.label}</span><strong>{item.value}</strong><small>{item.unit}</small>
        </div>)}
      </div>

      <div className="clinical-brief-grid">
        <section className="clinical-brief-panel clinical-temporal-panel">
          <div className="clinical-panel-title"><History size={17} /><span>Change over time</span></div>
          <p className="clinical-temporal-headline">{temporal.headline || 'No earlier visit is available for comparison.'}</p>
          {temporal.evidence_terms?.length > 0 && <div className="clinical-temporal-terms">
            {temporal.evidence_terms.map(term => <span key={term}>{term}</span>)}
          </div>}
          {temporal.changes?.slice(0, 2).map((change, index) => <p className="clinical-temporal-change" key={index}>{change}</p>)}
          {temporal.vital_trends?.length > 0 && <div className="clinical-temporal-vitals">
            {temporal.vital_trends.slice(0, 3).map(trend => <span key={trend.label}><strong>{trend.label}</strong>{trend.direction}</span>)}
          </div>}
        </section>
        <section className="clinical-brief-panel">
          <div className="clinical-panel-title"><History size={17} /><span>Relevant context</span></div>
          <ul>{historyItems.slice(0, 4).map((item, index) => <li key={index}>{item}</li>)}</ul>
        </section>
        <section className="clinical-brief-panel clinical-check-panel">
          <div className="clinical-panel-title"><ClipboardCheck size={17} /><span>Verify in room</span></div>
          <ul>{checks.slice(0, 5).map((item, index) => <li key={index}>{item}</li>)}</ul>
        </section>
      </div>

      <details className="clinical-prior-pattern">
        <summary><FlaskConical size={16} /><span>Previous presentation and evidence</span><small>{priorItems.length} item{priorItems.length === 1 ? '' : 's'}</small></summary>
        <ul>{priorItems.map((item, index) => <li key={index}>{item}</li>)}</ul>
      </details>
    </section>
  );
}
