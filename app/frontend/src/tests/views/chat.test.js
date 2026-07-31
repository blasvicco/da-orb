// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getSession: vi.fn().mockReturnValue({}),
  isAdmin: vi.fn().mockReturnValue(false),
  signout: vi.fn(),
}));

const mockChat = vi.hoisted(() => {
  const handlers = {};
  const instance = {
    connect: vi.fn(),
    disconnect: vi.fn(),
    on: vi.fn((event, cb) => { handlers[event] = cb; }),
    onAgentMessage: vi.fn((cb) => { handlers.agent = cb; }),
    onAlertMessage: vi.fn((cb) => { handlers.alert = cb; }),
    onSapData: vi.fn((cb) => { handlers['sap-data'] = cb; }),
    onStatusMessage: vi.fn((cb) => { handlers.status = cb; }),
    onSystemMessage: vi.fn((cb) => { handlers.system = cb; }),
    onUserMessage: vi.fn((cb) => { handlers.user = cb; }),
    sendMessage: vi.fn(),
    sessionId: null,
  };
  return { handlers, instance };
});

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/websocket/chat', () => ({
  default: vi.fn().mockImplementation(function MockChat() { return mockChat.instance; }),
}));
vi.mock('@/modules/api', () => ({
  default: {
    Chat: {
      deleteSession: vi.fn().mockResolvedValue({}),
      messages: vi.fn().mockResolvedValue([]),
      sessions: vi.fn().mockResolvedValue([]),
    },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import ChatView from '@/views/chat.vue';
import ChatBubble from '@/components/chat/bubble.vue';
import ChatHeader from '@/components/chat/header.vue';
import ChatHistory from '@/components/chat/history.vue';
import ChatInput from '@/components/chat/input.vue';
import ChatWelcome from '@/components/chat/welcome.vue';
import Settings from '@/components/chat/settings.vue';
import UserDetail from '@/components/user/detail.vue';

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({});
  mockAuth.isAdmin.mockReturnValue(false);
  AppAPI.Chat.sessions.mockResolvedValue([]);
  AppAPI.Chat.messages.mockResolvedValue([]);
  AppAPI.Chat.deleteSession.mockResolvedValue({});
  localStorage.clear();
});

describe('ChatView mount', () => {
  it('connects the chat socket on mount and disconnects on unmount', () => {
    const wrapper = mount(ChatView);
    expect(mockChat.instance.connect).toHaveBeenCalled();

    wrapper.unmount();
    expect(mockChat.instance.disconnect).toHaveBeenCalled();
  });

  it('does not crash if a message handler fires just after unmount, once the container ref is gone', async () => {
    mount(ChatView).unmount();

    // The mock doesn't actually sever the handler on disconnect(), unlike the
    // real socket — this simulates a message racing in right after teardown.
    expect(() => mockChat.handlers.user?.({ text: 'late', time: '2026-01-01T00:00:00Z' })).not.toThrow();
    await flushPromises();
  });

  it('shows the welcome screen when there are no messages yet', () => {
    const wrapper = mount(ChatView);
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(true);
  });

  it('reads the theme and expertise level from localStorage, defaulting when unset', () => {
    const wrapper = mount(ChatView);
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('light');
    expect(wrapper.findComponent(Settings).props('expertiseLevel')).toBe(2);
  });

  it('restores a persisted theme and expertise level', () => {
    localStorage.setItem('orb-theme', 'dark');
    localStorage.setItem('orb-expertise-level', '3');
    const wrapper = mount(ChatView);
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('dark');
    expect(wrapper.findComponent(Settings).props('expertiseLevel')).toBe(3);
  });
});

describe('ChatView user profile', () => {
  it('derives initials from a two-part name', () => {
    mockAuth.getSession.mockReturnValue({ database: 'PROD', user: { username: 'Bob Smith' } });
    const wrapper = mount(ChatView);
    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('BS');
    // chat.vue doesn't wire connection into UserDetail — that goes to ChatHeader instead.
    expect(wrapper.findComponent(ChatHeader).props('connection')).toBe('PROD');
  });

  it('derives initials from a single-word name', () => {
    mockAuth.getSession.mockReturnValue({ user: { username: 'Robert' } });
    const wrapper = mount(ChatView);
    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('RO');
  });

  it('falls back to "?" initials and standard role when there is no session', () => {
    mockAuth.getSession.mockReturnValue(null);
    const wrapper = mount(ChatView);
    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('?');
    expect(wrapper.findComponent(UserDetail).props('role')).toBe('standard');
  });

  it('passes the isAdmin flag through from auth', () => {
    mockAuth.isAdmin.mockReturnValue(true);
    const wrapper = mount(ChatView);
    expect(wrapper.findComponent(UserDetail).props('isAdmin')).toBe(true);
  });
});

describe('ChatView theme and expertise controls', () => {
  it('persists a theme change from the settings popover', async () => {
    const wrapper = mount(ChatView);
    await wrapper.findComponent(Settings).vm.$emit('theme-change', true);
    expect(localStorage.getItem('orb-theme')).toBe('dark');
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('dark');

    await wrapper.findComponent(Settings).vm.$emit('theme-change', false);
    expect(localStorage.getItem('orb-theme')).toBe('light');
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('light');
  });

  it('persists an expertise-level change from the settings popover', async () => {
    const wrapper = mount(ChatView);
    await wrapper.findComponent(Settings).vm.$emit('expertise-change', 1);
    expect(localStorage.getItem('orb-expertise-level')).toBe('1');
  });
});

describe('ChatView logout', () => {
  it('disconnects the socket, signs out, and navigates home on logout confirm', async () => {
    const router = buildRouter('/chat');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(ChatView, { global: { router } });

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');

    expect(mockChat.instance.disconnect).toHaveBeenCalled();
    expect(mockAuth.signout).toHaveBeenCalled();
    expect(pushSpy).toHaveBeenCalledWith('/');
  });
});

describe('ChatView sidebar actions', () => {
  it('starts a new chat: disconnects, clears state, and reconnects after a delay', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ChatView);
    mockChat.instance.disconnect.mockClear();
    mockChat.instance.connect.mockClear();

    await wrapper.find('.orb-new-chat-btn').trigger('click');
    expect(mockChat.instance.disconnect).toHaveBeenCalled();
    expect(mockChat.instance.sessionId).toBeNull();

    await vi.advanceTimersByTimeAsync(300);
    expect(mockChat.instance.connect).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it('loads a past session: fetches its messages and reconnects the socket', async () => {
    vi.useFakeTimers();
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, pending: false, title: 'Old chat' }]);
    AppAPI.Chat.messages.mockResolvedValue([
      { extra: null, text: 'hi', timestamp: '2026-01-01T00:00:00Z', type: 'user' },
    ]);
    const wrapper = mount(ChatView);
    await mockChat.handlers.open?.();
    await flushPromises();
    mockChat.instance.disconnect.mockClear();

    await wrapper.findComponent(ChatHistory).vm.$emit('select', 5);
    await flushPromises();

    expect(AppAPI.Chat.messages).toHaveBeenCalledWith(5);
    expect(mockChat.instance.disconnect).toHaveBeenCalled();
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);

    await vi.advanceTimersByTimeAsync(300);
    vi.useRealTimers();
  });

  it('translates a loaded message whose text is a known i18n key, defaulting a missing timestamp to now', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, pending: false, title: 'Old chat' }]);
    AppAPI.Chat.messages.mockResolvedValue([
      { extra: null, text: 'chat.system.agentError', timestamp: undefined, type: 'agent' },
    ]);
    const wrapper = mount(ChatView);
    await flushPromises();

    await wrapper.findComponent(ChatHistory).vm.$emit('select', 5);
    await flushPromises();

    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
  });

  it('leaves the sidebar sessions untouched when the sessions API errors', async () => {
    AppAPI.Chat.sessions.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(ChatView);
    await flushPromises();
    await mockChat.handlers.open?.();
    await flushPromises();

    expect(wrapper.findComponent(ChatHistory).props('sessions')).toEqual([]);
  });

  it('does not populate messages when the session messages API errors', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, pending: false, title: 'Old chat' }]);
    AppAPI.Chat.messages.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(ChatView);
    await flushPromises();

    await wrapper.findComponent(ChatHistory).vm.$emit('select', 5);
    await flushPromises();

    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(true);
  });

  it('forwards a process selection from a chat bubble into the prompt', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.agent?.({
      processes: [{ name: 'approve_po' }],
      state: null,
      text: 'pick one',
      time: '2026-01-01T00:00:00Z',
    });
    await wrapper.vm.$nextTick();

    await wrapper.findComponent(ChatBubble).vm.$emit('process-select', 'approve_po');

    expect(wrapper.findComponent(ChatInput).props('modelValue')).toBe('approve_po');
  });

  it('deletes a session and removes it from the sidebar', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, title: 'Old chat' }]);
    const wrapper = mount(ChatView);
    await mockChat.handlers.open?.();
    await flushPromises();

    await wrapper.findComponent(ChatHistory).vm.$emit('delete', 5);
    await flushPromises();

    expect(AppAPI.Chat.deleteSession).toHaveBeenCalledWith(5);
    expect(wrapper.findComponent(ChatHistory).props('sessions')).toEqual([]);
  });

  it('starts a new chat when the currently active session is deleted', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, title: 'Old chat' }]);
    AppAPI.Chat.messages.mockResolvedValue([]);
    const wrapper = mount(ChatView);
    await flushPromises();
    await wrapper.findComponent(ChatHistory).vm.$emit('select', 5);
    await flushPromises();
    mockChat.instance.disconnect.mockClear();

    await wrapper.findComponent(ChatHistory).vm.$emit('delete', 5);
    await flushPromises();

    expect(mockChat.instance.disconnect).toHaveBeenCalled();
    expect(mockChat.instance.sessionId).toBeNull();
  });
});

describe('ChatView sending a prompt', () => {
  it('does nothing when the prompt is blank', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.open?.();
    await flushPromises();
    await wrapper.findComponent(ChatInput).vm.$emit('send');
    expect(mockChat.instance.sendMessage).not.toHaveBeenCalled();
  });

  it('does nothing while disconnected, even with prompt text', async () => {
    const wrapper = mount(ChatView);
    await wrapper.findComponent(ChatInput).vm.$emit('update:modelValue', 'hello');
    await wrapper.findComponent(ChatInput).vm.$emit('send');
    expect(mockChat.instance.sendMessage).not.toHaveBeenCalled();
  });

  it('sends the trimmed prompt once connected, then clears it', async () => {
    const wrapper = mount(ChatView);
    await mockChat.handlers.open?.();
    await flushPromises();

    await wrapper.findComponent(ChatInput).vm.$emit('update:modelValue', '  hello  ');
    await wrapper.findComponent(ChatInput).vm.$emit('send');

    expect(mockChat.instance.sendMessage).toHaveBeenCalledWith('hello', 2);
    expect(wrapper.findComponent(ChatInput).props('modelValue')).toBe('');
  });

  it('uses a suggestion from the welcome screen as the prompt', async () => {
    const wrapper = mount(ChatView);
    await wrapper.findComponent(ChatWelcome).vm.$emit('suggestion', 'chat.suggestions.stock');
    expect(wrapper.findComponent(ChatInput).props('modelValue').length).toBeGreaterThan(0);
  });
});

describe('ChatView websocket event handling', () => {
  it('adopts a resumed session id from the auth event', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.auth?.({ session_id: 42 });
    await wrapper.vm.$nextTick();
    expect(wrapper.findComponent(ChatHistory).props('activeSessionId')).toBe(42);
  });

  it('ignores an auth event without a session_id', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.auth?.({});
    await wrapper.vm.$nextTick();
    expect(wrapper.findComponent(ChatHistory).props('activeSessionId')).toBeNull();
  });

  it('adopts a newly created session id and refreshes the sidebar', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 9, title: 'New chat' }]);
    const wrapper = mount(ChatView);
    await mockChat.handlers['session.created']?.({ session_id: 9 });
    await flushPromises();

    expect(wrapper.findComponent(ChatHistory).props('activeSessionId')).toBe(9);
    expect(wrapper.findComponent(ChatHistory).props('sessions')).toEqual([{ id: 9, title: 'New chat' }]);
  });

  it('marks the connection open and refreshes sessions on open', async () => {
    const wrapper = mount(ChatView);
    await mockChat.handlers.open?.();
    await flushPromises();
    expect(wrapper.findComponent(ChatHeader).props('connectionStatus')).toBe('connected');
  });

  it.each([
    ['close', 'close'],
    ['error', 'error'],
  ])('marks the connection disconnected on %s', async (_label, event) => {
    const wrapper = mount(ChatView);
    await mockChat.handlers.open?.();
    await flushPromises();
    mockChat.handlers[event]?.();
    await wrapper.vm.$nextTick();
    expect(wrapper.findComponent(ChatHeader).props('connectionStatus')).toBe('disconnected');
  });

  it('appends an echoed user message and marks the session pending', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 1, title: 'x' }]);
    const wrapper = mount(ChatView);
    // 'open' populates the sidebar sessions list; 'auth' only adopts the resumed id.
    await mockChat.handlers.open?.();
    mockChat.handlers.auth?.({ session_id: 1 });
    await flushPromises();

    mockChat.handlers.user?.({ text: 'hi there', time: '2026-01-01T00:00:00Z' });
    await wrapper.vm.$nextTick();

    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
    expect(wrapper.findComponent(ChatHistory).props('sessions')[0].pending).toBe(true);
  });

  it('appends an agent reply, clears typing, and refreshes the sidebar', async () => {
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 1, title: 'x' }]);
    const wrapper = mount(ChatView);
    mockChat.handlers.auth?.({ session_id: 1 });
    await flushPromises();
    AppAPI.Chat.sessions.mockClear();

    mockChat.handlers.agent?.({ processes: null, state: null, text: 'answer', time: '2026-01-01T00:00:00Z' });
    await flushPromises();

    expect(wrapper.find('.orb-chat-typing').exists()).toBe(false);
    expect(AppAPI.Chat.sessions).toHaveBeenCalled();
  });

  it('appends a sap-data card message', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers['sap-data']?.({ data: { a: 'b' }, time: '2026-01-01T00:00:00Z', titleKey: 'x.title' });
    await wrapper.vm.$nextTick();
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
  });

  it('appends a system message with literal text', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.system?.({ text: 'a system notice', time: '2026-01-01T00:00:00Z' });
    await wrapper.vm.$nextTick();
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
  });

  it('appends a system message translated from a known i18n key', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.system?.({ text: 'chat.system.agentError', time: '2026-01-01T00:00:00Z' });
    await wrapper.vm.$nextTick();
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
  });

  it('appends an alert message with literal text and refreshes the sidebar', async () => {
    const wrapper = mount(ChatView);
    AppAPI.Chat.sessions.mockClear();
    mockChat.handlers.alert?.({ processes: null, state: null, text: 'careful', time: '2026-01-01T00:00:00Z' });
    await flushPromises();
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
    expect(AppAPI.Chat.sessions).toHaveBeenCalled();
  });

  it('appends an alert message translated from a known i18n key', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.alert?.({ processes: null, state: null, text: 'chat.system.agentError', time: '2026-01-01T00:00:00Z' });
    await flushPromises();
    expect(wrapper.findComponent(ChatWelcome).exists()).toBe(false);
  });

  it('shows a translated status text and the typing indicator on a status event', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.status?.({ text: 'chat.system.queued' });
    await wrapper.vm.$nextTick();
    expect(wrapper.find('.orb-chat-typing').exists()).toBe(true);
    expect(wrapper.find('.orb-typing-status').text()).not.toBe('chat.system.queued');
  });

  it('shows a literal status text when it is not a known translation key', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.status?.({ text: 'Processing step 2 of 5' });
    await wrapper.vm.$nextTick();
    expect(wrapper.find('.orb-typing-status').text()).toBe('Processing step 2 of 5');
  });

  it('shows no status label when the status event carries no text', async () => {
    const wrapper = mount(ChatView);
    mockChat.handlers.status?.({});
    await wrapper.vm.$nextTick();
    expect(wrapper.find('.orb-typing-status').exists()).toBe(false);
  });
});
