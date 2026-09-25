// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/chat: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Chat from '@/modules/api/chat';

describe('Chat', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ([]), status: 200 });
  });

  it('sessions() GETs the sessions endpoint scoped to a project_id', async () => {
    await Chat.sessions(3);
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Chat.constants.ENDPOINT}/sessions/?project_id=3`);
    expect(opts.credentials).toBe('include');
  });

  it('recent() GETs the recent endpoint', async () => {
    await Chat.recent();
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Chat.constants.ENDPOINT}/recent/`);
    expect(opts.credentials).toBe('include');
  });

  it('messages() GETs the messages endpoint scoped to a session_id', async () => {
    await Chat.messages(42);
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Chat.constants.ENDPOINT}/messages/?session_id=42`);
  });

  it('deleteSession() DELETEs the delete_session endpoint scoped to a session_id', async () => {
    await Chat.deleteSession(42);
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Chat.constants.ENDPOINT}/delete_session/?session_id=42`);
    expect(opts.method).toBe('DELETE');
  });
});
