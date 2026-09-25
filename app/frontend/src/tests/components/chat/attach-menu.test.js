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
import { flushPromises, mount, waitForBody } from '@/tests/helpers/mount';
import AttachMenu from '@/components/chat/attach-menu.vue';

// a-popover uses trigger="click" and only mounts (teleported) content once opened, and
// mounts it asynchronously: resolves with the panel's two options once they are in the body.
const openMenu = async (wrapper) => {
  await wrapper.find('.orb-attach-trigger').trigger('click');
  return waitForBody('.orb-attach-option', 2);
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

  it('both drawers start closed', () => {
    const wrapper = mount(AttachMenu);
    const drawers = wrapper.findAllComponents({ name: 'ADrawer' });
    expect(drawers.every((drawer) => drawer.props('open') === false)).toBe(true);
  });

  it('emits pick-files and closes the menu when "Add files" is clicked, without opening the bucket drawer', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    const options = await openMenu(wrapper);
    await options[0].trigger('click');

    expect(wrapper.emitted('pick-files')).toHaveLength(1);
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(false);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
  });

  it('opens the intention graph drawer when "Show intention graph" is clicked', async () => {
    const wrapper = mount(AttachMenu);
    const options = await openMenu(wrapper);
    await options[1].trigger('click');

    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(false);
  });

  it('closes the intention graph drawer when the bucket drawer is opened afterwards', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    const options = await openMenu(wrapper);
    await options[1].trigger('click');
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);

    wrapper.vm.openBucket();
    await flushPromises();

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
  });

  it('switches from the bucket drawer to the intention graph drawer on switch-panel', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    wrapper.vm.openBucket();
    await flushPromises();
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);

    await wrapper.findComponent({ name: 'BucketTrigger' }).vm.$emit('switch-panel');

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(false);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);
  });

  it('switches from the intention graph drawer to the bucket drawer on switch-panel', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    const options = await openMenu(wrapper);
    await options[1].trigger('click');
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(true);

    await wrapper.findComponent({ name: 'IntentionStack' }).vm.$emit('switch-panel');

    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);
  });

  it.each(['BucketTrigger', 'IntentionStack'])('lets the %s drawer open and close itself', async (name) => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });
    const drawer = wrapper.findComponent({ name });

    await drawer.vm.$emit('update:open', true);
    expect(drawer.props('open')).toBe(true);

    await drawer.vm.$emit('update:open', false);
    expect(drawer.props('open')).toBe(false);
  });

  it('forwards messages/sessionState to IntentionStack', () => {
    const messages = [{ text: 'hi', type: 'user' }];
    const sessionState = { intention_nodes: [] };
    const wrapper = mount(AttachMenu, { props: { messages, sessionState } });

    const intentionStack = wrapper.findComponent({ name: 'IntentionStack' });
    expect(intentionStack.props('messages')).toEqual(messages);
    expect(intentionStack.props('sessionState')).toEqual(sessionState);
  });

  it('re-emits navigate from IntentionStack', async () => {
    const wrapper = mount(AttachMenu);
    const intentionStack = wrapper.findComponent({ name: 'IntentionStack' });

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

  it('forwards ensureSessionId to BucketTrigger', () => {
    const ensureSessionId = vi.fn().mockResolvedValue(99);
    const wrapper = mount(AttachMenu, { props: { ensureSessionId } });

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('ensureSessionId')).toBe(ensureSessionId);
  });

  it('exposes openBucket so a sibling button can open the bucket drawer directly', async () => {
    const wrapper = mount(AttachMenu, { props: { sessionId: 42 } });

    wrapper.vm.openBucket();
    await flushPromises();

    expect(wrapper.findComponent({ name: 'BucketTrigger' }).props('open')).toBe(true);
    expect(wrapper.findComponent({ name: 'IntentionStack' }).props('open')).toBe(false);
  });
});
