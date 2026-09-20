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
    Seat: {
      reinstate: vi.fn().mockResolvedValue({}),
      revoke: vi.fn().mockResolvedValue({}),
      seats: vi.fn().mockResolvedValue([]),
      setRole: vi.fn().mockResolvedValue({}),
    },
    Usage: { summary: vi.fn().mockResolvedValue({ plan: { seats: { total: 10, used: 1 } } }) },
  },
}));

// App imports
import AppAPI from '@/modules/api';
import { buildRouter, flushPromises, mount } from '@/tests/helpers/mount';
import AdminTabs from '@/components/admin/tabs.vue';
import List from '@/components/table/list.vue';
import UserDetail from '@/components/user/detail.vue';
import Seats from '@/views/admin/seats.vue';

const SEAT = { granted_on: '2026-01-15T00:00:00Z', id: 1, role: 'standard', status: 'active', username: 'bob' };

beforeEach(() => {
  vi.clearAllMocks();
  mockAuth.getSession.mockReturnValue({ database: 'PROD', role: 'admin', user: { username: 'admin.bob' } });
  AppAPI.Seat.seats.mockResolvedValue([SEAT]);
  AppAPI.Seat.reinstate.mockResolvedValue({});
  AppAPI.Seat.revoke.mockResolvedValue({});
  AppAPI.Seat.setRole.mockResolvedValue({});
  AppAPI.Usage.summary.mockResolvedValue({ plan: { seats: { total: 10, used: 1 } } });
  localStorage.clear();
});

describe('Seats mount', () => {
  it('shows a loading state, then loads seats and the plan summary in parallel', async () => {
    const wrapper = mount(Seats);
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(true);

    await flushPromises();

    expect(AppAPI.Seat.seats).toHaveBeenCalled();
    expect(AppAPI.Usage.summary).toHaveBeenCalled();
    expect(wrapper.find('.orb-admin-loading').exists()).toBe(false);
    expect(wrapper.findComponent({ name: 'PlanSummary' }).props('plan')).toEqual({ seats: { total: 10, used: 1 } });
  });

  it('marks the seats tab active and shows the admin-only sidebar entry', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    expect(wrapper.findComponent(AdminTabs).props('active')).toBe('seats');
    expect(wrapper.findComponent(UserDetail).props('isAdmin')).toBe(true);
  });

  it('navigates back to chat from the sidebar button', async () => {
    const router = buildRouter('/admin/seats');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(Seats, { global: { router } });
    await flushPromises();

    await wrapper.find('.orb-new-chat-btn').trigger('click');

    expect(pushSpy).toHaveBeenCalledWith('/chat');
  });
});

describe('Seats user profile fallbacks', () => {
  it('falls back to empty connection/name and a standard role, with "?" initials, when there is no session', async () => {
    mockAuth.getSession.mockReturnValue(null);
    const wrapper = mount(Seats);
    await flushPromises();

    expect(wrapper.findComponent(UserDetail).props('connection')).toBe('');
    expect(wrapper.findComponent(UserDetail).props('name')).toBe('');
    expect(wrapper.findComponent(UserDetail).props('role')).toBe('standard');
    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('?');
  });

  it('derives two-letter initials from a two-part name', async () => {
    mockAuth.getSession.mockReturnValue({ user: { username: 'Bob Smith' } });
    const wrapper = mount(Seats);
    await flushPromises();

    expect(wrapper.findComponent(UserDetail).props('initials')).toBe('BS');
  });
});

describe('Seats load errors', () => {
  it('leaves the seat list empty when the seats API errors', async () => {
    AppAPI.Seat.seats.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = wrapper.findComponent(List).props('loader');

    const result = await loader({ filters: {}, limit: 20, offset: 0, sorter: {} });

    expect(result.results).toEqual([]);
  });

  it('leaves the plan summary null when the usage summary API errors', async () => {
    AppAPI.Usage.summary.mockResolvedValue({ errors: [{ detail: 'boom' }] });
    const wrapper = mount(Seats);
    await flushPromises();

    expect(wrapper.findComponent({ name: 'PlanSummary' }).props('plan')).toBeNull();
  });
});

describe('Seats theme and logout', () => {
  it('persists a theme change', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', true);
    expect(localStorage.getItem('orb-theme')).toBe('dark');
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('dark');

    await wrapper.findComponent(UserDetail).vm.$emit('theme-change', false);
    expect(localStorage.getItem('orb-theme')).toBe('light');
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('light');
  });

  it('signs out and navigates home on logout', async () => {
    const router = buildRouter('/admin/seats');
    await router.isReady();
    const pushSpy = vi.spyOn(router, 'push');
    const wrapper = mount(Seats, { global: { router } });
    await flushPromises();

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');

    expect(mockAuth.signout).toHaveBeenCalled();
    expect(pushSpy).toHaveBeenCalledWith('/');
  });
});

describe('Seats action error handling', () => {
  it('shows a translated error and does not refresh when an action fails with a known code', async () => {
    AppAPI.Seat.revoke.mockResolvedValue({ errors: [{ detail: 'CANNOT_REVOKE_SELF' }] });
    const wrapper = mount(Seats);
    await flushPromises();
    AppAPI.Seat.seats.mockClear();

    const revokeSwitch = wrapper.findComponent(List).props('columns').find((c) => c.key === 'revoke');
    revokeSwitch.render(null, SEAT).props.onChange(false);
    await flushPromises();

    expect(wrapper.find('.orb-admin-error').text()).toContain('You cannot revoke your own seat.');
    expect(AppAPI.Seat.seats).not.toHaveBeenCalled();
  });

  it('falls back to the raw error / a generic code when no known detail is present', async () => {
    AppAPI.Seat.revoke.mockResolvedValue({ errors: [{ error: 'weird_code' }] });
    const wrapper = mount(Seats);
    await flushPromises();

    const revokeSwitch = wrapper.findComponent(List).props('columns').find((c) => c.key === 'revoke');
    revokeSwitch.render(null, SEAT).props.onChange(false);
    await flushPromises();
    expect(wrapper.find('.orb-admin-error').text()).toBe('weird_code');

    AppAPI.Seat.revoke.mockResolvedValue({ errors: [{}] });
    revokeSwitch.render(null, SEAT).props.onChange(false);
    await flushPromises();
    expect(wrapper.find('.orb-admin-error').text()).toBe('ERROR');
  });
});

describe('Seats table columns', () => {
  it('renders the role label via the role render function', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const roleColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'role');
    expect(roleColumn.render('standard')).toBe('Standard user');
    expect(roleColumn.render('admin')).toBe('Administrator');
  });

  it('renders a status badge reflecting active/revoked state', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const statusColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'status');

    const active = statusColumn.render(null, { status: 'active' });
    expect(active.props.class).toContain('orb-status-active');

    const revoked = statusColumn.render(null, { status: 'revoked' });
    expect(revoked.props.class).toContain('orb-status-revoked');
  });

  it('renders granted_on as a localized date', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const grantedColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'granted_on');
    expect(grantedColumn.render('2026-01-15T00:00:00Z')).toBe(new Date('2026-01-15T00:00:00Z').toLocaleDateString());
  });

  it('disables the revoke/demote switches for the currently signed-in user', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const self = { ...SEAT, username: 'admin.bob' };
    const revokeColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'revoke');
    const demoteColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'demote');

    expect(revokeColumn.render(null, self).props.disabled).toBe(true);
    expect(demoteColumn.render(null, self).props.disabled).toBe(true);
    expect(revokeColumn.render(null, SEAT).props.disabled).toBe(false);
  });

  it('reinstates a revoked seat when the revoke switch is turned on', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const revokeColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'revoke');

    await revokeColumn.render(null, SEAT).props.onChange(true);

    expect(AppAPI.Seat.reinstate).toHaveBeenCalledWith('bob');
  });

  it('revokes an active seat when the revoke switch is turned off', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const revokeColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'revoke');

    await revokeColumn.render(null, SEAT).props.onChange(false);

    expect(AppAPI.Seat.revoke).toHaveBeenCalledWith('bob');
  });

  it('promotes/demotes a seat via the demote switch', async () => {
    const wrapper = mount(Seats);
    await flushPromises();
    const demoteColumn = wrapper.findComponent(List).props('columns').find((c) => c.key === 'demote');

    await demoteColumn.render(null, SEAT).props.onChange(true);
    expect(AppAPI.Seat.setRole).toHaveBeenCalledWith('bob', 'admin');

    await demoteColumn.render(null, SEAT).props.onChange(false);
    expect(AppAPI.Seat.setRole).toHaveBeenCalledWith('bob', 'standard');
  });
});

describe('Seats client-side seatLoader', () => {
  const rows = [
    { granted_on: '2026-01-01T00:00:00Z', id: 1, role: 'standard', status: 'active', username: 'alice' },
    { granted_on: '2026-01-10T00:00:00Z', id: 2, role: 'admin', status: 'revoked', username: 'bob' },
    { granted_on: '2026-01-20T00:00:00Z', id: 3, role: 'standard', status: 'active', username: 'carol' },
  ];

  const seatLoader = async (wrapper) => wrapper.findComponent(List).props('loader');

  it('filters by username substring', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: { username__icontains: 'AL' }, limit: 20, offset: 0, sorter: {} });
    expect(result.results.map((r) => r.username)).toEqual(['alice']);
  });

  it('filters by a single role', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: { role: 'admin' }, limit: 20, offset: 0, sorter: {} });
    expect(result.results.map((r) => r.username)).toEqual(['bob']);
  });

  it('filters by multiple roles via role__in', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: { role__in: ['admin'] }, limit: 20, offset: 0, sorter: {} });
    expect(result.results.map((r) => r.username)).toEqual(['bob']);
  });

  it('filters by a single status', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: { status: 'revoked' }, limit: 20, offset: 0, sorter: {} });
    expect(result.results.map((r) => r.username)).toEqual(['bob']);
  });

  it('filters by multiple statuses via status__in', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: { status__in: ['revoked'] }, limit: 20, offset: 0, sorter: {} });
    expect(result.results.map((r) => r.username)).toEqual(['bob']);
  });

  it('filters by a granted_on date range', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({
      filters: { granted_on__gte: '2026-01-05', granted_on__lte: '2026-01-15' },
      limit: 20,
      offset: 0,
      sorter: {},
    });
    expect(result.results.map((r) => r.username)).toEqual(['bob']);
  });

  it('sorts ascending and descending by the requested field', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const asc = await loader({ filters: {}, limit: 20, offset: 0, sorter: { field: 'username', order: 'ascend' } });
    expect(asc.results.map((r) => r.username)).toEqual(['alice', 'bob', 'carol']);

    const desc = await loader({ filters: {}, limit: 20, offset: 0, sorter: { field: 'username', order: 'descend' } });
    expect(desc.results.map((r) => r.username)).toEqual(['carol', 'bob', 'alice']);
  });

  it('sorts starting from unordered input, including equal-valued rows', async () => {
    // The shared `rows` fixture is already username-ascending, so a sort over it
    // never actually needs to reorder anything — every comparison short-circuits
    // on the ">" branch. Shuffled input (plus a tie) exercises the "<" and "="
    // branches of the comparator too.
    const shuffled = [
      { granted_on: '2026-01-20T00:00:00Z', id: 3, role: 'standard', status: 'active', username: 'carol' },
      { granted_on: '2026-01-10T00:00:00Z', id: 2, role: 'admin', status: 'revoked', username: 'bob' },
      { granted_on: '2026-01-01T00:00:00Z', id: 1, role: 'standard', status: 'active', username: 'alice' },
      { granted_on: '2026-01-05T00:00:00Z', id: 4, role: 'standard', status: 'active', username: 'bob' },
    ];
    AppAPI.Seat.seats.mockResolvedValue(shuffled);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: {}, limit: 20, offset: 0, sorter: { field: 'username', order: 'ascend' } });

    expect(result.results.map((r) => r.username)).toEqual(['alice', 'bob', 'bob', 'carol']);
  });

  it('paginates using limit/offset', async () => {
    AppAPI.Seat.seats.mockResolvedValue(rows);
    const wrapper = mount(Seats);
    await flushPromises();
    const loader = await seatLoader(wrapper);

    const result = await loader({ filters: {}, limit: 1, offset: 1, sorter: {} });
    expect(result.count).toBe(3);
    expect(result.results).toHaveLength(1);
  });
});
