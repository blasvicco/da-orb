// Libs imports
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

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
import { body, flushPromises, mount, waitForBody } from '@/tests/helpers/mount';
import List from '@/components/table/list.vue';
import DocumentTemplates from '@/views/admin/document-templates.vue';

// Fixtures
const TEMPLATE = { created_on: '2026-09-20T00:00:00Z', document_type: 'invoice', id: 1, is_default: false, name: 'BVS Factura v4' };
const DEFAULT_SAMPLE = '[\n  {\n    "FieldName": "value"\n  }\n]';
const PDF = new Blob(['%PDF'], { type: 'application/pdf' });

// The preview modal is the second one in the view. It teleports its content onto
// document.body and only mounts it once opened: reach the sample box and the error
// through body(), and the modal itself through its component.
const previewModal = (wrapper) => wrapper.findAllComponents({ name: 'AModal' })[1];
const previewError = () => body().find('.orb-template-preview-error');

const mountView = async () => {
  const wrapper = mount(DocumentTemplates);
  await flushPromises();
  return wrapper;
};

// Opens the preview the way the table's eye button does.
const openPreview = async (wrapper) => {
  const column = wrapper.findComponent(List).props('columns').find((entry) => entry.key === 'preview');
  await column.render(null, TEMPLATE).props.onClick();
  await flushPromises();
};

const sampleBox = async () => {
  const [textarea] = await waitForBody('textarea', 1);
  return textarea;
};

const clickRender = async (wrapper) => {
  await previewModal(wrapper).vm.$emit('ok');
  await flushPromises();
};

describe('DocumentTemplates.preview', () => {
  const realCreateObjectURL = URL.createObjectURL;
  let openSpy;

  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.getSession.mockReturnValue({ database: 'PROD', role: 'admin', user: { username: 'admin.bob' } });
    AppAPI.DocumentTemplate.templates.mockResolvedValue([TEMPLATE]);
    AppAPI.DocumentTemplate.preview.mockResolvedValue(PDF);
    URL.createObjectURL = vi.fn(() => 'blob:preview');
    openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
    localStorage.clear();
  });

  afterEach(() => {
    URL.createObjectURL = realCreateObjectURL;
    openSpy.mockRestore();
  });

  it('starts closed, then opens for a template with the default sample data and no error', async () => {
    const wrapper = await mountView();
    expect(previewModal(wrapper).props('open')).toBe(false);

    await openPreview(wrapper);

    expect(previewModal(wrapper).props('open')).toBe(true);
    expect((await sampleBox()).element.value).toBe(DEFAULT_SAMPLE);
    expect(previewError().exists()).toBe(false);
  });

  it('shows a real eye button in the table row, and clicking it opens the preview', async () => {
    const wrapper = await mountView();

    const eye = wrapper.find('tbody .anticon-eye');
    expect(eye.exists()).toBe(true);
    expect(wrapper.find('tbody a-button').exists()).toBe(false);

    await eye.trigger('click');
    await flushPromises();

    expect(previewModal(wrapper).props('open')).toBe(true);
  });

  it('renders the sample data through the API for that template, opens the PDF in a new tab and closes', async () => {
    const wrapper = await mountView();
    await openPreview(wrapper);

    await clickRender(wrapper);

    expect(AppAPI.DocumentTemplate.preview).toHaveBeenCalledWith(1, [{ FieldName: 'value' }]);
    expect(URL.createObjectURL).toHaveBeenCalledWith(PDF);
    expect(openSpy).toHaveBeenCalledWith('blob:preview', '_blank');
    expect(previewModal(wrapper).props('open')).toBe(false);
  });

  it('renders the sample data the user edited', async () => {
    const wrapper = await mountView();
    await openPreview(wrapper);
    await (await sampleBox()).setValue('[{"Name":"Widget"}]');

    await clickRender(wrapper);

    expect(AppAPI.DocumentTemplate.preview).toHaveBeenCalledWith(1, [{ Name: 'Widget' }]);
  });

  it('explains that the sample data is not valid JSON, without calling the API or closing', async () => {
    const wrapper = await mountView();
    await openPreview(wrapper);
    await (await sampleBox()).setValue('not json');

    await clickRender(wrapper);

    expect(previewError().text()).toBe('Sample data must be valid JSON (an array of row objects).');
    expect(AppAPI.DocumentTemplate.preview).not.toHaveBeenCalled();
    expect(previewModal(wrapper).props('open')).toBe(true);
    expect(previewModal(wrapper).props('confirmLoading')).toBe(false);
  });

  it.each([
    ['a detail', { errors: [{ detail: 'The report could not be rendered.' }] }, 'The report could not be rendered.'],
    ['only an error code', { errors: [{ error: 'RENDER_FAILED' }] }, 'RENDER_FAILED'],
    ['neither a detail nor a code', { errors: [{}] }, 'ERROR'],
    ['no errors at all', {}, 'ERROR'],
    ['nothing at all', undefined, 'ERROR'],
  ])('keeps the preview open and shows the failure when the render answers with %s', async (_label, result, expected) => {
    AppAPI.DocumentTemplate.preview.mockResolvedValue(result);
    const wrapper = await mountView();
    await openPreview(wrapper);

    await clickRender(wrapper);

    expect(previewError().text()).toBe(expected);
    expect(previewModal(wrapper).props('open')).toBe(true);
    expect(previewModal(wrapper).props('confirmLoading')).toBe(false);
    expect(openSpy).not.toHaveBeenCalled();
  });

  it('shows the modal as busy while the render is in flight, then idle once it resolves', async () => {
    let resolvePreview;
    AppAPI.DocumentTemplate.preview.mockReturnValue(new Promise((resolve) => { resolvePreview = resolve; }));
    const wrapper = await mountView();
    await openPreview(wrapper);

    await clickRender(wrapper);
    expect(previewModal(wrapper).props('confirmLoading')).toBe(true);

    resolvePreview(PDF);
    await flushPromises();

    expect(previewModal(wrapper).props('confirmLoading')).toBe(false);
    expect(previewModal(wrapper).props('open')).toBe(false);
  });

  it('clears an earlier failure when the preview is opened again', async () => {
    const wrapper = await mountView();
    await openPreview(wrapper);
    await (await sampleBox()).setValue('not json');
    await clickRender(wrapper);
    expect(previewError().exists()).toBe(true);
    await previewModal(wrapper).vm.$emit('cancel');
    await flushPromises();

    await openPreview(wrapper);

    expect(previewError().exists()).toBe(false);
  });

  it('closes on cancel without rendering anything', async () => {
    const wrapper = await mountView();
    await openPreview(wrapper);

    await previewModal(wrapper).vm.$emit('cancel');
    await flushPromises();

    expect(previewModal(wrapper).props('open')).toBe(false);
    expect(AppAPI.DocumentTemplate.preview).not.toHaveBeenCalled();
  });

  it('lets the modal close itself', async () => {
    const wrapper = await mountView();
    await openPreview(wrapper);

    await previewModal(wrapper).vm.$emit('update:open', false);

    expect(previewModal(wrapper).props('open')).toBe(false);
  });
});
