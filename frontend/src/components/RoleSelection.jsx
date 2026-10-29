import React from 'react';
import { Activity, ArrowRight, ClipboardList, Stethoscope } from 'lucide-react';
import { Link } from 'react-router-dom';
import OrbitImages from './OrbitImages';

const orbitImages = Array.from({ length: 6 }, (_, index) => ({
  src: '/assets/clinical-orbit-contact-sheet.png',
  alt: [
    'Doctor ready to support a consultation',
    'Doctor reviewing clinical information',
    'Nurse speaking with a patient',
    'Clinician checking blood pressure',
    'Connected clinical care team',
    'Stethoscope and clinical clipboard'
  ][index],
  backgroundSize: '300% 200%',
  position: `${(index % 3) * 50}% ${Math.floor(index / 3) * 100}%`
}));

export default function RoleSelection() {
  return <section className="role-boundary">
    <div className="role-landing-visual">
      <OrbitImages images={orbitImages} radiusX={255} radiusY={190} rotation={-8} duration={36} itemSize={72} depth={0.5} showPath centerContent={<div className="role-mission">
        <span className="eyebrow">Care, clearly connected</span>
        <h1>One simple path from check-in to care.</h1>
        <p>Keep every patient, vital sign, and clinical decision moving with the right care team.</p>
      </div>} />
    </div>

    <div className="role-landing-actions">
      <div className="role-boundary-heading">
        <span className="eyebrow">Get started</span>
        <h2>Choose your workspace</h2>
        <p>Select where you want to continue.</p>
      </div>
      <div className="role-choice-grid">
        <Link to="/patient/check-in" className="role-choice"><ClipboardList size={26} /><div><h3>Patient check-in</h3><p>Check in and share today&apos;s concern.</p></div><ArrowRight size={20} /></Link>
        <Link to="/staff/login?role=nurse" className="role-choice"><Activity size={26} /><div><h3>Nurse station</h3><p>Open the triage queue and record vitals.</p></div><ArrowRight size={20} /></Link>
        <Link to="/staff/login?role=doctor" className="role-choice"><Stethoscope size={26} /><div><h3>Doctor workspace</h3><p>Review visits and complete consultations.</p></div><ArrowRight size={20} /></Link>
      </div>
    </div>
  </section>;
}
