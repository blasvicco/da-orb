<script setup>
  import { ref, watch } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { SettingOutlined } from '@ant-design/icons-vue';

  import '@/components/chat/settings.css';

  const props = defineProps({
    expertiseLevel: {
      default: 2,
      type: Number,
    },
    theme: {
      default: 'light',
      type: String,
    },
  });

  const emit = defineEmits(['expertise-change', 'theme-change']);

  const { t } = useI18n();

  const expertiseLabels = ['novice', 'intermediate', 'expert'];
  const localLevel = ref(props.expertiseLevel);

  watch(() => props.expertiseLevel, (val) => { localLevel.value = val; });
</script>

<template>
  <a-popover
    placement="topRight"
    trigger="click"
  >
    <template #title>
      <span>{{ $t('chat.settings.title') }}</span>
    </template>
    <template #content>
      <div class="orb-settings-panel">
        <div class="orb-settings-row">
          <span class="orb-settings-label">{{ $t('chat.settings.darkMode') }}</span>
          <a-switch
            size="small"
            :checked="theme === 'dark'"
            @change="emit('theme-change', $event)"
          />
        </div>
        <div class="orb-settings-row orb-settings-row--column">
          <span class="orb-settings-label">
            {{ $t('chat.settings.expertiseLevel') }}:
            <strong>{{ $t(`chat.settings.expertise.${expertiseLabels[localLevel - 1]}`) }}</strong>
          </span>
          <a-slider
            v-model:value="localLevel"
            :min="1"
            :max="3"
            :step="1"
            :tooltip-open="false"
            @change="emit('expertise-change', $event)"
          />
        </div>
      </div>
    </template>
    <button
      class="orb-prompt-tool-btn"
      :title="t('chat.settings.title')"
    >
      <SettingOutlined />
    </button>
  </a-popover>
</template>
