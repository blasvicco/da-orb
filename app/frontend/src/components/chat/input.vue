<script setup>
  import { nextTick, ref, watch } from 'vue';

  // Antd imports
  import {
    CloseOutlined,
    FileExcelOutlined,
    FileImageOutlined,
    FileOutlined,
    FilePdfOutlined,
    FileWordOutlined,
    FileZipOutlined,
    LinkOutlined,
  } from '@antdv-next/icons';

  // App modules imports
  import { useBucket } from '@/modules/bucket';
  import { formatFileSize } from '@/modules/bucket/trigger';

  // App components imports
  import AttachMenu from '@/components/chat/attach-menu.vue';

  import '@/components/chat/input.css';

  const props = defineProps({
    contextFiles: {
      default: () => [],
      type: Array,
    },
    disabled: {
      default: false,
      type: Boolean,
    },
    // Resolves to a real session_id, creating the session first if needed —
    // see commitStagedFiles(), which needs one to upload against even before
    // the user has sent their first message.
    ensureSessionId: {
      default: () => async () => null,
      type: Function,
    },
    messages: {
      default: () => [],
      type: Array,
    },
    modelValue: {
      default: '',
      type: String,
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

  const emit = defineEmits(['context-file', 'file-deleted', 'navigate', 'remove-context', 'resume', 'send', 'update:modelValue']);

  const bucket = useBucket();

  const promptTextarea = ref(null);
  const isDragging = ref(false);
  // Files dropped onto the composer, previewed here but not staged/uploaded to the
  // bucket until the user actually sends (Enter/click) — a drop shouldn't silently
  // start an upload the user hasn't committed to yet.
  const stagedFiles = ref([]);

  const resizeTextarea = () => {
    const el = promptTextarea.value;
    // v8 ignore next -- textarea is unconditionally rendered; unreachable pre-mount/post-unmount.
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  };

  watch(() => props.modelValue, async () => {
    await nextTick();
    resizeTextarea();
  });

  const FILE_ICON_MATCHERS = [
    { icon: FileImageOutlined, test: (type) => type.startsWith('image/') },
    { icon: FilePdfOutlined, test: (type) => type === 'application/pdf' },
    { icon: FileExcelOutlined, test: (type) => /excel|sheet/.test(type) },
    { icon: FileWordOutlined, test: (type) => /word|msword/.test(type) },
    { icon: FileZipOutlined, test: (type) => /zip|compressed/.test(type) },
  ];

  const fileIcon = (file) => (FILE_ICON_MATCHERS.find(({ test }) => test(file.type || ''))?.icon) || FileOutlined;

  const removeStagedFile = (idx) => {
    stagedFiles.value = stagedFiles.value.filter((_, pos) => pos !== idx);
  };

  // Commits any staged (dropped) files to the bucket — called right before a send,
  // so files only actually start uploading once the user presses Enter/Send. Every
  // newly uploaded file is auto-linked as context for this turn (a drop is already
  // an explicit choice to include the file — no separate "Use as context" needed).
  // Chips stay rendered (with an uploading overlay, see bucket.uploading) through
  // the await below rather than vanishing the instant Send is pressed.
  const commitStagedFiles = async () => {
    if (!stagedFiles.value.length) return;
    const staged = stagedFiles.value;
    // A brand-new chat has no session yet at this point — sessionId is only ever
    // set in response to a real session existing server-side, and bucket uploads
    // require one. Ensuring it here (rather than letting bucket.addFiles defer
    // to pendingFiles) is what lets files attached on the very first message
    // actually upload in time to be referenced by that same message.
    const realSessionId = props.sessionId || await props.ensureSessionId();
    const uploaded = await bucket.addFiles(realSessionId, staged);
    stagedFiles.value = [];
    uploaded.forEach((file) => emit('context-file', { id: file.id, name: file.name }));
  };

  const handleKeydown = async (event) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      await commitStagedFiles();
      emit('send');
    }
  };

  const handleSendClick = async () => {
    await commitStagedFiles();
    emit('send');
  };

  const onInput = (event) => {
    emit('update:modelValue', event.target.value);
    resizeTextarea();
  };

  const handleDragOver = () => {
    isDragging.value = true;
  };

  const handleDragLeave = () => {
    isDragging.value = false;
  };

  const handleDrop = (event) => {
    isDragging.value = false;
    const dropped = Array.from(event.dataTransfer?.files || []);
    if (dropped.length) stagedFiles.value = [...stagedFiles.value, ...dropped];
  };
</script>

<template>
  <div
    class="orb-prompt-wrapper"
    :class="{ 'orb-prompt-wrapper--dragging': isDragging }"
    @dragleave.prevent="handleDragLeave"
    @dragover.prevent="handleDragOver"
    @drop.prevent="handleDrop"
  >
    <div class="orb-prompt-bar">
      <div
        v-if="contextFiles.length"
        class="orb-prompt-context"
      >
        <div
          v-for="file in contextFiles"
          :key="file.id"
          class="orb-prompt-context-chip"
        >
          <LinkOutlined class="orb-prompt-context-icon" />
          <span class="orb-prompt-context-name">{{ file.name }}</span>
          <button
            class="orb-prompt-context-remove"
            :title="$t('chat.attach.removeContext')"
            @click="emit('remove-context', file.id)"
          >
            <CloseOutlined />
          </button>
        </div>
      </div>
      <div
        v-if="stagedFiles.length"
        class="orb-prompt-attachments"
      >
        <div
          v-for="(file, idx) in stagedFiles"
          :key="`${idx}-${file.name}`"
          class="orb-prompt-attachment"
        >
          <div
            v-if="bucket.uploading"
            class="orb-prompt-attachment-uploading"
          >
            <a-spin size="small" />
          </div>
          <button
            class="orb-prompt-attachment-remove"
            :title="$t('chat.attach.removeFile')"
            @click="removeStagedFile(idx)"
          >
            <CloseOutlined />
          </button>
          <component
            :is="fileIcon(file)"
            class="orb-prompt-attachment-icon"
          />
          <span class="orb-prompt-attachment-name">{{ file.name }}</span>
          <span class="orb-prompt-attachment-size">{{ formatFileSize(file.size) }}</span>
        </div>
      </div>
      <textarea
        ref="promptTextarea"
        :value="modelValue"
        rows="1"
        class="orb-prompt-input"
        :placeholder="$t('chat.input.placeholder')"
        @input="onInput"
        @keydown="handleKeydown"
      />
      <div class="orb-prompt-toolbar">
        <AttachMenu
          :messages="messages"
          :session-id="sessionId"
          :session-state="sessionState"
          @context-file="(file) => emit('context-file', file)"
          @file-deleted="(fileId) => emit('file-deleted', fileId)"
          @navigate="(node) => emit('navigate', node)"
          @resume="emit('resume')"
        />
        <button
          class="orb-prompt-send-btn"
          :disabled="!modelValue.trim() || disabled"
          :title="$t('chat.input.sendInquiry')"
          @click="handleSendClick"
        >
          ➔
        </button>
      </div>
    </div>
    <div class="orb-prompt-footnote">
      {{ $t('chat.input.info') }}
    </div>
  </div>
</template>
