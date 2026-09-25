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
    ensureSession: vi.fn(),
    on: vi.fn((event, cb) => { handlers[event] = cb; }),
    onAgentMessage: vi.fn((cb) => { handlers.agent = cb; }),
    onAlertMessage: vi.fn((cb) => { handlers.alert = cb; }),
    onSapData: vi.fn((cb) => { handlers['sap-data'] = cb; }),
    onStatusMessage: vi.fn((cb) => { handlers.status = cb; }),
    onSystemMessage: vi.fn((cb) => { handlers.system = cb; }),
    onUserMessage: vi.fn((cb) => { handlers.user = cb; }),
    sendMessage: vi.fn(),
    sessionId: null,
    switchActiveNode: vi.fn(),
  };
  return { handlers, instance };
});

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/websocket/chat', () => ({
  default: vi.fn().mockImplementation(function MockChat() { return mockChat.instance; }),
}));
vi.mock('@/modules/api', () => ({
  default: {
    Bucket: {
      downloadUrl: vi.fn().mockResolvedValue({ url: '' }),
      files: vi.fn().mockResolvedValue([]),
      upload: vi.fn().mockResolvedValue({}),
    },
    Chat: {
      deleteSession: vi.fn().mockResolvedValue({}),
      messages: vi.fn().mockResolvedValue([]),
      recent: vi.fn().mockResolvedValue([]),
      sessions: vi.fn().mockResolvedValue([]),
    },
    Project: {
      default: vi.fn(),
      list: vi.fn(),
      select: vi.fn(),
    },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import ChatView from '@/views/chat.vue';
import ChatHistory from '@/components/chat/history.vue';
import ProjectSelector from '@/components/project/selector.vue';
import RecentChats from '@/components/chat/recent-chats.vue';

// Fixtures
const DEFAULT_PROJECT = { id: 1, is_default: true, name: 'Default' };
const WORK_PROJECT = { id: 2, is_default: false, name: 'Work' };

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({});
  mockAuth.isAdmin.mockReturnValue(false);
  AppAPI.Bucket.files.mockResolvedValue([]);
  AppAPI.Bucket.downloadUrl.mockResolvedValue({ url: '' });
  AppAPI.Chat.sessions.mockResolvedValue([]);
  AppAPI.Chat.messages.mockResolvedValue([]);
  AppAPI.Chat.deleteSession.mockResolvedValue({});
  AppAPI.Chat.recent.mockResolvedValue([]);
  AppAPI.Project.default.mockResolvedValue(DEFAULT_PROJECT);
  AppAPI.Project.list.mockResolvedValue({ count: 2, results: [DEFAULT_PROJECT, WORK_PROJECT] });
  AppAPI.Project.select.mockImplementation(async (id) => (id === WORK_PROJECT.id ? WORK_PROJECT : DEFAULT_PROJECT));
  mockChat.instance.projectId = null;
  localStorage.clear();
});

describe('ChatView projects', () => {
  // Opens a session from the sidebar list, the way a user would, so it is "the open chat".
  const openChat = async (wrapper, id) => {
    await mockChat.handlers.open?.();
    await flushPromises();
    await wrapper.findComponent(ChatHistory).vm.$emit('select', id);
    await flushPromises();
  };

  it("starts in the Default project: shows its name and connects with it as the new chat's project", async () => {
    const wrapper = mount(ChatView);
    await flushPromises();

    expect(AppAPI.Project.default).toHaveBeenCalled();
    expect(wrapper.find('.orb-sidebar-project').text()).toBe('Default');
    expect(mockChat.instance.projectId).toBe(1);
    expect(mockChat.instance.connect).toHaveBeenCalled();
  });

  it('does not connect until the Default project is known, so the first chat cannot land in the wrong project', async () => {
    let resolveDefault;
    AppAPI.Project.default.mockReturnValue(new Promise((resolve) => { resolveDefault = resolve; }));
    mount(ChatView);
    await flushPromises();
    expect(mockChat.instance.connect).not.toHaveBeenCalled();

    resolveDefault(DEFAULT_PROJECT);
    await flushPromises();
    expect(mockChat.instance.connect).toHaveBeenCalled();
  });

  it('drops a connect that was still waiting on the Default project when the view unmounts', async () => {
    let resolveDefault;
    AppAPI.Project.default.mockReturnValue(new Promise((resolve) => { resolveDefault = resolve; }));
    const wrapper = mount(ChatView);
    wrapper.unmount();

    resolveDefault(DEFAULT_PROJECT);
    await flushPromises();

    expect(mockChat.instance.connect).not.toHaveBeenCalled();
  });

  it('hides the project name until a project is known', async () => {
    AppAPI.Project.default.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(ChatView);
    await flushPromises();
    expect(wrapper.find('.orb-sidebar-project').exists()).toBe(false);
  });

  it("stacks Recent Chats, the project selector, then the project's history in the sidebar", async () => {
    const wrapper = mount(ChatView);
    await flushPromises();
    const html = wrapper.find('.orb-sidebar-top').html();

    const positions = ['orb-new-chat-btn', 'orb-recent-section', 'orb-project-selector', 'orb-history-section']
      .map((name) => html.indexOf(name));
    expect(positions.every((position) => position >= 0)).toBe(true);
    expect([...positions].sort((a, b) => a - b)).toEqual(positions);
  });

  it("scopes the sidebar's session list to the selected project", async () => {
    mount(ChatView);
    await flushPromises();
    await mockChat.handlers.open?.();
    await flushPromises();

    expect(AppAPI.Chat.sessions).toHaveBeenCalledWith(1);
  });

  it('refreshes Recent Chats together with the session list', async () => {
    mount(ChatView);
    await flushPromises();
    const before = AppAPI.Chat.recent.mock.calls.length;

    await mockChat.handlers.open?.();
    await flushPromises();

    expect(AppAPI.Chat.recent.mock.calls.length).toBeGreaterThan(before);
  });

  it('starts a new chat with the selected project as the one it lands in', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ChatView);
    await flushPromises();
    await wrapper.findComponent(ProjectSelector).vm.$emit('select', 2);
    await flushPromises();
    mockChat.instance.projectId = null;

    await wrapper.find('.orb-new-chat-btn').trigger('click');

    expect(mockChat.instance.projectId).toBe(2);
    await vi.advanceTimersByTimeAsync(300);
    vi.useRealTimers();
  });

  describe('switching project', () => {
    it("selects it, shows its name and lists that project's chats", async () => {
      AppAPI.Chat.sessions.mockImplementation(async (id) => (id === 2 ? [{ id: 9, title: 'Work chat' }] : []));
      const wrapper = mount(ChatView);
      await flushPromises();

      await wrapper.findComponent(ProjectSelector).vm.$emit('select', 2);
      await flushPromises();

      expect(AppAPI.Project.select).toHaveBeenCalledWith(2);
      expect(wrapper.find('.orb-sidebar-project').text()).toBe('Work');
      expect(wrapper.findComponent(ChatHistory).props('sessions')).toEqual([{ id: 9, title: 'Work chat' }]);
    });

    it('ignores re-selecting the current project', async () => {
      const wrapper = mount(ChatView);
      await flushPromises();

      await wrapper.findComponent(ProjectSelector).vm.$emit('select', 1);
      await flushPromises();

      expect(AppAPI.Project.select).not.toHaveBeenCalled();
    });

    it('stays where it was when the project cannot be selected', async () => {
      AppAPI.Project.select.mockResolvedValue({ errors: [{ detail: 'Not found.' }] });
      const wrapper = mount(ChatView);
      await flushPromises();
      AppAPI.Chat.sessions.mockClear();

      await wrapper.findComponent(ProjectSelector).vm.$emit('select', 2);
      await flushPromises();

      expect(wrapper.find('.orb-sidebar-project').text()).toBe('Default');
      expect(AppAPI.Chat.sessions).not.toHaveBeenCalled();
    });

    it("leaves the open chat for a fresh one in the new project when it isn't in that project's list", async () => {
      vi.useFakeTimers();
      AppAPI.Chat.sessions.mockImplementation(async (id) => (id === 1 ? [{ id: 5, title: 'Old chat' }] : []));
      const wrapper = mount(ChatView);
      await flushPromises();
      await openChat(wrapper, 5);
      mockChat.instance.disconnect.mockClear();
      mockChat.instance.connect.mockClear();

      await wrapper.findComponent(ProjectSelector).vm.$emit('select', 2);
      await flushPromises();

      expect(mockChat.instance.disconnect).toHaveBeenCalled();
      expect(mockChat.instance.sessionId).toBeNull();
      expect(mockChat.instance.projectId).toBe(2);
      await vi.advanceTimersByTimeAsync(300);
      expect(mockChat.instance.connect).toHaveBeenCalled();
      vi.useRealTimers();
    });

    it('reconnects with the new project even when no chat has been created yet', async () => {
      // A brand-new chat's session is created lazily against whatever project the socket
      // authenticated with — staying on the old socket would file it in the old project.
      vi.useFakeTimers();
      const wrapper = mount(ChatView);
      await flushPromises();
      mockChat.instance.disconnect.mockClear();

      await wrapper.findComponent(ProjectSelector).vm.$emit('select', 2);
      await flushPromises();

      expect(mockChat.instance.disconnect).toHaveBeenCalled();
      expect(mockChat.instance.projectId).toBe(2);
      await vi.advanceTimersByTimeAsync(300);
      vi.useRealTimers();
    });

    it("keeps the open chat, without reconnecting, when it also belongs to the new project's list", async () => {
      vi.useFakeTimers();
      AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, title: 'Old chat' }]);
      const wrapper = mount(ChatView);
      await flushPromises();
      await openChat(wrapper, 5);
      await vi.advanceTimersByTimeAsync(300);
      mockChat.instance.disconnect.mockClear();

      await wrapper.findComponent(ProjectSelector).vm.$emit('select', 2);
      await flushPromises();

      expect(mockChat.instance.disconnect).not.toHaveBeenCalled();
      vi.useRealTimers();
    });
  });

  describe('opening a recent chat', () => {
    it('switches to its project first when it lives in another one', async () => {
      vi.useFakeTimers();
      AppAPI.Chat.sessions.mockImplementation(async (id) => (id === 2 ? [{ id: 9, title: 'Work chat' }] : []));
      const wrapper = mount(ChatView);
      await flushPromises();

      await wrapper.findComponent(RecentChats).vm.$emit('select', { projectId: 2, sessionId: 9 });
      await flushPromises();

      expect(AppAPI.Project.select).toHaveBeenCalledWith(2);
      expect(wrapper.find('.orb-sidebar-project').text()).toBe('Work');
      expect(AppAPI.Chat.messages).toHaveBeenCalledWith(9);
      await vi.advanceTimersByTimeAsync(300);
      vi.useRealTimers();
    });

    it('opens it directly, without re-selecting, when it is in the current project', async () => {
      vi.useFakeTimers();
      const wrapper = mount(ChatView);
      await flushPromises();

      await wrapper.findComponent(RecentChats).vm.$emit('select', { projectId: 1, sessionId: 9 });
      await flushPromises();

      expect(AppAPI.Project.select).not.toHaveBeenCalled();
      expect(AppAPI.Chat.messages).toHaveBeenCalledWith(9);
      await vi.advanceTimersByTimeAsync(300);
      vi.useRealTimers();
    });

    it('does not open it when its project can no longer be selected', async () => {
      AppAPI.Project.select.mockResolvedValue({ errors: [{ detail: 'Not found.' }] });
      const wrapper = mount(ChatView);
      await flushPromises();

      await wrapper.findComponent(RecentChats).vm.$emit('select', { projectId: 2, sessionId: 9 });
      await flushPromises();

      expect(AppAPI.Chat.messages).not.toHaveBeenCalled();
    });
  });
});

describe('ChatView opening a chat from a link', () => {
  // The links in a project's chat list: /chat?project=<id>&session=<id>
  const mountAt = async (path) => {
    const router = buildRouter(path);
    await router.isReady();
    const wrapper = mount(ChatView, { global: { router } });
    await flushPromises();
    return { router, wrapper };
  };

  beforeEach(() => {
    AppAPI.Chat.sessions.mockImplementation(async (id) => (id === 2 ? [{ id: 9, title: 'Linked chat' }] : []));
  });

  it('selects the linked chat\'s project and resumes that chat, connecting once and not as a new chat first', async () => {
    vi.useFakeTimers();
    const { wrapper } = await mountAt('/chat?project=2&session=9');

    expect(AppAPI.Project.select).toHaveBeenCalledWith(2);
    expect(AppAPI.Chat.sessions).toHaveBeenCalledWith(2);
    expect(AppAPI.Chat.messages).toHaveBeenCalledWith(9);
    expect(wrapper.find('.orb-sidebar-project').text()).toBe('Work');
    expect(mockChat.instance.sessionId).toBe(9);
    expect(mockChat.instance.projectId).toBe(2);
    expect(mockChat.instance.connect).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(300);
    expect(mockChat.instance.connect).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('shows the linked chat\'s history and highlights it in the project\'s list', async () => {
    vi.useFakeTimers();
    AppAPI.Chat.messages.mockResolvedValue([
      { extra: null, text: 'hello there', timestamp: '2026-01-01T00:00:00Z', type: 'user' },
    ]);
    const { wrapper } = await mountAt('/chat?project=2&session=9');

    expect(wrapper.text()).toContain('hello there');
    expect(wrapper.findComponent(ChatHistory).props('activeSessionId')).toBe(9);
    await vi.advanceTimersByTimeAsync(300);
    vi.useRealTimers();
  });

  it('consumes the link, so a reload does not keep re-opening it', async () => {
    vi.useFakeTimers();
    const { router } = await mountAt('/chat?project=2&session=9');

    expect(router.currentRoute.value.path).toBe('/chat');
    expect(router.currentRoute.value.query).toEqual({});
    await vi.advanceTimersByTimeAsync(300);
    vi.useRealTimers();
  });

  it.each([
    ['letters in the project', '/chat?project=abc&session=9'],
    ['no session', '/chat?project=2'],
    ['no project', '/chat?session=9'],
    ['a zero project', '/chat?project=0&session=9'],
    ['a decimal session', '/chat?project=2&session=1.5'],
    ['a repeated key', '/chat?project=2&session=9&session=10'],
  ])('starts normally in the Default project when the link has %s', async (_label, path) => {
    await mountAt(path);

    expect(AppAPI.Project.select).not.toHaveBeenCalled();
    expect(AppAPI.Chat.messages).not.toHaveBeenCalled();
    expect(mockChat.instance.projectId).toBe(1);
    expect(mockChat.instance.connect).toHaveBeenCalledTimes(1);
  });

  it('starts a fresh chat in that project, connecting once, when the linked chat no longer exists', async () => {
    vi.useFakeTimers();
    AppAPI.Chat.messages.mockResolvedValue({ errors: [{ code: 'not_found', detail: 'Not found.' }] });
    const { wrapper } = await mountAt('/chat?project=2&session=9');

    expect(mockChat.instance.sessionId).toBeNull();
    expect(mockChat.instance.projectId).toBe(2);
    expect(wrapper.find('.orb-sidebar-project').text()).toBe('Work');

    await vi.advanceTimersByTimeAsync(300);
    expect(mockChat.instance.connect).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('starts normally in the Default project when the linked project can no longer be selected', async () => {
    AppAPI.Project.select.mockResolvedValue({ errors: [{ code: 'not_found', detail: 'Not found.' }] });
    const { wrapper } = await mountAt('/chat?project=2&session=9');

    expect(AppAPI.Chat.messages).not.toHaveBeenCalled();
    expect(wrapper.find('.orb-sidebar-project').text()).toBe('Default');
    expect(mockChat.instance.projectId).toBe(1);
    expect(mockChat.instance.connect).toHaveBeenCalledTimes(1);
  });

  it.each([
    ['selected', WORK_PROJECT],
    ['not selectable any more', { errors: [{ code: 'not_found', detail: 'Not found.' }] }],
  ])('drops the whole thing, connecting nothing, when the view is left while the project is being selected and it ends up %s', async (_label, selection) => {
    vi.useFakeTimers();
    let resolveSelect;
    AppAPI.Project.select.mockReturnValue(new Promise((resolve) => { resolveSelect = resolve; }));
    const router = buildRouter('/chat?project=2&session=9');
    await router.isReady();
    const wrapper = mount(ChatView, { global: { router } });
    await flushPromises();

    wrapper.unmount();
    resolveSelect(selection);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(500);

    expect(AppAPI.Chat.messages).not.toHaveBeenCalled();
    expect(mockChat.instance.connect).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});

describe('ChatView reconnecting', () => {
  it('opens a single socket when two chats are picked in quick succession', async () => {
    vi.useFakeTimers();
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, title: 'A' }, { id: 6, title: 'B' }]);
    const wrapper = mount(ChatView);
    await flushPromises();
    await mockChat.handlers.open?.();
    await flushPromises();
    mockChat.instance.connect.mockClear();

    await wrapper.findComponent(ChatHistory).vm.$emit('select', 5);
    await wrapper.findComponent(ChatHistory).vm.$emit('select', 6);
    await flushPromises();
    await vi.advanceTimersByTimeAsync(300);

    expect(mockChat.instance.sessionId).toBe(6);
    expect(mockChat.instance.connect).toHaveBeenCalledTimes(1);
    vi.useRealTimers();
  });

  it('does not connect after the view has been left', async () => {
    vi.useFakeTimers();
    AppAPI.Chat.sessions.mockResolvedValue([{ id: 5, title: 'A' }]);
    const wrapper = mount(ChatView);
    await flushPromises();
    await mockChat.handlers.open?.();
    await flushPromises();
    mockChat.instance.connect.mockClear();

    await wrapper.findComponent(ChatHistory).vm.$emit('select', 5);
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(500);

    expect(mockChat.instance.connect).not.toHaveBeenCalled();
    vi.useRealTimers();
  });
});
