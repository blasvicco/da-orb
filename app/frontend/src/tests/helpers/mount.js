import { DOMWrapper, mount as vtuMount, shallowMount as vtuShallowMount } from '@vue/test-utils';
import { createI18n } from 'vue-i18n';
import { createMemoryHistory, createRouter } from 'vue-router';

import en from '@/i18n/lng/en.js';
import es from '@/i18n/lng/es.js';

export const TEST_ROUTES = [
  { path: '/', name: 'landing', component: { template: '<div />' } },
  { path: '/terms', name: 'terms', component: { template: '<div />' } },
  { path: '/privacy', name: 'privacy', component: { template: '<div />' } },
  { path: '/auth/callback', name: 'auth-callback', component: { template: '<div />' } },
  { path: '/chat', name: 'chat', component: { template: '<div />' } },
  { path: '/admin/seats', name: 'admin-seats', component: { template: '<div />' } },
  { path: '/admin/usage', name: 'admin-usage', component: { template: '<div />' } },
];

export const buildI18n = () => createI18n({
  fallbackLocale: 'en',
  legacy: false,
  locale: 'en',
  messages: { en, es },
});

export const buildRouter = (initialPath = '/') => {
  const router = createRouter({ history: createMemoryHistory(), routes: TEST_ROUTES });
  router.push(initialPath);
  return router;
};

const buildGlobal = ({ i18n, plugins = [], router, ...rest } = {}) => ({
  ...rest,
  plugins: [i18n || buildI18n(), router || buildRouter(), ...plugins],
});

export function mount(component, options = {}) {
  const { global: globalOpts = {}, ...rest } = options;
  return vtuMount(component, { ...rest, global: buildGlobal(globalOpts) });
}

export function shallowMount(component, options = {}) {
  const { global: globalOpts = {}, ...rest } = options;
  return vtuShallowMount(component, { ...rest, global: buildGlobal(globalOpts) });
}

export { flushPromises } from '@vue/test-utils';

// antdv-next popups (Popover/Tooltip/Modal/...) teleport their content onto a div
// appended to document.body, outside the mounted wrapper's own DOM subtree — use
// this to query/interact with that teleported content once the popup is open.
export const body = () => new DOMWrapper(document.body);
