// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/bucket: modules/api/abstract.js imports
// modules/auth, which imports the modules/api barrel — a real circular dependency that
// only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import Bucket from '@/modules/api/bucket';

describe('Bucket', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ json: async () => ([]), status: 200 });
  });

  it('files() GETs the files endpoint scoped to a session_id', async () => {
    await Bucket.files(42);
    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Bucket.constants.ENDPOINT}/files/?session_id=42`);
    expect(opts.credentials).toBe('include');
  });

  it('downloadUrl() GETs the download endpoint scoped to a file_id', async () => {
    await Bucket.downloadUrl(7);
    const [url] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Bucket.constants.ENDPOINT}/download/?file_id=7`);
  });

  it('upload() POSTs a multipart FormData carrying session_id and file, without a Content-Type header', async () => {
    const file = new File(['a,b\n1,2'], 'orders.csv', { type: 'text/csv' });

    await Bucket.upload(42, file);

    const [url, opts] = globalThis.fetch.mock.calls[0];
    expect(url).toBe(`${Bucket.constants.ENDPOINT}/upload/`);
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBeUndefined();
    expect(opts.body.get('session_id')).toBe('42');
    expect(opts.body.get('file')).toBe(file);
  });
});
