// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/context: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Context from '@/modules/api/context';

describe('Context', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({ auth_driver: 'open_id' }), status: 200 });
  });

  it('get() GETs the context endpoint', async () => {
    const result = await Context.get();
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Context.constants.ENDPOINT}/get/`);
    expect(opts.method).toBe('GET');
    expect(result).toEqual({ auth_driver: 'open_id' });
  });
});
