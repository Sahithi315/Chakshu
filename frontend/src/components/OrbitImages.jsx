import React, { useEffect, useRef } from 'react';
import './OrbitImages.css';

export default function OrbitImages({ images, radiusX = 230, radiusY = 168, rotation = -8, duration = 34, itemSize = 72, depth = 0.55, showPath = true, centerContent }) {
  const rootRef = useRef(null);
  const itemRefs = useRef([]);

  useEffect(() => {
    const root = rootRef.current;
    if (!root || !images.length) return undefined;
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    let frameId = 0;
    let start = performance.now();

    const draw = (now) => {
      const widthScale = Math.min(1, Math.max(0.58, root.clientWidth / 590));
      const heightScale = Math.min(1, Math.max(0.7, root.clientHeight / 470));
      const scale = Math.min(widthScale, heightScale);
      const rx = radiusX * scale;
      const ry = radiusY * scale;
      const size = itemSize * scale;
      const orbitRotation = (rotation * Math.PI) / 180;
      const progress = reduceMotion.matches ? 0.08 : ((now - start) / (duration * 1000)) * Math.PI * 2;

      itemRefs.current.forEach((node, index) => {
        if (!node) return;
        const angle = progress + (index / images.length) * Math.PI * 2;
        const x = Math.cos(angle) * rx;
        const y = Math.sin(angle) * ry;
        const rotatedX = x * Math.cos(orbitRotation) - y * Math.sin(orbitRotation);
        const rotatedY = x * Math.sin(orbitRotation) + y * Math.cos(orbitRotation);
        const front = (Math.sin(angle) + 1) / 2;
        const depthScale = 1 - depth * 0.16 + front * depth * 0.28;
        node.style.width = `${size}px`;
        node.style.height = `${size}px`;
        node.style.opacity = String(0.72 + front * 0.28);
        node.style.zIndex = String(2 + Math.round(front * 8));
        node.style.transform = `translate3d(${rotatedX}px, ${rotatedY}px, 0) scale(${depthScale})`;
      });
      if (!reduceMotion.matches) frameId = requestAnimationFrame(draw);
    };

    const restart = () => {
      cancelAnimationFrame(frameId);
      start = performance.now();
      frameId = requestAnimationFrame(draw);
    };
    frameId = requestAnimationFrame(draw);
    reduceMotion.addEventListener?.('change', restart);
    return () => {
      cancelAnimationFrame(frameId);
      reduceMotion.removeEventListener?.('change', restart);
    };
  }, [depth, duration, images, itemSize, radiusX, radiusY, rotation]);

  return <div className="orbit-images" ref={rootRef}>
    {showPath && <div className="orbit-images-path" aria-hidden="true" />}
    <div className="orbit-images-center">{centerContent}</div>
    {images.map((image, index) => {
      const data = typeof image === 'string' ? { src: image } : image;
      return <div className="orbit-image-item" key={`${data.src}-${index}`} ref={(node) => { itemRefs.current[index] = node; }} role="img" aria-label={data.alt || `Healthcare scene ${index + 1}`} style={{ backgroundImage: `url(${data.src})`, backgroundPosition: data.position || 'center', backgroundSize: data.backgroundSize || 'cover' }} />;
    })}
  </div>;
}
