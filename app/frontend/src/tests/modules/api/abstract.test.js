// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
import { useAuth } from '@/modules/auth';
import Abstract from '@/modules/api/abstract';

// Fixtures
class TestResource extends Abstract {
  constructor() {
    super();
    this.resource = 'test';
    this._updateEndpoint();
  }
}

describe('Abstract.constructor', () => {
  it('throws when instantiated directly', () => {
    expect(() => new Abstract()).toThrow(TypeError);
  });

  it('a subclass builds its endpoint from resource, api url, and version', () => {
    const resource = new TestResource();
    expect(resource.constants.ENDPOINT).toBe(`${resource.constants.API_URL}/v1/test`);
  });
});

describe('Abstract.header', () => {
  it('returns blank auth headers when no session exists', () => {
    const resource = new TestResource();
    expect(resource.header()).toEqual({
      Authorization: '',
      'X-SAP-Connection-Key': '',
      'X-SAP-Username': '',
    });
  });

  it('returns populated auth headers from an active session', () => {
    const auth = useAuth();
    auth.callback({ access_token: 'tok', database: 'TESTDB', user: { username: 'bob' } });
    const resource = new TestResource();
    expect(resource.header()).toEqual({
      Authorization: 'Bearer tok',
      'X-SAP-Connection-Key': 'TESTDB',
      'X-SAP-Username': 'bob',
    });
  });
});

describe('Abstract HTTP methods', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({ id: 1 }), status: 200 });
  });

  it('get() fetches the resource by id', async () => {
    const resource = new TestResource();
    await resource.get(5);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${resource.constants.ENDPOINT}/5/`,
      expect.objectContaining({ method: 'GET' }),
    );
  });

  it('delete() fetches DELETE for the given id', async () => {
    const resource = new TestResource();
    await resource.delete(5);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `${resource.constants.ENDPOINT}/5/`,
      expect.objectContaining({ method: 'DELETE' }),
    );
  });

  it.each([
    ['default pagination with no filters/sorter', {}, 'limit=20&offset=0&'],
    ['custom pagination', { limit: 5, offset: 10 }, 'limit=5&offset=10&'],
  ])('list() — %s', async (_label, opts, expectedQuery) => {
    const resource = new TestResource();
    await resource.list(opts);
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${resource.constants.ENDPOINT}/?${expectedQuery}`);
  });

  it('list() builds a filter query string, skipping empty filter values', async () => {
    const resource = new TestResource();
    await resource.list({ filters: { role: '', status: 'active' } });
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toContain('status=active&');
    expect(url).not.toContain('role=');
  });

  it.each([
    ['ascending sorter appends a plain ordering param', 'ascend', 'ordering=name'],
    ['descending sorter appends a minus-prefixed ordering param', 'descend', 'ordering=-name'],
  ])('list() — %s', async (_label, order, expectedFragment) => {
    const resource = new TestResource();
    await resource.list({ sorter: { field: 'name', order } });
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toContain(expectedFragment);
  });

  it('save() POSTs a new object without an id', async () => {
    const resource = new TestResource();
    await resource.save({ name: 'x' });
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${resource.constants.ENDPOINT}/`);
    expect(opts.method).toBe('POST');
    expect(JSON.parse(opts.body)).toEqual({ name: 'x' });
  });

  it('save() PATCHes and strips the id when updating an existing object', async () => {
    const resource = new TestResource();
    await resource.save({ id: 9, name: 'x' });
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${resource.constants.ENDPOINT}/9/`);
    expect(opts.method).toBe('PATCH');
    expect(JSON.parse(opts.body)).toEqual({ name: 'x' });
  });
});

describe('Abstract._handleError', () => {
  it.each([
    [
      'a 200 response returns the parsed body',
      { json: async () => ({ id: 1 }), status: 200 },
      { id: 1 },
    ],
    [
      'a 201 response returns the parsed body',
      { json: async () => ({ id: 1 }), status: 201 },
      { id: 1 },
    ],
    [
      'a 202 response returns the parsed body',
      { json: async () => ({ id: 1 }), status: 202 },
      { id: 1 },
    ],
    [
      'a 2xx response with unparsable json returns an empty object',
      { json: async () => { throw new Error('bad'); }, status: 200 },
      {},
    ],
    [
      'a 204 response returns errors: false',
      { json: async () => ({}), status: 204 },
      { errors: false },
    ],
    [
      'a non-2xx response carrying an error field is wrapped in errors',
      { json: async () => ({ error: 'bad' }), status: 400 },
      { errors: [{ error: 'bad' }] },
    ],
    [
      'a non-2xx response without an error field is returned as-is',
      { json: async () => ({ detail: 'bad' }), status: 400 },
      { detail: 'bad' },
    ],
    [
      'a non-2xx response with unparsable json falls back to a generic error',
      { json: async () => { throw new Error('bad'); }, status: 500 },
      { errors: [{ attr: null, detail: 'UKNOWN_ERROR' }] },
    ],
    [
      'a 401 response still falls through to the generic non-2xx handling',
      { json: async () => ({ detail: 'unauthorized' }), status: 401 },
      { detail: 'unauthorized' },
    ],
  ])('%s', async (_label, res, expected) => {
    const resource = new TestResource();
    const result = await resource._handleError(res);
    expect(result).toEqual(expected);
  });
});
