// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('@/modules/api', () => ({
  default: { Context: { get: vi.fn() } },
}));

// App imports
import AppAPI from '@/modules/api';
import { useOrganization } from '@/modules/organization';

describe('useOrganization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('getContext() defaults to an empty object before load()', () => {
    const org = useOrganization();
    expect(org.getContext()).toEqual({});
  });

  it('hasOrganization() is null (unresolved) before load()', () => {
    const org = useOrganization();
    expect(org.hasOrganization()).toBeNull();
  });

  it('load() populates context and sets hasOrganization true on success', async () => {
    AppAPI.Context.get.mockResolvedValue({ auth_driver: 'open_id' });
    const org = useOrganization();
    await org.load();
    expect(org.getContext()).toEqual({ auth_driver: 'open_id' });
    expect(org.hasOrganization()).toBe(true);
  });

  it('load() sets hasOrganization false and clears context when the response carries errors', async () => {
    AppAPI.Context.get.mockResolvedValue({ errors: [{ detail: 'ORGANIZATION_NOT_FOUND' }] });
    const org = useOrganization();
    await org.load();
    expect(org.getContext()).toEqual({});
    expect(org.hasOrganization()).toBe(false);
  });

  it('load() leaves hasOrganization null on network failure, not false', async () => {
    AppAPI.Context.get.mockRejectedValue(new Error('network down'));
    const org = useOrganization();
    await org.load();
    expect(org.hasOrganization()).toBeNull();
  });

  it('load() de-duplicates concurrent calls into a single API request', async () => {
    let resolvePromise;
    AppAPI.Context.get.mockReturnValue(new Promise((resolve) => {
      resolvePromise = resolve;
    }));
    const org = useOrganization();
    const first = org.load();
    const second = org.load();
    resolvePromise({ auth_driver: 'open_id' });
    await Promise.all([first, second]);

    expect(AppAPI.Context.get).toHaveBeenCalledTimes(1);
  });
});
