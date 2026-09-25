// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
// modules/auth must resolve before modules/api/document-template: modules/api/abstract.js
// imports modules/auth, which imports the modules/api barrel — a real circular dependency
// that only unwinds safely when modules/auth is the first side to start evaluating.
import '@/modules/auth';
import DocumentTemplate from '@/modules/api/document-template';

// Fixtures
const RPT_FILE = new File(['rpt'], 'invoice.rpt', { type: 'application/octet-stream' });
const formEntries = (body) => Object.fromEntries(body.entries());
const lastCall = () => globalThis.fetch.mock.calls.at(-1);

beforeEach(() => {
  globalThis.fetch.mockResolvedValue({ json: async () => ({}), status: 200 });
});

describe('DocumentTemplate.resource', () => {
  it('targets the document_template resource', () => {
    expect(DocumentTemplate.constants.ENDPOINT).toBe(`${DocumentTemplate.constants.API_URL}/v1/document_template`);
  });
});

describe('DocumentTemplate.templates', () => {
  it.each([
    ['no document type', undefined, ''],
    ['a document type', 'invoice', '?document_type=invoice'],
  ])('lists with %s', async (_label, documentType, query) => {
    await DocumentTemplate.templates(documentType);

    const [url, opts] = lastCall();
    expect(url).toBe(`${DocumentTemplate.constants.ENDPOINT}/templates/${query}`);
    expect(opts.credentials).toBe('include');
  });
});

describe('DocumentTemplate.upload', () => {
  it.each([
    ['no overrides', undefined, { business_partner_ref: '', language: '' }],
    ['both overrides', { businessPartnerRef: 'C20000', language: 'es' }, { business_partner_ref: 'C20000', language: 'es' }],
  ])('POSTs a multipart form with %s and no Content-Type header', async (_label, options, overrides) => {
    await DocumentTemplate.upload('Invoice', 'invoice', RPT_FILE, options);

    const [url, opts] = lastCall();
    expect(url).toBe(`${DocumentTemplate.constants.ENDPOINT}/upload/`);
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBeUndefined();
    expect(formEntries(opts.body)).toEqual({ document_type: 'invoice', file: RPT_FILE, name: 'Invoice', ...overrides });
  });
});

describe('DocumentTemplate.update', () => {
  it.each([
    [
      'every field',
      { businessPartnerRef: 'C20000', documentType: 'invoice', file: RPT_FILE, language: 'es', name: 'New name' },
      { business_partner_ref: 'C20000', document_type: 'invoice', file: RPT_FILE, language: 'es', name: 'New name', template_id: '5' },
    ],
    [
      'only the id, still sending both overrides empty so they can be cleared',
      undefined,
      { business_partner_ref: '', language: '', template_id: '5' },
    ],
  ])('PATCHes %s', async (_label, fields, expected) => {
    await DocumentTemplate.update(5, fields);

    const [url, opts] = lastCall();
    expect(url).toBe(`${DocumentTemplate.constants.ENDPOINT}/update_template/`);
    expect(opts.method).toBe('PATCH');
    expect(opts.headers['Content-Type']).toBeUndefined();
    expect(formEntries(opts.body)).toEqual(expected);
  });
});

describe('DocumentTemplate.remove', () => {
  it('DELETEs the remove endpoint scoped to a template_id', async () => {
    await DocumentTemplate.remove(5);

    const [url, opts] = lastCall();
    expect(url).toBe(`${DocumentTemplate.constants.ENDPOINT}/remove/?template_id=5`);
    expect(opts.method).toBe('DELETE');
    expect(opts.credentials).toBe('include');
  });
});

describe('DocumentTemplate.setDefault', () => {
  it('POSTs the template_id as JSON', async () => {
    await DocumentTemplate.setDefault(5);

    const [url, opts] = lastCall();
    expect(url).toBe(`${DocumentTemplate.constants.ENDPOINT}/set_default/`);
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(opts.body)).toEqual({ template_id: 5 });
  });
});

describe('DocumentTemplate.preview', () => {
  it('POSTs the sample data and resolves with the rendered PDF blob', async () => {
    const pdf = new Blob(['%PDF'], { type: 'application/pdf' });
    globalThis.fetch.mockResolvedValue({ blob: async () => pdf, ok: true, status: 200 });

    const result = await DocumentTemplate.preview(5, [{ Name: 'Widget' }]);

    const [url, opts] = lastCall();
    expect(url).toBe(`${DocumentTemplate.constants.ENDPOINT}/preview/`);
    expect(opts.method).toBe('POST');
    expect(opts.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(opts.body)).toEqual({ data: [{ Name: 'Widget' }], template_id: 5 });
    expect(result).toBe(pdf);
  });

  it('resolves with the parsed error, not a blob, when the render fails', async () => {
    globalThis.fetch.mockResolvedValue({ json: async () => ({ error: 'RENDER_FAILED' }), ok: false, status: 400 });

    const result = await DocumentTemplate.preview(5, []);

    expect(result).toEqual({ errors: [{ error: 'RENDER_FAILED' }] });
  });
});
