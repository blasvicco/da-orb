// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Project: { default: vi.fn(), list: vi.fn(), select: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { useProject } from '@/modules/project';
import { flushPromises, mount } from '@/tests/helpers/mount';
import ProjectSelect from '@/components/project/select.vue';
import ProjectSelector from '@/components/project/selector.vue';

// Fixtures
const DEFAULT_PROJECT = { id: 1, is_default: true, name: 'Default' };
const WORK_PROJECT = { id: 2, is_default: false, name: 'Work' };

describe('ProjectSelector', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    AppAPI.Project.default.mockResolvedValue(DEFAULT_PROJECT);
    AppAPI.Project.list.mockResolvedValue({ count: 2, results: [DEFAULT_PROJECT, WORK_PROJECT] });
  });

  it('titles the section and links to the project management view', async () => {
    const wrapper = mount(ProjectSelector);
    await flushPromises();

    expect(wrapper.find('.orb-project-selector-title').text()).toBe('Project');
    expect(wrapper.find('a.orb-project-selector-manage').attributes('href')).toBe('/projects');
  });

  it('shows the store\'s current project in its select', async () => {
    await useProject().loadDefault();
    const wrapper = mount(ProjectSelector);
    await flushPromises();

    expect(wrapper.findComponent(ProjectSelect).props('current')).toEqual(DEFAULT_PROJECT);
  });

  it('has no current project until one is loaded', async () => {
    const wrapper = mount(ProjectSelector);
    await flushPromises();

    expect(wrapper.findComponent(ProjectSelect).props('current')).toBeNull();
  });

  it('re-emits the project the user picks', async () => {
    const wrapper = mount(ProjectSelector);
    await flushPromises();

    await wrapper.findComponent(ProjectSelect).vm.$emit('select', 2);

    expect(wrapper.emitted('select')[0]).toEqual([2]);
  });
});
