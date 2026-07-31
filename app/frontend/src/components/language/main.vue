<script setup>
  // Libs imports
  import { useI18n } from 'vue-i18n';

  const { locale } = useI18n({ useScope: 'global' });
  const setLocale = (lng) => {
    locale.value = lng;
    window.localStorage.setItem('visitor_language', lng);
    window.dispatchEvent(new CustomEvent('language.changed', {
      detail: lng,
    }));
  };
</script>
<template>
  <a-select
    :defaultValue="$i18n.locale"
    :options="[{
      label: `${$t('commons.language.en')}`,
      value: 'en',
    }, {
      label: `${$t('commons.language.es')}`,
      value: 'es',
    }]"
    :placeholder="$t('commons.language.language')"
    class="w-max-[120px]"
    @change="setLocale"
  />
</template>
