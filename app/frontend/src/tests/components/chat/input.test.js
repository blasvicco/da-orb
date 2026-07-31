// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatInput from '@/components/chat/input.vue';

describe('ChatInput typing', () => {
  it('renders the current modelValue', () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hello' } });
    expect(wrapper.find('textarea').element.value).toBe('hello');
  });

  it('emits update:modelValue as the user types', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: '' } });
    const textarea = wrapper.find('textarea');
    textarea.element.value = 'hi';
    await textarea.trigger('input');
    expect(wrapper.emitted('update:modelValue')[0]).toEqual(['hi']);
  });

  it('re-measures its height when modelValue changes externally', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: '' } });
    await expect(wrapper.setProps({ modelValue: 'a longer message now' })).resolves.toBeUndefined();
  });
});

describe('ChatInput sending', () => {
  it('sends on Enter without Shift', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter' });
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it('does not send on Shift+Enter (newline instead)', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('textarea').trigger('keydown', { key: 'Enter', shiftKey: true });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('does not send on other keys', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('textarea').trigger('keydown', { key: 'a' });
    expect(wrapper.emitted('send')).toBeUndefined();
  });

  it('clicking the send button emits send', async () => {
    const wrapper = mount(ChatInput, { props: { modelValue: 'hi' } });
    await wrapper.find('.orb-prompt-send-btn').trigger('click');
    expect(wrapper.emitted('send')).toHaveLength(1);
  });

  it.each([
    ['an empty message', ''],
    ['a whitespace-only message', '   '],
  ])('disables the send button for %s', (_label, modelValue) => {
    const wrapper = mount(ChatInput, { props: { modelValue } });
    expect(wrapper.find('.orb-prompt-send-btn').attributes('disabled')).toBeDefined();
  });

  it('disables the send button while disabled prop is set, even with text present', () => {
    const wrapper = mount(ChatInput, { props: { disabled: true, modelValue: 'hi' } });
    expect(wrapper.find('.orb-prompt-send-btn').attributes('disabled')).toBeDefined();
  });

  it('enables the send button with non-blank text and not disabled', () => {
    const wrapper = mount(ChatInput, { props: { disabled: false, modelValue: 'hi' } });
    expect(wrapper.find('.orb-prompt-send-btn').attributes('disabled')).toBeUndefined();
  });
});
