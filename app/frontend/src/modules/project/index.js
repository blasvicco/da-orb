// Libs imports
import { defineStore } from 'pinia';
import { ref } from 'vue';

// App imports
import AppAPI from '@/modules/api';

// The project the sidebar is currently scoped to. Deliberately does not touch chat
// sessions: refreshing those after a switch stays with the chat view, the same way no other
// store reaches into a sibling domain's AppAPI surface. (Searching projects is per-widget:
// see useProjectSearch.)
export const useProject = defineStore('project', () => {
  const _currentProject = ref(null);

  const currentProject = () => _currentProject.value;

  const currentProjectId = () => _currentProject.value?.id ?? null;

  // The user's locked Default project — what sign-in always lands on.
  const loadDefault = async () => {
    const result = await AppAPI.Project.default();
    if (!result?.errors) _currentProject.value = result;
    return result;
  };

  const selectProject = async (id) => {
    const result = await AppAPI.Project.select(id);
    if (!result?.errors) _currentProject.value = result;
    return result;
  };

  return {
    currentProject,
    currentProjectId,
    loadDefault,
    selectProject,
  };
});
