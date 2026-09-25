// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getSession: vi.fn().mockReturnValue({}),
  isAdmin: vi.fn().mockReturnValue(false),
  signout: vi.fn(),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/api', () => ({
  default: {
    Project: {
      delete: vi.fn(),
      empty: vi.fn(),
      list: vi.fn(),
      save: vi.fn(),
    },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import List from '@/components/table/list.vue';
import UserDetail from '@/components/user/detail.vue';
import Projects from '@/views/projects.vue';

// Fixtures
const DEFAULT_PROJECT = { chat_sessions_count: 0, id: 1, is_default: true, name: 'Default', summary: '' };
const WORK_PROJECT = { chat_sessions_count: 3, id: 2, is_default: false, name: 'Work', summary: 'Client work' };

const list = (wrapper) => wrapper.findComponent(List);

const mountView = async (options = {}) => {
  const wrapper = mount(Projects, options);
  await flushPromises();
  return wrapper;
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({ database: 'PROD', user: { username: 'bob' } });
  mockAuth.isAdmin.mockReturnValue(false);
  AppAPI.Project.list.mockResolvedValue({ count: 2, results: [DEFAULT_PROJECT, WORK_PROJECT] });
  AppAPI.Project.save.mockResolvedValue({});
  AppAPI.Project.delete.mockResolvedValue({ errors: false });
  AppAPI.Project.empty.mockResolvedValue({ ...WORK_PROJECT, chat_sessions_count: 0 });
  localStorage.clear();
});

describe('Projects mount', () => {
  it("loads the table straight from the projects API with the table's own paging options", async () => {
    const wrapper = await mountView();

    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: {}, limit: 20, offset: 0, sorter: {} });
    expect(list(wrapper).props('loader')).toBeInstanceOf(Function);
    expect(await list(wrapper).props('loader')({ limit: 5, offset: 10 })).toEqual({
      count: 2,
      results: [DEFAULT_PROJECT, WORK_PROJECT],
    });
    expect(AppAPI.Project.list).toHaveBeenLastCalledWith({ limit: 5, offset: 10 });
  });

  it('is open to standard users: no admin tabs, and the sidebar carries the real admin flag', async () => {
    const wrapper = await mountView();

    expect(wrapper.findComponent({ name: 'AdminTabs' }).exists()).toBe(false);
    expect(wrapper.findComponent(UserDetail).props('isAdmin')).toBe(false);

    mockAuth.isAdmin.mockReturnValue(true);
    expect((await mountView()).findComponent(UserDetail).props('isAdmin')).toBe(true);
  });

  it('navigates back to chat from the sidebar button', async () => {
    const router = buildRouter('/projects');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = await mountView({ global: { router } });

    await wrapper.find('.orb-new-chat-btn').trigger('click');

    expect(pushSpy).toHaveBeenCalledWith('/chat');
  });

  it('falls back to empty connection/name, a standard role and "?" initials without a session', async () => {
    mockAuth.getSession.mockReturnValue(null);
    const wrapper = await mountView();

    expect(wrapper.findComponent(UserDetail).props()).toMatchObject({
      connection: '',
      initials: '?',
      name: '',
      role: 'standard',
    });
  });

  it('derives two-letter initials from a two-part name', async () => {
    mockAuth.getSession.mockReturnValue({ user: { username: 'Bob Smith' } });
    const wrapper = await mountView();

    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('BS');
  });
});

describe('Projects theme and logout', () => {
  it.each([
    ['dark', true],
    ['light', false],
  ])('persists a switch to the %s theme', async (theme, isDark) => {
    const wrapper = await mountView();

    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', isDark);

    expect(localStorage.getItem('orb-theme')).toBe(theme);
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe(theme);
  });

  it('signs out and navigates home on logout', async () => {
    const router = buildRouter('/projects');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = await mountView({ global: { router } });

    await wrapper.findComponent(UserDetail).vm.$emit('logout');

    expect(mockAuth.signout).toHaveBeenCalled();
    expect(pushSpy).toHaveBeenCalledWith('/');
  });
});

describe('Projects columns', () => {
  it('lists name, summary, chat count and the three dates, all sortable, in display order', async () => {
    const columns = list(await mountView()).props('columns');

    expect(columns.map((column) => column.key)).toEqual([
      'name',
      'summary',
      'chat_sessions_count',
      'created_on',
      'updated_on',
      'accessed_on',
    ]);
    expect(columns.every((column) => column.sorter === true)).toBe(true);
  });

  it.each([
    ['name', true, undefined],
    ['summary', true, undefined],
    ['chat_sessions_count', undefined, undefined],
    ['created_on', true, 'datetime'],
    ['updated_on', true, 'datetime'],
    ['accessed_on', true, 'datetime'],
  ])('%s: filterable=%s, type=%s', async (key, filterable, type) => {
    const column = list(await mountView()).props('columns').find((entry) => entry.key === key);

    expect(column.filterDropdown).toBe(filterable);
    expect(column.type).toBe(type);
  });

  it('renders dates with the locale date format', async () => {
    const column = list(await mountView()).props('columns').find((entry) => entry.key === 'created_on');

    expect(column.render('2026-03-10T12:00:00Z')).toBe(new Date('2026-03-10T12:00:00Z').toLocaleDateString());
  });

  it('renders each name as a link to that project\'s chats, and tags only the Default project with a badge', async () => {
    const wrapper = await mountView();
    const column = list(wrapper).props('columns').find((entry) => entry.key === 'name');

    const work = mount({ render: () => column.render('Work', WORK_PROJECT) });
    expect(work.find('a').attributes('href')).toBe('/projects/2');
    expect(work.find('a').text()).toBe('Work');
    expect(work.find('.orb-status-badge').exists()).toBe(false);

    const badged = mount({ render: () => column.render('Default', DEFAULT_PROJECT) });
    expect(badged.find('a').attributes('href')).toBe('/projects/1');
    expect(badged.find('.orb-status-badge').text()).toBe('Default');
  });

});

describe('Projects deleting', () => {
  it('deletes through the projects API and hands the response back to the table', async () => {
    const wrapper = await mountView();

    const result = await list(wrapper).props('actions').remover(2);

    expect(AppAPI.Project.delete).toHaveBeenCalledWith(2);
    expect(result).toEqual({ errors: false });
  });

  it("hands the backend's blocked-delete error back to the table so it can show it", async () => {
    const blocked = { errors: [{ attr: 'id', code: 'invalid', detail: 'Project still has active chat sessions.' }] };
    AppAPI.Project.delete.mockResolvedValue(blocked);
    const wrapper = await mountView();

    expect(await list(wrapper).props('actions').remover(2)).toEqual(blocked);
  });
});
