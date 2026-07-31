// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import Processes from '@/components/chat/processes.vue';

describe('Processes', () => {
  it('renders one numbered option per process, preferring display_name over name', () => {
    const wrapper = mount(Processes, {
      props: {
        processes: [
          { display_name: 'Create Purchase Order', name: 'create_po', slug: 'create-po' },
          { name: 'approve_po', slug: 'approve-po' },
        ],
      },
    });

    const options = wrapper.findAll('.orb-process-option');
    expect(options).toHaveLength(2);
    expect(options[0].text()).toContain('Create Purchase Order');
    expect(options[1].text()).toContain('approve_po');
  });

  it('emits select with the clicked process label', async () => {
    const wrapper = mount(Processes, {
      props: { processes: [{ display_name: 'Create PO', slug: 'create-po' }] },
    });

    await wrapper.find('.orb-process-option').trigger('click');

    expect(wrapper.emitted('select')[0]).toEqual(['Create PO']);
  });

  it('emits select with the raw name when the process has no display_name', async () => {
    const wrapper = mount(Processes, {
      props: { processes: [{ name: 'approve_po', slug: 'approve-po' }] },
    });

    await wrapper.find('.orb-process-option').trigger('click');

    expect(wrapper.emitted('select')[0]).toEqual(['approve_po']);
  });

  it('renders no options for an empty process list', () => {
    const wrapper = mount(Processes);
    expect(wrapper.findAll('.orb-process-option')).toHaveLength(0);
  });
});
