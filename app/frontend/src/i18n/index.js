// Lib imports
import { createI18n } from 'vue-i18n';

// Language imports
import en from '@/i18n/lng/en.js';
import es from '@/i18n/lng/es.js';

export default createI18n({
  fallbackLocale: __APP_ENV__.FALLBACK_LOCALE,
  globalInjection: true,
  legacy: false,
  locale: __APP_ENV__.DEFAULT_LOCALE,
  messages: { en, es },
});
