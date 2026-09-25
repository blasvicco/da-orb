// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
const mockAuth = vi.hoisted(() => ({
  getSession: vi.fn().mockReturnValue({ database: 'PROD', role: 'admin', user: { username: 'admin.bob' } }),
  signout: vi.fn(),
}));

vi.mock('@/modules/auth', () => ({ useAuth: () => mockAuth }));
vi.mock('@/modules/api', () => ({
  default: {
    DocumentTemplate: {
      preview: vi.fn(),
      remove: vi.fn().mockResolvedValue({}),
      setDefault: vi.fn().mockResolvedValue({}),
      templates: vi.fn().mockResolvedValue([]),
      update: vi.fn(),
      upload: vi.fn(),
    },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import AdminTabs from '@/components/admin/tabs.vue';
import List from '@/components/table/list.vue';
import UserDetail from '@/components/user/detail.vue';
import DocumentTemplates from '@/views/admin/document-templates.vue';

// Fixtures
const ADMIN_SESSION = { database: 'PROD', role: 'admin', user: { username: 'admin.bob' } };
const TEMPLATE = { created_on: '2026-09-20T00:00:00Z', document_type: 'invoice', id: 1, is_default: false, name: 'BVS Factura v4' };

const mountView = async (options = {}) => {
  const wrapper = mount(DocumentTemplates, options);
  await flushPromises();
  return wrapper;
};

const defaultColumn = async () => {
  const wrapper = await mountView();
  return wrapper.findComponent(List).props('columns').find((column) => column.key === 'is_default');
};

const loadedRows = (wrapper, paging = {}) => wrapper.findComponent(List).props('loader')(paging);

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue(ADMIN_SESSION);
  AppAPI.DocumentTemplate.templates.mockResolvedValue([TEMPLATE]);
  AppAPI.DocumentTemplate.setDefault.mockResolvedValue({});
  AppAPI.DocumentTemplate.remove.mockResolvedValue({});
  localStorage.clear();
});

describe('DocumentTemplates default switch', () => {
  it.each([
    ['a non-default template', false, 'Set as default'],
    ['the default template', true, 'Default'],
  ])('renders the switch for %s with no text inside it, only an accessible label', async (_label, isDefault, ariaLabel) => {
    const column = await defaultColumn();

    const { props } = column.render(null, { ...TEMPLATE, is_default: isDefault });

    expect(props).not.toHaveProperty('checkedChildren');
    expect(props).not.toHaveProperty('unCheckedChildren');
    expect(props['aria-label']).toBe(ariaLabel);
    expect(props.checked).toBe(isDefault);
  });

  it('locks the switch on the current default template, and sets a new default when another is turned on', async () => {
    const column = await defaultColumn();

    expect(column.render(null, { ...TEMPLATE, is_default: true }).props.disabled).toBe(true);
    const other = column.render(null, TEMPLATE).props;
    expect(other.disabled).toBe(false);

    await other.onChange();

    expect(AppAPI.DocumentTemplate.setDefault).toHaveBeenCalledWith(1);
  });
});

describe('DocumentTemplates.mount', () => {
  it('shows a loading state, then loads the templates into the table', async () => {
    const wrapper = mount(DocumentTemplates);
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(true);

    await flushPromises();

    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(1);
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(false);
    expect(await loadedRows(wrapper)).toEqual({ count: 1, results: [TEMPLATE] });
  });

  it('pages the loaded templates on the client, without asking the server again', async () => {
    const others = [{ ...TEMPLATE, id: 2 }, { ...TEMPLATE, id: 3 }];
    AppAPI.DocumentTemplate.templates.mockResolvedValue([TEMPLATE, ...others]);
    const wrapper = await mountView();

    expect(await loadedRows(wrapper, { limit: 2, offset: 2 })).toEqual({ count: 3, results: [others[1]] });
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(1);
  });

  it('keeps the table empty when the templates cannot be loaded', async () => {
    AppAPI.DocumentTemplate.templates.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = await mountView();

    expect(await loadedRows(wrapper)).toEqual({ count: 0, results: [] });
  });

  it('marks the document templates tab active and shows the admin-only sidebar entry', async () => {
    const wrapper = await mountView();

    expect(wrapper.findComponent(AdminTabs).props('active')).toBe('documentTemplates');
    expect(wrapper.findComponent(UserDetail).props('isAdmin')).toBe(true);
  });

  it('navigates back to chat from the sidebar button', async () => {
    const router = buildRouter('/admin/document-templates');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = await mountView({ global: { router } });

    await wrapper.find('.orb-new-chat-btn').trigger('click');

    expect(pushSpy).toHaveBeenCalledWith('/chat');
  });
});

describe('DocumentTemplates.userProfile', () => {
  it.each([
    ['no session at all', null, { connection: '', initials: '?', name: '', role: 'standard' }],
    ['a session without a user', {}, { connection: '', initials: '?', name: '', role: 'standard' }],
    ['a complete admin session', ADMIN_SESSION, { connection: 'PROD', initials: 'AD', name: 'admin.bob', role: 'admin' }],
    ['a two-word name', { user: { username: 'Bob Smith' } }, { connection: '', initials: 'BS', name: 'Bob Smith', role: 'standard' }],
    ['a one-word name', { user: { username: 'bob' } }, { connection: '', initials: 'BO', name: 'bob', role: 'standard' }],
  ])('shows the sidebar profile for %s', async (_label, session, expected) => {
    mockAuth.getSession.mockReturnValue(session);
    const wrapper = await mountView();
    const detail = wrapper.findComponent(UserDetail);

    expect({
      connection: detail.props('connection'),
      initials: detail.props('initials'),
      name: detail.props('name'),
      role: detail.props('role'),
    }).toEqual(expected);
  });
});

describe('DocumentTemplates.theme and logout', () => {
  it.each([
    ['dark', true],
    ['light', false],
  ])('persists a switch to the %s theme', async (theme, isDark) => {
    const wrapper = await mountView();

    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', isDark);

    expect(localStorage.getItem('orb-theme')).toBe(theme);
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe(theme);
  });

  it('starts in the theme the user saved earlier', async () => {
    localStorage.setItem('orb-theme', 'dark');
    const wrapper = await mountView();

    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('dark');
  });

  it('signs out and navigates home on logout', async () => {
    const router = buildRouter('/admin/document-templates');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = await mountView({ global: { router } });

    await wrapper.findComponent(UserDetail).vm.$emit('logout');

    expect(mockAuth.signout).toHaveBeenCalled();
    expect(pushSpy).toHaveBeenCalledWith('/');
  });
});

describe('DocumentTemplates.actions', () => {
  it('sets a new default, then reloads the templates so the table shows the change', async () => {
    const wrapper = await mountView();
    const column = wrapper.findComponent(List).props('columns').find((entry) => entry.key === 'is_default');
    AppAPI.DocumentTemplate.templates.mockResolvedValue([{ ...TEMPLATE, is_default: true }]);

    await column.render(null, TEMPLATE).props.onChange();
    await flushPromises();

    expect(AppAPI.DocumentTemplate.setDefault).toHaveBeenCalledWith(1);
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(2);
    expect(await loadedRows(wrapper)).toEqual({ count: 1, results: [{ ...TEMPLATE, is_default: true }] });
  });

  it('removes a template through the table, hands the result back and reloads', async () => {
    const wrapper = await mountView();

    const result = await wrapper.findComponent(List).props('actions').remover(1);
    await flushPromises();

    expect(AppAPI.DocumentTemplate.remove).toHaveBeenCalledWith(1);
    expect(result).toEqual({});
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(2);
  });

  it.each([
    ['a detail', [{ detail: 'The default template cannot be removed.' }], 'The default template cannot be removed.'],
    ['only an error code', [{ error: 'FILE_TOO_LARGE' }], 'FILE_TOO_LARGE'],
    ['neither a detail nor a code', [{}], 'ERROR'],
    ['no entries at all', [], 'ERROR'],
  ])('shows the failure of a remove that reports %s, hands back nothing and does not reload', async (_label, errors, expected) => {
    AppAPI.DocumentTemplate.remove.mockResolvedValue({ errors });
    const wrapper = await mountView();

    const result = await wrapper.findComponent(List).props('actions').remover(1);
    await flushPromises();

    expect(result).toBeNull();
    expect(wrapper.find('.orb-admin-error').text()).toBe(expected);
    expect(AppAPI.DocumentTemplate.templates).toHaveBeenCalledTimes(1);
  });

  it('clears an earlier failure as soon as the next action goes through', async () => {
    AppAPI.DocumentTemplate.remove.mockResolvedValueOnce({ errors: [{ detail: 'boom' }] });
    const wrapper = await mountView();
    const { remover } = wrapper.findComponent(List).props('actions');
    await remover(1);
    await flushPromises();
    expect(wrapper.find('.orb-admin-error').exists()).toBe(true);

    await remover(1);
    await flushPromises();

    expect(wrapper.find('.orb-admin-error').exists()).toBe(false);
  });
});
