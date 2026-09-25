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
    ChatSession: { list: vi.fn(), move: vi.fn() },
    Project: { get: vi.fn(), list: vi.fn() },
  },
}));
vi.mock('antdv-next', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, message: { error: vi.fn(), success: vi.fn() } };
});

// App imports
import { message } from 'antdv-next';
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import List from '@/components/table/list.vue';
import ProjectPicker from '@/components/project/picker.vue';
import ProjectSelect from '@/components/project/select.vue';
import UserDetail from '@/components/user/detail.vue';
import Project from '@/views/project.vue';

// Fixtures
const WORK_PROJECT = { chat_sessions_count: 2, id: 8, is_default: false, name: 'Work', summary: '' };
const HOME_PROJECT = { chat_sessions_count: 0, id: 9, is_default: false, name: 'Home', summary: '' };
const CHATS = [
  { created_on: '2026-09-20T10:00:00Z', id: 1, project: 8, project_name: 'Work', title: 'Quarterly report', tokens_used: 1234, updated_on: '2026-09-21T10:00:00Z' },
  { created_on: '2026-09-22T10:00:00Z', id: 2, project: 8, project_name: 'Work', title: '', tokens_used: 0, updated_on: '2026-09-22T10:00:00Z' },
];

const list = (wrapper) => wrapper.findComponent(List);
const moveButton = (wrapper) => wrapper.find('.orb-admin-actions button');

const mountAt = async (path = '/projects/8') => {
  const router = buildRouter(path);
  await router.isReady();
  const wrapper = mount(Project, { global: { router } });
  await flushPromises();
  return { router, wrapper };
};

// Ticks rows the way the table's checkboxes do: through the selection config it was given.
const select = async (wrapper, keys) => {
  list(wrapper).props('rowSelection').onChange(keys);
  await flushPromises();
};

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({ database: 'PROD', user: { username: 'bob' } });
  mockAuth.isAdmin.mockReturnValue(false);
  AppAPI.Project.get.mockImplementation(async (id) => (id === 9 ? HOME_PROJECT : (id === 8 ? WORK_PROJECT : { errors: [{ code: 'not_found', detail: 'Not found.' }] })));
  AppAPI.Project.list.mockResolvedValue({ count: 2, results: [WORK_PROJECT, HOME_PROJECT] });
  AppAPI.ChatSession.list.mockResolvedValue({ count: 2, results: CHATS });
  AppAPI.ChatSession.move.mockResolvedValue({ moved: 2, project_id: 9 });
  localStorage.clear();
});

describe('Project view loading', () => {
  it('shows the project name and lists its chats, filtered to that project, with the table\'s paging', async () => {
    const { wrapper } = await mountAt('/projects/8');

    expect(AppAPI.Project.get).toHaveBeenCalledWith(8);
    expect(wrapper.find('.orb-admin-title').text()).toBe('Work');
    expect(AppAPI.ChatSession.list).toHaveBeenCalledWith({
      filters: { project_id: 8 },
      limit: 20,
      offset: 0,
      sorter: {},
    });
    expect(list(wrapper).props('columns').length).toBeGreaterThan(0);
  });

  it('adds the project filter to whatever filters, sorter and paging the table asks for', async () => {
    const { wrapper } = await mountAt('/projects/8');
    const sorter = { field: 'title', order: 'ascend' };

    await list(wrapper).props('loader')({ filters: { title__icontains: 'rep' }, limit: 5, offset: 10, sorter });

    expect(AppAPI.ChatSession.list).toHaveBeenLastCalledWith({
      filters: { project_id: 8, title__icontains: 'rep' },
      limit: 5,
      offset: 10,
      sorter,
    });
  });

  it('shows a loading state until the project is known, and no table', async () => {
    let resolveProject;
    AppAPI.Project.get.mockReturnValue(new Promise((resolve) => { resolveProject = resolve; }));
    const router = buildRouter('/projects/8');
    await router.isReady();
    const wrapper = mount(Project, { global: { router } });
    await flushPromises();

    expect(wrapper.find('.orb-admin-loading').exists()).toBe(true);
    expect(list(wrapper).exists()).toBe(false);

    resolveProject(WORK_PROJECT);
    await flushPromises();
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(false);
    expect(list(wrapper).exists()).toBe(true);
  });

  it('says so, with no table, for a project that does not exist', async () => {
    const { wrapper } = await mountAt('/projects/404');

    expect(AppAPI.Project.get).toHaveBeenCalledWith(404);
    expect(wrapper.find('.orb-admin-error').text()).toBe('This project no longer exists.');
    expect(list(wrapper).exists()).toBe(false);
    expect(AppAPI.ChatSession.list).not.toHaveBeenCalled();
  });

  it.each([
    ['letters', '/projects/abc'],
    ['a decimal', '/projects/1.5'],
  ])('says so without even asking the server when the id is %s', async (_label, path) => {
    const { wrapper } = await mountAt(path);

    expect(wrapper.find('.orb-admin-error').text()).toBe('This project no longer exists.');
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(false);
    expect(AppAPI.Project.get).not.toHaveBeenCalled();
    expect(list(wrapper).exists()).toBe(false);
  });

  it('links back to the projects list, and back to chat from the sidebar', async () => {
    const { router, wrapper } = await mountAt('/projects/8');
    const pushSpy = vi.spyOn(router, 'push');

    expect(wrapper.find('a.orb-project-back').attributes('href')).toBe('/projects');
    await wrapper.find('.orb-new-chat-btn').trigger('click');

    expect(pushSpy).toHaveBeenCalledWith('/chat');
  });

  it('is open to a standard user: the sidebar carries the real admin flag', async () => {
    const { wrapper } = await mountAt('/projects/8');
    expect(wrapper.findComponent(UserDetail).props('isAdmin')).toBe(false);
  });
});

describe('Project view sidebar profile', () => {
  it.each([
    ['no session at all', null, { connection: '', initials: '?', name: '', role: 'standard' }],
    ['a session without a user', {}, { connection: '', initials: '?', name: '', role: 'standard' }],
    ['a full session', { database: 'PROD', role: 'admin', user: { username: 'bob' } }, { connection: 'PROD', initials: 'BO', name: 'bob', role: 'admin' }],
    ['a two-word name', { user: { username: 'Bob Smith' } }, { connection: '', initials: 'BS', name: 'Bob Smith', role: 'standard' }],
  ])('shows the profile for %s', async (_label, session, expected) => {
    mockAuth.getSession.mockReturnValue(session);
    const { wrapper } = await mountAt();

    expect(wrapper.findComponent(UserDetail).props()).toMatchObject(expected);
  });
});

describe('Project view theme and logout', () => {
  it.each([
    ['dark', true],
    ['light', false],
  ])('persists a switch to the %s theme', async (theme, isDark) => {
    const { wrapper } = await mountAt();

    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', isDark);

    expect(localStorage.getItem('orb-theme')).toBe(theme);
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe(theme);
  });

  it('signs out and navigates home on logout', async () => {
    const { router, wrapper } = await mountAt();
    const pushSpy = vi.spyOn(router, 'push');

    await wrapper.findComponent(UserDetail).vm.$emit('logout');

    expect(mockAuth.signout).toHaveBeenCalled();
    expect(pushSpy).toHaveBeenCalledWith('/');
  });
});

describe('Project view columns', () => {
  it('lists title, tokens, created and updated, all sortable, in display order', async () => {
    const { wrapper } = await mountAt();
    const columns = list(wrapper).props('columns');

    expect(columns.map((column) => column.key)).toEqual(['title', 'tokens_used', 'created_on', 'updated_on']);
    expect(columns.every((column) => column.sorter === true)).toBe(true);
  });

  it.each([
    ['title', true, undefined],
    ['tokens_used', undefined, undefined],
    ['created_on', true, 'datetime'],
    ['updated_on', true, 'datetime'],
  ])('%s: filterable=%s, type=%s', async (key, filterable, type) => {
    const { wrapper } = await mountAt();
    const column = list(wrapper).props('columns').find((entry) => entry.key === key);

    expect(column.filterDropdown).toBe(filterable);
    expect(column.type).toBe(type);
  });

  it.each([
    ['a titled chat', CHATS[0], 'Quarterly report'],
    ['an untitled chat', CHATS[1], 'Untitled chat'],
  ])('renders %s as a link that opens it in its project', async (_label, chat, text) => {
    const { wrapper } = await mountAt();
    const title = list(wrapper).props('columns').find((column) => column.key === 'title');

    const link = mount({ render: () => title.render(chat.title, chat) }).find('a');

    expect(link.text()).toBe(text);
    expect(link.attributes('href')).toBe(`/chat?project=${chat.project}&session=${chat.id}`);
  });

  it('renders tokens with thousands separators', async () => {
    const { wrapper } = await mountAt();
    const tokens = list(wrapper).props('columns').find((column) => column.key === 'tokens_used');

    expect(tokens.render(1234)).toBe((1234).toLocaleString());
  });

});

describe('Project view selection and move', () => {
  it('has a disabled Move button until chats are ticked, then shows how many', async () => {
    const { wrapper } = await mountAt();
    expect(moveButton(wrapper).text()).toBe('Move');
    expect(moveButton(wrapper).attributes('disabled')).toBeDefined();

    await select(wrapper, [1, 2]);

    expect(moveButton(wrapper).text()).toBe('Move (2)');
    expect(moveButton(wrapper).attributes('disabled')).toBeUndefined();
  });

  it('keeps ticked rows across pages, and reports the table\'s own selection back', async () => {
    const { wrapper } = await mountAt();
    await select(wrapper, [1]);

    const config = list(wrapper).props('rowSelection');

    expect(config.selectedRowKeys).toEqual([1]);
    expect(config.preserveSelectedRowKeys).toBe(true);
  });

  it('offers every project but the one being viewed as the destination', async () => {
    const { wrapper } = await mountAt();
    expect(wrapper.findComponent(ProjectPicker).props('excludeId')).toBe(8);
  });

  it('moves the ticked chats to the picked project, then clears the selection and reloads the list', async () => {
    const { wrapper } = await mountAt();
    await select(wrapper, [1, 2]);
    AppAPI.ChatSession.list.mockClear();

    await wrapper.findComponent(ProjectPicker).vm.$emit('select', 9);
    await flushPromises();

    expect(AppAPI.ChatSession.move).toHaveBeenCalledWith([1, 2], 9);
    expect(message.success).toHaveBeenCalledWith('2 chats moved');
    expect(list(wrapper).props('rowSelection').selectedRowKeys).toEqual([]);
    expect(moveButton(wrapper).text()).toBe('Move');
    expect(AppAPI.ChatSession.list).toHaveBeenCalledTimes(1);
  });

  it('says "1 chat moved" for a single chat', async () => {
    AppAPI.ChatSession.move.mockResolvedValue({ moved: 1, project_id: 9 });
    const { wrapper } = await mountAt();
    await select(wrapper, [1]);

    await wrapper.findComponent(ProjectPicker).vm.$emit('select', 9);
    await flushPromises();

    expect(message.success).toHaveBeenCalledWith('1 chat moved');
  });

  it('shows a translated error and keeps the selection when the move is refused', async () => {
    AppAPI.ChatSession.move.mockResolvedValue({
      errors: [{ attr: 'session_ids', code: 'invalid', detail: 'Too many chats selected.' }],
    });
    const { wrapper } = await mountAt();
    await select(wrapper, [1, 2]);
    AppAPI.ChatSession.list.mockClear();

    await wrapper.findComponent(ProjectPicker).vm.$emit('select', 9);
    await flushPromises();

    expect(message.error).toHaveBeenCalledWith('Too many chats selected at once.');
    expect(message.success).not.toHaveBeenCalled();
    expect(list(wrapper).props('rowSelection').selectedRowKeys).toEqual([1, 2]);
    expect(AppAPI.ChatSession.list).not.toHaveBeenCalled();
  });

  it('refreshes the list and drops the selection when a chat or the project turns out to be gone', async () => {
    AppAPI.ChatSession.move.mockResolvedValue({
      errors: [{ attr: null, code: 'not_found', detail: 'Some of the selected chats no longer exist.' }],
    });
    const { wrapper } = await mountAt();
    await select(wrapper, [1, 2]);
    AppAPI.ChatSession.list.mockClear();

    await wrapper.findComponent(ProjectPicker).vm.$emit('select', 9);
    await flushPromises();

    expect(message.error).toHaveBeenCalledWith('Some of the selected chats no longer exist. The list has been refreshed.');
    expect(list(wrapper).props('rowSelection').selectedRowKeys).toEqual([]);
    expect(AppAPI.ChatSession.list).toHaveBeenCalledTimes(1);
  });
});

describe('Project view switching project', () => {
  it('offers the searchable project dropdown, showing the viewed project', async () => {
    const { wrapper } = await mountAt();
    expect(wrapper.findComponent(ProjectSelect).props('current')).toEqual(WORK_PROJECT);
  });

  it('opens the picked project\'s chats', async () => {
    const { router, wrapper } = await mountAt('/projects/8');

    await wrapper.findComponent(ProjectSelect).vm.$emit('select', 9);
    await flushPromises();

    expect(router.currentRoute.value.path).toBe('/projects/9');
    expect(AppAPI.Project.get).toHaveBeenLastCalledWith(9);
    expect(wrapper.find('.orb-admin-title').text()).toBe('Home');
    expect(AppAPI.ChatSession.list).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { project_id: 9 } }),
    );
  });

  it('does nothing when the viewed project is picked again', async () => {
    const { router, wrapper } = await mountAt('/projects/8');
    const pushSpy = vi.spyOn(router, 'push');

    await wrapper.findComponent(ProjectSelect).vm.$emit('select', 8);

    expect(pushSpy).not.toHaveBeenCalled();
  });

  it('starts the new project with nothing ticked', async () => {
    const { router, wrapper } = await mountAt('/projects/8');
    await select(wrapper, [1, 2]);

    await router.push('/projects/9');
    await flushPromises();

    expect(list(wrapper).props('rowSelection').selectedRowKeys).toEqual([]);
  });

  it('ignores a slow answer for a project the user has already navigated away from', async () => {
    let resolveFirst;
    AppAPI.Project.get.mockReturnValueOnce(new Promise((resolve) => { resolveFirst = resolve; }));
    const router = buildRouter('/projects/8');
    await router.isReady();
    const wrapper = mount(Project, { global: { router } });
    await flushPromises();

    await router.push('/projects/9');
    await flushPromises();
    resolveFirst(WORK_PROJECT);
    await flushPromises();

    expect(wrapper.find('.orb-admin-title').text()).toBe('Home');
  });
});
