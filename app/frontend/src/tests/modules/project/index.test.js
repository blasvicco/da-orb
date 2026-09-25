// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Project: { default: vi.fn(), select: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { useProject } from '@/modules/project';

// Fixtures
const DEFAULT_PROJECT = { id: 1, is_default: true, name: 'Default' };
const WORK_PROJECT = { id: 2, is_default: false, name: 'Work' };

describe('useProject', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('starts with no current project', () => {
    const store = useProject();
    expect(store.currentProject()).toBeNull();
    expect(store.currentProjectId()).toBeNull();
  });

  it('loadDefault() makes the Default project current', async () => {
    AppAPI.Project.default.mockResolvedValue(DEFAULT_PROJECT);
    const store = useProject();
    await store.loadDefault();
    expect(store.currentProject()).toEqual(DEFAULT_PROJECT);
    expect(store.currentProjectId()).toBe(1);
  });

  it.each([
    ['loadDefault', 'default'],
    ['selectProject', 'select'],
  ])('%s() keeps the current project when the API reports errors', async (method, apiMethod) => {
    AppAPI.Project.default.mockResolvedValueOnce(DEFAULT_PROJECT);
    const store = useProject();
    await store.loadDefault();
    AppAPI.Project[apiMethod].mockResolvedValue({ errors: [{ detail: 'boom' }] });

    const result = await store[method](2);

    expect(result.errors).toBeTruthy();
    expect(store.currentProjectId()).toBe(1);
  });

  it('selectProject() asks the API to select it and makes it current', async () => {
    AppAPI.Project.select.mockResolvedValue(WORK_PROJECT);
    const store = useProject();
    await store.selectProject(2);
    expect(AppAPI.Project.select).toHaveBeenCalledWith(2);
    expect(store.currentProjectId()).toBe(2);
  });
});
