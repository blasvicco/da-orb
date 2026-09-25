// Libs imports
import { useI18n } from 'vue-i18n';

// Turns one API error into display text: { attr, detail } from drf-standardized-errors, or
// { error } from the hand-rolled resources. It applies the same detail -> key transform the
// shared table component uses (api.error.response.<attr>.<DETAIL_UPPER_SNAKE>), so one
// translation serves both; an error nobody has translated falls back to its own text.
export const useErrorText = () => {
  const { t, te } = useI18n();

  return (error) => {
    const code = (error?.detail || '').replace(/ /g, '_').replace(/\./g, '').toUpperCase();
    const key = `api.error.response.${error?.attr}.${code}`;
    return te(key) ? t(key) : (error?.detail || error?.error || 'ERROR');
  };
};
