// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Project: { list: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { body, flushPromises, mount, waitForBody } from '@/tests/helpers/mount';
import ProjectPicker from '@/components/project/picker.vue';

// Fixtures
const DEFAULT_PROJECT = { id: 1, name: 'Default' };
const WORK_PROJECT = { id: 2, name: 'Work' };
const HOME_PROJECT = { id: 3, name: 'Home' };

const popover = (wrapper) => wrapper.findComponent({ name: 'APopover' });
const input = (wrapper) => wrapper.findComponent({ name: 'AInput' });
const items = () => body().findAll('.orb-project-picker-item').map((item) => item.text());

const mountPicker = (props = {}) => mount(ProjectPicker, {
  props,
  slots: { default: '<button class="trigger">move</button>' },
});

// Opens the way the popover itself reports it: the model flips, then openChange fires.
// The popup's content is mounted asynchronously, so it also waits for that to be in the body.
const open = async (wrapper) => {
  await popover(wrapper).vm.$emit('update:open', true);
  await popover(wrapper).vm.$emit('openChange', true);
  await flushPromises();
  await waitForBody('.orb-project-picker');
};

describe('ProjectPicker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    AppAPI.Project.list.mockResolvedValue({ count: 3, results: [DEFAULT_PROJECT, WORK_PROJECT, HOME_PROJECT] });
  });

  it('renders its trigger and loads nothing until opened', async () => {
    const wrapper = mountPicker();
    await flushPromises();

    expect(wrapper.find('.trigger').exists()).toBe(true);
    expect(AppAPI.Project.list).not.toHaveBeenCalled();
  });

  it('loads the most recently accessed projects when opened and lists them by name', async () => {
    const wrapper = mountPicker();

    await open(wrapper);

    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: {}, limit: 8 });
    expect(items()).toEqual(['Default', 'Work', 'Home']);
  });

  it('opens from a click on its trigger', async () => {
    const wrapper = mountPicker();

    await wrapper.find('.trigger').trigger('click');
    await flushPromises();

    expect(AppAPI.Project.list).toHaveBeenCalledTimes(1);
    expect(items()).toEqual(['Default', 'Work', 'Home']);
  });

  it('leaves out the excluded project', async () => {
    const wrapper = mountPicker({ excludeId: 2 });

    await open(wrapper);

    expect(items()).toEqual(['Default', 'Home']);
  });

  it('emits the picked project id and closes', async () => {
    const wrapper = mountPicker();
    await open(wrapper);

    const [, workItem] = await waitForBody('.orb-project-picker-item', 3);

    await workItem.trigger('click');

    expect(wrapper.emitted('select')[0]).toEqual([2]);
    expect(wrapper.emitted('update:open').at(-1)).toEqual([false]);
  });

  it('focuses the search box on open', async () => {
    const wrapper = mountPicker();

    await open(wrapper);
    await flushPromises();

    expect(document.activeElement).toBe(body().find('.orb-project-picker input').element);
    expect(input(wrapper).exists()).toBe(true);
  });

  it('searches the server by name as the user types, debounced', async () => {
    const wrapper = mountPicker();
    await open(wrapper);
    vi.useFakeTimers();
    AppAPI.Project.list.mockClear();
    AppAPI.Project.list.mockResolvedValue({ count: 1, results: [WORK_PROJECT] });

    await input(wrapper).vm.$emit('update:value', 'w');
    await input(wrapper).vm.$emit('update:value', 'wor');
    await vi.advanceTimersByTimeAsync(249);
    expect(AppAPI.Project.list).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(1);

    expect(AppAPI.Project.list).toHaveBeenCalledTimes(1);
    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: { name__icontains: 'wor' }, limit: 8 });
    expect(items()).toEqual(['Work']);
  });

  it('shows the empty state when nothing matches, but not before the first results arrive', async () => {
    let resolveList;
    AppAPI.Project.list.mockReturnValueOnce(new Promise((resolve) => { resolveList = resolve; }));
    const wrapper = mountPicker();

    await popover(wrapper).vm.$emit('update:open', true);
    await popover(wrapper).vm.$emit('openChange', true);
    await flushPromises();
    expect(body().find('.orb-project-picker-empty').exists()).toBe(false);

    resolveList({ count: 0, results: [] });
    await flushPromises();
    expect(body().find('.orb-project-picker-empty').text()).toBe('No projects found');
  });

  it('shows the empty state when the only project is the excluded one', async () => {
    AppAPI.Project.list.mockResolvedValue({ count: 1, results: [DEFAULT_PROJECT] });
    const wrapper = mountPicker({ excludeId: 1 });

    await open(wrapper);

    expect(items()).toEqual([]);
    expect(body().find('.orb-project-picker-empty').exists()).toBe(true);
  });

  it('starts every opening with an empty search and fresh results', async () => {
    const wrapper = mountPicker();
    await open(wrapper);
    await input(wrapper).vm.$emit('update:value', 'wor');
    await popover(wrapper).vm.$emit('openChange', false);
    AppAPI.Project.list.mockClear();

    await popover(wrapper).vm.$emit('openChange', true);
    await flushPromises();

    expect(input(wrapper).props('value')).toBe('');
    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: {}, limit: 8 });
  });
});
