import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore';

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'applications',
      component: () => import('../views/ApplicationsDashboardView.vue'),
      meta: { requiresAuth: true, requiresStudent: true },
    },
    {
      path: '/workbench',
      name: 'workbench',
      component: () => import('../views/ApplicationsDashboardView.vue'),
      meta: { requiresAuth: true, requiresStudent: true },
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
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/documents/:type/new',
      name: 'document-new',
      component: () => import('../views/DocumentEditorView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/documents/:type/:id',
      name: 'document-edit',
      component: () => import('../views/DocumentEditorView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/homework',
      name: 'homework',
      component: () => import('../views/HomeworkCollectionView.vue'),
      meta: { requiresAuth: true, requiresStudent: true },
    },
    {
      path: '/submission-assets/:submissionId/:assetId/preview',
      name: 'submission-asset-preview',
      component: () => import('../views/HomeworkAssetPreviewView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/homework/submissions/:submissionId/assets/:assetId/preview',
      name: 'homework-asset-preview',
      component: () => import('../views/HomeworkAssetPreviewView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/homework/history/:type',
      name: 'homework-history',
      component: () => import('../views/HomeworkHistoryView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/users',
      name: 'admin-users',
      component: () => import('../views/AdminUsersView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/document-import',
      name: 'admin-document-import',
      component: () => import('../views/AdminDocumentImportView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/submissions',
      name: 'admin-submissions',
      component: () => import('../views/AdminSubmissionsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/submissions/:submissionId/repo',
      name: 'admin-repo-progress',
      component: () => import('../views/AdminRepoProgressView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/repo-overview',
      name: 'admin-repo-overview',
      component: () => import('../views/AdminRepoOverviewView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/submissions/:submissionId/workload',
      name: 'admin-workload-summary',
      component: () => import('../views/AdminWorkloadSummaryView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/submissions/:submissionId/teacher-assignments',
      name: 'admin-teacher-assignments',
      component: () => import('../views/AdminTeacherAssignmentsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/blog-overview',
      name: 'admin-blog-overview',
      component: () => import('../views/AdminBlogOverviewView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/requests',
      name: 'admin-requests',
      component: () => import('../views/AdminRequestsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/blog-runs',
      name: 'admin-blog-runs',
      component: () => import('../views/AdminBlogRunsView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/admin/groups',
      name: 'admin-groups',
      component: () => import('../views/AdminGroupsView.vue'),
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
    {
      path: '/admin/users/:userId/gitee',
      name: 'admin-user-gitee-insight',
      component: () => import('../views/AdminUserGiteeInsightView.vue'),
      meta: { requiresAuth: true, requiresAdmin: true },
    },
    {
      path: '/teacher/reviews',
      name: 'teacher-reviews',
      component: () => import('../views/TeacherScoringMobileView.vue'),
      meta: { requiresAuth: true, requiresStaff: true },
    },
    {
      path: '/teacher/reviews/:submissionId/members/:studentId/blogs',
      name: 'teacher-member-blogs',
      component: () => import('../views/TeacherMemberBlogsView.vue'),
      meta: { requiresAuth: true, requiresStaff: true },
    },
    {
      path: '/submissions/:submissionId/workload/:studentId',
      name: 'student-workload-summary',
      component: () => import('../views/StudentWorkloadSummaryView.vue'),
      meta: { requiresAuth: true, requiresStudent: true },
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

  if (to.meta?.requiresStaff && !authStore.isStaff) {
    return { name: 'applications' };
  }

  if (to.meta?.requiresStudent && authStore.isTeacher && !authStore.isAdmin) {
    return { name: 'teacher-reviews' };
  }

  if (to.name === 'applications' && authStore.isAdmin) {
    return { name: 'admin-users' };
  }

  if (to.name === 'applications' && authStore.isTeacher) {
    return { name: 'teacher-reviews' };
  }

  if (to.meta?.guestOnly && authStore.isAuthenticated) {
    if (authStore.isAdmin) return { name: 'admin-users' };
    if (authStore.isTeacher) return { name: 'teacher-reviews' };
    return { name: 'applications' };
  }

  return true;
});

export default router
