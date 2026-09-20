// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatLayout from '@/layouts/chat.vue';

describe('ChatLayout', () => {
  it('defaults to the light theme', () => {
    const wrapper = mount(ChatLayout);
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('light');
  });

  it('reflects a custom theme', () => {
    const wrapper = mount(ChatLayout, { props: { theme: 'dark' } });
    expect(wrapper.find('.orb-chat-layout').attributes('data-theme')).toBe('dark');
  });

  it('renders the sidebar-top, sidebar-bottom, and default slots in their own regions', () => {
    const wrapper = mount(ChatLayout, {
      slots: {
        default: '<div class="main-content">Main</div>',
        'sidebar-bottom': '<div class="bottom-content">Bottom</div>',
        'sidebar-top': '<div class="top-content">Top</div>',
      },
    });

    expect(wrapper.find('.orb-sidebar-top .top-content').exists()).toBe(true);
    expect(wrapper.find('.orb-sidebar .bottom-content').exists()).toBe(true);
    expect(wrapper.find('.orb-chat-pane .main-content').exists()).toBe(true);
  });
});
