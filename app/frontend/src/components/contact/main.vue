<script setup>
  // Libs imports
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { ExclamationCircleOutlined } from '@ant-design/icons-vue';

  // Styles
  import '@/components/contact/main.css';

  const { t, tm } = useI18n();
  const lng = 'commons.contactForm';

  const roleOptions = tm(`${lng}.roleOptions`);

  const form = ref({
    company: '',
    consent_given: false,
    message: '',
    name: '',
    role: '',
    website: '', // honeypot — must stay empty
    work_email: '',
  });

  const state = ref('idle'); // idle | submitting | success | error

  const submit = async () => {
    state.value = 'submitting';
    try {
      const response = await fetch(__APP_ENV__.LEADS_API_URL, {
        body: JSON.stringify({ ...form.value, inquiry_type: 'orb_demo' }),
        headers: { 'Content-Type': 'application/json' },
        method: 'POST',
      });
      if (!response.ok) throw new Error('request_failed');
      state.value = 'success';
    } catch {
      state.value = 'error';
    }
  };
</script>

<template>
  <div class="orb-contact">
    <form
      v-if="state !== 'success'"
      class="orb-contact-form"
      @submit.prevent="submit"
    >
      <h3 class="orb-contact-form-title">
        {{ t(`${lng}.title`) }}
      </h3>

      <div class="orb-contact-field">
        <label
          class="orb-contact-label"
          for="contact-name"
        >
          {{ t(`${lng}.name`) }}
        </label>
        <input
          id="contact-name"
          v-model="form.name"
          class="orb-contact-input"
          required
          type="text"
          :placeholder="t(`${lng}.namePlaceholder`)"
        >
      </div>

      <div class="orb-contact-field">
        <label
          class="orb-contact-label"
          for="contact-email"
        >
          {{ t(`${lng}.email`) }}
        </label>
        <input
          id="contact-email"
          v-model="form.work_email"
          class="orb-contact-input"
          pattern="[^\s@]+@[^\s@]+\.[^\s@]+"
          required
          type="email"
          :placeholder="t(`${lng}.emailPlaceholder`)"
        >
      </div>

      <div class="orb-contact-field">
        <label
          class="orb-contact-label"
          for="contact-company"
        >
          {{ t(`${lng}.company`) }}
        </label>
        <input
          id="contact-company"
          v-model="form.company"
          class="orb-contact-input"
          required
          type="text"
          :placeholder="t(`${lng}.companyPlaceholder`)"
        >
      </div>

      <div class="orb-contact-field">
        <label
          class="orb-contact-label"
          for="contact-role"
        >
          {{ t(`${lng}.role`) }}
        </label>
        <select
          id="contact-role"
          v-model="form.role"
          class="orb-contact-input"
        >
          <option value="">
            {{ t(`${lng}.rolePlaceholder`) }}
          </option>
          <option
            v-for="(option, key) in roleOptions"
            :key="key"
            :value="option"
          >
            {{ option }}
          </option>
        </select>
      </div>

      <div class="orb-contact-field">
        <label
          class="orb-contact-label"
          for="contact-message"
        >
          {{ t(`${lng}.message`) }}
        </label>
        <textarea
          id="contact-message"
          v-model="form.message"
          class="orb-contact-input"
          required
          rows="4"
          :placeholder="t(`${lng}.messagePlaceholder`)"
        />
      </div>

      <!-- Honeypot — hidden from sighted users and screen readers, bots fill it -->
      <label
        aria-hidden="true"
        class="sr-only"
      >
        Leave this field empty
        <input
          v-model="form.website"
          autocomplete="off"
          tabindex="-1"
          type="text"
        >
      </label>

      <label class="orb-contact-consent">
        <input
          v-model="form.consent_given"
          required
          type="checkbox"
        >
        <i18n-t
          :keypath="`${lng}.consent`"
          tag="span"
        >
          <template #link>
            <router-link :to="{ name: 'privacy' }">
              {{ t(`${lng}.consentLink`) }}
            </router-link>
          </template>
        </i18n-t>
      </label>

      <div
        v-if="state === 'error'"
        class="orb-contact-error"
      >
        <ExclamationCircleOutlined />
        <span>{{ t(`${lng}.error`) }}</span>
      </div>

      <button
        class="orb-btn-primary orb-contact-submit"
        :disabled="state === 'submitting'"
        type="submit"
      >
        {{ state === 'submitting' ? t(`${lng}.submitting`) : t(`${lng}.submit`) }}
      </button>
    </form>

    <div
      v-else
      class="orb-contact-success"
    >
      {{ t(`${lng}.success`) }}
    </div>
  </div>
</template>
