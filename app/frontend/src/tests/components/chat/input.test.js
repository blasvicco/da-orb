// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockBucket = vi.hoisted(() => ({
  downloadUrl: vi.fn().mockResolvedValue({ url: '' }),
  files: vi.fn().mockResolvedValue([]),
  upload: vi.fn().mockResolvedValue({}),
}));

vi.mock('@/modules/api', () => ({ default: { Bucket: mockBucket } }));

// App imports
import { flushPromises, mount } from '@/tests/helpers/mount';
import ChatInput from '@/components/chat/input.vue';

const makeDropEvent = (files) => ({ dataTransfer: { files } });

describe('ChatInput typing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.files.mockResolvedValue([]);
    mockBucket.upload.mockResolvedValue({});
  });

  it('renders the current modelValue', () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hello' } });
    expect(wrapper.find('textarea').element.value).toBe('hello');
  });

  it('emits update:modelValue as the user types', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: '' } });
    const textarea = wrapper.find('textarea');
    textarea.element.value = 'hi';
    await textarea.trigger('input');
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['hi']);
  });

  it('re-measures its height when modelValue changes externally', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: '' } });
    await expect(wrapper.setProps({ modelValue: 'a longer message now' })).resolves.toBeUndefined();
  });
});

describe('ChatInput sending', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.files.mockResolvedValue([]);
    mockBucket.upload.mockResolvedValue({});
  });

  it('sends on Enter without Shift', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' });
    await flushPromises();
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('does not send on Shift+Enter (newline instead)', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter', shiftKey: true });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('does not send on other keys', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('textarea').trigger('keydown', { key: 'a' });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('clicking the send button emits send', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    await flushPromises();
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it.each([
    ['an empty message', ''],
    ['a whitespace-only message', '   '],
  ])('disables the send button for %s', (_label, modelValue) => {
    const wrapper = mount(ChatInput, { props: { modelValue } });
    expect(wrapper.find('.orb-prompt-send-btn').attributes('disabled')).toBeDefined();
  });

  it('disables the send button while disabled prop is set, even with text present', () => {
    const wrapper = mount(ChatInput, { props: { disabled: true, modelValue: 'hi' } });
    expect(wrapper.find('.orb-prompt-send-btn').attributes('disabled')).toBeDefined();
  });

  it('enables the send button with non-blank text and not disabled', () => {
    const wrapper = mount(ChatInput, { props: { disabled: false, modelValue: 'hi' } });
    expect(wrapper.find('.orb-prompt-send-btn').attributes('disabled')).toBeUndefined();
  });
});

describe('ChatInput attach menu wiring', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.files.mockResolvedValue([]);
    mockBucket.upload.mockResolvedValue({});
  });

  it('forwards messages/sessionId/sessionState to AttachMenu', () => {
    const messages = [{ text: 'hi', type: 'user' }];
    const sessionState = { intention_nodes: [] };
    const wrapper = mount(ChatInput, { props: { messages, sessionId: 42, sessionState } });

    const attachMenu = wrapper.findComponent({ name: 'AttachMenu' });
    expect(attachMenu.props('messages')).toEqual(messages);
    expect(attachMenu.props('sessionId')).toBe(42);
    expect(attachMenu.props('sessionState')).toEqual(sessionState);
  });

  it('re-emits resume/navigate from AttachMenu', async () => {
    const wrapper = mount(ChatInput);
    const attachMenu = wrapper.findComponent({ name: 'AttachMenu' });

    await attachMenu.vm.$emit('resume');
    expect(wrapper.emitted('resume')).toHaveLength(1);

    await attachMenu.vm.$emit('navigate', { id: 'n1#0', label: 'Search Items' });
    expect(wrapper.emitted('navigate')[0][0]).toEqual({ id: 'n1#0', label: 'Search Items' });
  });

  it('re-emits context-file from AttachMenu', async () => {
    const wrapper = mount(ChatInput);
    const attachMenu = wrapper.findComponent({ name: 'AttachMenu' });

    await attachMenu.vm.$emit('context-file', { id: 3, name: 'orders.csv' });

    expect(wrapper.emitted('context-file')).toEqual([[{ id: 3, name: 'orders.csv' }]]);
  });

  it('re-emits file-deleted from AttachMenu', async () => {
    const wrapper = mount(ChatInput);
    const attachMenu = wrapper.findComponent({ name: 'AttachMenu' });

    await attachMenu.vm.$emit('file-deleted', 3);

    expect(wrapper.emitted('file-deleted')).toEqual([[3]]);
  });
});

describe('ChatInput context file chips', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.files.mockResolvedValue([]);
    mockBucket.upload.mockResolvedValue({});
  });

  it('shows no chip when there are no context files', () => {
    const wrapper = mount(ChatInput);
    expect(wrapper.find('.orb-prompt-context').exists()).toBe(false);
  });

  it('shows a chip with the context file name when one is set', () => {
    const wrapper = mount(ChatInput, { props: { contextFiles: [{ id: 3, name: 'orders.csv' }] } });
    expect(wrapper.find('.orb-prompt-context-name').text()).toBe('orders.csv');
  });

  it('shows one chip per context file', () => {
    const wrapper = mount(ChatInput, {
      props: { contextFiles: [{ id: 3, name: 'orders.csv' }, { id: 4, name: 'invoice.pdf' }] },
    });
    const names = wrapper.findAll('.orb-prompt-context-name').map((chip) => chip.text());
    expect(names).toEqual(['orders.csv', 'invoice.pdf']);
  });

  it('emits remove-context with the dismissed file id', async () => {
    const wrapper = mount(ChatInput, {
      props: { contextFiles: [{ id: 3, name: 'orders.csv' }, { id: 4, name: 'invoice.pdf' }] },
    });
    await wrapper.findAll('.orb-prompt-context-remove')[0].trigger('click');
    expect(wrapper.emitted('remove-context')).toEqual([[3]]);
  });
});

describe('ChatInput drag and drop', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.files.mockResolvedValue([]);
    mockBucket.upload.mockResolvedValue({});
  });

  it('marks the composer as dragging on dragover and clears it on dragleave', async () => {
    const wrapper = mount(ChatInput);
    const dropZone = wrapper.find('.orb-prompt-wrapper');

    await dropZone.trigger('dragover');
    expect(dropZone.classes()).toContain('orb-prompt-wrapper--dragging');

    await dropZone.trigger('dragleave');
    expect(dropZone.classes()).not.toContain('orb-prompt-wrapper--dragging');
  });

  it('previews a dropped file without uploading it, and clears the dragging state', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    const wrapper = mount(ChatInput, { props: { sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');

    await dropZone.trigger('dragover');
    await dropZone.trigger('drop', makeDropEvent([file]));

    expect(dropZone.classes()).not.toContain('orb-prompt-wrapper--dragging');
    expect(wrapper.find('.orb-prompt-attachment-name').text()).toBe('orders.csv');
    expect(mockBucket.upload).not.toHaveBeenCalled();
  });

  it('does nothing when the drop carries no files', async () => {
    const wrapper = mount(ChatInput);
    const dropZone = wrapper.find('.orb-prompt-wrapper');

    await dropZone.trigger('drop', makeDropEvent([]));
    await flushPromises();

    expect(wrapper.find('.orb-prompt-attachments').exists()).toBe(false);
  });

  it('removes a previewed file from the queue when its remove button is clicked', async () => {
    const fileA = new File(['a'], 'a.csv', { type: 'text/csv' });
    const fileB = new File(['b'], 'b.csv', { type: 'text/csv' });
    const wrapper = mount(ChatInput);
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([fileA, fileB]));

    await wrapper.findAll('.orb-prompt-attachment-remove')[0].trigger('click');

    const remaining = wrapper.findAll('.orb-prompt-attachment-name');
    expect(remaining).toHaveLength(1);
    expect(remaining[0].text()).toBe('b.csv');
  });

  it('commits (uploads) staged files only once the user presses Enter', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    mockBucket.upload.mockResolvedValue({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 });
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 }]);
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi', sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));
    expect(mockBucket.upload).not.toHaveBeenCalled();

    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' });
    await flushPromises();

    expect(mockBucket.upload).toHaveBeenCalledWith(42, file);
    expect(wrapper.find('.orb-prompt-attachments').exists()).toBe(false);
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('shows an uploading overlay on staged chips while the upload is in flight, then clears them once it resolves', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    let resolveUpload;
    mockBucket.upload.mockReturnValue(new Promise((resolve) => { resolveUpload = resolve; }));
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 }]);
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi', sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));

    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    await flushPromises();

    expect(wrapper.find('.orb-prompt-attachments').exists()).toBe(true);
    expect(wrapper.find('.orb-prompt-attachment-uploading').exists()).toBe(true);

    resolveUpload({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 });
    await flushPromises();

    expect(wrapper.find('.orb-prompt-attachments').exists()).toBe(false);
  });

  it('auto-links a dropped-and-uploaded file as context once committed', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    mockBucket.upload.mockResolvedValue({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 });
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 }]);
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi', sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));

    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' });
    await flushPromises();

    expect(wrapper.emitted('context-file')).toEqual([[{ id: 1, name: 'orders.csv' }]]);
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('does not emit context-file when a dropped upload fails', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    mockBucket.upload.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi', sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));

    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' });
    await flushPromises();

    expect(wrapper.emitted('context-file')).toBeUndefined();
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('commits staged files when the send button is clicked', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    mockBucket.upload.mockResolvedValue({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 });
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 }]);
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi', sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));

    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    await flushPromises();

    expect(mockBucket.upload).toHaveBeenCalledWith(42, file);
    expect(wrapper.find('.orb-prompt-attachments').exists()).toBe(false);
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('ensures a real session id before uploading when a file is attached before any session exists', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    mockBucket.upload.mockResolvedValue({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 });
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 }]);
    const ensureSessionId = vi.fn().mockResolvedValue(99);
    const wrapper = mount(ChatInput, { props: { ensureSessionId, modelValue: 'hi', sessionId: null } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));

    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    await flushPromises();

    expect(ensureSessionId).toHaveBeenCalled();
    expect(mockBucket.upload).toHaveBeenCalledWith(99, file);
    expect(wrapper.emitted('context-file')).toEqual([[{ id: 1, name: 'orders.csv' }]]);
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('does not call ensureSessionId when a session already exists', async () => {
    const file = new File(['a,b'], 'orders.csv', { type: 'text/csv' });
    mockBucket.upload.mockResolvedValue({ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 });
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'orders.csv', origin: 'user_upload', size: 5 }]);
    const ensureSessionId = vi.fn().mockResolvedValue(99);
    const wrapper = mount(ChatInput, { props: { ensureSessionId, modelValue: 'hi', sessionId: 42 } });
    const dropZone = wrapper.find('.orb-prompt-wrapper');
    await dropZone.trigger('drop', makeDropEvent([file]));

    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    await flushPromises();

    expect(ensureSessionId).not.toHaveBeenCalled();
    expect(mockBucket.upload).toHaveBeenCalledWith(42, file);
  });

  it('does nothing extra on send when there are no staged files', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    expect(mockBucket.upload).not.toHaveBeenCalled();
    expect(wrapper.emitted('send')).toHaveLength(1);
  });
});
