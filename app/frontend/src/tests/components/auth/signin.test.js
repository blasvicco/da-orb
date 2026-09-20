// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getError: vi.fn(),
  isLoading: vi.fn().mockReturnValue(false),
  signin: vi.fn(),
  signinWithCredentials: vi.fn().mockResolvedValue(),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));

// App imports
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import Signin from '@/components/auth/signin.vue';

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.isLoading.mockReturnValue(false);
});

describe('Signin — open_id / SAP shell', () => {
  it.each([
    ['an explicit open_id driver shows the SAP button', { auth_driver: 'open_id' }],
    ['no auth_driver at all also shows the SAP button', {}],
  ])('%s', (_label, context) => {
    const wrapper = mount(Signin, { props: { context } });
    expect(wrapper.find('#btn-sign-in-sap').exists()).toBe(true);
    expect(wrapper.find('#btn-sign-in-b1s').exists()).toBe(false);
  });

  it('clicking the SAP button starts the signin flow with the given context', async () => {
    const context = { auth_driver: 'open_id', base_url: 'https://sap.example.com' };
    const wrapper = mount(Signin, { props: { context } });

    await wrapper.find('#btn-sign-in-sap').trigger('click');

    expect(mockAuth.signin).toHaveBeenCalledWith(context);
  });

  it('disables the SAP button while auth is loading', () => {
    mockAuth.isLoading.mockReturnValue(true);
    const wrapper = mount(Signin, { props: { context: { auth_driver: 'open_id' } } });
    expect(wrapper.find('#btn-sign-in-sap').attributes('disabled')).toBeDefined();
  });
});

describe('Signin — B1S credential form', () => {
  it('renders the credential form for a b1s driver', () => {
    const wrapper = mount(Signin, { props: { context: { auth_driver: 'b1s' } } });
    expect(wrapper.find('#btn-sign-in-b1s').exists()).toBe(true);
    expect(wrapper.find('#btn-sign-in-sap').exists()).toBe(false);
  });

  it('submits the entered credentials and navigates to chat on success', async () => {
    mockAuth.getError.mockReturnValue(null);
    const router = buildRouter();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(Signin, {
      global: { router },
      props: { context: { auth_driver: 'b1s' } },
    });

    await wrapper.find('#b1s-username').setValue('bob');
    await wrapper.find('#b1s-password').setValue('secret');
    await wrapper.find('#b1s-database').setValue('TESTDB');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(mockAuth.signinWithCredentials).toHaveBeenCalledWith({
      database: 'TESTDB',
      password: 'secret',
      username: 'bob',
    });
    expect(pushSpy).toHaveBeenCalledWith({ name: 'chat' });
  });

  it('shows a translated message for a known error code, without navigating', async () => {
    mockAuth.getError.mockReturnValue('B1S_AUTH_FAILED');
    const router = buildRouter();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(Signin, {
      global: { router },
      props: { context: { auth_driver: 'b1s' } },
    });

    await wrapper.find('#b1s-username').setValue('bob');
    await wrapper.find('#b1s-password').setValue('wrong');
    await wrapper.find('#b1s-database').setValue('TESTDB');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('.orb-b1s-error').text()).toContain('We could not verify your SAP credentials');
    expect(pushSpy).not.toHaveBeenCalled();
  });

  it('falls back to the raw error code when no translation exists', async () => {
    mockAuth.getError.mockReturnValue('SOME_UNMAPPED_CODE');
    const wrapper = mount(Signin, { props: { context: { auth_driver: 'b1s' } } });

    await wrapper.find('#b1s-username').setValue('bob');
    await wrapper.find('#b1s-password').setValue('wrong');
    await wrapper.find('#b1s-database').setValue('TESTDB');
    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('.orb-b1s-error').text()).toContain('SOME_UNMAPPED_CODE');
  });

  it('disables the submit button and shows a submitting label while loading', () => {
    mockAuth.isLoading.mockReturnValue(true);
    const wrapper = mount(Signin, { props: { context: { auth_driver: 'b1s' } } });
    expect(wrapper.find('#btn-sign-in-b1s').attributes('disabled')).toBeDefined();
  });
});

describe('Signin loading overlay', () => {
  it('shows the loading overlay only while auth is loading', () => {
    mockAuth.isLoading.mockReturnValue(true);
    const loading = mount(Signin, { props: { context: {} } });
    expect(loading.find('.orb-auth-overlay').exists()).toBe(true);

    mockAuth.isLoading.mockReturnValue(false);
    const idle = mount(Signin, { props: { context: {} } });
    expect(idle.find('.orb-auth-overlay').exists()).toBe(false);
  });
});
