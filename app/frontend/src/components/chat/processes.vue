<script setup>
  import { useI18n } from 'vue-i18n';

  import '@/components/chat/processes.css';

  defineProps({
    processes: {
      default: () => [],
      type: Array,
    },
    variant: {
      default: 'agent',
      type: String,
    },
  });

  defineEmits(['select']);

  const { t } = useI18n();
</script>

<template>
  <div class="orb-process-list">
    <button
      v-for="(proc, idx) in processes"
      :key="proc.slug"
      class="orb-process-option"
      @click="$emit('select', proc.display_name || proc.name)"
    >
      <span class="orb-process-option-index">{{ idx + 1 }}</span>
      {{ proc.display_name || proc.name }}
    </button>
    <p class="orb-process-hint">
      {{ t('chat.processes.hint') }}
    </p>
  </div>
</template>
