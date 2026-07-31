// Libs imports
import { describe, expect, it, vi } from 'vitest';

// Mocks
vi.mock('@/modules/organization', () => ({
  useOrganization: () => ({
    getContext: vi.fn().mockReturnValue({}),
    hasOrganization: vi.fn().mockReturnValue(null),
    load: vi.fn().mockResolvedValue(),
  }),
}));

// App imports
import { mount } from '@/tests/helpers/mount';
import Privacy from '@/views/privacy.vue';

describe('Privacy view', () => {
  it('renders the title and every legal section', () => {
    const wrapper = mount(Privacy);
    expect(wrapper.find('.orb-legal-title').text()).toBe('Privacy Policy');
    expect(wrapper.findAll('.orb-legal-section')).toHaveLength(10);
  });
});
