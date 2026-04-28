<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap;">
        <h2 style="margin: 0;">后台管理 · 用户权限</h2>
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>

      <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

      <section class="panel" style="min-height: 0;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">用户列表</h3>
            <p class="panel-subtitle">默认所有用户为普通用户；可在此将其权限切换为管理员。</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="loadUsers">刷新</button>
        </div>

        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="users.length === 0" class="empty-state">暂无用户。</div>

          <table v-else style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="text-align: left; border-bottom: 1px solid var(--border);">
                <th style="padding: 10px 8px;">学号</th>
                <th style="padding: 10px 8px;">博客发布篇数</th>
                <th style="padding: 10px 8px;">提交申请书</th>
                <th style="padding: 10px 8px;">提交任务书</th>
                <th style="padding: 10px 8px;">权限等级</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in users" :key="u.id" style="border-bottom: 1px solid var(--border);">
                <td style="padding: 10px 8px; font-weight: 700;">{{ u.student_id }}</td>

                <td style="padding: 10px 8px;">
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto; padding: 6px 10px;"
                    :disabled="blogTotal(u) === 0"
                    @click="goBlogs(u)"
                  >
                    <span :style="{ color: '#16a34a', fontWeight: 800 }">{{ u.blog?.normal ?? 0 }}</span>
                    <span style="opacity: 0.6; font-weight: 700; padding: 0 6px;">/</span>
                    <span :style="{ color: '#ef4444', fontWeight: 800 }">{{ u.blog?.abnormal ?? 0 }}</span>
                  </button>
                </td>

                <td style="padding: 10px 8px;">
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto; padding: 6px 10px;"
                    :disabled="Number(u.application_draft_count || 0) === 0"
                    @click="goDocuments(u, 'application')"
                  >
                    {{ Number(u.application_draft_count || 0) === 0 ? '否' : '是' }}
                  </button>
                </td>

                <td style="padding: 10px 8px;">
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto; padding: 6px 10px;"
                    :disabled="Number(u.task_draft_count || 0) === 0"
                    @click="goDocuments(u, 'task')"
                  >
                    {{ Number(u.task_draft_count || 0) === 0 ? '否' : '是' }}
                  </button>
                </td>

                <td style="padding: 10px 8px;">
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto; padding: 6px 10px;"
                    :disabled="savingId === u.id || isRootAdmin(u)"
                    @click="toggleRole(u)"
                  >
                    {{ isRootAdmin(u) ? '初始管理员' : roleLabel(u.role) }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { adminListUsers, adminUpdateUserRole } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const users = ref([]);
const loading = ref(false);
const savingId = ref(null);
const localError = ref(null);

const errorMessage = computed(() => localError.value);

function roleLabel(role) {
  return String(role || '').toLowerCase() === 'admin' ? '管理员' : '普通用户';
}

function isRootAdmin(u) {
  return Boolean(u?.is_root_admin);
}

function blogTotal(u) {
  const n = Number(u?.blog?.normal || 0);
  const a = Number(u?.blog?.abnormal || 0);
  return n + a;
}

function goBack() {
  router.push({ name: 'applications' });
}

function goDocuments(u, type) {
  router.push({ name: 'admin-user-documents', params: { userId: String(u.id), type } });
}

function goBlogs(u) {
  router.push({ name: 'admin-user-blogs', params: { userId: String(u.id) } });
}

async function loadUsers() {
  localError.value = null;
  loading.value = true;
  try {
    const list = await adminListUsers(authStore.token);
    users.value = Array.isArray(list) ? list : [];
  } catch (e) {
    localError.value = e?.message || '加载失败';
    users.value = [];
  } finally {
    loading.value = false;
  }
}

async function toggleRole(u) {
  if (isRootAdmin(u)) return;
  const current = String(u?.role || '').toLowerCase() === 'admin' ? 'admin' : 'user';
  const next = current === 'admin' ? 'user' : 'admin';
  const ok = window.confirm('确认修改其权限等级？');
  if (!ok) return;

  savingId.value = u.id;
  localError.value = null;
  try {
    const resp = await adminUpdateUserRole(authStore.token, u.id, next);
    const updatedRole = resp?.role || next;
    users.value = users.value.map(item => (item.id === u.id ? { ...item, role: updatedRole } : item));
  } catch (e) {
    localError.value = e?.message || '修改失败';
  } finally {
    savingId.value = null;
  }
}

onMounted(() => {
  loadUsers();
});
</script>
