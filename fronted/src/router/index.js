import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore';

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'applications',
      component: () => import('../views/ApplicationsDashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue'),
      meta: { requiresAuth: true },
    },
  ]
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  await authStore.ensureInitialized();

  if (to.meta?.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }

  if (to.meta?.guestOnly && authStore.isAuthenticated) {
    return { name: 'applications' };
  }

  return true;
});

export default router
