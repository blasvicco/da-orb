// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { defineComponent } from 'vue';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Project: { list: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { mount } from '@/tests/helpers/mount';
import { useProjectSearch } from '@/modules/project/search';

// Fixtures
const WORK_PROJECT = { id: 2, name: 'Work' };
const HOME_PROJECT = { id: 3, name: 'Home' };

// The composable clears its timer on unmount, so it needs a real component's setup.
const mountSearch = () => {
  let api;
  const wrapper = mount(defineComponent({
    setup() {
      api = useProjectSearch();
      return () => null;
    },
  }));
  return { api, wrapper };
};

describe('useProjectSearch', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    AppAPI.Project.list.mockResolvedValue({ count: 1, results: [WORK_PROJECT] });
  });

  it('starts with no projects', () => {
    expect(mountSearch().api.projects.value).toEqual([]);
  });

  it.each([
    ['no query lists the most recently accessed, unfiltered', undefined, {}],
    ['an empty query is the same as none', '', {}],
    ['a query filters by name', 'wor', { name__icontains: 'wor' }],
  ])('load() — %s', async (_label, query, expectedFilters) => {
    const { api } = mountSearch();

    await api.load(query);

    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: expectedFilters, limit: 8 });
    expect(api.projects.value).toEqual([WORK_PROJECT]);
  });

  it('load() keeps the previous results when the API reports errors', async () => {
    const { api } = mountSearch();
    await api.load();
    AppAPI.Project.list.mockResolvedValue({ errors: [{ detail: 'boom' }] });

    const result = await api.load('x');

    expect(result.errors).toBeTruthy();
    expect(api.projects.value).toEqual([WORK_PROJECT]);
  });

  it('load() lets only the newest request fill the list, so a slow earlier search cannot overwrite it', async () => {
    const { api } = mountSearch();
    let resolveSlow;
    AppAPI.Project.list.mockReturnValueOnce(new Promise((resolve) => { resolveSlow = resolve; }));
    AppAPI.Project.list.mockResolvedValueOnce({ count: 1, results: [HOME_PROJECT] });

    const slow = api.load('w');
    await api.load('h');
    resolveSlow({ count: 1, results: [WORK_PROJECT] });
    await slow;

    expect(api.projects.value).toEqual([HOME_PROJECT]);
  });

  it('search() debounces: rapid input runs one load, with the last query', async () => {
    vi.useFakeTimers();
    const { api } = mountSearch();

    api.search('w');
    api.search('wo');
    api.search('wor');
    await vi.advanceTimersByTimeAsync(249);
    expect(AppAPI.Project.list).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(AppAPI.Project.list).toHaveBeenCalledTimes(1);
    expect(AppAPI.Project.list).toHaveBeenCalledWith({ filters: { name__icontains: 'wor' }, limit: 8 });
  });

  it('drops a pending search when its component unmounts', async () => {
    vi.useFakeTimers();
    const { api, wrapper } = mountSearch();

    api.search('wor');
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(500);

    expect(AppAPI.Project.list).not.toHaveBeenCalled();
  });

  it('gives each caller its own results, so one search box cannot disturb another', async () => {
    const first = mountSearch().api;
    const second = mountSearch().api;
    AppAPI.Project.list.mockResolvedValueOnce({ count: 1, results: [WORK_PROJECT] });
    AppAPI.Project.list.mockResolvedValueOnce({ count: 1, results: [HOME_PROJECT] });

    await first.load('w');
    await second.load('h');

    expect(first.projects.value).toEqual([WORK_PROJECT]);
    expect(second.projects.value).toEqual([HOME_PROJECT]);
  });
});
