// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/seat: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Seat from '@/modules/api/seat';

describe('Seat', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({}), status: 200 });
  });

  it('seats() GETs the seats endpoint', async () => {
    await Seat.seats();
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Seat.constants.ENDPOINT}/seats/`);
  });

  it('revoke() POSTs the username to the revoke endpoint', async () => {
    await Seat.revoke('bob');
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Seat.constants.ENDPOINT}/revoke/`);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ username: 'bob' });
  });

  it('reinstate() POSTs the username to the reinstate endpoint', async () => {
    await Seat.reinstate('bob');
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Seat.constants.ENDPOINT}/reinstate/`);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ username: 'bob' });
  });

  it('setRole() POSTs the username and role to the set_role endpoint', async () => {
    await Seat.setRole('bob', 'admin');
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Seat.constants.ENDPOINT}/set_role/`);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ role: 'admin', username: 'bob' });
  });
});
