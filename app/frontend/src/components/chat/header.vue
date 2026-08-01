<script setup>
  import Badge from '@/components/chat/badge.vue';
  import Export from '@/components/chat/export.vue';
  import IntentionStack from '@/components/intention/stack.vue';
  import { formatCompactNumber } from '@/modules/number/token';

  import '@/components/chat/header.css';

  const emit = defineEmits(['navigate', 'resume']);

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
    sessionState: {
      default: null,
      type: Object,
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
      <IntentionStack
        :messages="messages"
        :session-state="sessionState"
        @navigate="(node) => emit('navigate', node)"
        @resume="emit('resume')"
      />
      <Export
        :messages="messages"
        :session-title="sessionTitle"
        :user-name="userName"
      />
      <Badge :status="connectionStatus" />
    </div>
  </header>
</template>
