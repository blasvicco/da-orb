<script setup>
  // Libs imports
  import { onMounted, ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { ApartmentOutlined, DeleteOutlined, DownloadOutlined, LinkOutlined, UploadOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useBucket } from '@/modules/bucket';
  import { formatFileSize } from '@/modules/bucket/trigger';

  import '@/components/bucket/trigger.css';

  defineOptions({ name: 'BucketTrigger' });

  const props = defineProps({
    open: {
      default: false,
      type: Boolean,
    },
    sessionId: {
      default: null,
      type: [Number, String],
    },
  });

  const emit = defineEmits(['file-deleted', 'switch-panel', 'update:open', 'use-as-context']);

  const { t } = useI18n();
  const bucket = useBucket();

  const fileInput = ref(null);
  // Tracks which uploaded file's delete-confirm popup is open — only one at a time.
  const deletingId = ref(null);

  const previewOpen = ref(false);
  const previewFile = ref(null);
  const previewUrl = ref('');
  const previewText = ref('');
  const previewLoading = ref(false);

  onMounted(() => bucket.setSessionId(props.sessionId));
  watch(() => props.sessionId, (sessionId) => bucket.setSessionId(sessionId));

  const triggerUpload = () => fileInput.value?.click();

  const handleFilesSelected = async (event) => {
    const selected = Array.from(event.target.files || []);
    event.target.value = '';
    await bucket.addFiles(props.sessionId, selected);
  };

  const handleDownload = async (file) => {
    const result = await bucket.downloadUrl(file.id);
    if (result?.url) window.open(result.url, '_blank');
  };

  const handleUseAsContext = (file) => {
    emit('update:open', false);
    emit('use-as-context', { id: file.id, name: file.name });
  };

  const handleRemovePending = (idx) => bucket.removePendingFile(idx);

  const openDeleteConfirm = (fileId) => {
    deletingId.value = fileId;
  };

  const handleDeleteConfirm = async (file) => {
    deletingId.value = null;
    const result = await bucket.deleteFile(file.id);
    if (!result?.errors) emit('file-deleted', file.id);
  };

  const handleDeleteCancel = () => {
    deletingId.value = null;
  };

  const handleDeleteOpenChange = (isOpen) => {
    if (!isOpen) deletingId.value = null;
  };

  const isPreviewableImage = (mimeType) => (mimeType || '').startsWith('image/');
  const isPreviewableText = (mimeType) => (mimeType || '').startsWith('text/') || mimeType === 'application/json';
  const isPreviewable = (file) => isPreviewableImage(file.mime_type) || isPreviewableText(file.mime_type);

  const openPreview = async (file) => {
    if (!isPreviewable(file)) return;
    previewFile.value = file;
    previewOpen.value = true;
    previewUrl.value = '';
    previewText.value = '';
    previewLoading.value = true;

    const result = await bucket.downloadUrl(file.id);
    if (!result?.url) {
      previewLoading.value = false;
      return;
    }
    if (isPreviewableImage(file.mime_type)) {
      previewUrl.value = result.url;
      previewLoading.value = false;
      return;
    }

    const response = await fetch(result.url);
    const text = await response.text();
    if (file.mime_type === 'application/json') {
      try {
        previewText.value = JSON.stringify(JSON.parse(text), null, 2);
      } catch {
        previewText.value = text;
      }
    } else {
      previewText.value = text;
    }
    previewLoading.value = false;
  };
</script>

<template>
  <a-drawer
    :open="open"
    placement="right"
    root-class="orb-bucket-drawer"
    size="360"
    @update:open="(val) => emit('update:open', val)"
  >
    <template #title>
      <div class="orb-panel-title">
        <span>{{ t('chat.bucket.title') }}</span>
        <button
          class="orb-panel-switch"
          :title="t('chat.attach.showIntentionGraph')"
          @click="emit('switch-panel')"
        >
          <ApartmentOutlined />
        </button>
      </div>
    </template>

    <input
      ref="fileInput"
      class="orb-bucket-file-input"
      multiple
      type="file"
      @change="handleFilesSelected"
    >
    <a-button
      block
      class="orb-bucket-upload-btn"
      :loading="bucket.uploading"
      @click="triggerUpload"
    >
      <UploadOutlined />
      {{ t('chat.bucket.upload') }}
    </a-button>

    <p
      v-if="bucket.files.length === 0 && bucket.pendingFiles.length === 0"
      class="orb-bucket-empty"
    >
      {{ t('chat.bucket.empty') }}
    </p>
    <ul
      v-else
      class="orb-bucket-list"
    >
      <li
        v-for="(file, idx) in bucket.pendingFiles"
        :key="`pending-${idx}-${file.name}`"
        class="orb-bucket-item orb-bucket-item--pending"
      >
        <div class="orb-bucket-item-info">
          <span class="orb-bucket-item-name">{{ file.name }}</span>
          <span class="orb-bucket-item-meta">
            {{ t('chat.bucket.pending') }} · {{ formatFileSize(file.size) }}
          </span>
        </div>
        <a-button
          class="orb-bucket-remove-btn"
          size="small"
          :title="t('chat.bucket.remove')"
          @click="handleRemovePending(idx)"
        >
          <DeleteOutlined />
        </a-button>
      </li>
      <li
        v-for="file in bucket.files"
        :key="file.id"
        class="orb-bucket-item"
      >
        <div class="orb-bucket-item-info">
          <span
            class="orb-bucket-item-name"
            :class="{ 'orb-bucket-item-name--clickable': isPreviewable(file) }"
            @click="openPreview(file)"
          >{{ file.name }}</span>
          <span class="orb-bucket-item-meta">
            {{ file.origin === 'user_upload' ? t('chat.bucket.originUser') : t('chat.bucket.originWorkflow') }}
            · {{ formatFileSize(file.size) }}
          </span>
        </div>
        <div class="orb-bucket-item-actions">
          <a-button
            class="orb-bucket-context-btn"
            size="small"
            :title="t('chat.bucket.useAsContext')"
            @click="handleUseAsContext(file)"
          >
            <LinkOutlined />
          </a-button>
          <a-button
            class="orb-bucket-download-btn"
            size="small"
            @click="handleDownload(file)"
          >
            <DownloadOutlined />
          </a-button>
          <a-popconfirm
            :open="deletingId === file.id"
            :title="t('chat.bucket.deleteConfirm', { name: file.name })"
            :ok-text="t('commons.yes')"
            :cancel-text="t('commons.no')"
            @confirm="handleDeleteConfirm(file)"
            @cancel="handleDeleteCancel"
            @openChange="handleDeleteOpenChange"
          >
            <a-button
              class="orb-bucket-delete-btn"
              size="small"
              :title="t('chat.bucket.remove')"
              @click="openDeleteConfirm(file.id)"
            >
              <DeleteOutlined />
            </a-button>
          </a-popconfirm>
        </div>
      </li>
    </ul>

    <a-modal
      v-model:open="previewOpen"
      :title="previewFile?.name"
      :footer="null"
      width="600"
    >
      <div
        v-if="previewLoading"
        class="orb-bucket-preview-loading"
      >
        <a-spin />
      </div>
      <img
        v-else-if="previewUrl"
        :src="previewUrl"
        class="orb-bucket-preview-image"
        alt=""
      >
      <pre
        v-else
        class="orb-bucket-preview-text"
      >{{ previewText }}</pre>
    </a-modal>
  </a-drawer>
</template>
