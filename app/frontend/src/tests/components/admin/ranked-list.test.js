// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import RankedList from '@/components/admin/ranked-list.vue';

describe('RankedList', () => {
  it('renders the title', () => {
    const wrapper = mount(RankedList, { props: { items: [], title: 'Most active' } });
    expect(wrapper.find('.orb-usage-card-title').text()).toBe('Most active');
  });

  it('shows the empty label when there are no items', () => {
    const wrapper = mount(RankedList, { props: { emptyLabel: 'No data yet', items: [], title: 'x' } });
    expect(wrapper.find('.orb-usage-empty').text()).toBe('No data yet');
    expect(wrapper.find('.orb-usage-ranked-list').exists()).toBe(false);
  });

  it('renders one row per item, scaling bar width against the largest value', () => {
    const wrapper = mount(RankedList, {
      props: {
        items: [{ label: 'bob', value: 100 }, { label: 'alice', value: 50 }],
        title: 'x',
      },
    });
    const rows = wrapper.findAll('.orb-usage-ranked-item');
    expect(rows).toHaveLength(2);
    expect(rows[0].find('.orb-usage-ranked-bar-fill').attributes('style')).toContain('100%');
    expect(rows[1].find('.orb-usage-ranked-bar-fill').attributes('style')).toContain('50%');
  });

  it('prefers displayValue over the raw value for the label', () => {
    const wrapper = mount(RankedList, {
      props: { items: [{ displayValue: '1.2k', label: 'bob', value: 1200 }], title: 'x' },
    });
    expect(wrapper.find('.orb-usage-ranked-value').text()).toBe('1.2k');
  });

  it('falls back to the raw value when displayValue is absent', () => {
    const wrapper = mount(RankedList, {
      props: { items: [{ label: 'bob', value: 42 }], title: 'x' },
    });
    expect(wrapper.find('.orb-usage-ranked-value').text()).toBe('42');
  });

  it('never divides by zero when every value is 0', () => {
    const wrapper = mount(RankedList, {
      props: { items: [{ label: 'bob', value: 0 }], title: 'x' },
    });
    expect(wrapper.find('.orb-usage-ranked-bar-fill').attributes('style')).toContain('0%');
  });
});
