// Libs imports
import { beforeEach, describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('antdv-next', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, message: { error: vi.fn(), success: vi.fn() } };
});

// App imports
import { message } from 'antdv-next';
import { flushPromises, mount } from '@/tests/helpers/mount';
import TableList from '@/components/table/list.vue';

const table = (wrapper) => wrapper.findComponent({ name: 'ATable' });

const columns = () => [
  { dataIndex: 'username', filterDropdown: true, key: 'username', title: 'Username' },
  {
    dataIndex: 'role',
    filters: [],
    key: 'role',
    title: 'Role',
    type: 'options',
  },
  { dataIndex: 'amount', key: 'amount', title: 'Amount', type: 'number' },
  { dataIndex: 'granted_on', key: 'granted_on', title: 'Granted', type: 'datetime' },
];

describe('TableList initial load', () => {
  it('loads data on mount with the default page/filters/sorter', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 0, results: [] });
    mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    expect(loader).toHaveBeenCalledWith({ filters: {}, limit: 20, offset: 0, sorter: {} });
  });

  it('renders the returned rows and updates the pagination total', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 1, results: [{ id: 1, username: 'bob' }] });
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    expect(table(wrapper).props('dataSource')).toEqual([{ id: 1, username: 'bob' }]);
    expect(table(wrapper).props('pagination').total).toBe(1);
  });
});

describe('TableList onChange filter translation', () => {
  let loader;

  beforeEach(() => {
    loader = vi.fn().mockResolvedValue({ count: 0, results: [] });
  });

  it('translates a plain text filter using the default icontains lookup', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 1, pageSize: 20 }, { username: 'bob' }, {});
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { username__icontains: 'bob' } }),
    );
  });

  it('translates a datetime range filter into __gte/__lte lookups', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit(
      'change',
      { current: 1, pageSize: 20 },
      { granted_on: [['2025-01-01', '2025-01-31']] },
      {},
    );
    await flushPromises();

    const call = loader.mock.calls.at(-1)[0];
    expect(call.filters.granted_on__gte).toBe('2025-01-01');
    expect(call.filters.granted_on__lte).toBe('2025-01-31');
  });

  it('translates a single-value options filter to the plain field', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 1, pageSize: 20 }, { role: ['admin'] }, {});
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { role: ['admin'] } }),
    );
  });

  it('translates a multi-value options filter to the __in lookup', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit(
      'change',
      { current: 1, pageSize: 20 },
      { role: ['admin', 'standard'] },
      {},
    );
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { role__in: ['admin', 'standard'] } }),
    );
  });

  it('translates a partial numeric range filter, keeping only the bound that was set', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 1, pageSize: 20 }, { amount: [undefined, 100] }, {});
    await flushPromises();

    const call = loader.mock.calls.at(-1)[0];
    expect(call.filters.amount__lte).toBe(100);
  });

  it('ignores a null filter value entirely', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 1, pageSize: 20 }, { username: null }, {});
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(expect.objectContaining({ filters: {} }));
  });

  it('paginates using the requested page/pageSize', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 3, pageSize: 10 }, {}, {});
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(
      expect.objectContaining({ limit: 10, offset: 20 }),
    );
  });

  it('forwards the sorter unchanged to the loader', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    const sorter = { field: 'username', order: 'descend' };
    await table(wrapper).vm.$emit('change', { current: 1, pageSize: 20 }, {}, sorter);
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(expect.objectContaining({ sorter }));
  });
});

describe('TableList error handling', () => {
  it('surfaces each API error as a translated message and stops loading', async () => {
    const loader = vi.fn()
      .mockResolvedValueOnce({ count: 0, results: [] })
      .mockResolvedValueOnce({ errors: [{ attr: 'username', detail: 'This field is required.' }] });
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 1, pageSize: 20 }, {}, {});
    await flushPromises();

    expect(message.error).toHaveBeenCalledWith('api.error.response.username.THIS_FIELD_IS_REQUIRED');
    expect(table(wrapper).props('loading')).toBe(false);
  });
});

describe('TableList filterIcon rendering', () => {
  it('marks the filter icon as filtered/unfiltered based on antd column state', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 0, results: [] });
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    const usernameColumn = table(wrapper).props('columns').find((column) => column.dataIndex === 'username');
    expect(usernameColumn.filterIcon(true).props.class).toBe('filtered');
    expect(usernameColumn.filterIcon(false).props.class).toBe('');
  });
});

describe('TableList row actions', () => {
  it('injects an actions column with edit/delete controls when actions are given and none exist', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 1, results: [{ id: 1, username: 'bob' }] });
    const editor = vi.fn();
    const remover = vi.fn().mockResolvedValue({ errors: false });
    const wrapper = mount(TableList, {
      props: { actions: { editor, remover }, columns: columns(), loader },
    });
    await flushPromises();

    const editButton = wrapper.findComponent({ name: 'EditOutlined' });
    expect(editButton.exists()).toBe(true);

    await editButton.trigger('click');
    expect(editor).toHaveBeenCalledWith({ id: 1, username: 'bob' });
  });

  it('renders only the edit control when no remover is given', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 1, results: [{ id: 1, username: 'bob' }] });
    const wrapper = mount(TableList, {
      props: { actions: { editor: vi.fn() }, columns: columns(), loader },
    });
    await flushPromises();

    expect(wrapper.findComponent({ name: 'EditOutlined' }).exists()).toBe(true);
    expect(wrapper.findComponent({ name: 'APopconfirm' }).exists()).toBe(false);
  });

  it('renders only the delete control when no editor is given', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 1, results: [{ id: 1, username: 'bob' }] });
    const wrapper = mount(TableList, {
      props: { actions: { remover: vi.fn() }, columns: columns(), loader },
    });
    await flushPromises();

    expect(wrapper.findComponent({ name: 'EditOutlined' }).exists()).toBe(false);
    expect(wrapper.findComponent({ name: 'APopconfirm' }).exists()).toBe(true);
  });

  it('does not duplicate an actions column that already exists', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 0, results: [] });
    const cols = [...columns(), { key: 'actions', title: 'Actions' }];
    const wrapper = mount(TableList, {
      props: { actions: { editor: vi.fn(), remover: vi.fn() }, columns: cols, loader },
    });
    await flushPromises();

    const actionColumns = table(wrapper).props('columns').filter((column) => column.key === 'actions');
    expect(actionColumns).toHaveLength(1);
  });

  it('removes a row on confirm and refreshes the list', async () => {
    const loader = vi.fn()
      .mockResolvedValueOnce({ count: 1, results: [{ id: 1, username: 'bob' }] })
      .mockResolvedValueOnce({ count: 0, results: [] });
    const remover = vi.fn().mockResolvedValue({ errors: false });
    const wrapper = mount(TableList, {
      props: { actions: { editor: vi.fn(), remover }, columns: columns(), loader },
    });
    await flushPromises();

    const popconfirm = wrapper.findComponent({ name: 'APopconfirm' });
    await popconfirm.vm.$emit('confirm');
    await flushPromises();

    expect(remover).toHaveBeenCalledWith(1);
    expect(loader).toHaveBeenCalledTimes(2); // initial mount load + the post-removal refresh
  });

  it('surfaces a remover error instead of refreshing the list', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 1, results: [{ id: 1, username: 'bob' }] });
    const remover = vi.fn().mockResolvedValue({
      errors: [{ attr: 'id', detail: 'Cannot delete active seat.' }],
    });
    const wrapper = mount(TableList, {
      props: { actions: { editor: vi.fn(), remover }, columns: columns(), loader },
    });
    await flushPromises();
    const callsBefore = loader.mock.calls.length;

    const popconfirm = wrapper.findComponent({ name: 'APopconfirm' });
    await popconfirm.vm.$emit('confirm');
    await flushPromises();

    expect(message.error).toHaveBeenCalledWith('api.error.response.id.CANNOT_DELETE_ACTIVE_SEAT');
    expect(loader.mock.calls.length).toBe(callsBefore);
  });
});

describe('TableList exposed refresh', () => {
  it('refresh() re-triggers the loader for the current page', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 0, results: [] });
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();
    const callsBefore = loader.mock.calls.length;

    await wrapper.vm.refresh();

    expect(loader.mock.calls.length).toBe(callsBefore + 1);
  });

  it('refresh() repeats the current filters, sorter and page, so the data matches what the table shows', async () => {
    const loader = vi.fn().mockResolvedValue({ count: 100, results: [{ id: 1, username: 'bob' }] });
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();
    const sorter = { field: 'username', order: 'ascend' };
    await table(wrapper).vm.$emit('change', { current: 3, pageSize: 20 }, { username: 'bob' }, sorter);
    await flushPromises();

    await wrapper.vm.refresh();

    expect(loader).toHaveBeenLastCalledWith({
      filters: { username__icontains: 'bob' },
      limit: 20,
      offset: 40,
      sorter,
    });
  });
});

describe('TableList page past the end', () => {
  it('steps back to the last page that exists when the requested one has no rows any more', async () => {
    // e.g. every row on page 3 was just moved to another project
    const loader = vi.fn(async ({ offset }) => (offset >= 40
      ? { count: 25, results: [] }
      : { count: 25, results: [{ id: 21, username: 'last-page' }] }));
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 3, pageSize: 20 }, {}, {});
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 }));
    expect(table(wrapper).props('dataSource')).toEqual([{ id: 21, username: 'last-page' }]);
    expect(table(wrapper).props('pagination').current).toBe(2);
  });

  it('keeps the active filters while stepping back', async () => {
    const loader = vi.fn(async ({ offset }) => (offset >= 20
      ? { count: 5, results: [] }
      : { count: 5, results: [{ id: 1, username: 'bob' }] }));
    const wrapper = mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    await table(wrapper).vm.$emit('change', { current: 2, pageSize: 20 }, { username: 'bob' }, {});
    await flushPromises();

    expect(loader).toHaveBeenLastCalledWith(
      expect.objectContaining({ filters: { username__icontains: 'bob' }, offset: 0 }),
    );
  });

  it.each([
    ['the list is genuinely empty', { count: 0, results: [] }],
    ['it is already the first page', { count: 30, results: [] }],
  ])('does not loop when %s', async (_label, response) => {
    const loader = vi.fn().mockResolvedValue(response);
    mount(TableList, { props: { columns: columns(), loader } });
    await flushPromises();

    expect(loader).toHaveBeenCalledTimes(1);
  });
});

describe('TableList shared look', () => {
  it('pins the table size, whatever the global antd config says, so every list matches', async () => {
    const wrapper = mount(TableList, { props: { columns: columns(), loader: vi.fn().mockResolvedValue({ count: 0, results: [] }) } });
    await flushPromises();

    expect(table(wrapper).props('size')).toBe('large');
  });
});

describe('TableList row selection', () => {
  it('hands the given selection config to the table', async () => {
    const rowSelection = { onChange: vi.fn(), selectedRowKeys: [1] };
    const wrapper = mount(TableList, {
      props: { columns: columns(), loader: vi.fn().mockResolvedValue({ count: 0, results: [] }), rowSelection },
    });
    await flushPromises();

    expect(table(wrapper).props('rowSelection')).toEqual(rowSelection);
  });

  it('is a plain list (no selection column) when none is given', async () => {
    const wrapper = mount(TableList, {
      props: { columns: columns(), loader: vi.fn().mockResolvedValue({ count: 0, results: [] }) },
    });
    await flushPromises();

    expect(table(wrapper).props('rowSelection')).toBeUndefined();
  });
});
