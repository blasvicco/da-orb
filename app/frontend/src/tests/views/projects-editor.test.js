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
import { body, flushPromises, mount } from '@/tests/helpers/mount';
import List from '@/components/table/list.vue';
import Projects from '@/views/projects.vue';

// Fixtures
const DEFAULT_PROJECT = { chat_sessions_count: 0, id: 1, is_default: true, name: 'Default', summary: '' };
const WORK_PROJECT = { chat_sessions_count: 3, id: 2, is_default: false, name: 'Work', summary: 'Client work' };

const list = (wrapper) => wrapper.findComponent(List);
// The editor modal teleports its content onto document.body: reach it through components
// (modal/nameInput/summaryInput) or body(), never wrapper.find().
const modal = (wrapper) => wrapper.findComponent({ name: 'AModal' });
const nameInput = (wrapper) => wrapper.findComponent({ name: 'AInput' });
const summaryInput = (wrapper) => wrapper.findComponent({ name: 'ATextarea' });

const mountView = async (options = {}) => {
  const wrapper = mount(Projects, options);
  await flushPromises();
  return wrapper;
};

// Opens the editor the way the table's edit button does.
const openEditor = async (wrapper, record) => {
  await list(wrapper).props('actions').editor(record);
  await flushPromises();
};

const clickOk = async (wrapper) => {
  await modal(wrapper).vm.$emit('ok');
  await flushPromises();
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

describe('Projects editor', () => {
  it('starts closed', async () => {
    expect(modal(await mountView()).props('open')).toBe(false);
  });

  it('opens a regular project with its name and summary, and the empty-project danger zone', async () => {
    const wrapper = await mountView();

    await openEditor(wrapper, WORK_PROJECT);

    expect(modal(wrapper).props('open')).toBe(true);
    expect(modal(wrapper).props('title')).toBe('Edit Project');
    expect(nameInput(wrapper).props('value')).toBe('Work');
    expect(nameInput(wrapper).props('disabled')).toBe(false);
    expect(summaryInput(wrapper).props('value')).toBe('Client work');
    expect(body().find('.orb-project-danger').exists()).toBe(true);
  });

  it('locks the Default project’s name and offers no empty-project action for it', async () => {
    const wrapper = await mountView();

    await openEditor(wrapper, DEFAULT_PROJECT);

    expect(nameInput(wrapper).props('disabled')).toBe(true);
    expect(body().find('.orb-project-danger').exists()).toBe(false);
  });

  it('opens blank in create mode from the New Project button', async () => {
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);
    await modal(wrapper).vm.$emit('cancel');

    await wrapper.find('.orb-admin-actions button').trigger('click');
    await flushPromises();

    expect(modal(wrapper).props('title')).toBe('New Project');
    expect(nameInput(wrapper).props('value')).toBe('');
    expect(nameInput(wrapper).props('disabled')).toBe(false);
    expect(body().find('.orb-project-danger').exists()).toBe(false);
  });

  it('lets the modal close itself', async () => {
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);
    expect(modal(wrapper).props('open')).toBe(true);

    await modal(wrapper).vm.$emit('update:open', false);

    expect(modal(wrapper).props('open')).toBe(false);
  });

  it('closes on cancel without saving', async () => {
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);

    await modal(wrapper).vm.$emit('cancel');
    await flushPromises();

    expect(modal(wrapper).props('open')).toBe(false);
    expect(AppAPI.Project.save).not.toHaveBeenCalled();
  });
});

describe('Projects saving', () => {
  it('creates a project from the entered name and summary, then closes and reloads the table', async () => {
    const wrapper = await mountView();
    await wrapper.find('.orb-admin-actions button').trigger('click');
    await flushPromises();
    await nameInput(wrapper).vm.$emit('update:value', 'Client Alpha');
    await summaryInput(wrapper).vm.$emit('update:value', 'All things Alpha');
    AppAPI.Project.list.mockClear();

    await clickOk(wrapper);

    expect(AppAPI.Project.save).toHaveBeenCalledWith({ name: 'Client Alpha', summary: 'All things Alpha' });
    expect(modal(wrapper).props('open')).toBe(false);
    expect(AppAPI.Project.list).toHaveBeenCalledTimes(1);
  });

  it('updates an existing project by id, with its edited name and summary', async () => {
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);
    await nameInput(wrapper).vm.$emit('update:value', 'Work 2');

    await clickOk(wrapper);

    expect(AppAPI.Project.save).toHaveBeenCalledWith({ id: 2, name: 'Work 2', summary: 'Client work' });
    expect(modal(wrapper).props('open')).toBe(false);
  });

  it('never sends the Default project’s name, only its summary', async () => {
    const wrapper = await mountView();
    await openEditor(wrapper, DEFAULT_PROJECT);
    await summaryInput(wrapper).vm.$emit('update:value', 'My default notes');

    await clickOk(wrapper);

    expect(AppAPI.Project.save).toHaveBeenCalledWith({ id: 1, summary: 'My default notes' });
  });

  it.each([
    [
      'a translated message for a known error',
      { attr: 'name', code: 'blank', detail: 'This field may not be blank.' },
      'A name is required.',
    ],
    [
      'the default-rename guard',
      { attr: 'name', code: 'invalid', detail: 'Default project cannot be renamed.' },
      'The Default project cannot be renamed.',
    ],
    [
      'the raw detail for an error nobody has translated',
      { attr: 'summary', code: 'invalid', detail: 'Something odd.' },
      'Something odd.',
    ],
    ['a generic error when there is nothing to show', {}, 'ERROR'],
  ])('keeps the editor open and shows %s', async (_label, error, expected) => {
    AppAPI.Project.save.mockResolvedValue({ errors: [error] });
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);

    await clickOk(wrapper);

    expect(modal(wrapper).props('open')).toBe(true);
    expect(body().find('.orb-project-form-error').text()).toBe(expected);
  });

  it('shows the raw error field when the response carries no detail', async () => {
    AppAPI.Project.save.mockResolvedValue({ errors: [{ error: 'MISSING_NAME' }] });
    const wrapper = await mountView();
    await wrapper.find('.orb-admin-actions button').trigger('click');
    await flushPromises();

    await clickOk(wrapper);

    expect(body().find('.orb-project-form-error').text()).toBe('MISSING_NAME');
  });

  it('clears a previous error when the editor is reopened', async () => {
    AppAPI.Project.save.mockResolvedValue({ errors: [{ attr: 'name', detail: 'This field may not be blank.' }] });
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);
    await clickOk(wrapper);
    expect(body().find('.orb-project-form-error').exists()).toBe(true);

    await openEditor(wrapper, WORK_PROJECT);

    expect(body().find('.orb-project-form-error').exists()).toBe(false);
  });
});

describe('Projects emptying', () => {
  const emptyButton = () => body().find('.orb-project-danger button');
  // The table's own row-delete buttons are Popconfirms too — pick the one guarding "empty".
  const confirmEmpty = async (wrapper) => {
    await wrapper
      .findAllComponents({ name: 'APopconfirm' })
      .find((popconfirm) => popconfirm.props('title') === 'Delete every chat in this project?')
      .vm.$emit('confirm');
    await flushPromises();
  };

  it('empties the project, shows the new zero count, disables the button and reloads the table', async () => {
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);
    expect(body().find('.orb-project-danger-text').text()).toContain('3');
    expect(emptyButton().attributes('disabled')).toBeUndefined();
    AppAPI.Project.list.mockClear();

    await confirmEmpty(wrapper);

    expect(AppAPI.Project.empty).toHaveBeenCalledWith(2);
    expect(body().find('.orb-project-danger-text').text()).toContain('0');
    expect(emptyButton().attributes('disabled')).toBeDefined();
    expect(AppAPI.Project.list).toHaveBeenCalledTimes(1);
    expect(modal(wrapper).props('open')).toBe(true);
  });

  it('has nothing to empty when the project is already empty', async () => {
    const wrapper = await mountView();

    await openEditor(wrapper, { ...WORK_PROJECT, chat_sessions_count: 0 });

    expect(emptyButton().attributes('disabled')).toBeDefined();
  });

  it('shows the error and keeps the count when emptying fails', async () => {
    AppAPI.Project.empty.mockResolvedValue({ errors: [{ attr: 'id', detail: 'Not found.' }] });
    const wrapper = await mountView();
    await openEditor(wrapper, WORK_PROJECT);

    await confirmEmpty(wrapper);

    expect(body().find('.orb-project-form-error').text()).toBe('Not found.');
    expect(body().find('.orb-project-danger-text').text()).toContain('3');
  });
});
