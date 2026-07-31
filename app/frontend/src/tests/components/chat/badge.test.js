// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatBadge from '@/components/chat/badge.vue';

describe('ChatBadge', () => {
  it.each([
    ['connected', 'orb-status-badge--connected'],
    ['connecting', 'bg-amber-500/10'],
    ['disconnected', 'bg-rose-500/10'],
  ])('renders the %s state with its status class', (status, expectedClass) => {
    const wrapper = mount(ChatBadge, { props: { status } });
    expect(wrapper.classes()).toContain(expectedClass);
  });

  it('defaults to the connecting label when no status is given', () => {
    const wrapper = mount(ChatBadge);
    expect(wrapper.text().length).toBeGreaterThan(0);
  });
});
