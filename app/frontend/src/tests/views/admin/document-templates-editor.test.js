// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getSession: vi.fn().mockReturnValue({ database: 'PROD', role: 'admin', user: { username: 'admin.bob' } }),
  signout: vi.fn(),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/api', () => ({
  default: {
    DocumentTemplate: {
      preview: vi.fn(),
      remove: vi.fn().mockResolvedValue({}),
      setDefault: vi.fn().mockResolvedValue({}),
      templates: vi.fn().mockResolvedValue([]),
      update: vi.fn(),
      upload: vi.fn(),
    },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { flushPromises, mount, waitForBody } from '@/tests/helpers/mount';
import List from '@/components/table/list.vue';
import DocumentTemplates from '@/views/admin/document-templates.vue';

// Fixtures
const TEMPLATE = { created_on: '2026-09-20T00:00:00Z', document_type: 'invoice', id: 1, is_default: false, name: 'BVS Factura v4' };
const CUSTOMER_TEMPLATE = {
  business_partner_ref: 'C20000',
  created_on: '2026-09-21T00:00:00Z',
  document_type: 'invoice',
  id: 2,
  is_default: false,
  language: 'es',
  name: 'Orion Factura',
};
const RPT_FILE = new File(['rpt'], 'invoice.rpt', { type: 'application/octet-stream' });

const list = (wrapper) => wrapper.findComponent(List);
// The editor modal teleports its content onto document.body, and only mounts it once opened:
// reach the fields through the modal's component tree, never wrapper.find().
const editorModal = (wrapper) => wrapper.findAllComponents({ name: 'AModal' })[0];
const inputs = (wrapper) => editorModal(wrapper).findAllComponents({ name: 'AInput' });
const selects = (wrapper) => editorModal(wrapper).findAllComponents({ name: 'ASelect' });
const nameInput = (wrapper) => inputs(wrapper)[0];
const partnerRefInput = (wrapper) => inputs(wrapper)[1];
const typeSelect = (wrapper) => selects(wrapper)[0];
const languageSelect = (wrapper) => selects(wrapper)[1];

const mountView = async () => {
  const wrapper = mount(DocumentTemplates);
  await flushPromises();
  return wrapper;
};

// Opens the editor the way the upload button does.
const openCreate = async (wrapper) => {
  await wrapper.find('.orb-admin-actions button').trigger('click');
  await flushPromises();
};

// Opens the editor the way the table's edit button does.
const openEdit = async (wrapper, record) => {
  await list(wrapper).props('actions').editor(record);
  await flushPromises();
};

const clickOk = async (wrapper) => {
  await editorModal(wrapper).vm.$emit('ok');
  await flushPromises();
};

// Picks a file the way the browser's file dialog reports it: through the input's `files`.
const chooseFile = async (files) => {
  const [fileInput] = await waitForBody('input[type="file"]', 1);
  Object.defineProperty(fileInput.element, 'files', { configurable: true, value: files });
  await fileInput.trigger('change');
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({ database: 'PROD', role: 'admin', user: { username: 'admin.bob' } });
  AppAPI.DocumentTemplate.templates.mockResolvedValue([TEMPLATE]);
  AppAPI.DocumentTemplate.upload.mockResolvedValue({});
  AppAPI.DocumentTemplate.update.mockResolvedValue({});
  localStorage.clear();
});

describe('DocumentTemplates.editor opening', () => {
  it('starts closed', async () => {
    const wrapper = await mountView();

    expect(editorModal(wrapper).props('open')).toBe(false);
  });

  it('opens blank in create mode from the upload button', async () => {
    const wrapper = await mountView();

    await openCreate(wrapper);

    expect(editorModal(wrapper).props('open')).toBe(true);
    expect(editorModal(wrapper).props('title')).toBe('Upload Template');
    expect(nameInput(wrapper).props('value')).toBe('');
    expect(partnerRefInput(wrapper).props('value')).toBe('');
    expect(typeSelect(wrapper).props('value')).toBe('invoice');
    expect(languageSelect(wrapper).props('value')).toBe('');
  });

  it.each([
    ['a template with overrides', CUSTOMER_TEMPLATE, { language: 'es', name: 'Orion Factura', partnerRef: 'C20000' }],
    ['a template without overrides', TEMPLATE, { language: '', name: 'BVS Factura v4', partnerRef: '' }],
  ])('opens in edit mode prefilled from %s', async (_label, record, expected) => {
    const wrapper = await mountView();

    await openEdit(wrapper, record);

    expect(editorModal(wrapper).props('open')).toBe(true);
    expect(editorModal(wrapper).props('title')).toBe('Edit Template');
    expect(nameInput(wrapper).props('value')).toBe(expected.name);
    expect(typeSelect(wrapper).props('value')).toBe('invoice');
    expect(partnerRefInput(wrapper).props('value')).toBe(expected.partnerRef);
    expect(languageSelect(wrapper).props('value')).toBe(expected.language);
  });

  it('starts every creation from blank fields, even after editing another template', async () => {
    const wrapper = await mountView();
    await openEdit(wrapper, CUSTOMER_TEMPLATE);
    await editorModal(wrapper).vm.$emit('cancel');
    await flushPromises();

    await openCreate(wrapper);

    expect(editorModal(wrapper).props('title')).toBe('Upload Template');
    expect(nameInput(wrapper).props('value')).toBe('');
    expect(partnerRefInput(wrapper).props('value')).toBe('');
    expect(languageSelect(wrapper).props('value')).toBe('');
  });

  it('closes on cancel without saving', async () => {
    const wrapper = await mountView();
    await openCreate(wrapper);

    await editorModal(wrapper).vm.$emit('cancel');
    await flushPromises();

    expect(editorModal(wrapper).props('open')).toBe(false);
    expect(AppAPI.DocumentTemplate.upload).not.toHaveBeenCalled();
  });

  it('lets the modal close itself', async () => {
    const wrapper = await mountView();
    await openCreate(wrapper);

    await editorModal(wrapper).vm.$emit('update:open', false);

    expect(editorModal(wrapper).props('open')).toBe(false);
  });
});

describe('DocumentTemplates.editor saving', () => {
  it('uploads a new template from the entered fields and file, then closes and reloads the table', async () => {
    const wrapper = await mountView();
    await openCreate(wrapper);
    await nameInput(wrapper).vm.$emit('update:value', 'Orion Factura');
    await typeSelect(wrapper).vm.$emit('update:value', 'invoice');
    await partnerRefInput(wrapper).vm.$emit('update:value', 'C20000');
    await languageSelect(wrapper).vm.$emit('update:value', 'es');
    await chooseFile([RPT_FILE]);
    AppAPI.DocumentTemplate.templates.mockResolvedValue([TEMPLATE, CUSTOMER_TEMPLATE]);

    await clickOk(wrapper);

    expect(AppAPI.DocumentTemplate.upload).toHaveBeenCalledWith(
      'Orion Factura', 'invoice', RPT_FILE, { businessPartnerRef: 'C20000', language: 'es' },
    );
    expect(AppAPI.DocumentTemplate.update).not.toHaveBeenCalled();
    expect(editorModal(wrapper).props('open')).toBe(false);
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(2);
    expect(await list(wrapper).props('loader')({})).toEqual({ count: 2, results: [TEMPLATE, CUSTOMER_TEMPLATE] });
  });

  it('updates an existing template by id, with its edited fields and no new file', async () => {
    const wrapper = await mountView();
    await openEdit(wrapper, CUSTOMER_TEMPLATE);
    await nameInput(wrapper).vm.$emit('update:value', 'Orion Factura v2');

    await clickOk(wrapper);

    expect(AppAPI.DocumentTemplate.update).toHaveBeenCalledWith(2, {
      businessPartnerRef: 'C20000',
      documentType: 'invoice',
      file: null,
      language: 'es',
      name: 'Orion Factura v2',
    });
    expect(AppAPI.DocumentTemplate.upload).not.toHaveBeenCalled();
    expect(editorModal(wrapper).props('open')).toBe(false);
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(2);
  });

  it.each([
    ['a chosen file', [RPT_FILE], RPT_FILE],
    ['an emptied selection', [], null],
    ['no file list at all', undefined, null],
  ])('sends %s along with the template', async (_label, files, expected) => {
    const wrapper = await mountView();
    await openCreate(wrapper);
    await chooseFile(files);

    await clickOk(wrapper);

    // Compared by value: the view keeps the file in a ref, so it is handed on as a reactive proxy.
    expect(AppAPI.DocumentTemplate.upload.mock.calls[0][2]).toEqual(expected);
  });

  it.each([
    ['a detail', [{ detail: 'The file is not a valid report.' }], 'The file is not a valid report.'],
    ['only an error code', [{ error: 'FILE_TOO_LARGE' }], 'FILE_TOO_LARGE'],
    ['neither a detail nor a code', [{}], 'ERROR'],
  ])('keeps the editor open and shows the failure when the save reports %s', async (_label, errors, expected) => {
    AppAPI.DocumentTemplate.upload.mockResolvedValue({ errors });
    const wrapper = await mountView();
    await openCreate(wrapper);

    await clickOk(wrapper);

    expect(wrapper.find('.orb-admin-error').text()).toBe(expected);
    expect(editorModal(wrapper).props('open')).toBe(true);
    expect(editorModal(wrapper).props('confirmLoading')).toBe(false);
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(1);
  });

  it('shows the modal as busy while the save is in flight, then idle once it resolves', async () => {
    let resolveUpload;
    AppAPI.DocumentTemplate.upload.mockReturnValue(new Promise((resolve) => { resolveUpload = resolve; }));
    const wrapper = await mountView();
    await openCreate(wrapper);

    await clickOk(wrapper);
    expect(editorModal(wrapper).props('confirmLoading')).toBe(true);

    resolveUpload({});
    await flushPromises();

    expect(editorModal(wrapper).props('confirmLoading')).toBe(false);
    expect(editorModal(wrapper).props('open')).toBe(false);
  });
});
