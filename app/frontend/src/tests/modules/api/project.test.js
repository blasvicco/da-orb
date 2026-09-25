// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/project: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Project from '@/modules/api/project';

describe('Project', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({}), status: 200 });
  });

  it('targets the project resource', () => {
    expect(Project.constants.ENDPOINT).toBe(`${Project.constants.API_URL}/v1/project`);
  });

  it('default() GETs the default endpoint', async () => {
    await Project.default();
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Project.constants.ENDPOINT}/default/`);
    expect(opts.credentials).toBe('include');
  });

  it.each([
    ['select', 'select'],
    ['empty', 'empty'],
  ])('%s() POSTs to the detail action for the given id', async (method, action) => {
    await Project[method](7);
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Project.constants.ENDPOINT}/7/${action}/`);
    expect(opts.method).toBe('POST');
    expect(opts.credentials).toBe('include');
  });

  it('inherits list() with the filters/ordering query the backend filterset speaks', async () => {
    await Project.list({
      filters: { name__icontains: 'a&b c' },
      limit: 8,
      sorter: { field: 'chat_sessions_count', order: 'descend' },
    });
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(
      `${Project.constants.ENDPOINT}/?limit=8&offset=0&name__icontains=a%26b%20c&ordering=-chat_sessions_count`,
    );
  });

  it('surfaces a backend validation error in the shape the shared table component reads', async () => {
    const body = { errors: [{ attr: 'id', code: 'invalid', detail: 'Default project cannot be deleted.' }], type: 'validation_error' };
    globalThis.fetch.mockResolvedValue({ json: async () => body, status: 400 });
    expect(await Project.delete(1)).toEqual(body);
  });
});
