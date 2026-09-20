<script setup>
  import { useI18n } from 'vue-i18n';

  import { DownloadOutlined, PaperClipOutlined } from '@antdv-next/icons';

  import AppAPI from '@/modules/api';

  import '@/components/chat/document-chip.css';

  defineOptions({ name: 'DocumentChip' });

  const props = defineProps({
    attachment: {
      required: true,
      type: Object,
    },
  });

  const { t } = useI18n();

  const handleDownload = async () => {
    const result = await AppAPI.Bucket.downloadUrl(props.attachment.id);
    if (result?.url) window.open(result.url, '_blank');
  };
</script>

<template>
  <div class="orb-document-chip">
    <PaperClipOutlined class="orb-document-chip-icon" />
    <span class="orb-document-chip-name">{{ attachment.name }}</span>
    <a-button
      class="orb-document-chip-download-btn"
      size="small"
      :title="t('chat.documentChip.download')"
      @click="handleDownload"
    >
      <DownloadOutlined />
    </a-button>
  </div>
</template>
