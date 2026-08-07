// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockBucket = vi.hoisted(() => ({
  deleteFile: vi.fn().mockResolvedValue({}),
  downloadUrl: vi.fn().mockResolvedValue({ url: '' }),
  files: vi.fn().mockResolvedValue([]),
  upload: vi.fn().mockResolvedValue({}),
}));

vi.mock('@/modules/api', () => ({ default: { Bucket: mockBucket } }));

// App imports
import { body, flushPromises, mount } from '@/tests/helpers/mount';
import BucketTrigger from '@/components/bucket/trigger.vue';

// Fixtures
const makeFile = (overrides = {}) => ({
  created_on: '2026-08-01T00:00:00Z',
  description: '',
  id: 1,
  mime_type: 'text/csv',
  name: 'orders.csv',
  origin: 'user_upload',
  size: 2048,
  ...overrides,
});

describe('BucketTrigger', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.deleteFile.mockResolvedValue({});
    mockBucket.files.mockResolvedValue([]);
    mockBucket.downloadUrl.mockResolvedValue({ url: '' });
    mockBucket.upload.mockResolvedValue({});
  });

  it('is closed by default', () => {
    const wrapper = mount(BucketTrigger);
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(false);
  });

  it('emits switch-panel when the switch-to-intention-graph button is clicked', async () => {
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-panel-switch').trigger('click');

    expect(wrapper.emitted('switch-panel')).toHaveLength(1);
  });

  it('opens the drawer when the open prop is set', async () => {
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(true);
  });

  it('emits update:open when the drawer closes itself', async () => {
    const wrapper = mount(BucketTrigger, { props: { open: true } });
    await wrapper.findComponent({ name: 'ADrawer' }).vm.$emit('update:open', false);
    expect(wrapper.emitted('update:open')).toEqual([[false]]);
  });

  it('does not fetch files when there is no session', () => {
    mount(BucketTrigger, { props: { sessionId: null } });
    expect(mockBucket.files).not.toHaveBeenCalled();
  });

  it('fetches and lists files for the given session', async () => {
    mockBucket.files.mockResolvedValue([makeFile()]);
    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();
    expect(mockBucket.files).toHaveBeenCalledWith(42);
    expect(body().find('.orb-bucket-item-name').text()).toBe('orders.csv');
  });

  it('re-fetches files when sessionId changes', async () => {
    const wrapper = mount(BucketTrigger, { props: { sessionId: 1 } });
    await flushPromises();
    await wrapper.setProps({ sessionId: 2 });
    await flushPromises();
    expect(mockBucket.files).toHaveBeenCalledWith(1);
    expect(mockBucket.files).toHaveBeenCalledWith(2);
  });

  it('shows the empty state when the session has no files', async () => {
    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();
    expect(body().find('.orb-bucket-empty').exists()).toBe(true);
  });

  it('uploads each selected file then refreshes the list when a session exists', async () => {
    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();
    mockBucket.files.mockResolvedValue([makeFile()]);

    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    const input = body().find('.orb-bucket-file-input');
    Object.defineProperty(input.element, 'files', { value: [file] });
    await input.trigger('change');
    await flushPromises();

    expect(mockBucket.upload).toHaveBeenCalledWith(42, file);
    expect(mockBucket.files).toHaveBeenCalledTimes(2);
  });

  it('stages a selected file instead of uploading when there is no session yet', async () => {
    mount(BucketTrigger, { props: { open: true, sessionId: null } });
    await flushPromises();

    const file = new File(['a,b'], 'draft.csv', { type: 'text/csv' });
    const input = body().find('.orb-bucket-file-input');
    Object.defineProperty(input.element, 'files', { value: [file] });
    await input.trigger('change');
    await flushPromises();

    expect(mockBucket.upload).not.toHaveBeenCalled();
    expect(body().find('.orb-bucket-item--pending .orb-bucket-item-name').text()).toBe('draft.csv');
  });

  it('uploads staged files automatically once a session becomes available', async () => {
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: null } });
    await flushPromises();

    const file = new File(['a,b'], 'draft.csv', { type: 'text/csv' });
    const input = body().find('.orb-bucket-file-input');
    Object.defineProperty(input.element, 'files', { value: [file] });
    await input.trigger('change');
    await flushPromises();

    mockBucket.files.mockResolvedValue([makeFile({ name: 'draft.csv' })]);
    await wrapper.setProps({ sessionId: 99 });
    await flushPromises();

    expect(mockBucket.upload).toHaveBeenCalledWith(99, file);
    expect(body().find('.orb-bucket-item--pending').exists()).toBe(false);
  });

  it('removes a staged file from the pending list when its trash icon is clicked', async () => {
    mount(BucketTrigger, { props: { open: true, sessionId: null } });
    await flushPromises();

    const fileA = new File(['a'], 'a.csv', { type: 'text/csv' });
    const fileB = new File(['b'], 'b.csv', { type: 'text/csv' });
    const input = body().find('.orb-bucket-file-input');
    Object.defineProperty(input.element, 'files', { value: [fileA, fileB] });
    await input.trigger('change');
    await flushPromises();

    expect(body().findAll('.orb-bucket-item--pending')).toHaveLength(2);

    await body().find('.orb-bucket-remove-btn').trigger('click');

    const remaining = body().findAll('.orb-bucket-item--pending');
    expect(remaining).toHaveLength(1);
    expect(remaining[0].find('.orb-bucket-item-name').text()).toBe('b.csv');
    expect(mockBucket.upload).not.toHaveBeenCalled();
  });

  it('opens a delete confirm for the clicked file, closing others', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ id: 1 }), makeFile({ id: 2, name: 'b.csv' })]);
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().findAll('.orb-bucket-delete-btn')[0].trigger('click');

    // findComponent walks the component tree, not the DOM, so it locates these
    // regardless of ADrawer teleporting its content elsewhere (unlike body().find()
    // above, which is a real DOM query and needs the teleported location).
    const confirms = wrapper.findAllComponents({ name: 'APopconfirm' });
    expect(confirms[0].props('open')).toBe(true);
    expect(confirms[1].props('open')).toBe(false);
  });

  it('deletes the file and removes it from the list once the confirm is accepted', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ id: 1 }), makeFile({ id: 2, name: 'b.csv' })]);
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().findAll('.orb-bucket-delete-btn')[0].trigger('click');
    await wrapper.findAllComponents({ name: 'APopconfirm' })[0].vm.$emit('confirm');
    await flushPromises();

    expect(mockBucket.deleteFile).toHaveBeenCalledWith(1);
    const remaining = body().findAll('.orb-bucket-item-name');
    expect(remaining).toHaveLength(1);
    expect(remaining[0].text()).toBe('b.csv');
  });

  it('emits file-deleted with the deleted file id once the confirm is accepted', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ id: 1 })]);
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-delete-btn').trigger('click');
    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');
    await flushPromises();

    expect(wrapper.emitted('file-deleted')).toEqual([[1]]);
  });

  it('does not emit file-deleted when the delete API call fails', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ id: 1 })]);
    mockBucket.deleteFile.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-delete-btn').trigger('click');
    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');
    await flushPromises();

    expect(wrapper.emitted('file-deleted')).toBeUndefined();
  });

  it('keeps the file when the delete confirm is cancelled', async () => {
    mockBucket.files.mockResolvedValue([makeFile()]);
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-delete-btn').trigger('click');
    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('cancel');

    expect(mockBucket.deleteFile).not.toHaveBeenCalled();
    expect(body().find('.orb-bucket-item-name').text()).toBe('orders.csv');
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('opens an image preview when an image file name is clicked', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ mime_type: 'image/png', name: 'logo.png' })]);
    mockBucket.downloadUrl.mockResolvedValue({ url: 'https://signed.example/logo.png' });
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-item-name').trigger('click');
    await flushPromises();

    expect(wrapper.findComponent({ name: 'AModal' }).props('open')).toBe(true);
    expect(body().find('.orb-bucket-preview-image').attributes('src')).toBe('https://signed.example/logo.png');
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it('opens a text preview and fetches its content when a text file name is clicked', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ mime_type: 'text/csv', name: 'orders.csv' })]);
    mockBucket.downloadUrl.mockResolvedValue({ url: 'https://signed.example/orders.csv' });
    globalThis.fetch.mockResolvedValue({ text: async () => 'a,b\n1,2' });
    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-item-name').trigger('click');
    await flushPromises();

    expect(globalThis.fetch).toHaveBeenCalledWith('https://signed.example/orders.csv');
    expect(body().find('.orb-bucket-preview-text').text()).toBe('a,b\n1,2');
  });

  it('pretty-prints JSON content in the preview', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ mime_type: 'application/json', name: 'data.json' })]);
    mockBucket.downloadUrl.mockResolvedValue({ url: 'https://signed.example/data.json' });
    globalThis.fetch.mockResolvedValue({ text: async () => '{"a":1}' });
    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-item-name').trigger('click');
    await flushPromises();

    expect(body().find('.orb-bucket-preview-text').text()).toBe(JSON.stringify({ a: 1 }, null, 2));
  });

  it('falls back to raw text when a file claims application/json but is not valid JSON', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ mime_type: 'application/json', name: 'data.json' })]);
    mockBucket.downloadUrl.mockResolvedValue({ url: 'https://signed.example/data.json' });
    globalThis.fetch.mockResolvedValue({ text: async () => 'not json' });
    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-item-name').trigger('click');
    await flushPromises();

    expect(body().find('.orb-bucket-preview-text').text()).toBe('not json');
  });

  it('does not open a preview for a non-previewable file', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ mime_type: 'application/pdf', name: 'report.pdf' })]);
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-item-name').trigger('click');

    expect(wrapper.findComponent({ name: 'AModal' }).props('open')).toBe(false);
    expect(mockBucket.downloadUrl).not.toHaveBeenCalled();
  });

  it('emits use-as-context and closes the drawer when the context button is clicked', async () => {
    mockBucket.files.mockResolvedValue([makeFile({ id: 1, name: 'orders.csv' })]);
    const wrapper = mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();

    await body().find('.orb-bucket-context-btn').trigger('click');

    expect(wrapper.emitted('use-as-context')).toEqual([[{ id: 1, name: 'orders.csv' }]]);
    expect(wrapper.emitted('update:open')).toEqual([[false]]);
  });

  it('opens the presigned download URL when the download button is clicked', async () => {
    mockBucket.files.mockResolvedValue([makeFile()]);
    mockBucket.downloadUrl.mockResolvedValue({ url: 'https://signed.example/orders.csv' });
    const originalOpen = window.open;
    window.open = vi.fn();

    mount(BucketTrigger, { props: { open: true, sessionId: 42 } });
    await flushPromises();
    await body().find('.orb-bucket-download-btn').trigger('click');
    await flushPromises();

    expect(mockBucket.downloadUrl).toHaveBeenCalledWith(1);
    expect(window.open).toHaveBeenCalledWith('https://signed.example/orders.csv', '_blank');
    window.open = originalOpen;
  });
});
