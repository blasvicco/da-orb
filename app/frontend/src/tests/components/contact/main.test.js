// Libs imports
import { beforeEach, describe, expect, it } from 'vitest';

// App imports
import { flushPromises, mount } from '@/tests/helpers/mount';
import ContactForm from '@/components/contact/main.vue';

const fillRequiredFields = async (wrapper) => {
  await wrapper.find('#contact-name').setValue('Bob');
  await wrapper.find('#contact-email').setValue('bob@example.com');
  await wrapper.find('#contact-company').setValue('Acme');
  await wrapper.find('#contact-message').setValue('Tell me more');
  await wrapper.find('label.orb-contact-consent input').setValue(true);
};

describe('ContactForm', () => {
  beforeEach(() => {
    globalThis.fetch.mockResolvedValue({ ok: true });
  });

  it('renders the form in its idle state', () => {
    const wrapper = mount(ContactForm);
    expect(wrapper.find('.orb-contact-form').exists()).toBe(true);
    expect(wrapper.find('.orb-contact-success').exists()).toBe(false);
  });

  it('submits the form payload with inquiry_type set, and shows the success view', async () => {
    const wrapper = mount(ContactForm);
    await fillRequiredFields(wrapper);

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(globalThis.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({ method: 'POST' }),
    );
    const sentBody = JSON.parse(globalThis.fetch.mock.calls[0][1].body);
    expect(sentBody).toEqual(
      expect.objectContaining({
        company: 'Acme',
        consent_given: true,
        inquiry_type: 'orb_demo',
        message: 'Tell me more',
        name: 'Bob',
        work_email: 'bob@example.com',
      }),
    );
    expect(wrapper.find('.orb-contact-success').exists()).toBe(true);
    expect(wrapper.find('.orb-contact-form').exists()).toBe(false);
  });

  it('shows an error message when the request responds with a non-ok status', async () => {
    globalThis.fetch.mockResolvedValue({ ok: false });
    const wrapper = mount(ContactForm);
    await fillRequiredFields(wrapper);

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('.orb-contact-error').exists()).toBe(true);
    expect(wrapper.find('.orb-contact-success').exists()).toBe(false);
  });

  it('shows an error message when the request itself fails', async () => {
    globalThis.fetch.mockRejectedValue(new Error('network down'));
    const wrapper = mount(ContactForm);
    await fillRequiredFields(wrapper);

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    expect(wrapper.find('.orb-contact-error').exists()).toBe(true);
  });

  it('disables the submit button while the request is in flight', async () => {
    let resolveFetch;
    globalThis.fetch.mockReturnValue(new Promise((resolve) => {
      resolveFetch = resolve;
    }));
    const wrapper = mount(ContactForm);
    await fillRequiredFields(wrapper);

    await wrapper.find('form').trigger('submit');

    expect(wrapper.find('.orb-contact-submit').attributes('disabled')).toBeDefined();

    resolveFetch({ ok: true });
    await flushPromises();
  });

  it('offers the configured role options in the role select', () => {
    const wrapper = mount(ContactForm);
    const options = wrapper.findAll('#contact-role option');
    expect(options.length).toBeGreaterThan(1);
  });

  it('includes the selected role in the submitted payload', async () => {
    const wrapper = mount(ContactForm);
    await fillRequiredFields(wrapper);
    const roleValue = wrapper.findAll('#contact-role option')[1].attributes('value');
    await wrapper.find('#contact-role').setValue(roleValue);

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    const sentBody = JSON.parse(globalThis.fetch.mock.calls[0][1].body);
    expect(sentBody.role).toBe(roleValue);
  });

  it('includes the honeypot field verbatim in the submitted payload', async () => {
    const wrapper = mount(ContactForm);
    await fillRequiredFields(wrapper);
    await wrapper.find('label.sr-only input').setValue('bot-filled');

    await wrapper.find('form').trigger('submit');
    await flushPromises();

    const sentBody = JSON.parse(globalThis.fetch.mock.calls[0][1].body);
    expect(sentBody.website).toBe('bot-filled');
  });
});
