<script setup>
  // Libs imports
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { ApartmentOutlined, PaperClipOutlined, PlusOutlined } from '@antdv-next/icons';

  // App components imports
  import BucketTrigger from '@/components/bucket/trigger.vue';
  import IntentionStack from '@/components/intention/stack.vue';

  import '@/components/chat/attach-menu.css';

  defineOptions({ name: 'AttachMenu' });

  defineProps({
    ensureSessionId: {
      default: async () => null,
      type: Function,
    },
    messages: {
      default: () => [],
      type: Array,
    },
    sessionId: {
      default: null,
      type: [Number, String],
    },
    sessionState: {
      default: null,
      type: Object,
    },
  });

  const emit = defineEmits(['context-file', 'file-deleted', 'navigate', 'pick-files']);

  const { t } = useI18n();

  const menuOpen = ref(false);
  const bucketOpen = ref(false);
  const intentionOpen = ref(false);

  // "Add files" no longer opens the bucket drawer — it goes straight to the
  // native file picker (handled by the composer, which owns stagedFiles), the
  // same entry point drag-and-drop already uses. See input.vue's triggerFilePicker.
  const pickFiles = () => {
    menuOpen.value = false;
    emit('pick-files');
  };

  // Mutually exclusive — the two are visually treated as one shared side-panel
  // slot rather than independent overlays, so opening one closes the other.
  const openBucket = () => {
    menuOpen.value = false;
    intentionOpen.value = false;
    bucketOpen.value = true;
  };

  const openIntention = () => {
    menuOpen.value = false;
    bucketOpen.value = false;
    intentionOpen.value = true;
  };

  // Lets the dedicated file-bucket toolbar button open this drawer instance
  // without lifting bucketOpen out of this component.
  defineExpose({ openBucket });
</script>

<template>
  <a-popover
    v-model:open="menuOpen"
    placement="topLeft"
    trigger="click"
  >
    <template #content>
      <div class="orb-attach-panel">
        <button
          class="orb-attach-option"
          @click="pickFiles"
        >
          <PaperClipOutlined />
          <span>{{ t('chat.attach.addFiles') }}</span>
        </button>
        <button
          class="orb-attach-option"
          @click="openIntention"
        >
          <ApartmentOutlined />
          <span>{{ t('chat.attach.showIntentionGraph') }}</span>
        </button>
      </div>
    </template>
    <button
      class="orb-attach-trigger"
      :title="t('chat.attach.title')"
    >
      <PlusOutlined />
    </button>
  </a-popover>

  <BucketTrigger
    v-model:open="bucketOpen"
    :ensure-session-id="ensureSessionId"
    :session-id="sessionId"
    @file-deleted="(fileId) => emit('file-deleted', fileId)"
    @switch-panel="openIntention"
    @use-as-context="(file) => emit('context-file', file)"
  />
  <IntentionStack
    v-model:open="intentionOpen"
    :messages="messages"
    :session-state="sessionState"
    @navigate="(node) => emit('navigate', node)"
    @switch-panel="openBucket"
  />
</template>
