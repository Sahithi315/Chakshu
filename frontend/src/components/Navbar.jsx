import React, { useMemo, useState } from 'react';
import { LogOut, Stethoscope } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import CardNav from './CardNav';

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [showLogoutConfirmation, setShowLogoutConfirmation] = useState(false);
  const [loggingOut, setLoggingOut] = useState(false);

  const requestLogout = event => {
    event?.preventDefault?.();
    setShowLogoutConfirmation(true);
  };

  const handleLogoClick = event => {
    if (user) requestLogout(event);
  };

  const confirmLogout = async () => {
    setLoggingOut(true);
    await logout();
    setShowLogoutConfirmation(false);
    setLoggingOut(false);
    navigate('/', { replace: true });
  };

  const items = useMemo(() => {
    if (user?.role === 'doctor') return [
      {
        label: 'Doctor workspace',
        description: 'Open the current queue or patient history.',
        links: [
          { label: 'Patient queue', href: '/doctor/queue' },
          { label: 'Patient records', href: '/doctor/records' }
        ]
      },
      {
        label: user.display_name,
        description: 'Signed in as doctor.',
        links: [{ label: 'Sign out', onClick: requestLogout }]
      }
    ];
    if (user?.role === 'nurse') return [
      {
        label: 'Nurse workspace',
        description: 'Open the allotted patient queue.',
        links: [{ label: 'Vitals queue', href: '/nurse/queue' }]
      },
      {
        label: user.display_name,
        description: 'Signed in as nurse.',
        links: [{ label: 'Sign out', onClick: requestLogout }]
      }
    ];
    return [
      {
        label: 'Patient',
        description: 'Register or continue today’s check-in.',
        links: [{ label: 'Patient check-in', href: '/patient/check-in' }]
      },
      {
        label: 'Nurse',
        description: 'Open the nurse sign-in and triage workspace.',
        links: [{ label: 'Nurse sign-in', href: '/staff/login?role=nurse' }]
      },
      {
        label: 'Doctor',
        description: 'Open the doctor sign-in and consultation workspace.',
        links: [{ label: 'Doctor sign-in', href: '/staff/login?role=doctor' }]
      }
    ];
  }, [user]);

  const logo = <><span className="card-nav__brand-mark"><Stethoscope size={20} /></span><span>CareVision</span></>;

  return <>
    <CardNav
      logo={logo}
      logoAlt="CareVision home"
      items={items}
      cta={user ? { label: 'Sign out', onClick: requestLogout } : { label: 'Home', href: '/' }}
      cardEffect="rise"
      openOn="click"
      onLogoClick={handleLogoClick}
    />

    {showLogoutConfirmation && user && <div className="logout-confirm-backdrop" role="presentation" onMouseDown={event => { if (event.target === event.currentTarget) setShowLogoutConfirmation(false); }}>
      <div className="logout-confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="logout-confirm-title">
        <div className="logout-confirm-icon"><LogOut size={23} /></div>
        <h3 id="logout-confirm-title">Log out of the {user.role} workspace?</h3>
        <p>You are currently signed in as <strong>{user.display_name}</strong>. Would you like to log out and return to workspace selection?</p>
        <div className="logout-confirm-actions">
          <button type="button" className="btn-secondary" onClick={() => setShowLogoutConfirmation(false)} disabled={loggingOut}>Stay on this page</button>
          <button type="button" className="btn-primary" onClick={confirmLogout} disabled={loggingOut}><LogOut size={17} />{loggingOut ? 'Logging out...' : 'Yes, log out'}</button>
        </div>
      </div>
    </div>}
  </>;
}
