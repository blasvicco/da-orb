// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { body, mount } from '@/tests/helpers/mount';
import IntentionStack from '@/components/intention/stack.vue';

// Fixtures
const makeMessage = (state) => ({ state, text: 'hi', type: 'agent' });

describe('IntentionStack', () => {
  it('is closed by default', () => {
    const wrapper = mount(IntentionStack, { props: { messages: [] } });
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(false);
  });

  it('opens the drawer when the open prop is set', () => {
    const wrapper = mount(IntentionStack, { props: { messages: [], open: true } });
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(true);
  });

  it('emits update:open when the drawer closes itself', async () => {
    const wrapper = mount(IntentionStack, { props: { messages: [], open: true } });
    await wrapper.findComponent({ name: 'ADrawer' }).vm.$emit('update:open', false);
    expect(wrapper.emitted('update:open')).toEqual([[false]]);
  });

  it('emits switch-panel when the switch-to-bucket button is clicked', async () => {
    const wrapper = mount(IntentionStack, { props: { messages: [], open: true } });

    await body().find('.orb-panel-switch').trigger('click');

    expect(wrapper.emitted('switch-panel')).toHaveLength(1);
  });

  it('does not render a resume button when nothing is resumable', () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'active' }],
        })],
        open: true,
      },
    });
    expect(wrapper.findComponent({ name: 'AButton' }).exists()).toBe(false);
  });

  it('renders the tree from sessionState when no message carries its own state (a reloaded session)', () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [{ text: 'hi', type: 'user' }],
        open: true,
        sessionState: {
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' }],
        },
      },
    });
    expect(wrapper.findComponent({ name: 'ATree' }).exists()).toBe(true);
  });

  it('shows the empty state when neither messages nor sessionState carry any intention data', () => {
    const wrapper = mount(IntentionStack, { props: { messages: [{ text: 'hi', type: 'user' }], open: true, sessionState: null } });
    expect(wrapper.findComponent({ name: 'ATree' }).exists()).toBe(false);
  });

  it('emits resume and update:open(false) when the resume button is clicked', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          awaiting_stack_resume: true,
          intention_nodes: [{ id: 'si#0', parent_id: null, process_id: 'search_items', status: 'paused' }],
          paused_node_ids: ['si#0'],
        })],
        open: true,
      },
    });
    await wrapper.findComponent({ name: 'AButton' }).trigger('click');
    expect(wrapper.emitted('resume')).toHaveLength(1);
    expect(wrapper.emitted('update:open')).toEqual([[false]]);
  });

  it('does not open the load-context confirm when the active node label is clicked', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'active' }],
        })],
        open: true,
      },
    });
    await body().find('.orb-intention-node-label').trigger('click');
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('does not mark the active node label as clickable', () => {
    mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'active' }],
        })],
        open: true,
      },
    });
    expect(body().find('.orb-intention-node-label').classes()).not.toContain('orb-intention-node-label--clickable');
  });

  it.each([
    ['completed', 'completed'],
    ['paused', 'paused'],
    ['abandoned', 'abandoned'],
    ['failed', 'failed'],
  ])('opens the load-context confirm when a %s node label is clicked', async (_label, status) => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status }],
        })],
        open: true,
      },
    });
    expect(body().find('.orb-intention-node-label').classes()).toContain('orb-intention-node-label--clickable');

    await body().find('.orb-intention-node-label').trigger('click');

    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(true);
  });

  it('emits navigate with the node id/label and update:open(false) once the confirm is accepted', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{
            id: 'pr#0', parent_id: null,
            process_definition: { name: 'Purchase Request' }, process_id: 'purchase_request', status: 'completed',
          }],
        })],
        open: true,
      },
    });
    await body().find('.orb-intention-node-label').trigger('click');
    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');

    expect(wrapper.emitted('navigate')).toHaveLength(1);
    expect(wrapper.emitted('navigate')[0][0]).toEqual({ id: 'pr#0', label: 'Purchase Request' });
    expect(wrapper.emitted('update:open')).toEqual([[false]]);
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('closes the confirm without navigating on cancel', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' }],
        })],
        open: true,
      },
    });
    await body().find('.orb-intention-node-label').trigger('click');
    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('cancel');

    expect(wrapper.emitted('navigate')).toBeUndefined();
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('closes the confirm when its openChange reports closed', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' }],
        })],
        open: true,
      },
    });
    await body().find('.orb-intention-node-label').trigger('click');
    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('openChange', false);

    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });
});
