// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/usage: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Usage from '@/modules/api/usage';

describe('Usage', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({ plan: {} }), status: 200 });
  });

  it('summary() GETs the summary endpoint', async () => {
    const result = await Usage.summary();
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Usage.constants.ENDPOINT}/summary/`);
    expect(result).toEqual({ plan: {} });
  });
});
