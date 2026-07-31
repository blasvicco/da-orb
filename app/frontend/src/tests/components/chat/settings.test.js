// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { body, mount } from '@/tests/helpers/mount';
import Settings from '@/components/chat/settings.vue';

// a-popover uses trigger="click" and only mounts its #content slot once opened.
const openSettings = async (wrapper) => {
  await wrapper.find('.orb-prompt-tool-btn').trigger('click');
};

describe('Settings', () => {
  it.each([
    [1, 'novice'],
    [2, 'intermediate'],
    [3, 'expert'],
  ])('labels expertise level %i as %s', async (expertiseLevel) => {
    const wrapper = mount(Settings, { props: { expertiseLevel } });
    await openSettings(wrapper);
    expect(body().find('.orb-settings-label strong').exists()).toBe(true);
  });

  it('reflects the theme prop on the dark-mode switch', async () => {
    const dark = mount(Settings, { props: { theme: 'dark' } });
    await openSettings(dark);
    expect(dark.findComponent({ name: 'ASwitch' }).props('checked')).toBe(true);

    const light = mount(Settings, { props: { theme: 'light' } });
    await openSettings(light);
    expect(light.findComponent({ name: 'ASwitch' }).props('checked')).toBe(false);
  });

  it('emits theme-change when the switch is toggled', async () => {
    const wrapper = mount(Settings, { props: { theme: 'light' } });
    await openSettings(wrapper);
    await wrapper.findComponent({ name: 'ASwitch' }).vm.$emit('change', true);
    expect(wrapper.emitted('theme-change')[0]).toEqual([true]);
  });

  it('emits expertise-change when the slider is moved', async () => {
    const wrapper = mount(Settings, { props: { expertiseLevel: 2 } });
    await openSettings(wrapper);
    await wrapper.findComponent({ name: 'ASlider' }).vm.$emit('change', 3);
    expect(wrapper.emitted('expertise-change')[0]).toEqual([3]);
  });

  it('updates its local level via the slider v-model', async () => {
    const wrapper = mount(Settings, { props: { expertiseLevel: 2 } });
    await openSettings(wrapper);
    await wrapper.findComponent({ name: 'ASlider' }).vm.$emit('update:value', 3);
    expect(wrapper.findComponent({ name: 'ASlider' }).props('value')).toBe(3);
  });

  it('syncs its local level when the expertiseLevel prop changes externally', async () => {
    const wrapper = mount(Settings, { props: { expertiseLevel: 1 } });
    await openSettings(wrapper);
    await wrapper.setProps({ expertiseLevel: 3 });
    expect(wrapper.findComponent({ name: 'ASlider' }).props('value')).toBe(3);
  });
});
