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
    {
      path: '/documents',
      name: 'documents',
      component: () => import('../views/MyDocumentsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:type/new',
      name: 'document-new',
      component: () => import('../views/DocumentEditorView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:type/:id',
      name: 'document-edit',
      component: () => import('../views/DocumentEditorView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/homework',
      name: 'homework',
      component: () => import('../views/HomeworkCollectionView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/homework/history/:type',
      name: 'homework-history',
      component: () => import('../views/HomeworkHistoryView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('../views/AdminUsersView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/users/:userId/documents/:type',
      name: 'admin-user-documents',
      component: () => import('../views/AdminUserDocumentsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/users/:userId/blogs',
      name: 'admin-user-blogs',
      component: () => import('../views/AdminUserBlogsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
  ]
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore();
  await authStore.ensureInitialized();

  if (to.meta?.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } };
  }

  if (to.meta?.requiresAdmin && !authStore.isAdmin) {
    return { name: 'applications' };
  }

  if (to.meta?.guestOnly && authStore.isAuthenticated) {
    return { name: 'applications' };
  }

  return true;
});

export default router
