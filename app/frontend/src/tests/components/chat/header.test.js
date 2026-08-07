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
  it('forwards messages/sessionId/sessionTitle/userName to Export and status to Badge', () => {
    const messages = [{ text: 'hi', type: 'user' }];
    const wrapper = mount(ChatHeader, {
      props: {
        connectionStatus: 'connected',
        messages,
        sessionId: 208,
        sessionTitle: 'My chat',
        userName: 'Bob',
      },
    });

    const exportComponent = wrapper.findComponent({ name: 'Export' });
    expect(exportComponent.props('messages')).toEqual(messages);
    expect(exportComponent.props('sessionId')).toBe(208);
    expect(exportComponent.props('sessionTitle')).toBe('My chat');
    expect(exportComponent.props('userName')).toBe('Bob');
    expect(wrapper.findComponent({ name: 'Badge' }).props('status')).toBe('connected');
  });
});
