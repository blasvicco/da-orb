// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getSession: vi.fn().mockReturnValue({}),
  hasSession: vi.fn().mockReturnValue(false),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));

// App imports
import { buildI18n, buildRouter, mount } from '@/tests/helpers/mount';
import App from '@/app.vue';

const setNavigatorLanguage = (lang) => {
  Object.defineProperty(window.navigator, 'language', { configurable: true, value: lang });
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.hasSession.mockReturnValue(false);
  mockAuth.getSession.mockReturnValue({});
  setNavigatorLanguage('en-US');
});

describe('App locale resolution on mount', () => {
  it("prefers the logged-in user's stored language", () => {
    mockAuth.hasSession.mockReturnValue(true);
    mockAuth.getSession.mockReturnValue({ language: 'es' });
    const i18n = buildI18n();
    mount(App, { global: { i18n } });
    expect(i18n.global.locale.value).toBe('es');
  });

  it("falls back to the visitor's stored language when logged out", () => {
    localStorage.setItem('visitor_language', 'es');
    const i18n = buildI18n();
    mount(App, { global: { i18n } });
    expect(i18n.global.locale.value).toBe('es');
  });

  it('ignores an unsupported stored visitor language', () => {
    localStorage.setItem('visitor_language', 'fr');
    setNavigatorLanguage('en-US');
    const i18n = buildI18n();
    mount(App, { global: { i18n } });
    expect(i18n.global.locale.value).toBe('en');
  });

  it('falls back to a supported browser language when nothing is stored', () => {
    setNavigatorLanguage('es-AR');
    const i18n = buildI18n();
    mount(App, { global: { i18n } });
    expect(i18n.global.locale.value).toBe('es');
  });

  it('falls back to the configured default locale when nothing else matches', () => {
    setNavigatorLanguage('fr-FR');
    const i18n = buildI18n();
    mount(App, { global: { i18n } });
    expect(i18n.global.locale.value).toBe('en');
  });
});

describe('App window event wiring', () => {
  it('navigates to landing on auth.logout', async () => {
    const router = buildRouter('/chat');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    mount(App, { global: { router } });

    window.dispatchEvent(new CustomEvent('auth.logout'));

    expect(pushSpy).toHaveBeenCalledWith({ name: 'landing' });
  });

  it('re-resolves and dispatches a language.changed event on auth.updated', () => {
    const changeSpy = vi.fn();
    window.addEventListener('language.changed', changeSpy);
    mockAuth.hasSession.mockReturnValue(true);
    mockAuth.getSession.mockReturnValue({ language: 'es' });
    mount(App);

    window.dispatchEvent(new CustomEvent('auth.updated'));

    expect(changeSpy).toHaveBeenCalledWith(expect.objectContaining({ detail: 'es' }));
    window.removeEventListener('language.changed', changeSpy);
  });

  it('stops reacting to window events after unmount', () => {
    const router = buildRouter('/chat');
    const wrapper = mount(App, { global: { router } });
    const pushSpy = vi.spyOn(router, 'push');
    wrapper.unmount();

    window.dispatchEvent(new CustomEvent('auth.logout'));

    expect(pushSpy).not.toHaveBeenCalled();
  });
});
