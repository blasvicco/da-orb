<script setup>
  import { marked } from 'marked';
  import { DesktopOutlined } from '@ant-design/icons-vue';

  import Processes from '@/components/chat/processes.vue';

  import '@/components/chat/bubble.css';

  defineProps({
    msg: {
      required: true,
      type: Object,
    },
  });

  defineEmits(['process-select']);

  const renderMd = (text) => marked.parse(text || '', { breaks: true });
</script>

<template>
  <div
    class="orb-msg-row"
    :class="msg.type === 'user' ? 'orb-row-user' : 'orb-row-agent'"
  >
    <!-- User -->
    <div
      v-if="msg.type === 'user'"
      class="orb-msg-bubble orb-bubble-user"
    >
      <div>{{ msg.text }}</div>
      <span class="orb-msg-time orb-time-user">{{ msg.time }}</span>
    </div>

    <!-- Agent -->
    <div
      v-else-if="msg.type === 'agent'"
      class="orb-msg-bubble orb-bubble-agent"
    >
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="orb-md"
        v-html="renderMd(msg.text)"
      />
      <!-- eslint-enable vue/no-v-html -->
      <Processes
        v-if="msg.processes && msg.processes.length"
        :processes="msg.processes"
        variant="agent"
        @select="$emit('process-select', $event)"
      />
      <span class="orb-msg-time orb-time-agent">{{ msg.time }}</span>
    </div>

    <!-- System -->
    <div
      v-else-if="msg.type === 'system'"
      class="orb-msg-bubble orb-bubble-system"
    >
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="orb-md"
        v-html="renderMd(msg.text)"
      />
      <!-- eslint-enable vue/no-v-html -->
      <span class="orb-msg-time orb-time-agent">{{ msg.time }}</span>
    </div>

    <!-- Alert -->
    <div
      v-else-if="msg.type === 'alert'"
      class="orb-msg-bubble orb-bubble-alert"
    >
      <!-- eslint-disable vue/no-v-html -->
      <div
        class="orb-md"
        v-html="renderMd(msg.text)"
      />
      <!-- eslint-enable vue/no-v-html -->
      <Processes
        v-if="msg.processes && msg.processes.length"
        :processes="msg.processes"
        variant="alert"
        @select="$emit('process-select', $event)"
      />
      <span class="orb-msg-time orb-time-agent">{{ msg.time }}</span>
    </div>

    <!-- SAP Data -->
    <div
      v-else-if="msg.type === 'sap-data'"
      class="orb-msg-bubble orb-bubble-agent"
    >
      <div class="orb-msg-sap-data">
        <div class="orb-msg-sap-data-header">
          <span><DesktopOutlined /> {{ $t(msg.titleKey) }}</span>
          <span>{{ $t('commons.success') }}</span>
        </div>
        <div class="grid grid-cols-2 gap-x-4 gap-y-1">
          <template
            v-for="(valKey, labelKey) in msg.data"
            :key="labelKey"
          >
            <div class="text-left text-slate-400">
              {{ $t(labelKey) }}:
            </div>
            <div class="truncate text-right text-teal-300">
              {{ $t(valKey) }}
            </div>
          </template>
        </div>
      </div>
      <span class="orb-msg-time orb-time-agent">{{ msg.time }}</span>
    </div>
  </div>
</template>
