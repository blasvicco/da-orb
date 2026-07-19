<script setup>
  import Badge from '@/components/chat/badge.vue';
  import Export from '@/components/chat/export.vue';

  import '@/components/chat/header.css';

  defineProps({
    connection: {
      default: '',
      type: String,
    },
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
    sessionTitle: {
      default: null,
      type: String,
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
        v-if="connection"
        class="orb-header-connection"
      >
        {{ $t('component.userDetail.connectedTo', { database: connection }) }}
      </span>
      <Export
        :messages="messages"
        :session-title="sessionTitle"
        :user-name="userName"
      />
      <Badge :status="connectionStatus" />
    </div>
  </header>
</template>
