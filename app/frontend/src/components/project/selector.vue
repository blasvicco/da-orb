<script setup>
  // Antd imports
  import { MoreOutlined } from '@antdv-next/icons';

  // App modules imports
  import { useProject } from '@/modules/project';

  // App components imports
  import ProjectSelect from '@/components/project/select.vue';

  import '@/components/project/selector.css';

  const emit = defineEmits(['select']);

  const projectStore = useProject();
</script>

<template>
  <div class="orb-project-selector">
    <div class="orb-project-selector-header">
      <span class="orb-project-selector-title">
        {{ $t('chat.sidebar.project.title') }}
      </span>
      <router-link
        class="orb-project-selector-manage"
        :title="$t('chat.sidebar.project.manage')"
        to="/projects"
      >
        <MoreOutlined />
      </router-link>
    </div>
    <ProjectSelect
      :current="projectStore.currentProject()"
      @select="emit('select', $event)"
    />
  </div>
</template>
