// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getSession: vi.fn().mockReturnValue({ database: 'PROD', user: { username: 'admin.bob' } }),
  signout: vi.fn(),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/api', () => ({
  default: { Usage: { summary: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import AdminTabs from '@/components/admin/tabs.vue';
import RankedList from '@/components/admin/ranked-list.vue';
import UserDetail from '@/components/user/detail.vue';
import Usage from '@/views/admin/usage.vue';

const rankedList = (wrapper, index) => wrapper.findAllComponents(RankedList)[index];

const SUMMARY = {
  plan: { seats: { total: 5, used: 2 } },
  processes: {
    by_process: [{ count: 3, process_name: 'goods_receipt' }],
    total: 10,
  },
  session_time: [
    { seconds: 0, username: 'zero' },
    { seconds: 45, username: 'short' },
    { seconds: 4000, username: 'long' },
  ],
  tokens: {
    by_process: [
      { process_name: 'goods_receipt', total_tokens: 500 },
      { process_name: null, total_tokens: 0 },
    ],
    total: 12345,
  },
  top_users: {
    by_messages: [{ count: 9, username: 'alice' }],
    by_processes: [{ count: 4, username: 'bob' }],
    by_tokens: [
      { total_tokens: 800, username: 'carol' },
      { total_tokens: 0, username: 'dave' },
    ],
  },
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({ database: 'PROD', user: { username: 'admin.bob' } });
  AppAPI.Usage.summary.mockResolvedValue(SUMMARY);
  localStorage.clear();
});

describe('Usage mount', () => {
  it('shows a loading state, then the dashboard once summary resolves', async () => {
    const wrapper = mount(Usage);
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(true);

    await flushPromises();

    expect(wrapper.find('.orb-admin-loading').exists()).toBe(false);
    expect(wrapper.find('.orb-usage-stats').exists()).toBe(true);
  });

  it('marks the usage tab active', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    expect(wrapper.findComponent(AdminTabs).props('active')).toBe('usage');
  });

  it('does not render the dashboard body when the summary call errors', async () => {
    AppAPI.Usage.summary.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(Usage);
    await flushPromises();
    expect(wrapper.find('.orb-usage-stats').exists()).toBe(false);
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(false);
  });

  it('navigates back to chat from the sidebar button', async () => {
    const router = buildRouter('/admin/usage');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(Usage, { global: { router } });
    await flushPromises();

    await wrapper.find('.orb-new-chat-btn').trigger('click');

    expect(pushSpy).toHaveBeenCalledWith('/chat');
  });
});

describe('Usage theme and logout', () => {
  it('persists a theme change', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', true);
    expect(localStorage.getItem('orb-theme')).toBe('dark');

    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', false);
    expect(localStorage.getItem('orb-theme')).toBe('light');
  });

  it('signs out and navigates home on logout', async () => {
    const router = buildRouter('/admin/usage');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(Usage, { global: { router } });
    await flushPromises();

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');

    expect(mockAuth.signout).toHaveBeenCalled();
    expect(pushSpy).toHaveBeenCalledWith('/');
  });
});

describe('Usage user profile fallbacks', () => {
  it('falls back to empty connection/name and a standard role, with "?" initials, when there is no session', async () => {
    mockAuth.getSession.mockReturnValue(null);
    const wrapper = mount(Usage);
    await flushPromises();

    expect(wrapper.findComponent(UserDetail).props('connection')).toBe('');
    expect(wrapper.findComponent(UserDetail).props('name')).toBe('');
    expect(wrapper.findComponent(UserDetail).props('role')).toBe('standard');
    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('?');
  });

  it('derives two-letter initials from a two-part name', async () => {
    mockAuth.getSession.mockReturnValue({ user: { username: 'Bob Smith' } });
    const wrapper = mount(Usage);
    await flushPromises();

    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('BS');
  });
});

describe('Usage summary tiles', () => {
  it('formats total tokens and total processes', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    const values = wrapper.findAll('.orb-usage-stat-value');
    expect(values[0].text()).toBe((12345).toLocaleString());
    expect(values[1].text()).toBe('10');
  });

  it('defaults to zero when the summary has no tokens/processes data', async () => {
    AppAPI.Usage.summary.mockResolvedValue({});
    const wrapper = mount(Usage);
    await flushPromises();
    const values = wrapper.findAll('.orb-usage-stat-value');
    expect(values[0].text()).toBe('0');
    expect(values[1].text()).toBe('0');
  });
});

describe('Usage ranked lists', () => {
  it('passes the top-messages users through untouched', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 0).props('items')).toEqual([{ displayValue: '9', label: 'alice', value: 9 }]);
  });

  it('filters out zero-token users from the top-tokens list', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 1).props('items')).toEqual([{ displayValue: '800', label: 'carol', value: 800 }]);
  });

  it('passes the top-processes users through untouched', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 2).props('items')).toEqual([{ displayValue: '4', label: 'bob', value: 4 }]);
  });

  it('filters zero-token processes and falls back to an unknown-process label', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 3).props('items')).toEqual([
      { displayValue: '500', label: 'goods_receipt', value: 500 },
    ]);
  });

  it('falls back to an unknown-process label for a nameless (but non-zero) token entry', async () => {
    AppAPI.Usage.summary.mockResolvedValue({
      ...SUMMARY,
      tokens: { by_process: [{ process_name: null, total_tokens: 50 }], total: 50 },
    });
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 3).props('items')).toEqual([
      { displayValue: '50', label: 'Unknown process', value: 50 },
    ]);
  });

  it('labels processes-by-type with the process name or an unknown-process fallback', async () => {
    AppAPI.Usage.summary.mockResolvedValue({
      ...SUMMARY,
      processes: { by_process: [{ count: 2, process_name: null }], total: 2 },
    });
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 4).props('items')).toEqual([
      { displayValue: '2', label: 'Unknown process', value: 2 },
    ]);
  });

  it('filters zero-second sessions and formats duration under a minute, minutes-only, and hours+minutes', async () => {
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 5).props('items')).toEqual([
      { displayValue: '1m', label: 'short', value: 45 },
      { displayValue: '1h 7m', label: 'long', value: 4000 },
    ]);
  });

  it('formats a sub-minute duration as "<1m"', async () => {
    AppAPI.Usage.summary.mockResolvedValue({ ...SUMMARY, session_time: [{ seconds: 10, username: 'tiny' }] });
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 5).props('items')).toEqual([
      { displayValue: '<1m', label: 'tiny', value: 10 },
    ]);
  });

  it('shows an empty-label state when a summary section has no rows', async () => {
    AppAPI.Usage.summary.mockResolvedValue({ ...SUMMARY, top_users: {} });
    const wrapper = mount(Usage);
    await flushPromises();
    expect(rankedList(wrapper, 0).props('items')).toEqual([]);
  });
});
