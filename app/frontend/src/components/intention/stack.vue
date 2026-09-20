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

  const emit = defineEmits(['navigate', 'switch-panel', 'update:open']);

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

  const handleNavigate = (node) => {
    emit('update:open', false);
    emit('navigate', { id: node.id, label: node.label });
  };

  // Tracks which node's overlay (navigate-confirm or error popover) is open —
  // only one at a time, across both kinds, so opening one always closes the other.
  const openOverlay = ref(null);

  const isNavigateOpen = (node) => openOverlay.value?.kind === 'navigate' && openOverlay.value?.id === node.id;
  const isErrorOpen = (node) => openOverlay.value?.kind === 'error' && openOverlay.value?.id === node.id;

  const onLabelClick = (node) => {
    if (node.status === 'active') return;
    openOverlay.value = { id: node.id, kind: 'navigate' };
  };

  const onConfirmNavigate = (node) => {
    openOverlay.value = null;
    handleNavigate(node);
  };

  const onCancelNavigate = () => {
    openOverlay.value = null;
  };

  const onConfirmOpenChange = (open) => {
    if (!open) openOverlay.value = null;
  };

  const onErrorIconClick = (node) => {
    openOverlay.value = { id: node.id, kind: 'error' };
  };

  const onErrorOpenChange = (open) => {
    if (!open) openOverlay.value = null;
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
            <a-popover
              v-if="node.status === 'failed' && node.errorDetail"
              :open="isErrorOpen(node)"
              trigger="click"
              @openChange="onErrorOpenChange"
            >
              <template #title>
                {{ t('chat.intentionGraph.errorDetail') }}
              </template>
              <template #content>
                <div class="orb-intention-error-popover">
                  <div class="orb-intention-error-popover-label">
                    {{ node.label }}
                  </div>
                  <div class="orb-intention-error-popover-detail">
                    {{ node.errorDetail }}
                  </div>
                </div>
              </template>
              <component
                :is="STATUS_ICON[node.status]"
                class="orb-intention-node-status orb-intention-node-status--clickable"
                :style="{ color: STATUS_COLOR[node.status] }"
                @click="onErrorIconClick(node)"
              />
            </a-popover>
            <a-tooltip
              v-else
              :title="t(`chat.intentionGraph.status.${node.status}`)"
            >
              <component
                :is="STATUS_ICON[node.status]"
                class="orb-intention-node-status"
                :style="{ color: STATUS_COLOR[node.status] }"
              />
            </a-tooltip>
            <a-popconfirm
              :open="isNavigateOpen(node)"
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
        </div>
      </template>
    </a-tree>
  </a-drawer>
</template>
