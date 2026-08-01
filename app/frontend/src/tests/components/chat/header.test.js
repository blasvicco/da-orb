// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatHeader from '@/components/chat/header.vue';

describe('ChatHeader title', () => {
  it('prefers the session title when one is set', () => {
    const wrapper = mount(ChatHeader, { props: { hasMessages: true, sessionTitle: 'My chat' } });
    expect(wrapper.find('.orb-header-title').text()).toBe('My chat');
  });

  it('falls back to the active-workflow label once messages exist', () => {
    const wrapper = mount(ChatHeader, { props: { hasMessages: true, sessionTitle: null } });
    expect(wrapper.find('.orb-header-title').text().length).toBeGreaterThan(0);
  });

  it('falls back to the new-chat label with no messages and no title', () => {
    const withMessages = mount(ChatHeader, { props: { hasMessages: true, sessionTitle: null } });
    const withoutMessages = mount(ChatHeader, { props: { hasMessages: false, sessionTitle: null } });
    expect(withoutMessages.find('.orb-header-title').text())
      .not.toBe(withMessages.find('.orb-header-title').text());
  });
});

describe('ChatHeader tokens', () => {
  it('shows the compacted token count only when tokensUsed is positive', () => {
    const withTokens = mount(ChatHeader, { props: { tokensUsed: 1500 } });
    expect(withTokens.find('.orb-header-tokens').text()).toContain('1.5k');

    const withoutTokens = mount(ChatHeader, { props: { tokensUsed: 0 } });
    expect(withoutTokens.find('.orb-header-tokens').exists()).toBe(false);
  });
});

describe('ChatHeader child components', () => {
  it('forwards messages/sessionTitle/userName to Export and status to Badge', () => {
    const messages = [{ text: 'hi', type: 'user' }];
    const sessionState = { intention_nodes: [] };
    const wrapper = mount(ChatHeader, {
      props: {
        connectionStatus: 'connected',
        messages,
        sessionState,
        sessionTitle: 'My chat',
        userName: 'Bob',
      },
    });

    const exportComponent = wrapper.findComponent({ name: 'Export' });
    expect(exportComponent.props('messages')).toEqual(messages);
    expect(exportComponent.props('sessionTitle')).toBe('My chat');
    expect(exportComponent.props('userName')).toBe('Bob');
    expect(wrapper.findComponent({ name: 'Badge' }).props('status')).toBe('connected');
    const intentionStack = wrapper.findComponent({ name: 'IntentionStack' });
    expect(intentionStack.props('messages')).toEqual(messages);
    expect(intentionStack.props('sessionState')).toEqual(sessionState);
  });

  it('re-emits resume when IntentionStack emits it', async () => {
    const wrapper = mount(ChatHeader);
    await wrapper.findComponent({ name: 'IntentionStack' }).vm.$emit('resume');
    expect(wrapper.emitted('resume')).toHaveLength(1);
  });

  it('re-emits navigate with its payload when IntentionStack emits it', async () => {
    const wrapper = mount(ChatHeader);
    await wrapper.findComponent({ name: 'IntentionStack' }).vm.$emit('navigate', { id: 'n1#0', label: 'Search Items' });
    expect(wrapper.emitted('navigate')).toHaveLength(1);
    expect(wrapper.emitted('navigate')[0][0]).toEqual({ id: 'n1#0', label: 'Search Items' });
  });
});
