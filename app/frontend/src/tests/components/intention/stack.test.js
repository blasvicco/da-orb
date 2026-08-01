// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import IntentionStack from '@/components/intention/stack.vue';

// Fixtures
const makeMessage = (state) => ({ state, text: 'hi', type: 'agent' });

const openDrawer = async (wrapper) => {
  await wrapper.find('.orb-prompt-tool-btn').trigger('click');
};

describe('IntentionStack', () => {
  it('renders a trigger button labeled with the intention-graph title', () => {
    const wrapper = mount(IntentionStack, { props: { messages: [] } });
    const button = wrapper.find('.orb-prompt-tool-btn');
    expect(button.exists()).toBe(true);
    expect(button.attributes('title')).toBe('Intention Graph');
  });

  it('is closed by default', () => {
    const wrapper = mount(IntentionStack, { props: { messages: [] } });
    // ADrawer's content teleports onto document.body and never actually renders
    // it under happy-dom (see landing.test.js), so assert against the reactive
    // `open` prop that drives visibility rather than the DOM artifact.
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(false);
  });

  it('opens the drawer when the trigger button is clicked', async () => {
    const wrapper = mount(IntentionStack, { props: { messages: [] } });
    await openDrawer(wrapper);
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(true);
  });

  it('does not render a resume button when nothing is resumable', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'active' }],
        })],
      },
    });
    await openDrawer(wrapper);
    expect(wrapper.findComponent({ name: 'AButton' }).exists()).toBe(false);
  });

  it('renders the tree from sessionState when no message carries its own state (a reloaded session)', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [{ text: 'hi', type: 'user' }],
        sessionState: {
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'completed' }],
        },
      },
    });
    await openDrawer(wrapper);
    expect(wrapper.findComponent({ name: 'ATree' }).exists()).toBe(true);
  });

  it('shows the empty state when neither messages nor sessionState carry any intention data', async () => {
    const wrapper = mount(IntentionStack, { props: { messages: [{ text: 'hi', type: 'user' }], sessionState: null } });
    await openDrawer(wrapper);
    expect(wrapper.findComponent({ name: 'ATree' }).exists()).toBe(false);
  });

  it('emits resume and closes the drawer when the resume button is clicked', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          awaiting_stack_resume: true,
          intention_nodes: [{ id: 'si#0', parent_id: null, process_id: 'search_items', status: 'paused' }],
          paused_node_ids: ['si#0'],
        })],
      },
    });
    await openDrawer(wrapper);
    // AButton is a real (mounted) component instance even though ADrawer's Portal
    // never attaches its DOM to document — findComponent walks the component
    // tree, not document.querySelector, so it locates it regardless.
    await wrapper.findComponent({ name: 'AButton' }).trigger('click');
    expect(wrapper.emitted('resume')).toHaveLength(1);
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(false);
  });

  it('does not render a navigate button for the active node', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status: 'active' }],
        })],
      },
    });
    await openDrawer(wrapper);
    expect(wrapper.findComponent({ name: 'AButton' }).exists()).toBe(false);
  });

  it.each([
    ['completed', 'completed'],
    ['paused', 'paused'],
    ['abandoned', 'abandoned'],
  ])('renders a navigate button for a %s node', async (_label, status) => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{ id: 'pr#0', parent_id: null, process_id: 'purchase_request', status }],
        })],
      },
    });
    await openDrawer(wrapper);
    expect(wrapper.findComponent({ name: 'AButton' }).exists()).toBe(true);
  });

  it('emits navigate with the node id/label and closes the drawer when the navigate button is clicked', async () => {
    const wrapper = mount(IntentionStack, {
      props: {
        messages: [makeMessage({
          intention_nodes: [{
            id: 'pr#0', parent_id: null,
            process_definition: { name: 'Purchase Request' }, process_id: 'purchase_request', status: 'completed',
          }],
        })],
      },
    });
    await openDrawer(wrapper);
    await wrapper.findComponent({ name: 'AButton' }).trigger('click');
    expect(wrapper.emitted('navigate')).toHaveLength(1);
    expect(wrapper.emitted('navigate')[0][0]).toEqual({ id: 'pr#0', label: 'Purchase Request' });
    expect(wrapper.findComponent({ name: 'ADrawer' }).props('open')).toBe(false);
  });
});
