<script setup>
  import '@/components/admin/tabs.css';

  defineProps({
    active: {
      required: true,
      type: String,
    },
  });
</script>

<template>
  <nav class="orb-admin-tabs">
    <router-link
      to="/admin/seats"
      :class="['orb-admin-tab', { 'orb-admin-tab-active': active === 'seats' }]"
    >
      {{ $t('admin.tabs.seats') }}
    </router-link>
    <router-link
      to="/admin/usage"
      :class="['orb-admin-tab', { 'orb-admin-tab-active': active === 'usage' }]"
    >
      {{ $t('admin.tabs.usage') }}
    </router-link>
    <router-link
      to="/admin/document-templates"
      :class="['orb-admin-tab', { 'orb-admin-tab-active': active === 'documentTemplates' }]"
    >
      {{ $t('admin.tabs.documentTemplates') }}
    </router-link>
  </nav>
</template>
