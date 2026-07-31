// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatHistory from '@/components/chat/history.vue';

describe('ChatHistory', () => {
  it('renders one SessionItem per session', () => {
    const sessions = [{ id: 1, title: 'First' }, { id: 2, title: 'Second' }];
    const wrapper = mount(ChatHistory, { props: { sessions } });
    expect(wrapper.findAllComponents({ name: 'SessionItem' })).toHaveLength(2);
    expect(wrapper.find('.orb-history-empty').exists()).toBe(false);
  });

  it('shows the empty state with no sessions', () => {
    const wrapper = mount(ChatHistory, { props: { sessions: [] } });
    expect(wrapper.find('.orb-history-empty').exists()).toBe(true);
  });

  it('forwards select and delete events from a session item', async () => {
    const sessions = [{ id: 1, title: 'First' }];
    const wrapper = mount(ChatHistory, { props: { activeSessionId: null, sessions } });
    const item = wrapper.findComponent({ name: 'SessionItem' });

    await item.vm.$emit('select', 1);
    await item.vm.$emit('delete', 1);

    expect(wrapper.emitted('select')[0]).toEqual([1]);
    expect(wrapper.emitted('delete')[0]).toEqual([1]);
  });

  it('passes the active session id down to each item', () => {
    const sessions = [{ id: 1, title: 'First' }];
    const wrapper = mount(ChatHistory, { props: { activeSessionId: 1, sessions } });
    expect(wrapper.findComponent({ name: 'SessionItem' }).props('activeSessionId')).toBe(1);
  });
});
