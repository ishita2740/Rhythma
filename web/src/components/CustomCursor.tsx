import { useEffect, useRef, useState } from 'react';
import './CustomCursor.css';

const INTERACTIVE_SELECTOR = 'a, button, input, textarea, select, [role="button"], [data-cursor-hover]';

export function CustomCursor() {
  const dotRef = useRef<HTMLDivElement>(null);
  const ringRef = useRef<HTMLDivElement>(null);
  const rafId = useRef<number | null>(null);
  const [isTouchDevice, setIsTouchDevice] = useState(true);
  const [isPointer, setIsPointer] = useState(false);
  const [isClicking, setIsClicking] = useState(false);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const hasTouch = window.matchMedia('(pointer: coarse)').matches || 'ontouchstart' in window;
    setIsTouchDevice(hasTouch);
  }, []);

  useEffect(() => {
    if (isTouchDevice) {
      document.body.classList.remove('custom-cursor-active');
      return;
    }

    document.body.classList.add('custom-cursor-active');

    const handleMouseMove = (e: MouseEvent) => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current);
      }

      rafId.current = requestAnimationFrame(() => {
        setIsVisible(true);
        if (dotRef.current) {
          dotRef.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
        }
        if (ringRef.current) {
          ringRef.current.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
        }
        const target = e.target as HTMLElement | null;
        if (target) {
          setIsPointer(Boolean(target.closest(INTERACTIVE_SELECTOR)));
        }
      });
    };

    const handleMouseDown = () => setIsClicking(true);
    const handleMouseUp = () => setIsClicking(false);
    const handleMouseLeave = () => setIsVisible(false);

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mousedown', handleMouseDown);
    window.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      if (rafId.current !== null) {
        cancelAnimationFrame(rafId.current);
      }
      document.body.classList.remove('custom-cursor-active');
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mousedown', handleMouseDown);
      window.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [isTouchDevice]);

  if (isTouchDevice) return null;

  // Purely decorative — two divs that trail the pointer. Without
  // `aria-hidden` a screen reader walks into them as unlabelled nodes in
  // the middle of the page content (#409).
  return (
    <>
      <div
        ref={dotRef}
        aria-hidden="true"
        className={`custom-cursor-dot ${isVisible ? 'is-visible' : ''} ${isClicking ? 'is-clicking' : ''}`}
      />
      <div
        ref={ringRef}
        aria-hidden="true"
        className={`custom-cursor-ring ${isVisible ? 'is-visible' : ''} ${isPointer ? 'is-pointer' : ''} ${isClicking ? 'is-clicking' : ''}`}
      />
    </>
  );
}