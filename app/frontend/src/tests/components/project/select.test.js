// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { Select } from 'antdv-next';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Project: { list: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { flushPromises, mount } from '@/tests/helpers/mount';
import ProjectSelect from '@/components/project/select.vue';

// Fixtures
const DEFAULT_PROJECT = { id: 1, is_default: true, name: 'Default' };
const WORK_PROJECT = { id: 2, is_default: false, name: 'Work' };
const select = (wrapper) => wrapper.findComponent(Select);

describe('ProjectSelect', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    AppAPI.Project.list.mockResolvedValue({ count: 2, results: [DEFAULT_PROJECT, WORK_PROJECT] });
  });

  it('loads the most recently accessed projects on mount and offers them as options', async () => {
    const wrapper = mount(ProjectSelect);
    await flushPromises();

    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: {}, limit: 8 });
    expect(select(wrapper).props('options')).toEqual([
      { label: 'Default', value: 1 },
      { label: 'Work', value: 2 },
    ]);
  });

  it('is a searchable select that leaves filtering to the server', async () => {
    const wrapper = mount(ProjectSelect);
    await flushPromises();

    expect(select(wrapper).props('showSearch')).toBeTruthy();
    expect(select(wrapper).props('filterOption')).toBe(false);
  });

  it('shows the current project as the selected value', async () => {
    const wrapper = mount(ProjectSelect, { props: { current: DEFAULT_PROJECT } });
    await flushPromises();

    expect(select(wrapper).props('value')).toBe(1);
  });

  it('selects nothing when there is no current project', async () => {
    const wrapper = mount(ProjectSelect);
    await flushPromises();

    expect(select(wrapper).props('value')).toBeUndefined();
  });

  it('keeps the current project among the options even when it is not in the loaded list', async () => {
    const wrapper = mount(ProjectSelect, { props: { current: { id: 99, name: 'Old project' } } });
    await flushPromises();

    expect(select(wrapper).props('options')[0]).toEqual({ label: 'Old project', value: 99 });
    expect(select(wrapper).props('options')).toHaveLength(3);
  });

  it('does not list the current project twice when it is already among the results', async () => {
    const wrapper = mount(ProjectSelect, { props: { current: WORK_PROJECT } });
    await flushPromises();

    expect(select(wrapper).props('options')).toHaveLength(2);
  });

  it('emits select with the chosen project id', async () => {
    const wrapper = mount(ProjectSelect);
    await flushPromises();

    await select(wrapper).vm.$emit('change', 2);

    expect(wrapper.emitted('select')[0]).toEqual([2]);
  });

  it('debounces searching, then filters the options by name', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ProjectSelect);
    await flushPromises();
    AppAPI.Project.list.mockClear();

    await select(wrapper).vm.$emit('search', 'w');
    await select(wrapper).vm.$emit('search', 'wo');
    await select(wrapper).vm.$emit('search', 'wor');
    await vi.advanceTimersByTimeAsync(249);
    expect(AppAPI.Project.list).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(AppAPI.Project.list).toHaveBeenCalledTimes(1);
    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: { name__icontains: 'wor' }, limit: 8 });
  });

  it('cancels a pending search when unmounted', async () => {
    vi.useFakeTimers();
    const wrapper = mount(ProjectSelect);
    await flushPromises();
    AppAPI.Project.list.mockClear();

    await select(wrapper).vm.$emit('search', 'wor');
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(500);

    expect(AppAPI.Project.list).not.toHaveBeenCalled();
  });

  it.each([
    ['opens', true, 1],
    ['closes', false, 0],
  ])('reloads the options when the dropdown %s: %i extra load(s)', async (_label, open, extraLoads) => {
    const wrapper = mount(ProjectSelect);
    await flushPromises();
    AppAPI.Project.list.mockClear();

    await select(wrapper).vm.$emit('openChange', open);
    await flushPromises();

    expect(AppAPI.Project.list).toHaveBeenCalledTimes(extraLoads);
  });
});
