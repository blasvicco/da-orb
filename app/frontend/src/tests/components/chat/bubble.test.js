// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatBubble from '@/components/chat/bubble.vue';

describe('ChatBubble', () => {
  it('renders a user message as plain text', () => {
    const wrapper = mount(ChatBubble, { props: { msg: { text: 'hello', time: '10:00', type: 'user' } } });
    expect(wrapper.find('.orb-bubble-user').text()).toContain('hello');
  });

  it('renders an agent message as parsed markdown', () => {
    const wrapper = mount(ChatBubble, {
      props: { msg: { text: '**bold**', time: '10:00', type: 'agent' } },
    });
    expect(wrapper.find('.orb-bubble-agent .orb-md').html()).toContain('<strong>bold</strong>');
  });

  it('renders an agent message with no text as an empty body', () => {
    const wrapper = mount(ChatBubble, {
      props: { msg: { time: '10:00', type: 'agent' } },
    });
    expect(wrapper.find('.orb-bubble-agent .orb-md').exists()).toBe(true);
  });

  it('shows a process list on an agent message and forwards selection', async () => {
    const wrapper = mount(ChatBubble, {
      props: {
        msg: {
          processes: [{ display_name: 'Create PO', slug: 'create-po' }],
          text: 'pick one',
          time: '10:00',
          type: 'agent',
        },
      },
    });

    await wrapper.findComponent({ name: 'Processes' }).vm.$emit('select', 'Create PO');

    expect(wrapper.emitted('process-select')[0]).toEqual(['Create PO']);
  });

  it('omits the process list on an agent message with no processes', () => {
    const wrapper = mount(ChatBubble, {
      props: { msg: { text: 'hi', time: '10:00', type: 'agent' } },
    });
    expect(wrapper.findComponent({ name: 'Processes' }).exists()).toBe(false);
  });

  it('renders a system message as parsed markdown', () => {
    const wrapper = mount(ChatBubble, {
      props: { msg: { text: '_note_', time: '10:00', type: 'system' } },
    });
    expect(wrapper.find('.orb-bubble-system .orb-md').html()).toContain('<em>note</em>');
  });

  it('renders an alert message with its own process list and forwards selection', async () => {
    const wrapper = mount(ChatBubble, {
      props: {
        msg: {
          processes: [{ name: 'approve_po' }],
          text: 'careful',
          time: '10:00',
          type: 'alert',
        },
      },
    });
    expect(wrapper.find('.orb-bubble-alert').exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'Processes' }).props('variant')).toBe('alert');

    await wrapper.findComponent({ name: 'Processes' }).vm.$emit('select', 'approve_po');

    expect(wrapper.emitted('process-select')[0]).toEqual(['approve_po']);
  });

  it('renders a sap-data message as a labelled key/value grid', () => {
    const wrapper = mount(ChatBubble, {
      props: {
        msg: {
          data: { 'landing.chat.step3.inStock': 'landing.chat.step3.inStockVal' },
          time: '10:00',
          titleKey: 'landing.chat.step3.title',
          type: 'sap-data',
        },
      },
    });
    expect(wrapper.find('.orb-msg-sap-data').exists()).toBe(true);
  });

  it('handles an unrecognised message type without rendering any bubble content', () => {
    const wrapper = mount(ChatBubble, { props: { msg: { text: 'x', time: '10:00', type: 'unknown' } } });
    expect(wrapper.find('.orb-msg-bubble').exists()).toBe(false);
  });
});
