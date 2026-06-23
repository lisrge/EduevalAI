<template>
  <!-- 顶部导航栏：边框改为更明确但依然极浅的灰色 #e2e8f0 -->
  <header class="h-24 flex items-center justify-between px-12 bg-[#f0f4f9] shrink-0 relative z-10 border-b border-[#f1f5f9] shadow-sm pt-6 pb-2">
    <!-- 左侧：项目 Logo 与 名称 -->
    <div class="flex items-center" style="gap: 24px;">
      <img src="../assets/EduevalAI_logo.png" style="margin-left: 24px;" alt="Logo" class="logo-image rounded-2xl object-contain shadow-sm" />
      <div class="flex items-center" style="gap: 16px;">
        <h1 class="font-kavo text-3xl text-text-primary tracking-normal">EduevalAI</h1>
        <!-- BETA 标签：紫色渐变或纯色 -->
        <span class="px-3 py-1 text-[9px] bg-purple-100 text-purple-600 rounded-full font-black uppercase tracking-widest shadow-sm inline-flex items-center justify-center">Beta</span>
      </div>
    </div>

    <!-- 右侧：功能按钮 -->
    <div class="flex items-center" style="gap: 40px; margin-right: 24px;">
      <div class="flex items-center" style="gap: 16px;">
        <button class="p-3 text-text-secondary bg-white hover:text-primary rounded-xl shadow-sm hover:shadow-md transition-all duration-300 border-none active:scale-95" title="切换主题" @click="themeStore.toggle">
          <Moon v-if="themeStore.isDark" :size="20" />
          <Sun v-else :size="20" />
        </button>
        <button class="p-3 text-text-secondary bg-white hover:text-red-500 rounded-xl shadow-sm hover:shadow-md transition-all duration-300 border-none active:scale-95" title="清空对话">
          <Trash2 :size="20" />
        </button>
      </div>

      <!-- 用户资料区域：优化布局并强制锁定头像尺寸 -->
      <div
        ref="userMenuRef"
        class="flex items-center group cursor-pointer bg-white/80 rounded-full shadow-sm hover:shadow-md transition-all duration-300 relative"
        style="padding: 4px 12px; gap: 8px;"
        @click="toggleMenu"
      >
        <div class="flex flex-col items-end hidden md:flex">
          <span class="text-[11px] font-black text-text-primary leading-none">{{ displayName }}</span>
          <span class="text-[9px] text-text-tertiary mt-0.5 font-bold uppercase tracking-tighter">{{ displayRole }}</span>
        </div>
        <!-- 用户头像：强制使用 inline style 锁定极小尺寸 (32px) -->
        <div 
          class="rounded-full border border-gray-100 overflow-hidden shadow-sm shrink-0" 
          style="width: 32px !important; height: 32px !important; min-width: 32px !important; min-height: 32px !important;"
        >
          <img src="https://ui-avatars.com/api/?name=User&background=2563eb&color=fff" alt="Avatar" style="width: 100%; height: 100%; object-fit: cover;" />
        </div>

        <div
          v-if="menuOpen && authStore.user"
          style="position: absolute; top: calc(100% + 10px); right: 0; min-width: 220px; z-index: 50; background: var(--surface); border: 1px solid var(--border); border-radius: 16px; box-shadow: 0 16px 40px rgba(0, 0, 0, 0.16); overflow: hidden;"
          @click.stop
        >
          <button
            v-if="!authStore.isTeacher"
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goWorkbench"
          >
            工作台
          </button>
          <button
            v-if="!authStore.isTeacher"
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goHomework"
          >
            交作业
          </button>
          <button
            v-if="authStore.isTeacher"
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goTeacherReviews"
          >
            教师评分端
          </button>
          <button
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goProfile"
          >
            个人空间
          </button>
          <button
            v-if="authStore.isAdmin"
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goAdmin"
          >
            后台管理
          </button>
          <button
            v-if="authStore.isAdmin"
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goBlogQuality"
          >
            博客质量总览
          </button>
          <button
            v-if="authStore.isAdmin"
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; border-bottom: 1px solid var(--border); background: transparent;"
            @click="goRepoOverview"
          >
            Gitee总览
          </button>
          <button
            type="button"
            class="ghost-button"
            style="width: 100%; border-radius: 0; justify-content: flex-start; border: 0; background: transparent;"
            @click="doLogout"
          >
            退出登录
          </button>
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
  if (!authStore.user) return 'Guest';
  if (authStore.isAdmin) return 'Admin';
  if (authStore.isTeacher) return 'Teacher';
  return 'Student';
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
/* 显式定义 Logo 尺寸 */
.logo-image {
  width: 48px !important;
  height: 48px !important;
  min-width: 36px;
  min-height: 36px;
}
</style>
