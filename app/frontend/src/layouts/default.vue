<script setup>
  // Libs imports
  import { onMounted } from 'vue';
  import { useRoute, useRouter } from 'vue-router';

  // Components imports
  import LanguageSelector from '@/components/language/main.vue';
  import ContactForm from '@/components/contact/main.vue';
  import orbLogo from '@/assets/img/logo.svg?url';

  // Modules imports
  import { useContactModal } from '@/modules/contact';
  import { useOrganization } from '@/modules/organization';

  const route = useRoute();
  const router = useRouter();
  const contactModal = useContactModal();
  const org = useOrganization();

  onMounted(() => org.load());

  // The #features / #security sections only exist on the landing page, so
  // this needs to route there first when clicked from privacy/terms/chat.
  const goToAnchor = (hash) => {
    if (route.name !== 'landing') {
      router.push({ name: 'landing', hash });
      return;
    }
    document.querySelector(hash)?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleCta = () => {
    if (org.hasOrganization() === false) {
      contactModal.open();
    } else {
      window.dispatchEvent(new CustomEvent('auth.trigger_signin'));
    }
  };
</script>

<template>
  <div class="orb-page">
    <!-- Global Header -->
    <header class="orb-header">
      <div class="orb-container orb-header-inner">
        <!-- Logo -->
        <a
          href="/"
          class="orb-logo-wrap"
        >
          <img
            :src="orbLogo"
            class="orb-logo-icon"
            alt="Orb"
          >
          <span class="orb-logo-text">
            {{ $t('landing.title') }}
          </span>
        </a>

        <div class="orb-header-right">
          <!-- Main Nav -->
          <nav class="orb-nav">
            <a
              href="#features"
              class="orb-nav-link"
              @click.prevent="goToAnchor('#features')"
            >{{ $t('landing.nav.features') }}</a>
            <a
              href="#security"
              class="orb-nav-link"
              @click.prevent="goToAnchor('#security')"
            >{{ $t('landing.nav.security') }}</a>
          </nav>

          <!-- Dynamic Actions & Selector -->
          <div class="orb-actions-wrap">
            <LanguageSelector />
            <button
              class="orb-btn-primary"
              @click="handleCta"
            >
              {{ org.hasOrganization() === false ? $t('landing.cta.signup') : $t('landing.cta.signin') }}
            </button>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="flex-1 flex flex-col justify-start">
      <slot />
    </main>

    <!-- Global Footer -->
    <footer class="orb-footer">
      <div class="orb-container orb-footer-inner">
        <div class="orb-footer-text">
          <div>&copy; {{ new Date().getFullYear() }} {{ $t('landing.title') }}. {{ $t('commons.footerText') }}</div>
          <div class="orb-footer-powered">
            {{ $t('commons.poweredBy') }}
            <a
              href="https://darchsystems.com/"
              target="_blank"
              rel="noopener"
              class="orb-footer-link"
            >D'Arch Systems</a>
          </div>
        </div>
        <div class="orb-footer-links">
          <router-link
            :to="{ name: 'privacy' }"
            class="orb-footer-link"
          >
            {{ $t('commons.privacyPolicy') }}
          </router-link>
          <router-link
            :to="{ name: 'terms' }"
            class="orb-footer-link"
          >
            {{ $t('commons.termsOfService') }}
          </router-link>
        </div>
      </div>
    </footer>
  </div>

  <!-- Contact modal — shown in place of sign-in when no organization/company is resolved -->
  <a-modal
    id="modal-contact"
    :open="contactModal.isOpen"
    :footer="null"
    centered
    @cancel="contactModal.close()"
  >
    <ContactForm />
  </a-modal>
</template>
