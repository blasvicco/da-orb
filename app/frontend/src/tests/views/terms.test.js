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
import Terms from '@/views/terms.vue';

describe('Terms view', () => {
  it('renders the title and every legal section', () => {
    const wrapper = mount(Terms);
    expect(wrapper.find('.orb-legal-title').text()).toBe('Terms of Service');
    expect(wrapper.findAll('.orb-legal-section')).toHaveLength(10);
  });
});
