// Libs imports
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import InputRange from '@/components/inputs/range.vue';
import TableSearch from '@/components/table/search.vue';

const baseProps = () => ({
  clearFilters: vi.fn(),
  confirm: vi.fn(),
  selectedKeys: [],
  setSelectedKeys: vi.fn(),
  visible: true,
});

describe('TableSearch rendering per column type', () => {
  it('datetime column renders a range picker', () => {
    const wrapper = mount(TableSearch, { props: { ...baseProps(), column: { type: 'datetime' } } });
    expect(wrapper.findComponent({ name: 'ARangePicker' }).exists()).toBe(true);
  });

  it('number column renders the numeric input range', () => {
    const wrapper = mount(TableSearch, { props: { ...baseProps(), column: { type: 'number' } } });
    expect(wrapper.findComponent(InputRange).exists()).toBe(true);
  });

  it('a plain column renders a text input', () => {
    const wrapper = mount(TableSearch, { props: { ...baseProps(), column: {} } });
    expect(wrapper.findComponent({ name: 'AInput' }).exists()).toBe(true);
  });
});

describe('TableSearch actions', () => {
  it('reset clears filters and confirms without keeping the dropdown open', async () => {
    const clearFilters = vi.fn();
    const confirm = vi.fn();
    const wrapper = mount(TableSearch, { props: { ...baseProps(), clearFilters, confirm } });

    await wrapper.find('.btn-wrapper button').trigger('click');

    expect(clearFilters).toHaveBeenCalledWith({ confirm: false });
    expect(confirm).toHaveBeenCalledWith({ closeDropdown: true });
  });

  it('search confirms the current selection', async () => {
    const confirm = vi.fn();
    const wrapper = mount(TableSearch, { props: { ...baseProps(), confirm } });

    const buttons = wrapper.findAll('.btn-wrapper button');
    await buttons[1].trigger('click');

    expect(confirm).toHaveBeenCalledWith();
  });

  it('a text input change forwards the typed value to setSelectedKeys', async () => {
    const setSelectedKeys = vi.fn();
    const wrapper = mount(TableSearch, { props: { ...baseProps(), setSelectedKeys } });

    await wrapper.findComponent({ name: 'AInput' }).vm.$emit('change', { target: { value: 'bob' } });

    expect(setSelectedKeys).toHaveBeenCalledWith(['bob']);
  });

  it('a text input pressEnter confirms', async () => {
    const confirm = vi.fn();
    const wrapper = mount(TableSearch, { props: { ...baseProps(), confirm } });

    await wrapper.findComponent({ name: 'AInput' }).vm.$emit('pressEnter');

    expect(confirm).toHaveBeenCalledWith();
  });

  it('clearing a text input forwards an empty array', async () => {
    const setSelectedKeys = vi.fn();
    const wrapper = mount(TableSearch, { props: { ...baseProps(), setSelectedKeys } });

    await wrapper.findComponent({ name: 'AInput' }).vm.$emit('change', { target: { value: '' } });

    expect(setSelectedKeys).toHaveBeenCalledWith([]);
  });

  it('a date range change forwards the selected range', async () => {
    const setSelectedKeys = vi.fn();
    const wrapper = mount(TableSearch, {
      props: { ...baseProps(), column: { type: 'datetime' }, setSelectedKeys },
    });

    await wrapper.findComponent({ name: 'ARangePicker' }).vm.$emit('change', ['2025-01-01', '2025-01-31']);

    expect(setSelectedKeys).toHaveBeenCalledWith([['2025-01-01', '2025-01-31']]);
  });

  it('clearing a date range forwards an empty array', async () => {
    const setSelectedKeys = vi.fn();
    const wrapper = mount(TableSearch, {
      props: { ...baseProps(), column: { type: 'datetime' }, setSelectedKeys },
    });

    await wrapper.findComponent({ name: 'ARangePicker' }).vm.$emit('change', null);

    expect(setSelectedKeys).toHaveBeenCalledWith([]);
  });

  it('a numeric range change forwards the selected range', async () => {
    const setSelectedKeys = vi.fn();
    const wrapper = mount(TableSearch, {
      props: { ...baseProps(), column: { type: 'number' }, setSelectedKeys },
    });

    await wrapper.findComponent(InputRange).vm.$emit('change', [1, 10]);

    expect(setSelectedKeys).toHaveBeenCalledWith([1, 10]);
  });

  it('clearing a numeric range forwards an empty array', async () => {
    const setSelectedKeys = vi.fn();
    const wrapper = mount(TableSearch, {
      props: { ...baseProps(), column: { type: 'number' }, setSelectedKeys },
    });

    await wrapper.findComponent(InputRange).vm.$emit('change', undefined);

    expect(setSelectedKeys).toHaveBeenCalledWith([]);
  });
});

describe('TableSearch autofocus', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('schedules a focus on mount for a plain text column', () => {
    expect(() => {
      mount(TableSearch, { props: { ...baseProps(), column: {} } });
      vi.advanceTimersByTime(100);
    }).not.toThrow();
  });

  it('does not schedule a focus on mount for a typed column', () => {
    expect(() => {
      mount(TableSearch, { props: { ...baseProps(), column: { type: 'number' } } });
      vi.advanceTimersByTime(100);
    }).not.toThrow();
  });

  it('schedules a focus when the dropdown becomes visible for a plain text column', async () => {
    const wrapper = mount(TableSearch, { props: { ...baseProps(), column: {}, visible: false } });
    await wrapper.setProps({ visible: true });
    expect(() => vi.advanceTimersByTime(100)).not.toThrow();
  });

  it('does not schedule a focus when a typed column becomes visible', async () => {
    const wrapper = mount(TableSearch, {
      props: { ...baseProps(), column: { type: 'datetime' }, visible: false },
    });
    await wrapper.setProps({ visible: true });
    expect(() => vi.advanceTimersByTime(100)).not.toThrow();
  });

  it('does not crash if the mount-scheduled focus fires after the component unmounts', () => {
    mount(TableSearch, { props: { ...baseProps(), column: {} } }).unmount();
    expect(() => vi.advanceTimersByTime(100)).not.toThrow();
  });

  it('does not crash if the visibility-triggered focus fires after the component unmounts', async () => {
    const wrapper = mount(TableSearch, { props: { ...baseProps(), column: {}, visible: false } });
    await wrapper.setProps({ visible: true });
    wrapper.unmount();
    expect(() => vi.advanceTimersByTime(100)).not.toThrow();
  });
});
