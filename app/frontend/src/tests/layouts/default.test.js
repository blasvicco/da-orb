// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockOrg = vi.hoisted(() => ({
  getContext: vi.fn().mockReturnValue({}),
  hasOrganization: vi.fn().mockReturnValue(null),
  load: vi.fn().mockResolvedValue(),
}));

vi.mock('@/modules/organization', () => ({ useOrganization: () => mockOrg }));

// App imports
import { buildRouter, mount } from '@/tests/helpers/mount';
import { useContactModal } from '@/modules/contact';
import DefaultLayout from '@/layouts/default.vue';

beforeEach(() => {
  vi.clearAllMocks();
  mockOrg.getContext.mockReturnValue({});
  mockOrg.hasOrganization.mockReturnValue(null);
  mockOrg.load.mockResolvedValue();
});

describe('DefaultLayout mount', () => {
  it('loads the organization context on mount', () => {
    mount(DefaultLayout);
    expect(mockOrg.load).toHaveBeenCalled();
  });
});

describe('DefaultLayout nav anchors', () => {
  it('navigates to the landing page with a hash when clicked from a non-landing route', async () => {
    const router = buildRouter('/terms');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(DefaultLayout, { global: { router } });

    await wrapper.find('.orb-nav-link').trigger('click');

    expect(pushSpy).toHaveBeenCalledWith({ hash: '#features', name: 'landing' });
  });

  it('scrolls the section into view when already on the landing page', async () => {
    const router = buildRouter('/');
    await router.isReady();
    const scrollIntoView = vi.fn();
    // Scoped to '#features' only — antdv-next's own style-injection also calls
    // document.querySelector internally, so a blanket stub breaks unrelated renders.
    const realQuerySelector = document.querySelector.bind(document);
    const querySelectorSpy = vi.spyOn(document, 'querySelector').mockImplementation((selector) =>
      (selector === '#features' ? { scrollIntoView } : realQuerySelector(selector)));
    const wrapper = mount(DefaultLayout, { global: { router } });

    await wrapper.find('.orb-nav-link').trigger('click');

    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: 'smooth' });
    querySelectorSpy.mockRestore();
  });

  it('does nothing when the anchor target is not found on the landing page', async () => {
    const router = buildRouter('/');
    await router.isReady();
    const realQuerySelector = document.querySelector.bind(document);
    const querySelectorSpy = vi.spyOn(document, 'querySelector').mockImplementation((selector) =>
      (selector === '#security' ? null : realQuerySelector(selector)));
    const wrapper = mount(DefaultLayout, { global: { router } });

    await wrapper.findAll('.orb-nav-link')[1].trigger('click');

    expect(querySelectorSpy).toHaveBeenCalledWith('#security');
    querySelectorSpy.mockRestore();
  });
});

describe('DefaultLayout CTA', () => {
  it('shows the signup label and opens the contact modal when no organization is resolved', async () => {
    mockOrg.hasOrganization.mockReturnValue(false);
    const wrapper = mount(DefaultLayout);

    expect(wrapper.find('.orb-btn-primary').text()).toBe('Request Orb');

    await wrapper.find('.orb-btn-primary').trigger('click');

    const contactModal = useContactModal();
    expect(contactModal.isOpen).toBe(true);
  });

  it('shows the signin label and dispatches auth.trigger_signin when an organization is resolved', async () => {
    mockOrg.hasOrganization.mockReturnValue(true);
    const wrapper = mount(DefaultLayout);
    const dispatchSpy = vi.spyOn(window, 'dispatchEvent');

    expect(wrapper.find('.orb-btn-primary').text()).toBe('Sign In to Orb');

    await wrapper.find('.orb-btn-primary').trigger('click');

    expect(dispatchSpy).toHaveBeenCalledWith(expect.objectContaining({ type: 'auth.trigger_signin' }));
    dispatchSpy.mockRestore();
  });
});

describe('DefaultLayout contact modal', () => {
  it('closes the contact modal on cancel', async () => {
    const contactModal = useContactModal();
    contactModal.open();
    const wrapper = mount(DefaultLayout);

    await wrapper.findComponent({ name: 'AModal' }).vm.$emit('cancel');

    expect(contactModal.isOpen).toBe(false);
  });
});

describe('DefaultLayout footer', () => {
  it('links to the privacy and terms routes', () => {
    const wrapper = mount(DefaultLayout);
    const links = wrapper.findAllComponents({ name: 'RouterLink' });
    expect(links.some((link) => link.props('to').name === 'privacy')).toBe(true);
    expect(links.some((link) => link.props('to').name === 'terms')).toBe(true);
  });
});
