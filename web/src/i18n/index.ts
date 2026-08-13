import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import en from './locales/en.json';
import gu from './locales/gu.json';
import hi from './locales/hi.json';
import kn from './locales/kn.json';
import ml from './locales/ml.json';
import mr from './locales/mr.json';
import ta from './locales/ta.json';
import te from './locales/te.json';
import bn from './locales/bn.json';
import as from './locales/as.json';
import ks from './locales/ks.json';
import mai from './locales/mai.json';
import ne from './locales/ne.json';
import or from './locales/or.json';
import sat from './locales/sat.json';
import sd from './locales/sd.json';
import ur from './locales/ur.json';

// Matches the Flutter app's supported locales.
i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      gu: { translation: gu },
      hi: { translation: hi },
      kn: { translation: kn },
      ml: { translation: ml },
      mr: { translation: mr },
      ta: { translation: ta },
      te: { translation: te },
      bn: { translation: bn },
      as: { translation: as },
      ks: { translation: ks },
      mai: { translation: mai },
      ne: { translation: ne },
      or: { translation: or },
      sat: { translation: sat },
      sd: { translation: sd },
      ur: { translation: ur },
    },
    fallbackLng: 'en',
    interpolation: { escapeValue: false },
  });

export default i18n;