// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/auth: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Auth from '@/modules/api/auth';

describe('Auth', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({ access_token: 'tok' }), status: 200 });
  });

  it('refresh() POSTs the given token to the refresh endpoint', async () => {
    const result = await Auth.refresh('old-refresh-token');
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Auth.constants.ENDPOINT}/refresh/`);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ token: 'old-refresh-token' });
    expect(result).toEqual({ access_token: 'tok' });
  });

  it('login() POSTs username/password/database to the login endpoint', async () => {
    await Auth.login('bob', 'secret', 'TESTDB');
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Auth.constants.ENDPOINT}/login/`);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ database: 'TESTDB', password: 'secret', username: 'bob' });
  });

  it('login() defaults database to an empty string when omitted', async () => {
    await Auth.login('bob', 'secret');
    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(JSON.parse(opts.body)).toEqual({ database: '', password: 'secret', username: 'bob' });
  });
});
