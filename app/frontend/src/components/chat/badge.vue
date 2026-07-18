<script setup>
  import { computed } from 'vue';
  import { useI18n } from 'vue-i18n';

  import '@/components/chat/badge.css';

  const props = defineProps({
    status: {
      default: 'connecting',
      type: String,
    },
  });

  const { t } = useI18n();

  const statusText = computed(() => {
    if (props.status === 'connected') return t('chat.header.connected');
    if (props.status === 'connecting') return t('chat.header.connecting');
    return t('chat.header.disconnected');
  });
</script>

<template>
  <div
    class="orb-status-badge"
    :class="{
      'orb-status-badge--connected': status === 'connected',
      'bg-amber-500/10 border-amber-500/20 text-amber-700': status === 'connecting',
      'bg-rose-500/10 border-rose-500/20 text-rose-700': status === 'disconnected'
    }"
  >
    <span
      class="orb-status-indicator"
      :class="{
        'orb-status-indicator--connected': status === 'connected',
        'bg-amber-500': status === 'connecting',
        'bg-rose-500': status === 'disconnected'
      }"
    />
    {{ statusText }}
  </div>
</template>
