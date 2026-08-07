<script setup>
  // Libs imports
  import { ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { ApartmentOutlined, PaperClipOutlined, PlusOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useBucket } from '@/modules/bucket';

  // App components imports
  import BucketTrigger from '@/components/bucket/trigger.vue';
  import IntentionStack from '@/components/intention/stack.vue';

  import '@/components/chat/attach-menu.css';

  defineOptions({ name: 'AttachMenu' });

  defineProps({
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

  const emit = defineEmits(['context-file', 'file-deleted', 'navigate', 'resume']);

  const { t } = useI18n();
  const bucket = useBucket();

  const menuOpen = ref(false);
  const bucketOpen = ref(false);
  const intentionOpen = ref(false);

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
          @click="openBucket"
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
    <a-badge
      class="orb-attach-badge"
      :count="bucket.files.length + bucket.pendingFiles.length"
      :offset="[-2, 2]"
      size="small"
    >
      <button
        class="orb-attach-trigger"
        :title="t('chat.attach.title')"
      >
        <PlusOutlined />
      </button>
    </a-badge>
  </a-popover>

  <BucketTrigger
    v-model:open="bucketOpen"
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
    @resume="emit('resume')"
    @switch-panel="openBucket"
  />
</template>
