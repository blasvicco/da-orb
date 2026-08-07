<script setup>
  // Libs imports
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    PaperClipOutlined,
    PauseCircleOutlined,
    StopOutlined,
    SyncOutlined,
  } from '@antdv-next/icons';

  // App modules imports
  import { buildIntentionTree, deriveIntentionNodes } from '@/modules/chat/intention/stack';

  import '@/components/intention/stack.css';

  defineOptions({ name: 'IntentionStack' });

  const props = defineProps({
    messages: {
      default: () => [],
      type: Array,
    },
    open: {
      default: false,
      type: Boolean,
    },
    sessionState: {
      default: null,
      type: Object,
    },
  });

  const emit = defineEmits(['navigate', 'resume', 'switch-panel', 'update:open']);

  const { t } = useI18n();

  const intentionNodes = computed(() => deriveIntentionNodes(props.messages, props.sessionState));
  const treeData = computed(() => buildIntentionTree(intentionNodes.value));

  const STATUS_ICON = {
    abandoned: StopOutlined,
    active: SyncOutlined,
    completed: CheckCircleOutlined,
    failed: CloseCircleOutlined,
    paused: PauseCircleOutlined,
  };

  const STATUS_COLOR = {
    abandoned: '#8c8c8c',
    active: '#52c41a',
    completed: '#1677ff',
    failed: '#f5222d',
    paused: '#fa8c16',
  };

  const handleResume = () => {
    emit('update:open', false);
    emit('resume');
  };

  const handleNavigate = (node) => {
    emit('update:open', false);
    emit('navigate', { id: node.id, label: node.label });
  };

  // Tracks which node's confirm popup is currently open — only one at a time,
  // and clicking a different label while one is open just moves it there.
  const confirmingId = ref(null);

  const onLabelClick = (node) => {
    if (node.status === 'active') return;
    confirmingId.value = node.id;
  };

  const onConfirmNavigate = (node) => {
    confirmingId.value = null;
    handleNavigate(node);
  };

  const onCancelNavigate = () => {
    confirmingId.value = null;
  };

  const onConfirmOpenChange = (open) => {
    if (!open) confirmingId.value = null;
  };
</script>

<template>
  <a-drawer
    :open="open"
    placement="right"
    root-class="orb-intention-drawer"
    size="320"
    @update:open="(val) => emit('update:open', val)"
  >
    <template #title>
      <div class="orb-panel-title">
        <span>{{ t('chat.intentionGraph.title') }}</span>
        <button
          class="orb-panel-switch"
          :title="t('chat.attach.addFiles')"
          @click="emit('switch-panel')"
        >
          <PaperClipOutlined />
        </button>
      </div>
    </template>

    <p
      v-if="intentionNodes.length === 0"
      class="orb-intention-stack-empty"
    >
      {{ t('chat.intentionGraph.empty') }}
    </p>
    <a-tree
      v-else
      class="orb-intention-tree"
      :tree-data="treeData"
      :selectable="false"
      default-expand-all
      show-line
      block-node
    >
      <template #titleRender="node">
        <div class="orb-intention-node">
          <div class="orb-intention-node-heading">
            <a-tooltip :title="t(`chat.intentionGraph.status.${node.status}`)">
              <component
                :is="STATUS_ICON[node.status]"
                class="orb-intention-node-status"
                :style="{ color: STATUS_COLOR[node.status] }"
              />
            </a-tooltip>
            <a-popconfirm
              :open="confirmingId === node.id"
              :title="t('chat.intentionGraph.navigateConfirm', { label: node.label })"
              :ok-text="t('commons.yes')"
              :cancel-text="t('commons.no')"
              @confirm="onConfirmNavigate(node)"
              @cancel="onCancelNavigate"
              @openChange="onConfirmOpenChange"
            >
              <span
                class="orb-intention-node-label"
                :class="{ 'orb-intention-node-label--clickable': node.status !== 'active' }"
                @click="onLabelClick(node)"
              >{{ node.label }}</span>
            </a-popconfirm>
          </div>
          <div class="orb-intention-stack-actions">
            <a-button
              v-if="node.resumable"
              size="small"
              type="primary"
              @click="handleResume"
            >
              {{ t('chat.intentionGraph.resume') }}
            </a-button>
          </div>
        </div>
      </template>
    </a-tree>
  </a-drawer>
</template>
