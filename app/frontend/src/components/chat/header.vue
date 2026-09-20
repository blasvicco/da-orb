<script setup>
  import Badge from '@/components/chat/badge.vue';
  import Export from '@/components/chat/export.vue';
  import { formatCompactNumber } from '@/modules/number/token';

  import '@/components/chat/header.css';

  defineProps({
    connectionStatus: {
      default: 'connecting',
      type: String,
    },
    hasMessages: {
      default: false,
      type: Boolean,
    },
    messages: {
      default: () => [],
      type: Array,
    },
    sessionId: {
      default: null,
      type: [Number, String],
    },
    sessionTitle: {
      default: null,
      type: String,
    },
    tokensUsed: {
      default: 0,
      type: Number,
    },
    userName: {
      default: '',
      type: String,
    },
  });
</script>

<template>
  <header class="orb-chat-pane-header">
    <div class="orb-header-title">
      {{ sessionTitle || (hasMessages ? $t('chat.header.activeWorkflow') : $t('chat.sidebar.newChat')) }}
    </div>
    <div class="orb-header-status">
      <span
        v-if="tokensUsed > 0"
        class="orb-header-tokens"
      >
        {{ $t('chat.header.tokensUsed', { count: formatCompactNumber(tokensUsed) }) }}
      </span>
      <Export
        :messages="messages"
        :session-id="sessionId"
        :session-title="sessionTitle"
        :user-name="userName"
      />
      <Badge :status="connectionStatus" />
    </div>
  </header>
</template>
