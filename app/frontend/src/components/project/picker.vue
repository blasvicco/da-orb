<script setup>
  // Libs imports
  import { computed, nextTick, ref, watch } from 'vue';

  // App modules imports
  import { useProjectSearch } from '@/modules/project/search';

  import '@/components/project/picker.css';

  const props = defineProps({
    // A project to leave out of the results, e.g. the chat's own project when moving it.
    excludeId: {
      default: null,
      type: [String, Number],
    },
  });

  const emit = defineEmits(['select']);
  const open = defineModel('open', { default: false, type: Boolean });

  const { load, projects, search } = useProjectSearch();
  const inputRef = ref(null);
  // False until the first results of an opening arrive, so "no projects" doesn't flash first.
  const loaded = ref(false);
  const query = ref('');

  const options = computed(() => projects.value.filter((project) => project.id !== props.excludeId));

  const onOpenChange = async (isOpen) => {
    if (!isOpen) return;
    query.value = '';
    loaded.value = false;
    nextTick(() => inputRef.value?.focus());
    await load();
    loaded.value = true;
  };

  const onPick = (project) => {
    open.value = false;
    emit('select', project.id);
  };

  watch(query, (value) => search(value));
</script>

<template>
  <a-popover
    v-model:open="open"
    placement="bottomRight"
    trigger="click"
    @openChange="onOpenChange"
  >
    <template #content>
      <div class="orb-project-picker">
        <a-input
          ref="inputRef"
          v-model:value="query"
          allow-clear
          :placeholder="$t('chat.sidebar.project.searchPlaceholder')"
          size="small"
        />
        <div class="orb-project-picker-list">
          <button
            v-for="project in options"
            :key="project.id"
            class="orb-project-picker-item"
            type="button"
            @click="onPick(project)"
          >
            {{ project.name }}
          </button>
          <div
            v-if="loaded && options.length === 0"
            class="orb-project-picker-empty"
          >
            {{ $t('chat.sidebar.project.empty') }}
          </div>
        </div>
      </div>
    </template>
    <slot />
  </a-popover>
</template>
