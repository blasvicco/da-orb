// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/chat-session: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import ChatSession from '@/modules/api/chat-session';

describe('ChatSession', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({}), status: 200 });
  });

  it('targets the chat_session resource', () => {
    expect(ChatSession.constants.ENDPOINT).toBe(`${ChatSession.constants.API_URL}/v1/chat_session`);
  });

  it('inherits list(), filtered to one project and sorted, in the query the backend speaks', async () => {
    await ChatSession.list({
      filters: { project_id: 8, title__icontains: 'a&b' },
      limit: 20,
      offset: 40,
      sorter: { field: 'tokens_used', order: 'descend' },
    });
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(
      `${ChatSession.constants.ENDPOINT}/?limit=20&offset=40&project_id=8&title__icontains=a%26b&ordering=-tokens_used`,
    );
  });

  it('move() POSTs the chat ids and the destination project as JSON', async () => {
    await ChatSession.move([4, 5, 6], 2);
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${ChatSession.constants.ENDPOINT}/move/`);
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(opts.body)).toEqual({ project_id: 2, session_ids: [4, 5, 6] });
  });

  it('surfaces a backend error in the shape the shared table component reads', async () => {
    const body = { errors: [{ attr: null, code: 'not_found', detail: 'The destination project no longer exists.' }], type: 'client_error' };
    globalThis.fetch.mockResolvedValue({ json: async () => body, status: 404 });
    expect(await ChatSession.move([1], 99)).toEqual(body);
  });
});
