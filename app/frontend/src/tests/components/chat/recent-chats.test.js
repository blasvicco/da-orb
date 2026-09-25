// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Chat: { recent: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { flushPromises, mount } from '@/tests/helpers/mount';
import RecentChats from '@/components/chat/recent-chats.vue';

// Fixtures
const makeSession = (overrides = {}) => ({
  id: 1,
  project: 10,
  project_name: 'Default',
  title: 'A chat',
  tokens_used: 1500,
  ...overrides,
});

describe('RecentChats', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    AppAPI.Chat.recent.mockResolvedValue([]);
  });

  it('fetches the recent chats on mount and renders one "{project} - {tokens}" row each', async () => {
    AppAPI.Chat.recent.mockResolvedValue([
      makeSession(),
      makeSession({ id: 2, project: 11, project_name: 'Work', tokens_used: 42 }),
    ]);
    const wrapper = mount(RecentChats);
    await flushPromises();

    expect(AppAPI.Chat.recent).toHaveBeenCalledTimes(1);
    expect(wrapper.findAll('.orb-recent-item').map((row) => row.text())).toEqual([
      'Default - 1.5k tokens',
      'Work - 42 tokens',
    ]);
  });

  it.each([
    ['null', null],
    ['missing', undefined],
    ['zero', 0],
  ])('shows 0 tokens when tokens_used is %s', async (_label, tokens) => {
    AppAPI.Chat.recent.mockResolvedValue([makeSession({ tokens_used: tokens })]);
    const wrapper = mount(RecentChats);
    await flushPromises();

    expect(wrapper.find('.orb-recent-item').text()).toBe('Default - 0 tokens');
  });

  it('shows the empty state when there are no recent chats', async () => {
    const wrapper = mount(RecentChats);
    await flushPromises();

    expect(wrapper.find('.orb-recent-empty').exists()).toBe(true);
    expect(wrapper.find('.orb-recent-item').exists()).toBe(false);
  });

  it('hides the empty state once there are chats', async () => {
    AppAPI.Chat.recent.mockResolvedValue([makeSession()]);
    const wrapper = mount(RecentChats);
    await flushPromises();

    expect(wrapper.find('.orb-recent-empty').exists()).toBe(false);
  });

  it.each([
    ['its own title', 'A chat', 'A chat'],
    ['the untitled label when it has none', '', 'Untitled chat'],
  ])('tooltips a row with %s', async (_label, title, expected) => {
    AppAPI.Chat.recent.mockResolvedValue([makeSession({ title })]);
    const wrapper = mount(RecentChats);
    await flushPromises();

    expect(wrapper.find('.orb-recent-item').attributes('title')).toBe(expected);
  });

  it("emits select with the chat's project and session ids when a row is clicked", async () => {
    AppAPI.Chat.recent.mockResolvedValue([makeSession({ id: 7, project: 3 })]);
    const wrapper = mount(RecentChats);
    await flushPromises();

    await wrapper.find('.orb-recent-item').trigger('click');

    expect(wrapper.emitted('select')[0]).toEqual([{ projectId: 3, sessionId: 7 }]);
  });

  it('highlights only the active chat', async () => {
    AppAPI.Chat.recent.mockResolvedValue([makeSession({ id: 1 }), makeSession({ id: 2 })]);
    const wrapper = mount(RecentChats, { props: { activeSessionId: 2 } });
    await flushPromises();

    const [first, second] = wrapper.findAll('.orb-recent-item');
    expect(first.classes()).not.toContain('orb-recent-item--active');
    expect(second.classes()).toContain('orb-recent-item--active');
  });

  it('re-fetches, replacing the list, when the parent calls refresh()', async () => {
    AppAPI.Chat.recent.mockResolvedValueOnce([makeSession({ id: 1 })]);
    const wrapper = mount(RecentChats);
    await flushPromises();
    AppAPI.Chat.recent.mockResolvedValueOnce([makeSession({ id: 2, project_name: 'Work' })]);

    await wrapper.vm.refresh();
    await flushPromises();

    expect(wrapper.findAll('.orb-recent-item').map((row) => row.text())).toEqual(['Work - 1.5k tokens']);
  });

  it('keeps the previous list when the API reports errors', async () => {
    AppAPI.Chat.recent.mockResolvedValueOnce([makeSession()]);
    const wrapper = mount(RecentChats);
    await flushPromises();
    AppAPI.Chat.recent.mockResolvedValueOnce({ errors: [{ detail: 'boom' }] });

    await wrapper.vm.refresh();
    await flushPromises();

    expect(wrapper.findAll('.orb-recent-item')).toHaveLength(1);
  });
});
