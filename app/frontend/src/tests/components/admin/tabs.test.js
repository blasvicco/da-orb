// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import AdminTabs from '@/components/admin/tabs.vue';

// Fixtures
const TABS = [
  ['seats', '/admin/seats'],
  ['usage', '/admin/usage'],
  ['documentTemplates', '/admin/document-templates'],
];

describe('AdminTabs', () => {
  it('renders every tab, in order, each linking to its own admin page', () => {
    const wrapper = mount(AdminTabs, { props: { active: 'seats' } });
    expect(wrapper.findAll('a').map((link) => link.attributes('href'))).toEqual(TABS.map(([, href]) => href));
  });

  it.each(TABS)('marks only the "%s" tab active', (active, _href) => {
    const wrapper = mount(AdminTabs, { props: { active } });
    const activeIndexes = wrapper.findAll('a')
      .map((link, index) => (link.classes().includes('orb-admin-tab-active') ? index : -1))
      .filter((index) => index >= 0);
    expect(activeIndexes).toEqual([TABS.findIndex(([key]) => key === active)]);
  });

  it('marks no tab active for an unknown key', () => {
    const wrapper = mount(AdminTabs, { props: { active: 'nope' } });
    expect(wrapper.findAll('.orb-admin-tab-active')).toHaveLength(0);
  });
});
