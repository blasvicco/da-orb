// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import SessionItem from '@/components/chat/session-item.vue';

const daysAgo = (n) => {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
};

describe('SessionItem title / active state', () => {
  it('falls back to an untitled label when the session has no title', () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 1, title: '' } } });
    expect(wrapper.find('.orb-history-title').text().length).toBeGreaterThan(0);
  });

  it('renders the session title when present', () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 1, title: 'My chat' } } });
    expect(wrapper.find('.orb-history-title').text()).toBe('My chat');
  });

  it('marks the dot active only when this session is the active one', () => {
    const active = mount(SessionItem, { props: { activeSessionId: 1, session: { id: 1, title: 'x' } } });
    expect(active.find('svg').classes()).toContain('orb-session-dot--active');

    const inactive = mount(SessionItem, { props: { activeSessionId: 2, session: { id: 1, title: 'x' } } });
    expect(inactive.find('svg').classes()).toContain('orb-session-dot--inactive');
  });

  it('shows a pending indicator instead of the status dot while pending', () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 1, pending: true, title: 'x' } } });
    expect(wrapper.find('.orb-history-pending-dot').exists()).toBe(true);
    // Scoped to the status icon slot — DeleteOutlined elsewhere in the template is also an <svg>.
    expect(wrapper.find('.orb-history-icon svg').exists()).toBe(false);
  });
});

describe('SessionItem date formatting', () => {
  it('shows nothing when the session has no updated_on', () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 1, title: 'x' } } });
    expect(wrapper.find('.orb-history-date').exists()).toBe(false);
  });

  it("shows the yesterday label for yesterday's session", () => {
    const wrapper = mount(SessionItem, {
      props: { session: { id: 1, title: 'x', updated_on: daysAgo(1) } },
    });
    expect(wrapper.find('.orb-history-date').exists()).toBe(true);
  });

  it('shows a formatted date for an older session', () => {
    const wrapper = mount(SessionItem, {
      props: { session: { id: 1, title: 'x', updated_on: daysAgo(10) } },
    });
    expect(wrapper.find('.orb-history-date').text().length).toBeGreaterThan(0);
  });

  it("shows a time for today's session", () => {
    const wrapper = mount(SessionItem, {
      props: { session: { id: 1, title: 'x', updated_on: new Date().toISOString() } },
    });
    expect(wrapper.find('.orb-history-date').text().length).toBeGreaterThan(0);
  });
});

describe('SessionItem tokens', () => {
  it('shows the token count only when tokens_used is set', () => {
    const withTokens = mount(SessionItem, {
      props: { session: { id: 1, title: 'x', tokens_used: 500 } },
    });
    expect(withTokens.find('.orb-history-tokens').exists()).toBe(true);

    const withoutTokens = mount(SessionItem, { props: { session: { id: 1, title: 'x' } } });
    expect(withoutTokens.find('.orb-history-tokens').exists()).toBe(false);
  });
});

describe('SessionItem interactions', () => {
  it('emits select when the row is clicked', async () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });
    await wrapper.find('.orb-history-item').trigger('click');
    expect(wrapper.emitted('select')[0]).toEqual([7]);
  });

  it('opens the delete confirm without selecting when the delete icon is clicked', async () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });

    await wrapper.findComponent({ name: 'DeleteOutlined' }).trigger('click');

    expect(wrapper.emitted('select')).toBeUndefined();
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(true);
  });

  it('does not emit select while the delete confirm is open', async () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });
    await wrapper.findComponent({ name: 'DeleteOutlined' }).trigger('click');

    await wrapper.find('.orb-history-item').trigger('click');

    expect(wrapper.emitted('select')).toBeUndefined();
  });

  it('emits delete and closes the confirm on confirmation', async () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });
    await wrapper.findComponent({ name: 'DeleteOutlined' }).trigger('click');

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');

    expect(wrapper.emitted('delete')[0]).toEqual([7]);
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('closes the confirm without emitting delete on cancel', async () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });
    await wrapper.findComponent({ name: 'DeleteOutlined' }).trigger('click');

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('cancel');

    expect(wrapper.emitted('delete')).toBeUndefined();
    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('closes the confirm when its openChange reports closed', async () => {
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });
    await wrapper.findComponent({ name: 'DeleteOutlined' }).trigger('click');

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('openChange', false);

    expect(wrapper.findComponent({ name: 'APopconfirm' }).props('open')).toBe(false);
  });

  it('shows the delete icon on hover even without an active confirm', async () => {
    // v-show leaves the style attribute unset while visible (it only ever writes
    // "display: none"), so the visible case must tolerate an absent attribute.
    const wrapper = mount(SessionItem, { props: { session: { id: 7, title: 'x' } } });

    await wrapper.find('.orb-history-item').trigger('mouseenter');
    expect(wrapper.findComponent({ name: 'DeleteOutlined' }).attributes('style') || '').not.toContain('display: none');

    await wrapper.find('.orb-history-item').trigger('mouseleave');
    expect(wrapper.findComponent({ name: 'DeleteOutlined' }).attributes('style')).toContain('display: none');
  });
});
