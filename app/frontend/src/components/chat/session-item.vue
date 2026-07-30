<script setup>
  import { ref, computed } from 'vue';
  import { useI18n } from 'vue-i18n';
  import { DeleteOutlined } from '@antdv-next/icons';
  import { formatCompactNumber } from '@/modules/number/token';

  const { t, locale } = useI18n();

  const props = defineProps({
    activeSessionId: {
      default: null,
      type: [String, Number],
    },
    session: {
      type: Object,
      required: true,
    },
  });

  const isActive = computed(() => props.session.id === props.activeSessionId);

  const emit = defineEmits(['select', 'delete']);

  const hovered = ref(false);
  const popOpen = ref(false);

  const sessionDate = computed(() => {
    if (!props.session.updated_on) return '';
    const d = new Date(props.session.updated_on);
    const now = new Date();
    if (d.toDateString() === now.toDateString()) {
      return d.toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit' });
    }
    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) {
      return t('chat.sidebar.history.yesterday');
    }
    return d.toLocaleDateString(locale.value, { month: 'short', day: 'numeric' });
  });

  const onSelect = () => { if (!popOpen.value) emit('select', props.session.id); };
  const onDeleteIconClick = (e) => { e.stopPropagation(); popOpen.value = true; };
  const onDeleteConfirm = () => { popOpen.value = false; emit('delete', props.session.id); };
  const onDeleteCancel = () => { popOpen.value = false; };
  const onOpenChange = (val) => { if (!val) popOpen.value = false; };
</script>

<template>
  <div
    class="orb-history-item"
    @mouseenter="hovered = true"
    @mouseleave="hovered = false"
    @click="onSelect"
  >
    <span class="orb-history-icon">
      <span
        v-if="session.pending"
        class="orb-history-pending-dot"
        :title="$t('chat.sidebar.history.pending')"
      />
      <svg
        v-else
        width="8"
        height="8"
        viewBox="0 0 8 8"
        xmlns="http://www.w3.org/2000/svg"
        :class="isActive ? 'orb-session-dot--active' : 'orb-session-dot--inactive'"
      >
        <circle
          cx="4"
          cy="4"
          r="4"
          fill="currentColor"
        />
      </svg>
    </span>
    <div class="orb-history-label">
      <span class="orb-history-title truncate">
        {{ session.title || $t('chat.sidebar.history.untitled') }}
      </span>
      <span
        v-if="sessionDate"
        class="orb-history-date"
      >
        {{ sessionDate }}
      </span>
      <span
        v-if="session.tokens_used"
        class="orb-history-tokens"
      >
        {{ $t('chat.sidebar.history.tokensUsed', { count: formatCompactNumber(session.tokens_used) }) }}
      </span>
    </div>
    <a-popconfirm
      :title="$t('chat.sidebar.history.deleteConfirm')"
      :ok-text="$t('commons.yes')"
      :cancel-text="$t('commons.no')"
      placement="right"
      :open="popOpen"
      @confirm="onDeleteConfirm"
      @cancel="onDeleteCancel"
      @openChange="onOpenChange"
    >
      <DeleteOutlined
        v-show="hovered || popOpen"
        class="orb-history-delete"
        @click="onDeleteIconClick"
      />
    </a-popconfirm>
  </div>
</template>
