import { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import './AnimatedList.css';

const useIsomorphicLayoutEffect = typeof window === 'undefined' ? useEffect : useLayoutEffect;

const THEMES = {
  light: {
    '--al-frame': 'rgba(240, 246, 252, 0.88)',
    '--al-frame-edge': 'rgba(37, 99, 235, 0.10)',
    '--al-frame-highlight': 'rgba(255, 255, 255, 0.98)',
    '--al-frame-shadow': '0 18px 38px -24px rgba(37, 99, 235, 0.34)',
    '--al-tile': 'linear-gradient(180deg, #ffffff 0%, #f8fbff 100%)',
    '--al-tile-edge': 'rgba(37, 99, 235, 0.10)',
    '--al-tile-highlight': '#ffffff',
    '--al-tile-shadow': '0 4px 10px -7px rgba(15, 23, 42, 0.28)',
    '--al-ink': '#0f172a',
    '--al-muted': '#64748b',
    '--al-thumb': 'rgba(37, 99, 235, 0.22)',
    '--al-ring': '#2563eb',
    '--al-ring-fill': 'rgba(37, 99, 235, 0.07)',
    '--al-hover': 'brightness(0.985)',
    '--al-press': 'brightness(0.94)'
  },
  dark: {
    '--al-frame': 'rgba(38, 35, 46, 0.78)',
    '--al-frame-edge': 'rgba(255, 255, 255, 0.08)',
    '--al-frame-highlight': 'rgba(255, 255, 255, 0.07)',
    '--al-frame-shadow': '0 22px 44px -20px rgba(0, 0, 0, 0.8)',
    '--al-tile': 'linear-gradient(180deg, #3a3644 0%, #27242f 100%)',
    '--al-tile-edge': 'rgba(255, 255, 255, 0.07)',
    '--al-tile-highlight': 'rgba(255, 255, 255, 0.12)',
    '--al-tile-shadow': '0 4px 10px -4px rgba(0, 0, 0, 0.7)',
    '--al-ink': '#f4f4f5',
    '--al-muted': 'rgba(244, 244, 245, 0.58)',
    '--al-thumb': 'rgba(255, 255, 255, 0.16)',
    '--al-ring': '#f4f4f5',
    '--al-ring-fill': 'rgba(244, 244, 245, 0.05)',
    '--al-hover': 'brightness(1.1)',
    '--al-press': 'brightness(0.86)'
  }
};

const HIDDEN = {
  pop: { above: 'translate3d(0,-12px,0) scale(.82)', below: 'translate3d(0,12px,0) scale(.82)' },
  slide: { above: 'translate3d(0,-26px,0) scale(.98)', below: 'translate3d(0,26px,0) scale(.98)' },
  fade: { above: 'translate3d(0,-4px,0)', below: 'translate3d(0,4px,0)' }
};

const size = value => typeof value === 'number' ? `${value}px` : value;

export default function AnimatedList({
  items = [], onItemSelect, renderItem, selectedIndex, initialSelectedIndex = -1,
  selectOnHover = false, animation = 'pop', theme = 'light', frame = true,
  showGradients = true, radius = 12, gap = 8, width = '100%', maxHeight = 440,
  className = ''
}) {
  const rootRef = useRef(null);
  const viewportRef = useRef(null);
  const itemRefs = useRef([]);
  const [selected, setSelected] = useState(selectedIndex ?? initialSelectedIndex);
  const baseId = useId();

  useEffect(() => {
    if (typeof selectedIndex === 'number') setSelected(selectedIndex);
  }, [selectedIndex]);

  useIsomorphicLayoutEffect(() => {
    const root = rootRef.current;
    const viewport = viewportRef.current;
    if (!root || !viewport) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const mode = reduced ? 'fade' : animation;
    const pose = HIDDEN[mode] || HIDDEN.fade;
    const elements = itemRefs.current.filter(Boolean);
    elements.forEach((element, index) => {
      element.style.transition = 'none';
      element.style.opacity = '0';
      element.style.transform = pose.below;
      element.style.transitionDelay = `${Math.min(index * 0.045, 0.32)}s`;
    });
    void root.offsetHeight;
    elements.forEach(element => {
      element.style.transition = 'transform 540ms cubic-bezier(.2,.9,.25,1.18), opacity 280ms ease, filter 160ms ease';
      element.style.opacity = '1';
      element.style.transform = 'translate3d(0,0,0) scale(1)';
    });
    const onScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = viewport;
      root.dataset.topFade = showGradients && scrollTop > 4 ? 'true' : 'false';
      root.dataset.bottomFade = showGradients && scrollHeight - clientHeight - scrollTop > 4 ? 'true' : 'false';
    };
    viewport.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => viewport.removeEventListener('scroll', onScroll);
  // Entrance motion is intentionally mount-only. Selection and filtering must
  // not replay the pop animation or make the queue feel like it is jumping.
  }, []);

  const choose = (item, index) => {
    setSelected(index);
    onItemSelect?.(item, index);
  };

  const onKeyDown = event => {
    if (!items.length) return;
    let next = selected;
    if (event.key === 'ArrowDown') next = Math.min(items.length - 1, selected < 0 ? 0 : selected + 1);
    else if (event.key === 'ArrowUp') next = Math.max(0, selected < 0 ? items.length - 1 : selected - 1);
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = items.length - 1;
    else if ((event.key === 'Enter' || event.key === ' ') && selected >= 0) {
      event.preventDefault(); onItemSelect?.(items[selected], selected); return;
    } else return;
    event.preventDefault();
    setSelected(next);
    itemRefs.current[next]?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  };

  return <div ref={rootRef} className={`animated-list ${frame ? 'animated-list--framed' : ''} ${className}`.trim()} style={{ ...(THEMES[theme] || THEMES.light), '--al-radius': `${radius}px`, '--al-gap': `${gap}px`, '--al-width': size(width) }}>
    <div ref={viewportRef} className="animated-list__viewport" role="listbox" tabIndex={0} onKeyDown={onKeyDown} aria-activedescendant={selected >= 0 ? `${baseId}-${selected}` : undefined} style={{ maxHeight: size(maxHeight) }}>
      <div className="animated-list__track">
        {items.map((item, index) => {
          const entry = item && typeof item === 'object' ? item : { title: item };
          const isSelected = selected === index;
          return <div key={entry.id ?? index} ref={element => { itemRefs.current[index] = element; }} id={`${baseId}-${index}`} className="animated-list__item" role="option" aria-selected={isSelected} data-selected={isSelected ? '' : undefined} onPointerEnter={selectOnHover ? () => setSelected(index) : undefined} onClick={() => choose(item, index)}>
            {renderItem ? renderItem(item, index, isSelected) : <><span className="animated-list__text"><span className="animated-list__title">{entry.title}</span>{entry.description && <span className="animated-list__description">{entry.description}</span>}</span>{entry.meta && <span className="animated-list__meta">{entry.meta}</span>}</>}
            <span className="animated-list__rim" aria-hidden="true" />
          </div>;
        })}
      </div>
    </div>
    <span className="animated-list__frame-rim" aria-hidden="true" />
  </div>;
}
