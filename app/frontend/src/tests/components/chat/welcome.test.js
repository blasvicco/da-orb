// Libs imports
import { describe, expect, it } from 'vitest';

// App imports
import { mount } from '@/tests/helpers/mount';
import ChatWelcome from '@/components/chat/welcome.vue';

describe('ChatWelcome', () => {
  it('greets the user by name', () => {
    const wrapper = mount(ChatWelcome, { props: { userName: 'Bob' } });
    expect(wrapper.find('.orb-welcome-title').text()).toContain('Bob');
  });

  it('emits suggestion with the prompt key for each suggestion card', async () => {
    const wrapper = mount(ChatWelcome);
    const cards = wrapper.findAll('.orb-suggestion-card');
    expect(cards).toHaveLength(3);

    await cards[0].trigger('click');
    expect(wrapper.emitted('suggestion')[0]).toEqual(['chat.suggestions.createPR.prompt']);

    await cards[1].trigger('click');
    expect(wrapper.emitted('suggestion')[1]).toEqual(['chat.suggestions.openPRs.prompt']);

    await cards[2].trigger('click');
    expect(wrapper.emitted('suggestion')[2]).toEqual(['chat.suggestions.myRecentPR.prompt']);
  });
});
