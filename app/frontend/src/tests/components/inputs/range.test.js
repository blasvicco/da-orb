// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import InputRange from '@/components/inputs/range.vue';

const inputs = (wrapper) => wrapper.findAllComponents({ name: 'AInputNumber' });

describe('InputRange', () => {
  it('renders two number inputs seeded from value/placeholder props', () => {
    const wrapper = mount(InputRange, {
      props: { placeholder: ['min', 'max'], value: [10, 20] },
    });
    const fields = inputs(wrapper);
    expect(fields).toHaveLength(2);
    expect(fields[0].props('value')).toBe(10);
    expect(fields[1].props('value')).toBe(20);
  });

  it('emits [raw, value[1]] when the first field changes', async () => {
    const wrapper = mount(InputRange, { props: { value: [10, 20] } });
    await inputs(wrapper)[0].vm.$emit('change', 15);
    expect(wrapper.emitted('change')[0]).toEqual([[15, 20]]);
  });

  it('emits [value[0], raw] when the second field changes', async () => {
    const wrapper = mount(InputRange, { props: { value: [10, 20] } });
    await inputs(wrapper)[1].vm.$emit('change', 25);
    expect(wrapper.emitted('change')[0]).toEqual([[10, 25]]);
  });

  it('treats a cleared field as undefined, keeping the other bound', async () => {
    const wrapper = mount(InputRange, { props: { value: [10, 20] } });
    await inputs(wrapper)[0].vm.$emit('change', '');
    expect(wrapper.emitted('change')[0]).toEqual([[undefined, 20]]);
  });

  it('emits undefined (not an array) once both fields are cleared', async () => {
    const wrapper = mount(InputRange, { props: { value: [10, undefined] } });
    await inputs(wrapper)[0].vm.$emit('change', '');
    expect(wrapper.emitted('change')[0]).toEqual([undefined]);
  });
});
