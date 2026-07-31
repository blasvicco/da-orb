// Libs imports
import { createRouter, createWebHistory } from 'vue-router';

// Modules imports
import { useAuth } from '@/modules/auth';

// Views imports
import landing from '@/views/landing.vue';
import chat from '@/views/chat.vue';
import privacy from '@/views/privacy.vue';
import seats from '@/views/admin/seats.vue';
import terms from '@/views/terms.vue';
import usage from '@/views/admin/usage.vue';

const router = createRouter({
  history: createWebHistory(__APP_ENV__.BASE_URL),
  routes: [{
    path: '/',
    name: 'landing',
    component: landing,
  }, {
    path: '/terms',
    name: 'terms',
    component: terms,
  }, {
    path: '/privacy',
    name: 'privacy',
    component: privacy,
  }, {
    path: '/auth/callback',
    name: 'auth-callback',
    // Blank shell — beforeEnter always redirects before anything renders
    component: { template: '<div />' },
    beforeEnter: (to) => {
      const auth = useAuth();
      const encoded = to.query.session;

      if (!encoded) {
        return { name: 'landing', query: { error: 'auth_failed' } };
      }

      try {
        const payload = JSON.parse(atob(encoded));
        auth.callback(payload);
        return { name: 'chat' };
      } catch {
        return { name: 'landing', query: { error: 'invalid_session' } };
      }
    },
  }, {
    path: '/chat',
    name: 'chat',
    component: chat,
    meta: {
      auth: true,
    },
  }, {
    path: '/admin/seats',
    name: 'admin-seats',
    component: seats,
    meta: {
      auth: true,
      adminOnly: true,
    },
  }, {
    path: '/admin/usage',
    name: 'admin-usage',
    component: usage,
    meta: {
      auth: true,
      adminOnly: true,
    },
  }],
  scrollBehavior: (to, from, _savedPosition) => {
    if (to.name === from.name) return;

    return {
      behavior: 'smooth',
      ...(to.hash && {
        el: to.hash,
        top: 150,
      } || { top: 0 }),
    };
  },
});

router.beforeEach((to, from, next) => {
  const auth = useAuth();
  // if route requires authentication - auth is true
  if (to.matched.some((record) => record.meta.auth)) {
    if (!auth.hasSession()) {
      next({
        name: 'landing',
        query: { redirect: to.fullPath }
      });
    } else if (to.matched.some((record) => record.meta.adminOnly) && !auth.isAdmin()) {
      next({ name: 'chat' });
    } else {
      next();
    }
  }
  // if route can be accessed without authentication - guest is true
  else {
    // v8 ignore next -- no route sets meta.guest yet; reserved for Phase 2.
    if (to.matched.some((record) => record.meta.guest)) {
      // guest handling reserved for Phase 2
    }
    // if not guest or requiresAuth continue
    else {
      next();
    }
  }
});

export default router;
