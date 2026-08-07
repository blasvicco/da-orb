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
import { body, flushPromises, mount } from '@/tests/helpers/mount';
import AttachMenu from '@/components/chat/attach-menu.vue';

// a-popover uses trigger="click" and only mounts (teleported) content once opened.
const openMenu = async (wrapper) => {
  await wrapper.find('.orb-attach-trigger').trigger('click');
};

describe('AttachMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockBucket.files.mockResolvedValue([]);
    mockBucket.downloadUrl.mockResolvedValue({ url: '' });
    mockBucket.upload.mockResolvedValue({});
  });

  it('renders a trigger button labeled with the attach title', () => {
    const wrapper = mount(AttachMenu);
    const button = wrapper.find('.orb-attach-trigger');
    expect(button.exists()).toBe(true);
    expect(button.attributes('title')).toBe('Add attachment');
  });

  it('badges the trigger with the total file count (uploaded + pending)', async () => {
    mockBucket.files.mockResolvedValue([{ id: 1, name: 'a.csv', origin: 'user_upload', size: 5 }]);
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    await flushPromises();

    expect(wrapper.findComponent({ name: 'ABadge' }).props('count')).toBe(1);
  });

  it('both drawers start closed', () => {
    const wrapper = mount(AttachMenu);
    const drawers = wrapper.findAllComponents({ name: 'ADrawer' });
    expect(drawers.every((drawer) => drawer.props('open') === false)).toBe(true);
  });

  it('opens the bucket drawer when "Add files" is clicked', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    await openMenu(wrapper);
    const options = body().findAll('.orb-attach-option');
    await options[0].trigger('click');

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
  });

  it('opens the intention graph drawer when "Show intention graph" is clicked', async () => {
    const wrapper = mount(AttachMenu);
    await openMenu(wrapper);
    const options = body().findAll('.orb-attach-option');
    await options[1].trigger('click');

    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(false);
  });

  it('closes the intention graph drawer when the bucket drawer is opened afterwards', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    await openMenu(wrapper);
    let options = body().findAll('.orb-attach-option');
    await options[1].trigger('click');
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);

    await openMenu(wrapper);
    options = body().findAll('.orb-attach-option');
    await options[0].trigger('click');

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
  });

  it('switches from the bucket drawer to the intention graph drawer on switch-panel', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    await openMenu(wrapper);
    const options = body().findAll('.orb-attach-option');
    await options[0].trigger('click');
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);

    await wrapper.findComponent({ name: 'BucketTrigger' }).vm.$emit('switch-panel');

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(false);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);
  });

  it('switches from the intention graph drawer to the bucket drawer on switch-panel', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    await openMenu(wrapper);
    const options = body().findAll('.orb-attach-option');
    await options[1].trigger('click');
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);

    await wrapper.findComponent({ name: 'IntentionStack' }).vm.$emit('switch-panel');

    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);
  });

  it('forwards messages/sessionState to IntentionStack', () => {
    const messages = [{ text: 'hi', type: 'user' }];
    const sessionState = { intention_nodes: [] };
    const wrapper = mount(AttachMenu, { props: { messages, sessionState } });

    const intentionStack = wrapper.findComponent({ name: 'IntentionStack' });
    expect(intentionStack.props('messages')).toEqual(messages);
    expect(intentionStack.props('sessionState')).toEqual(sessionState);
  });

  it('re-emits resume/navigate from IntentionStack', async () => {
    const wrapper = mount(AttachMenu);
    const intentionStack = wrapper.findComponent({ name: 'IntentionStack' });

    await intentionStack.vm.$emit('resume');
    expect(wrapper.emitted('resume')).toHaveLength(1);

    await intentionStack.vm.$emit('navigate', { id: 'n1#0', label: 'Search Items' });
    expect(wrapper.emitted('navigate')[0][0]).toEqual({ id: 'n1#0', label: 'Search Items' });
  });

  it('re-emits context-file from BucketTrigger', async () => {
    const wrapper = mount(AttachMenu);
    const bucketTrigger = wrapper.findComponent({ name: 'BucketTrigger' });

    await bucketTrigger.vm.$emit('use-as-context', { id: 3, name: 'orders.csv' });

    expect(wrapper.emitted('context-file')).toEqual([[{ id: 3, name: 'orders.csv' }]]);
  });

  it('re-emits file-deleted from BucketTrigger', async () => {
    const wrapper = mount(AttachMenu);
    const bucketTrigger = wrapper.findComponent({ name: 'BucketTrigger' });

    await bucketTrigger.vm.$emit('file-deleted', 3);

    expect(wrapper.emitted('file-deleted')).toEqual([[3]]);
  });
});
