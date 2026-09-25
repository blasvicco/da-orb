<script setup>
  // Libs imports
  import { onMounted, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  // App modules imports
  import AppAPI from '@/modules/api';
  import { formatCompactNumber } from '@/modules/number/token';

  import '@/components/chat/recent-chats.css';

  defineProps({
    activeSessionId: {
      default: null,
      type: [String, Number],
    },
  });

  const emit = defineEmits(['select']);

  const { t } = useI18n();
  const sessions = ref([]);

  // "{project} - {N tokens}" — the chat's own title is only the hover tooltip, this widget
  // is a compact cross-project shortcut, not a second history list.
  const entryText = (session) => t('chat.sidebar.recentChats.entry', {
    project: session.project_name,
    tokens: t('chat.sidebar.history.tokensUsed', { count: formatCompactNumber(session.tokens_used || 0) }),
  });

  // Re-fetched rather than accumulated client-side, like the project's own session list,
  // so token totals can't drift. The parent calls this whenever the list may have changed.
  const refresh = async () => {
    const result = await AppAPI.Chat.recent();
    if (!result?.errors) sessions.value = result;
  };

  onMounted(refresh);

  defineExpose({ refresh });
</script>

<template>
  <div class="orb-recent-section">
    <div class="orb-recent-title">
      {{ $t('chat.sidebar.recentChats.title') }}
    </div>
    <div class="orb-recent-list">
      <button
        v-for="session in sessions"
        :key="session.id"
        class="orb-recent-item"
        :class="{ 'orb-recent-item--active': session.id === activeSessionId }"
        :title="session.title || $t('chat.sidebar.history.untitled')"
        type="button"
        @click="emit('select', { projectId: session.project, sessionId: session.id })"
      >
        {{ entryText(session) }}
      </button>
      <div
        v-if="sessions.length === 0"
        class="orb-recent-empty"
      >
        {{ $t('chat.sidebar.recentChats.empty') }}
      </div>
    </div>
  </div>
</template>
