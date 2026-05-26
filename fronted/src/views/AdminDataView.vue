<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap;">
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
          <h2 style="margin: 0;">后台管理</h2>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="ghost-button" type="button" style="width: auto;" :style="menuStyle('admin-users')" @click="goAdminUsers">权限管理</button>
            <button class="ghost-button" type="button" style="width: auto;" :style="menuStyle('admin-data')" @click="goAdminData">数据管理</button>
          </div>
        </div>
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>

      <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

      <section class="panel" style="min-height: 0;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">学号与博客地址</h3>
            <p class="panel-subtitle">用于后端调用的绑定表。</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="loadList">刷新</button>
        </div>

        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="items.length === 0" class="empty-state">暂无数据。</div>

          <table v-else style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="text-align: left; border-bottom: 1px solid var(--border);">
                <th style="padding: 10px 8px; width: 140px;">学号</th>
                <th style="padding: 10px 8px;">博客地址</th>
                <th style="padding: 10px 8px; width: 180px;">更新时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in items" :key="row.student_id" style="border-bottom: 1px solid var(--border);">
                <td style="padding: 10px 8px; font-weight: 700;">{{ row.student_id }}</td>
                <td style="padding: 10px 8px; word-break: break-word;">
                  <a v-if="row.blog_url" :href="row.blog_url" target="_blank" rel="noreferrer">{{ row.blog_url }}</a>
                  <span v-else style="opacity: 0.6;">-</span>
                </td>
                <td style="padding: 10px 8px;">{{ formatTime(row.updated_at) }}</td>
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
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { adminListStudentBlogBindings } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const items = ref([]);
const loading = ref(false);
const localError = ref(null);

const errorMessage = computed(() => localError.value);

function goBack() {
  router.push({ name: 'applications' });
}

function menuStyle(name) {
  const active = String(route.name || '') === String(name || '');
  if (!active) return {};
  return { background: 'var(--primary)', color: 'white', borderColor: 'transparent' };
}

function goAdminUsers() {
  router.push({ name: 'admin-users' });
}

function goAdminData() {
  router.push({ name: 'admin-data' });
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

async function loadList() {
  localError.value = null;
  loading.value = true;
  try {
    const list = await adminListStudentBlogBindings(authStore.token);
    items.value = Array.isArray(list) ? list : [];
  } catch (e) {
    localError.value = e?.message || '加载失败';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadList();
});
</script>
