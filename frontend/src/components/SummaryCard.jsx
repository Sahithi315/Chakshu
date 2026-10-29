import React, { useState } from 'react';
import { Clock, AlertTriangle, CheckSquare, Copy, Check, Sparkles } from 'lucide-react';

export default function SummaryCard({ summary, patient, visit }) {
  const [copied, setCopied] = useState(false);

  if (!summary) {
    return (
      <div className="single-summary-card" style={{ textAlign: 'center', padding: '40px 20px', color: '#64748b' }}>
        <Sparkles size={32} style={{ color: '#94a3b8', margin: '0 auto 12px' }} />
        <div style={{ fontWeight: 600, fontSize: '0.98rem' }}>Summary Card Generating...</div>
        <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
          Will update automatically when patient intake or lab report is processed.
        </div>
      </div>
    );
  }

  const card = summary.single_card || {};
  const header = card.header || `PATIENT: ${patient?.name || 'Patient'}, ${patient?.age || '-'} | MRN ${patient?.patient_id || '-'} | Token ${visit?.token_number || '-'}`;
  const today = card.today || summary.concise_brief || 'Patient reported symptoms undergoing intake.';
  const historyBullets = card.relevant_history || (summary.patient_reported?.chronic_conditions ? [summary.patient_reported.chronic_conditions] : []);
  const sameComplaintBullets = card.same_complaint_before || ['First recorded presentation in this hospital OPD.'];
  const redFlag = card.red_flag;
  const confirmInRoom = card.confirm_in_room || summary.information_gaps || [];

  const handleCopy = () => {
    const textToCopy = card.raw_text || `${header}\n\nTODAY\n${today}\n\nRELEVANT HISTORY\n${historyBullets.map(b => `- ${b}`).join('\n')}\n\nSAME COMPLAINT BEFORE\n${sameComplaintBullets.map(b => `- ${b}`).join('\n')}\n\n${redFlag ? `⚠️ RED FLAG\n${redFlag}\n\n` : ''}CONFIRM IN ROOM\n${confirmInRoom.map(c => `- ${c}`).join('\n')}`;
    navigator.clipboard.writeText(textToCopy);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="single-summary-card">
      {/* Header bar */}
      <div className="summary-card-header">
        <div>
          <div className="summary-card-headline">{header}</div>
          <div style={{ fontSize: '0.76rem', color: '#64748b', marginTop: '2px' }}>
            Structured 10-15s Clinical Brief · Verified against uploaded evidence
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div className="summary-badge-timer">
            <Clock size={12} />
            <span>10-15 sec read</span>
          </div>
          <button
            onClick={handleCopy}
            className="btn-secondary"
            style={{ padding: '4px 10px', fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '4px' }}
            title="Copy brief to clipboard"
          >
            {copied ? <Check size={13} style={{ color: '#10b981' }} /> : <Copy size={13} />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
        </div>
      </div>

      {/* TODAY */}
      <div className="summary-section">
        <div className="summary-section-title">TODAY</div>
        <div className="summary-section-body" style={{ fontWeight: 500 }}>
          {today}
        </div>
      </div>

      {/* RELEVANT HISTORY */}
      <div className="summary-section">
        <div className="summary-section-title">RELEVANT HISTORY</div>
        <ul className="summary-bullets">
          {historyBullets.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      </div>

      {/* SAME COMPLAINT BEFORE */}
      <div className="summary-section">
        <div className="summary-section-title">SAME COMPLAINT BEFORE</div>
        <ul className="summary-bullets">
          {sameComplaintBullets.map((item, idx) => (
            <li key={idx} style={{ whiteSpace: 'pre-line' }}>{item}</li>
          ))}
        </ul>
      </div>

      {/* RED FLAG (Image 4 exact styling) */}
      {redFlag && (
        <div className="red-flag-box">
          <div className="red-flag-title">
            <AlertTriangle size={15} />
            <span>RED FLAG</span>
          </div>
          <div className="red-flag-body">{redFlag}</div>
        </div>
      )}

      {/* CONFIRM IN ROOM */}
      <div className="confirm-room-box">
        <div className="confirm-room-title">
          <CheckSquare size={13} style={{ display: 'inline', marginRight: '6px' }} />
          CONFIRM IN ROOM
        </div>
        <ul className="summary-bullets" style={{ marginTop: '6px' }}>
          {confirmInRoom.map((item, idx) => (
            <li key={idx} style={{ color: '#334155', fontWeight: 500 }}>{item}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
