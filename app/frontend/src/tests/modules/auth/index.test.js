// Libs imports
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const { mockSigninRedirect, mockUserManagerCtor } = vi.hoisted(() => {
  const mockSigninRedirect = vi.fn().mockResolvedValue();
  // A plain `function`, not an arrow function — the source calls `new UserManager(...)`,
  // and arrow functions can't be used as constructors ("is not a constructor").
  const mockUserManagerCtor = vi.fn().mockImplementation(function MockUserManager() {
    return { signinRedirect: mockSigninRedirect };
  });
  return { mockSigninRedirect, mockUserManagerCtor };
});

vi.mock('oidc-client-ts', () => ({
  UserManager: mockUserManagerCtor,
  WebStorageStateStore: vi.fn(),
}));

vi.mock('@/modules/api', () => ({
  default: {
    Auth: {
      constants: { ENDPOINT: 'https://api.test/api/v1/auth' },
      login: vi.fn(),
      refresh: vi.fn(),
    },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { useAuth } from '@/modules/auth';

beforeEach(() => {
  vi.clearAllMocks();
});

describe('useAuth bootstrap / getters', () => {
  it('getSession/hasSession are blank when nothing is stored', () => {
    const auth = useAuth();
    expect(auth.getSession()).toBeNull();
    expect(auth.hasSession()).toBe(false);
  });

  it('getSession/hasSession resolve from a previously stored session', () => {
    sessionStorage.setItem('orb_session', JSON.stringify({ role: 'standard' }));
    const auth = useAuth();
    expect(auth.getSession()).toEqual({ role: 'standard' });
    expect(auth.hasSession()).toBe(true);
  });

  it('treats unparsable stored session data as no session', () => {
    sessionStorage.setItem('orb_session', 'not-json');
    const auth = useAuth();
    expect(auth.getSession()).toBeNull();
  });

  it.each([
    ['role admin resolves isAdmin true', 'admin', true],
    ['role standard resolves isAdmin false', 'standard', false],
    ['no session resolves isAdmin false', null, false],
  ])('%s', (_label, role, expected) => {
    if (role) sessionStorage.setItem('orb_session', JSON.stringify({ role }));
    const auth = useAuth();
    expect(auth.isAdmin()).toBe(expected);
  });

  it('getError/isLoading default to blank', () => {
    const auth = useAuth();
    expect(auth.getError()).toBeNull();
    expect(auth.isLoading()).toBe(false);
  });
});

describe('useAuth.callback', () => {
  it('stores the session and clears loading', () => {
    const auth = useAuth();
    auth.callback({ role: 'standard', user: { username: 'bob' } });
    expect(auth.getSession()).toEqual({ role: 'standard', user: { username: 'bob' } });
    expect(auth.isLoading()).toBe(false);
    expect(JSON.parse(sessionStorage.getItem('orb_session'))).toEqual({
      role: 'standard',
      user: { username: 'bob' },
    });
  });
});

describe('useAuth.signin', () => {
  afterEach(() => {
    delete window.sap;
  });

  it('uses the SAP Fiori shell navigation when embedded, without opening a redirect flow', async () => {
    const toExternal = vi.fn();
    window.sap = { ushell: { Container: { getService: vi.fn().mockReturnValue({ toExternal }) } } };

    const auth = useAuth();
    await auth.signin({ base_url: 'https://sap.example.com' });

    expect(toExternal).toHaveBeenCalledWith({ target: { shellHash: '#' } });
    expect(mockUserManagerCtor).not.toHaveBeenCalled();
  });

  it('starts the standard OAuth2 + PKCE redirect flow outside the SAP shell', async () => {
    const auth = useAuth();
    await auth.signin({ base_url: 'https://sap.example.com', client_id: 'public-id' });

    expect(mockUserManagerCtor).toHaveBeenCalledWith(
      expect.objectContaining({
        authority: 'https://sap.example.com',
        client_id: 'public-id',
        redirect_uri: `${AppAPI.Auth.constants.ENDPOINT}/callback/`,
        response_type: 'code',
        scope: 'openid profile email',
      }),
    );
    expect(mockSigninRedirect).toHaveBeenCalled();
  });

  it('uses a custom scope when the context provides one', async () => {
    const auth = useAuth();
    await auth.signin({ base_url: 'https://sap.example.com', scopes: 'openid custom' });

    expect(mockUserManagerCtor).toHaveBeenCalledWith(
      expect.objectContaining({ scope: 'openid custom' }),
    );
  });

  it('captures the error and clears loading when signinRedirect fails', async () => {
    mockSigninRedirect.mockRejectedValueOnce(new Error('redirect_failed'));
    const auth = useAuth();
    await auth.signin({ base_url: 'https://sap.example.com' });

    expect(auth.getError()).toBe('redirect_failed');
    expect(auth.isLoading()).toBe(false);
  });
});

describe('useAuth.signinWithCredentials', () => {
  it('stores the session on a successful login', async () => {
    AppAPI.Auth.login.mockResolvedValue({ access_token: 'tok', role: 'standard' });
    const auth = useAuth();

    await auth.signinWithCredentials({ database: 'TESTDB', password: 'secret', username: 'bob' });

    expect(AppAPI.Auth.login).toHaveBeenCalledWith('bob', 'secret', 'TESTDB');
    expect(auth.getSession()).toEqual({ access_token: 'tok', role: 'standard' });
    expect(auth.isLoading()).toBe(false);
    expect(auth.getError()).toBeNull();
  });

  it.each([
    [
      'a detail error message is surfaced',
      { errors: [{ detail: 'INVALID_CREDENTIALS' }] },
      'INVALID_CREDENTIALS',
    ],
    [
      'an error-field message is surfaced when detail is absent',
      { errors: [{ error: 'SEAT_REVOKED' }] },
      'SEAT_REVOKED',
    ],
    ['a falsy response falls back to a generic message', null, 'B1S_AUTH_FAILED'],
  ])('%s', async (_label, response, expectedError) => {
    AppAPI.Auth.login.mockResolvedValue(response);
    const auth = useAuth();

    await auth.signinWithCredentials({ password: 'secret', username: 'bob' });

    expect(auth.getError()).toBe(expectedError);
    expect(auth.getSession()).toBeNull();
    expect(auth.isLoading()).toBe(false);
  });
});

describe('useAuth.signout', () => {
  it('clears the session, storage, and navigates home', () => {
    const auth = useAuth();
    auth.callback({ role: 'standard' });

    auth.signout();

    expect(auth.getSession()).toBeNull();
    expect(sessionStorage.getItem('orb_session')).toBeNull();
    expect(window.location.href).toContain('/');
  });

  it('cancels a pending scheduled refresh, if any', () => {
    vi.useFakeTimers();
    try {
      const auth = useAuth();
      const expiresAt = Math.floor(Date.now() / 1000) + 600;
      auth.callback({ expires_at: expiresAt, refresh_token: 'old-refresh', role: 'standard' });

      auth.signout();
      vi.advanceTimersByTime(10 * 60 * 1000);

      expect(AppAPI.Auth.refresh).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe('useAuth scheduled refresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('does not schedule a refresh for a session without a refresh_token (e.g. B1S)', () => {
    const auth = useAuth();
    auth.callback({ expires_at: Math.floor(Date.now() / 1000) + 3600, role: 'standard' });

    vi.advanceTimersByTime(10 * 60 * 60 * 1000);

    expect(AppAPI.Auth.refresh).not.toHaveBeenCalled();
  });

  it('schedules a refresh 5 minutes before expiry and applies the refreshed session', async () => {
    AppAPI.Auth.refresh.mockResolvedValue({
      access_token: 'new-tok',
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      refresh_token: 'new-refresh',
    });
    const auth = useAuth();
    const expiresAt = Math.floor(Date.now() / 1000) + 600; // 10 minutes out
    auth.callback({ expires_at: expiresAt, refresh_token: 'old-refresh', role: 'standard' });

    // 5 minutes to refresh point: advance just past it.
    await vi.advanceTimersByTimeAsync(5 * 60 * 1000 + 1000);

    expect(AppAPI.Auth.refresh).toHaveBeenCalledWith('old-refresh');
    expect(auth.getSession().access_token).toBe('new-tok');
  });

  it('refreshes immediately when already within the refresh window', async () => {
    AppAPI.Auth.refresh.mockResolvedValue({
      access_token: 'new-tok',
      expires_at: Math.floor(Date.now() / 1000) + 3600,
      refresh_token: 'new-refresh',
    });
    const auth = useAuth();
    const expiresAt = Math.floor(Date.now() / 1000) + 60; // already inside the 5-minute window
    await auth.callback({ expires_at: expiresAt, refresh_token: 'old-refresh', role: 'standard' });

    expect(AppAPI.Auth.refresh).toHaveBeenCalledWith('old-refresh');
  });

  it('clears a previous pending refresh timer when a new one is scheduled', () => {
    const auth = useAuth();
    const firstExpiry = Math.floor(Date.now() / 1000) + 600;
    auth.callback({ expires_at: firstExpiry, refresh_token: 'first-refresh', role: 'standard' });

    const secondExpiry = Math.floor(Date.now() / 1000) + 1200;
    auth.callback({ expires_at: secondExpiry, refresh_token: 'second-refresh', role: 'standard' });

    // Past when the first (now-superseded) timer would have fired.
    vi.advanceTimersByTime(6 * 60 * 1000);

    expect(AppAPI.Auth.refresh).not.toHaveBeenCalled();
  });

  it('signs the user out when the scheduled refresh itself fails', async () => {
    AppAPI.Auth.refresh.mockResolvedValue(null);
    const auth = useAuth();
    const expiresAt = Math.floor(Date.now() / 1000) + 60;
    await auth.callback({ expires_at: expiresAt, refresh_token: 'old-refresh', role: 'standard' });

    expect(auth.getSession()).toBeNull();
  });
});
