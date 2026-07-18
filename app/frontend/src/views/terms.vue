<script setup>
  // Layout import
  import Default from '@/layouts/default.vue';

  // Styles
  import "@/views/terms.css";

  const sections = ['s1', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10'];
</script>

<template>
  <Default>
    <section class="orb-container orb-legal">
      <div class="orb-legal-header">
        <h1 class="orb-legal-title">
          {{ $t('legal.terms.title') }}
        </h1>
        <p class="orb-legal-updated">
          {{ $t('legal.terms.updated') }}
        </p>
      </div>

      <div class="orb-legal-prose">
        <div
          v-for="key in sections"
          :key="key"
          class="orb-legal-section"
        >
          <h2 class="orb-legal-section-title">
            {{ $t(`legal.terms.${key}.title`) }}
          </h2>
          <p class="orb-legal-section-body">
            {{ $t(`legal.terms.${key}.body`) }}
          </p>
        </div>
      </div>
    </section>
  </Default>
</template>
