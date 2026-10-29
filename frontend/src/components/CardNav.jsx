import React, { useEffect, useId, useRef, useState } from 'react';
import { ArrowUpRight, Menu, X } from 'lucide-react';
import { Link } from 'react-router-dom';
import './CardNav.css';

export default function CardNav({
  logo,
  logoAlt = 'Home',
  logoHref = '/',
  onLogoClick,
  items = [],
  cta,
  openOn = 'click',
  cardEffect = 'rise'
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const contentId = useId();

  useEffect(() => {
    if (!open) return undefined;
    const closeOutside = event => {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    };
    const closeOnEscape = event => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', closeOutside);
    document.addEventListener('keydown', closeOnEscape);
    return () => {
      document.removeEventListener('pointerdown', closeOutside);
      document.removeEventListener('keydown', closeOnEscape);
    };
  }, [open]);

  const handlePointerEnter = event => {
    if (openOn === 'hover' && event.pointerType !== 'touch') setOpen(true);
  };

  const renderLink = link => link.href ? (
    <Link key={link.label} to={link.href} className="card-nav__link" onClick={() => setOpen(false)}>
      <span>{link.label}</span><ArrowUpRight size={15} />
    </Link>
  ) : (
    <button key={link.label} type="button" className="card-nav__link" onClick={event => { link.onClick?.(event); setOpen(false); }}>
      <span>{link.label}</span><ArrowUpRight size={15} />
    </button>
  );

  return (
    <div ref={rootRef} className={`card-nav ${open ? 'is-open' : ''}`} data-effect={cardEffect} onPointerEnter={handlePointerEnter}>
      <nav className="card-nav__panel" aria-label="Primary navigation">
        <div className="card-nav__bar">
          <button type="button" className="card-nav__menu" aria-expanded={open} aria-controls={contentId} onClick={() => setOpen(current => !current)}>
            {open ? <X size={18} /> : <Menu size={18} />}
            <span>{open ? 'Close' : 'Menu'}</span>
          </button>

          <Link to={logoHref} onClick={onLogoClick} className="card-nav__logo" aria-label={logoAlt}>
            {logo}
          </Link>

          {cta && (cta.href ? (
            <Link to={cta.href} className="card-nav__cta" onClick={() => setOpen(false)}>{cta.label}</Link>
          ) : (
            <button type="button" className="card-nav__cta" onClick={cta.onClick}>{cta.label}</button>
          ))}
        </div>

        <div id={contentId} className="card-nav__content" aria-hidden={!open}>
          <div className="card-nav__cards">
            {items.map((item, index) => (
              <section key={item.label} className="card-nav__card" style={{ '--card-order': index }}>
                <div>
                  <h2>{item.label}</h2>
                  {item.description && <p>{item.description}</p>}
                </div>
                <div className="card-nav__links">{(item.links || []).map(renderLink)}</div>
              </section>
            ))}
          </div>
        </div>
      </nav>
    </div>
  );
}
