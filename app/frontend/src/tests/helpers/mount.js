import { DOMWrapper, mount as vtuMount, shallowMount as vtuShallowMount } from '@vue/test-utils';
import { vi } from 'vitest';
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
  { path: '/projects', name: 'projects', component: { template: '<div />' } },
  { path: '/projects/:id', name: 'project', component: { template: '<div />' } },
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

// The teleported content of those popups is mounted asynchronously, not within the
// tick that `await trigger('click')` waits for, so on a loaded machine it can still be
// missing (or half there) right after opening. This resolves with the matching elements
// once `selector` matches exactly `count` of them (any number > 0 when count is omitted),
// and fails loudly, instead of clicking whatever happens to be there, if it never does.
export const waitForBody = (selector, count) => vi.waitFor(() => {
  const found = body().findAll(selector);
  const ready = count === undefined ? found.length > 0 : found.length === count;
  if (!ready) throw new Error(`Expected ${count ?? 'some'} "${selector}" in the body, found ${found.length}`);
  return found;
}, { interval: 20, timeout: 10000 });
