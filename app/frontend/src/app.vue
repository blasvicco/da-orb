<script setup>
  // Libs imports
  import { onMounted, onUnmounted } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { RouterView, useRouter } from 'vue-router';

  // Modules imports
  import { useAuth } from '@/modules/auth';

  // Constants
  const { locale } = useI18n({ useScope: 'global' });
  const router = useRouter();

  const getSupportedLocales = () => ['en', 'es'];
  const resolveLocale = () => {
    const auth = useAuth();

    // 1. Logged-in user preference
    if (auth.hasSession()) {
      return auth.getSession()?.language;
    }

    // 2. Visitor's stored selection
    const stored = window.localStorage.getItem('visitor_language');
    if (stored && getSupportedLocales().includes(stored)) return stored;

    // 3. Browser/system language
    const browserLang = navigator.language?.split('-')[0];
    if (getSupportedLocales().includes(browserLang)) return browserLang;

    // 4. Fallback
    return __APP_ENV__.FALLBACK_LOCALE;
  };

  const logoutHandler = () => router.push({ name: 'landing' });
  const setLocale = (lng) => {
    locale.setter(lng);
    window.dispatchEvent(
      new CustomEvent('language.changed', { detail: lng })
    );
  };
  const sessionUpdateHandler = () => {
    setLocale(resolveLocale());
  };

  // Calling methods
  window.addEventListener('auth.logout', logoutHandler);
  window.addEventListener('auth.updated', sessionUpdateHandler);
  onUnmounted(() => {
    window.removeEventListener('auth.logout', logoutHandler);
    window.removeEventListener('auth.updated', sessionUpdateHandler);
  });
  onMounted(() => sessionUpdateHandler());
</script>

<template>
  <a-config-provider
    :theme="{
      cssVar: true,
      token: {
        colorPrimary: '#0F52BA',
        fontFamily: 'Plus Jakarta Sans, system-ui, -apple-system, sans-serif',
        borderRadius: 12
      }
    }"
    componentSize="large"
  >
    <router-view />
  </a-config-provider>
</template>
