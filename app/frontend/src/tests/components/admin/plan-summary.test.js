// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import PlanSummary from '@/components/admin/plan-summary.vue';

describe('PlanSummary severity levels (tag variant)', () => {
  it.each([
    ['well under the limit renders an info tag', { total: 100, used: 10 }, 'blue'],
    ['within 25% of the limit renders a warning tag', { total: 100, used: 80 }, 'gold'],
    ['within 5% of the limit renders an error tag', { total: 100, used: 97 }, 'red'],
  ])('%s', (_label, seats, expectedColor) => {
    const wrapper = mount(PlanSummary, { props: { plan: { seats }, variant: 'tag' } });
    const tag = wrapper.findComponent({ name: 'ATag' });
    expect(tag.props('color')).toBe(expectedColor);
  });

  it('formats the label as used / total (remaining)', () => {
    const wrapper = mount(PlanSummary, { props: { plan: { seats: { total: 10, used: 3 } }, variant: 'tag' } });
    expect(wrapper.findComponent({ name: 'ATag' }).text()).toContain('3');
    expect(wrapper.findComponent({ name: 'ATag' }).text()).toContain('10');
    expect(wrapper.findComponent({ name: 'ATag' }).text()).toContain('7');
  });

  it('treats a missing metric as 0/0 and never divides by zero', () => {
    const wrapper = mount(PlanSummary, { props: { plan: {}, variant: 'tag' } });
    expect(wrapper.findComponent({ name: 'ATag' }).props('color')).toBe('blue');
  });

  it('floors remaining at 0 when usage exceeds the total', () => {
    const wrapper = mount(PlanSummary, {
      props: { plan: { seats: { total: 10, used: 15 } }, variant: 'tag' } ,
    });
    expect(wrapper.findComponent({ name: 'ATag' }).text()).toContain('(0)');
  });
});

describe('PlanSummary progress variant', () => {
  it('renders the plain value and a progress bar capped at 100%', () => {
    const wrapper = mount(PlanSummary, {
      props: { plan: { tokens: { total: 100, used: 150 } }, variant: 'progress' },
    });
    expect(wrapper.findComponent({ name: 'ATag' }).exists()).toBe(false);
    expect(wrapper.find('.orb-plan-summary-value').exists()).toBe(true);
    const progresses = wrapper.findAllComponents({ name: 'AProgress' });
    expect(progresses.some((p) => p.props('percent') === 100)).toBe(true);
  });

  it('reports 0% progress when the total is 0', () => {
    const wrapper = mount(PlanSummary, { props: { plan: {}, variant: 'progress' } });
    const progresses = wrapper.findAllComponents({ name: 'AProgress' });
    expect(progresses.every((p) => p.props('percent') === 0)).toBe(true);
  });
});
