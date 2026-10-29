import { useEffect, useLayoutEffect, useRef } from 'react';
import './AnimatedContent.css';

const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

const easingMap = {
  'power3.out': 'cubic-bezier(0.22, 1, 0.36, 1)',
  'power2.out': 'cubic-bezier(0.16, 1, 0.3, 1)',
  'power3.in': 'cubic-bezier(0.64, 0, 0.78, 0)'
};

export default function AnimatedContent({
  children,
  distance = 100,
  direction = 'vertical',
  reverse = false,
  duration = 0.8,
  ease = 'power3.out',
  initialOpacity = 0,
  animateOpacity = true,
  scale = 1,
  blur = 0,
  threshold = 0.1,
  delay = 0,
  stagger = 0,
  trigger = 'scroll',
  once = true,
  className = '',
  style,
  onStart,
  onComplete,
  ...props
}) {
  const ref = useRef(null);
  const hasPlayed = useRef(false);
  const callbacks = useRef({ onStart, onComplete });
  callbacks.current = { onStart, onComplete };

  useIsomorphicLayoutEffect(() => {
    const element = ref.current;
    if (!element) return undefined;

    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    let animations = [];
    let observer;

    const findTargets = () => {
      const directChildren = Array.from(element.children).filter(child => child.getAttribute('aria-hidden') !== 'true');
      if (stagger <= 0) return [element];
      if (directChildren.length === 1) {
        const pageSections = Array.from(directChildren[0].children).filter(child => child.getAttribute('aria-hidden') !== 'true');
        if (pageSections.length > 1) return pageSections;
      }
      return directChildren.length ? directChildren : [element];
    };

    const play = () => {
      if (hasPlayed.current && once) return;
      hasPlayed.current = true;
      element.style.visibility = 'visible';
      callbacks.current.onStart?.();

      if (reduceMotion || !element.animate) {
        callbacks.current.onComplete?.();
        return;
      }

      const offset = distance * (reverse ? -1 : 1);
      const fromTransform = direction === 'horizontal'
        ? `translate3d(${offset}px, 0, 0) scale(${scale})`
        : `translate3d(0, ${offset}px, 0) scale(${scale})`;
      const targets = findTargets();
      let completed = 0;

      animations = targets.map((target, index) => {
        const animation = target.animate([
          {
            transform: fromTransform,
            opacity: animateOpacity ? initialOpacity : 1,
            filter: blur > 0 ? `blur(${blur}px)` : 'none'
          },
          { transform: 'translate3d(0, 0, 0) scale(1)', opacity: 1, filter: 'none' }
        ], {
          duration: Math.max(0, duration) * 1000,
          delay: (Math.max(0, delay) + index * Math.max(0, stagger)) * 1000,
          easing: easingMap[ease] || ease,
          fill: 'both'
        });
        animation.finished.then(() => {
          animation.cancel();
          completed += 1;
          if (completed === targets.length) callbacks.current.onComplete?.();
        }).catch(() => {});
        return animation;
      });
    };

    if (trigger === 'mount') {
      play();
    } else {
      observer = new IntersectionObserver(([entry]) => {
        if (entry.isIntersecting) play();
        else if (!once) hasPlayed.current = false;
      }, { threshold: Math.max(0, Math.min(1, threshold)) });
      observer.observe(element);
    }

    return () => {
      observer?.disconnect();
      animations.forEach(animation => animation.cancel());
    };
  }, [distance, direction, reverse, duration, ease, initialOpacity, animateOpacity, scale, blur, threshold, delay, stagger, trigger, once]);

  return (
    <div
      ref={ref}
      className={`animated-content ${className}`.trim()}
      style={{ visibility: 'hidden', ...style }}
      {...props}
    >
      {children}
    </div>
  );
}
