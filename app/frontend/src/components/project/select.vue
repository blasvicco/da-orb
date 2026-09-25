<script setup>
  // Libs imports
  import { computed, onMounted } from 'vue';

  // App modules imports
  import { useProjectSearch } from '@/modules/project/search';

  import '@/components/project/select.css';

  const props = defineProps({
    // The selected project ({ id, name }). It is always kept among the options, even when it
    // isn't in the (most-recent / searched) results, so the select shows its name, not its id.
    current: {
      default: null,
      type: Object,
    },
  });

  const emit = defineEmits(['select']);

  const { load, projects, search } = useProjectSearch();

  const options = computed(() => {
    const list = projects.value.map((project) => ({ label: project.name, value: project.id }));
    if (props.current && !list.some((option) => option.value === props.current.id)) {
      list.unshift({ label: props.current.name, value: props.current.id });
    }
    return list;
  });

  const onOpenChange = (open) => {
    // Re-fetched on every open so the order (most recently accessed first) and any
    // project created since are up to date.
    if (open) load();
  };

  onMounted(() => load());
</script>

<template>
  <a-select
    class="orb-project-select"
    :filter-option="false"
    :not-found-content="$t('chat.sidebar.project.empty')"
    :options="options"
    :placeholder="$t('chat.sidebar.project.searchPlaceholder')"
    show-search
    :value="current?.id"
    @change="emit('select', $event)"
    @openChange="onOpenChange"
    @search="search"
  />
</template>
