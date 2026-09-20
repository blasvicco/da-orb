// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getError: vi.fn().mockReturnValue(null),
  isLoading: vi.fn().mockReturnValue(false),
  signin: vi.fn(),
  signinWithCredentials: vi.fn().mockResolvedValue(),
}));
const mockOrg = vi.hoisted(() => ({
  getContext: vi.fn().mockReturnValue({}),
  hasOrganization: vi.fn().mockReturnValue(null),
  load: vi.fn().mockResolvedValue(),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/organization', () => ({ useOrganization: () => mockOrg }));

// App imports
import { body, buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import { useContactModal } from '@/modules/contact';
import Landing from '@/views/landing.vue';
import Signin from '@/components/auth/signin.vue';

beforeEach(() => {
  vi.clearAllMocks();
  mockOrg.getContext.mockReturnValue({});
  mockOrg.hasOrganization.mockReturnValue(null);
  mockOrg.load.mockResolvedValue();
});

describe('Landing mount', () => {
  it('loads the organization context on mount', () => {
    mount(Landing);
    expect(mockOrg.load).toHaveBeenCalled();
  });

  it('unmounts cleanly, clearing its pending scenario timer and listener', () => {
    vi.useFakeTimers();
    const wrapper = mount(Landing);
    wrapper.unmount();
    expect(() => vi.runOnlyPendingTimers()).not.toThrow();
    vi.useRealTimers();
  });
});

describe('Landing chat scenario simulator', () => {
  it('plays through every scripted step and loops back to the start', async () => {
    vi.useFakeTimers();
    mount(Landing, { attachTo: document.body });

    // Step delays: user(1500), agent(hardcoded 1500), sap-data(hardcoded 1500),
    // user(2000), agent(hardcoded 1500), sap-data(hardcoded 1500).
    for (const ms of [1500, 1500, 1500, 2000, 1500, 1500]) {
      await vi.advanceTimersByTimeAsync(ms);
    }
    // All 6 steps have played; runScenarioStep now schedules the 8s loop-restart timer.
    await vi.advanceTimersByTimeAsync(8000);
    vi.useRealTimers();
  });

  it('does not crash if a scroll-to-bottom timer fires after unmount, once the container ref is gone', async () => {
    vi.useFakeTimers();
    const wrapper = mount(Landing, { attachTo: document.body });

    // First step (1500ms) pushes a message and schedules scrollToBottom's own
    // untracked 100ms timer — unmount races it before that timer fires.
    await vi.advanceTimersByTimeAsync(1500);
    wrapper.unmount();

    expect(() => vi.advanceTimersByTime(100)).not.toThrow();
    vi.useRealTimers();
  });
});

describe('Landing CTA', () => {
  it('shows the signup label and opens the contact modal when no organization is resolved', async () => {
    mockOrg.hasOrganization.mockReturnValue(false);
    const wrapper = mount(Landing);

    expect(wrapper.find('#btn-hero-signin').text()).toContain('Request Orb');

    await wrapper.find('#btn-hero-signin').trigger('click');

    const contactModal = useContactModal();
    expect(contactModal.isOpen).toBe(true);
  });

  it('signs in directly for an open_id (or driver-less) organization', async () => {
    mockOrg.hasOrganization.mockReturnValue(true);
    mockOrg.getContext.mockReturnValue({ auth_driver: 'open_id' });
    const wrapper = mount(Landing);

    expect(wrapper.find('#btn-hero-signin').text()).toContain('Sign In to Orb');
    await wrapper.find('#btn-hero-signin').trigger('click');

    expect(mockAuth.signin).toHaveBeenCalledWith({ auth_driver: 'open_id' });
  });

  it('signs in directly when no auth_driver is set at all', async () => {
    mockOrg.hasOrganization.mockReturnValue(true);
    mockOrg.getContext.mockReturnValue({});
    const wrapper = mount(Landing);

    await wrapper.find('#btn-hero-signin').trigger('click');

    expect(mockAuth.signin).toHaveBeenCalledWith({});
  });

  it('opens the credential sign-in modal for a b1s organization', async () => {
    mockOrg.hasOrganization.mockReturnValue(true);
    mockOrg.getContext.mockReturnValue({ auth_driver: 'b1s' });
    const wrapper = mount(Landing);

    await wrapper.find('#btn-hero-signin').trigger('click');

    // AModal's content is only reachable through the component tree here — its
    // Teleport target never receives content under happy-dom, so this checks the
    // reactive state that actually drives visibility rather than the DOM artifact.
    const [, , signinModal] = wrapper.findAllComponents({ name: 'AModal' });
    expect(signinModal.props('open')).toBe(true);
    expect(wrapper.findComponent(Signin).props('context')).toEqual({ auth_driver: 'b1s' });
  });

  it('closes the credential sign-in modal on cancel', async () => {
    mockOrg.hasOrganization.mockReturnValue(true);
    mockOrg.getContext.mockReturnValue({ auth_driver: 'b1s' });
    const wrapper = mount(Landing);
    await wrapper.find('#btn-hero-signin').trigger('click');
    await flushPromises();

    // Render order: [0] Default layout's own contact modal, [1] auth-error modal,
    // [2] sign-in modal (landing.vue's two trailing modals, in declaration order).
    const [, , signinModal] = wrapper.findAllComponents({ name: 'AModal' });
    expect(signinModal.props('open')).toBe(true);

    await signinModal.vm.$emit('cancel');

    expect(signinModal.props('open')).toBe(false);
  });

  it('re-triggers the CTA flow when auth.trigger_signin is dispatched on window', async () => {
    mockOrg.hasOrganization.mockReturnValue(false);
    mount(Landing);

    window.dispatchEvent(new CustomEvent('auth.trigger_signin'));

    const contactModal = useContactModal();
    expect(contactModal.isOpen).toBe(true);
  });

  it('stops reacting to auth.trigger_signin after unmount', async () => {
    mockOrg.hasOrganization.mockReturnValue(false);
    const wrapper = mount(Landing);
    wrapper.unmount();

    window.dispatchEvent(new CustomEvent('auth.trigger_signin'));

    const contactModal = useContactModal();
    expect(contactModal.isOpen).toBe(false);
  });
});

describe('Landing auth-error modal', () => {
  // Render order: [0] Default layout's own contact modal, [1] auth-error modal,
  // [2] sign-in modal (landing.vue's two trailing modals, in declaration order).
  const authErrorModal = (wrapper) => wrapper.findAllComponents({ name: 'AModal' })[1];

  it('shows the auth error modal when the route carries an error query param', async () => {
    const router = buildRouter('/?error=access_denied');
    await router.isReady();
    const wrapper = mount(Landing, { global: { router } });
    await flushPromises();

    expect(authErrorModal(wrapper).props('open')).toBe(true);
  });

  it('does not show the auth error modal without an error query param', () => {
    const wrapper = mount(Landing);
    expect(authErrorModal(wrapper).props('open')).toBe(false);
  });

  it('closes the auth error modal and clears the query param', async () => {
    const router = buildRouter('/?error=access_denied');
    await router.isReady();
    const replaceSpy = vi.spyOn(router, 'replace');
    const wrapper = mount(Landing, { global: { router } });

    await authErrorModal(wrapper).vm.$emit('cancel');

    expect(replaceSpy).toHaveBeenCalledWith({ name: 'landing' });
  });

  it('closes the auth error modal via its close button', async () => {
    const router = buildRouter('/?error=access_denied');
    await router.isReady();
    const replaceSpy = vi.spyOn(router, 'replace');
    mount(Landing, { global: { router }, attachTo: document.body });
    await flushPromises();

    await body().find('#btn-auth-error-close').trigger('click');

    expect(replaceSpy).toHaveBeenCalledWith({ name: 'landing' });
  });
});
