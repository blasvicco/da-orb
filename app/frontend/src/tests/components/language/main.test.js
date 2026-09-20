// Libs imports
import { describe, expect, it, vi } from 'vitest';

// App imports
import { buildI18n, mount } from '@/tests/helpers/mount';
import LanguageSelector from '@/components/language/main.vue';

describe('LanguageSelector', () => {
  it('renders the language select control seeded with the active locale', () => {
    const wrapper = mount(LanguageSelector);
    expect(wrapper.findComponent({ name: 'ASelect' }).props('defaultValue')).toBe('en');
  });

  it('changing the selection updates the active locale, persists it, and notifies listeners', async () => {
    const i18n = buildI18n();
    const wrapper = mount(LanguageSelector, { global: { i18n } });
    const listener = vi.fn();
    window.addEventListener('language.changed', listener);

    await wrapper.findComponent({ name: 'ASelect' }).vm.$emit('change', 'es');

    expect(i18n.global.locale.value).toBe('es');
    expect(localStorage.getItem('visitor_language')).toBe('es');
    expect(listener).toHaveBeenCalledWith(expect.objectContaining({ detail: 'es' }));

    window.removeEventListener('language.changed', listener);
  });
});
