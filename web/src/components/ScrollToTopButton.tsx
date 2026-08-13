import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import './ScrollToTopButton.css';

const SCROLL_THRESHOLD = 300;

export function ScrollToTopButton() {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsVisible(window.scrollY > SCROLL_THRESHOLD);
    };

    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  if (!isVisible) return null;

  // The visible label is an arrow glyph, so the accessible name comes
  // entirely from `aria-label`. It was hardcoded English on an app that
  // ships nine locales (#409), and the glyph is hidden so a screen reader
  // reads the name rather than announcing "up arrow" after it.
  return (
    <button
      type="button"
      className="scroll-to-top-btn"
      onClick={scrollToTop}
      aria-label={t('a11y.scrollToTop')}
    >
      <span aria-hidden="true">↑</span>
    </button>
  );
}