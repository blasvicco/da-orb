<script setup>
  import SessionItem from '@/components/chat/session-item.vue';

  import '@/components/chat/history.css';

  defineProps({
    activeSessionId: {
      default: null,
      type: [String, Number],
    },
    sessions: {
      default: () => [],
      type: Array,
    },
  });

  defineEmits(['delete', 'select']);
</script>

<template>
  <div class="orb-history-section">
    <div class="orb-history-title">
      {{ $t('chat.sidebar.historyTitle') }}
    </div>
    <div class="orb-history-list">
      <SessionItem
        v-for="s in sessions"
        :key="s.id"
        :session="s"
        :active-session-id="activeSessionId"
        @select="$emit('select', $event)"
        @delete="$emit('delete', $event)"
      />
      <div
        v-if="sessions.length === 0"
        class="orb-history-empty"
      >
        {{ $t('chat.sidebar.history.empty') }}
      </div>
    </div>
  </div>
</template>
