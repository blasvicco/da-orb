// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import UserDetail from '@/components/user/detail.vue';

describe('UserDetail rendering', () => {
  it('renders the name and initials', () => {
    const wrapper = mount(UserDetail, { props: { initials: 'BV', name: 'Bob' } });
    expect(wrapper.find('.orb-user-name').text()).toBe('Bob');
    expect(wrapper.find('.orb-user-avatar').text()).toBe('BV');
  });

  it.each([
    ['admin', 'admin'],
    ['standard', 'standard'],
  ])('labels the %s role appropriately', (role) => {
    const wrapper = mount(UserDetail, { props: { role } });
    expect(wrapper.find('.orb-user-role').text()).not.toBe('');
  });

  it('shows the connection line only when a connection is given', () => {
    const withConnection = mount(UserDetail, { props: { connection: 'TESTDB' } });
    expect(withConnection.find('.orb-user-connection').exists()).toBe(true);

    const withoutConnection = mount(UserDetail, { props: {} });
    expect(withoutConnection.find('.orb-user-connection').exists()).toBe(false);
  });

  it('shows the admin panel link only for admins', () => {
    const admin = mount(UserDetail, { props: { isAdmin: true } });
    expect(admin.find('.orb-admin-link-btn').exists()).toBe(true);

    const standard = mount(UserDetail, { props: { isAdmin: false } });
    expect(standard.find('.orb-admin-link-btn').exists()).toBe(false);
  });
});

describe('UserDetail events', () => {
  it('forwards theme-change and expertise-change from the Settings child', async () => {
    const wrapper = mount(UserDetail, { props: {} });
    const settings = wrapper.findComponent({ name: 'Settings' });

    await settings.vm.$emit('theme-change', true);
    await settings.vm.$emit('expertise-change', 3);

    expect(wrapper.emitted('theme-change')[0]).toEqual([true]);
    expect(wrapper.emitted('expertise-change')[0]).toEqual([3]);
  });

  it('emits logout when the sign-out confirmation is accepted', async () => {
    const wrapper = mount(UserDetail, { props: {} });

    await wrapper.findComponent({ name: 'APopconfirm' }).vm.$emit('confirm');

    expect(wrapper.emitted('logout')).toHaveLength(1);
  });
});
