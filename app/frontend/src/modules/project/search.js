// Libs imports
import { onUnmounted, ref } from 'vue';

// App imports
import AppAPI from '@/modules/api';

// How many projects a search offers at once, and how long typing pauses before it runs.
const RESULTS_LIMIT = 8;
const SEARCH_DEBOUNCE_MS = 250;

// Server-side project name search with its own result list. Every widget that needs one
// calls this for itself, so typing in one search box never disturbs the options another
// shows. Call it from a component's setup: it drops a pending search on unmount.
export const useProjectSearch = () => {
  const projects = ref([]);
  let latest = 0;
  let timer = null;

  // Most recently accessed first (the server's default ordering), narrowed by name when given.
  const load = async (query = '') => {
    const request = ++latest;
    const filters = query ? { name__icontains: query } : {};
    const result = await AppAPI.Project.list({ filters, limit: RESULTS_LIMIT });
    // Only the newest request may fill the list, so a slow earlier search can't overwrite it.
    if (request === latest && !result?.errors) projects.value = result.results;
    return result;
  };

  // Debounced load, for a search box's input.
  const search = (query) => {
    clearTimeout(timer);
    timer = setTimeout(() => load(query), SEARCH_DEBOUNCE_MS);
  };

  onUnmounted(() => clearTimeout(timer));

  return { load, projects, search };
};
