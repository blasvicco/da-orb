// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  callback: vi.fn(),
  hasSession: vi.fn().mockReturnValue(false),
  isAdmin: vi.fn().mockReturnValue(false),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));

// App imports
import router from '@/router';

beforeEach(async () => {
  vi.clearAllMocks();
  mockAuth.hasSession.mockReturnValue(false);
  mockAuth.isAdmin.mockReturnValue(false);
  await router.push('/');
  await router.isReady();
});

describe('router auth guard', () => {
  it('redirects an unauthenticated user away from an auth-required route, preserving the target', async () => {
    await router.push('/chat');
    expect(router.currentRoute.value.name).toBe('landing');
    expect(router.currentRoute.value.query.redirect).toBe('/chat');
  });

  it('allows an authenticated user onto an auth-required, non-admin route', async () => {
    mockAuth.hasSession.mockReturnValue(true);
    await router.push('/chat');
    expect(router.currentRoute.value.name).toBe('chat');
  });

  it('bounces a non-admin authenticated user away from an admin-only route', async () => {
    mockAuth.hasSession.mockReturnValue(true);
    mockAuth.isAdmin.mockReturnValue(false);
    await router.push('/admin/seats');
    expect(router.currentRoute.value.name).toBe('chat');
  });

  it('allows an admin onto an admin-only route', async () => {
    mockAuth.hasSession.mockReturnValue(true);
    mockAuth.isAdmin.mockReturnValue(true);
    await router.push('/admin/seats');
    expect(router.currentRoute.value.name).toBe('admin-seats');
  });

  it('lets an unauthenticated visitor reach a public route unaffected', async () => {
    await router.push('/terms');
    expect(router.currentRoute.value.name).toBe('terms');
  });
});

describe('router auth-callback route', () => {
  it('redirects to landing with an error when no session payload is present', async () => {
    await router.push({ name: 'auth-callback' });
    expect(router.currentRoute.value.name).toBe('landing');
    expect(router.currentRoute.value.query.error).toBe('auth_failed');
  });

  it('decodes a valid session payload, hands it to auth, and lands on chat', async () => {
    const payload = { role: 'admin', user: { username: 'bob' } };
    const encoded = btoa(JSON.stringify(payload));
    // The redirect to 'chat' re-enters the global auth guard, which needs to see
    // the session auth.callback() just established, not this test's default mock.
    mockAuth.hasSession.mockReturnValue(true);

    await router.push({ name: 'auth-callback', query: { session: encoded } });

    expect(mockAuth.callback).toHaveBeenCalledWith(payload);
    expect(router.currentRoute.value.name).toBe('chat');
  });

  it('redirects to landing with an error when the session payload cannot be decoded', async () => {
    await router.push({ name: 'auth-callback', query: { session: 'not-valid-base64-json' } });
    expect(router.currentRoute.value.name).toBe('landing');
    expect(router.currentRoute.value.query.error).toBe('invalid_session');
    expect(mockAuth.callback).not.toHaveBeenCalled();
  });
});

describe('router scrollBehavior', () => {
  it('does not scroll when navigating within the same named route', () => {
    const result = router.options.scrollBehavior({ name: 'chat', hash: '' }, { name: 'chat' }, null);
    expect(result).toBeUndefined();
  });

  it('scrolls smoothly to the top when the target route has no hash', () => {
    const result = router.options.scrollBehavior({ name: 'landing', hash: '' }, { name: 'terms' }, null);
    expect(result).toEqual({ behavior: 'smooth', top: 0 });
  });

  it('scrolls smoothly to the hash target, offset for the fixed header', () => {
    const result = router.options.scrollBehavior({ name: 'landing', hash: '#features' }, { name: 'terms' }, null);
    expect(result).toEqual({ behavior: 'smooth', el: '#features', top: 150 });
  });
});
