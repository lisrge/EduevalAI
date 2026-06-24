<template>
  <header class="app-header">
    <div class="app-header__inner">
      <div class="brand-block">
        <img src="../assets/EduevalAI_logo.png" alt="Logo" class="logo-image" />
        <div>
          <div class="brand-row">
            <h1 class="brand-title brand-name">EduevalAI</h1>
            <span class="badge badge-warning">Beta</span>
          </div>
          <p class="brand-subtitle">课程过程材料、博客抓取、教师评分一体化工作台</p>
        </div>
    </div>
    <!-- 右侧：功能按钮 -->
      <div class="header-actions">
        <div v-if="false" class="header-icon-actions">
          <button type="button" class="header-icon-button" title="切换主题" @click="themeStore.toggle">
            <Moon v-if="themeStore.isDark" :size="18" />
            <Sun v-else :size="18" />
          </button>
          <button type="button" class="header-icon-button" title="功能预留">
            <Trash2 :size="18" />
          </button>
        </div>

        <div
          ref="userMenuRef"
          class="user-menu-trigger"
          :class="{ 'is-open': menuOpen }"
          @click="toggleMenu"
        >
          <div class="user-meta">
            <span class="user-name">{{ displayName }}</span>
            <span class="user-role">{{ displayRole }}</span>
          </div>
          <div class="avatar-shell">
            <img :src="avatarUrl" alt="Avatar" class="avatar-image" />
          </div>

          <div
            v-if="menuOpen && authStore.user"
            class="user-dropdown"
            @click.stop
          >
            <button
              v-if="!authStore.isTeacher"
              type="button"
              class="dropdown-item"
              @click="goWorkbench"
            >
              工作台
            </button>
            <button
              v-if="!authStore.isTeacher"
              type="button"
              class="dropdown-item"
              @click="goHomework"
            >
              交作业
            </button>
            <button
              v-if="authStore.isTeacher"
              type="button"
              class="dropdown-item"
              @click="goTeacherReviews"
            >
              教师评分端
            </button>
            <button
              type="button"
              class="dropdown-item"
              @click="goProfile"
            >
              个人空间
            </button>
            <button
              v-if="authStore.isAdmin"
              type="button"
              class="dropdown-item"
              @click="goAdmin"
            >
              后台管理
            </button>
            <button
              v-if="authStore.isAdmin"
              type="button"
              class="dropdown-item"
              @click="goBlogQuality"
            >
              博客质量总览
            </button>
            <button
              v-if="authStore.isAdmin"
              type="button"
              class="dropdown-item"
              @click="goRepoOverview"
            >
              Gitee总览
            </button>
            <button
              type="button"
              class="dropdown-item danger"
              @click="doLogout"
            >
              退出登录
            </button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { Moon, Sun, Trash2 } from 'lucide-vue-next';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';
import { useThemeStore } from '../stores/themeStore';

const authStore = useAuthStore();
const themeStore = useThemeStore();
const router = useRouter();

const displayName = computed(() => authStore.user?.student_id || '未登录');
const displayRole = computed(() => {
  if (!authStore.user) return '游客';
  if (authStore.isAdmin) return '管理员';
  if (authStore.isTeacher) return '教师';
  return '学生';
});
const avatarUrl = computed(() => {
  const name = encodeURIComponent(String(displayName.value || 'User'));
  return `https://ui-avatars.com/api/?name=${name}&background=3d63dd&color=fff`;
});

const menuOpen = ref(false);
const userMenuRef = ref(null);

function closeMenu() {
  menuOpen.value = false;
}

function toggleMenu() {
  if (!authStore.user) return;
  menuOpen.value = !menuOpen.value;
}

function onDocumentClick(event) {
  const el = userMenuRef.value;
  if (!el) return;
  if (el.contains(event.target)) return;
  closeMenu();
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick);
});

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick);
});

function goProfile() {
  closeMenu();
  router.push({ name: 'profile' });
}

function goWorkbench() {
  closeMenu();
  router.push({ name: 'workbench' });
}

function goHomework() {
  closeMenu();
  router.push({ name: 'homework' });
}

function goTeacherReviews() {
  closeMenu();
  router.push({ name: 'teacher-reviews' });
}

function goAdmin() {
  closeMenu();
  router.push({ name: 'admin-users' });
}

function goBlogQuality() {
  closeMenu();
  router.push({ name: 'admin-blog-overview' });
}

function goRepoOverview() {
  closeMenu();
  router.push({ name: 'admin-repo-overview' });
}

async function doLogout() {
  closeMenu();
  await authStore.logout();
  router.replace({ name: 'login' });
}
</script>

<style scoped>
.app-header {
  position: sticky;
  top: 0;
  z-index: 30;
  padding: 18px 0 0;
  backdrop-filter: blur(12px);
}

.app-header__inner {
  width: min(1320px, calc(100% - 40px));
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  padding: 14px 18px;
  border: 1px solid var(--border);
  border-radius: 26px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: var(--shadow-sm);
}

:global([data-web-theme='dark']) .app-header__inner {
  background: rgba(15, 23, 42, 0.72);
}

.brand-block {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.logo-image {
  width: 54px;
  height: 54px;
  border-radius: 18px;
  object-fit: contain;
  box-shadow: 0 10px 24px rgba(61, 99, 221, 0.18);
}

.brand-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.brand-name {
  font-size: 30px;
}

.brand-subtitle {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-left: auto;
}

.header-icon-actions {
  display: flex;
  gap: 10px;
}

.header-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 42px;
  height: 42px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  color: var(--text-secondary);
  cursor: pointer;
  transition: transform 0.2s ease, color 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.header-icon-button:hover {
  color: var(--primary);
  border-color: var(--border-strong);
  transform: translateY(-1px);
}

.user-menu-trigger {
  position: relative;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 8px 6px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
}

.user-menu-trigger.is-open {
  border-color: var(--border-strong);
}

.user-meta {
  display: grid;
  justify-items: end;
  min-width: 0;
}

.user-name {
  font-size: 12px;
  font-weight: 800;
  color: var(--text-primary);
}

.user-role {
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--text-secondary);
}

.avatar-shell {
  width: 36px;
  height: 36px;
  border-radius: 999px;
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.avatar-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.user-dropdown {
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  min-width: 240px;
  display: grid;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: var(--shadow-md);
}

.dropdown-item {
  width: 100%;
  min-height: 46px;
  padding: 0 16px;
  border: 0;
  border-bottom: 1px solid var(--border);
  background: transparent;
  text-align: left;
  color: var(--text-primary);
  cursor: pointer;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.dropdown-item:last-child {
  border-bottom: 0;
}

.dropdown-item:hover {
  background: var(--surface-soft);
  color: var(--primary);
}

.dropdown-item.danger:hover {
  color: var(--danger);
}

@media (max-width: 1024px) {
  .app-header__inner {
    width: min(100%, calc(100% - 24px));
  }
}

@media (max-width: 720px) {
  .app-header {
    padding-top: 12px;
  }

  .app-header__inner {
    width: min(100%, calc(100% - 16px));
    padding: 12px 14px;
  }

  .brand-name {
    font-size: 24px;
  }

  .brand-subtitle {
    display: none;
  }
}

@media (max-width: 560px) {
  .header-actions {
    width: 100%;
    justify-content: space-between;
  }

  .user-menu-trigger {
    margin-left: auto;
  }
}
</style>
