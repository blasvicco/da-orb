<script setup>
  // Libs imports
  import { computed, ref } from 'vue';
  import { useI18n } from 'vue-i18n';

  // Antd imports
  import { ApartmentOutlined } from '@antdv-next/icons';

  // App modules imports
  import { buildIntentionTree, deriveIntentionNodes } from '@/modules/chat/intention/stack';

  import '@/components/intention/stack.css';

  defineOptions({ name: 'IntentionStack' });

  const props = defineProps({
    messages: {
      default: () => [],
      type: Array,
    },
    sessionState: {
      default: null,
      type: Object,
    },
  });

  const emit = defineEmits(['navigate', 'resume']);

  const { t } = useI18n();

  const drawerOpen = ref(false);

  const intentionNodes = computed(() => deriveIntentionNodes(props.messages, props.sessionState));
  const treeData = computed(() => buildIntentionTree(intentionNodes.value));

  const STATUS_COLOR = {
    abandoned: 'default',
    active: 'green',
    completed: 'blue',
    paused: 'orange',
  };

  const handleResume = () => {
    drawerOpen.value = false;
    emit('resume');
  };

  const handleNavigate = (node) => {
    drawerOpen.value = false;
    emit('navigate', { id: node.id, label: node.label });
  };
</script>

<template>
  <button
    class="orb-prompt-tool-btn"
    :title="t('chat.intentionGraph.title')"
    @click="drawerOpen = true"
  >
    <ApartmentOutlined />
  </button>

  <a-drawer
    v-model:open="drawerOpen"
    placement="right"
    width="320"
  >
    <template #title>
      <span>{{ t('chat.intentionGraph.title') }}</span>
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
          <span class="orb-intention-node-label">{{ node.label }}</span>
          <div class="orb-intention-stack-actions">
            <a-button
              v-if="node.resumable"
              size="small"
              type="primary"
              @click="handleResume"
            >
              {{ t('chat.intentionGraph.resume') }}
            </a-button>
            <a-button
              v-if="node.status !== 'active'"
              size="small"
              @click="handleNavigate(node)"
            >
              {{ t('chat.intentionGraph.navigate') }}
            </a-button>
            <a-tag :color="STATUS_COLOR[node.status] || 'default'">
              {{ t(`chat.intentionGraph.status.${node.status}`) }}
            </a-tag>
          </div>
        </div>
      </template>
    </a-tree>
  </a-drawer>
</template>
