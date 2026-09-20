// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import AdminTabs from '@/components/admin/tabs.vue';

describe('AdminTabs', () => {
  it('renders both tabs', () => {
    const wrapper = mount(AdminTabs, { props: { active: 'seats' } });
    const links = wrapper.findAll('a');
    expect(links).toHaveLength(2);
  });

  it('marks the seats tab active when active="seats"', () => {
    const wrapper = mount(AdminTabs, { props: { active: 'seats' } });
    const [seats, usage] = wrapper.findAll('a');
    expect(seats.classes()).toContain('orb-admin-tab-active');
    expect(usage.classes()).not.toContain('orb-admin-tab-active');
  });

  it('marks the usage tab active when active="usage"', () => {
    const wrapper = mount(AdminTabs, { props: { active: 'usage' } });
    const [seats, usage] = wrapper.findAll('a');
    expect(usage.classes()).toContain('orb-admin-tab-active');
    expect(seats.classes()).not.toContain('orb-admin-tab-active');
  });
});
