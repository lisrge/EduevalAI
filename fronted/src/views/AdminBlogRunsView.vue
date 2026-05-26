<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap;">
        <h2 style="margin: 0;">后台管理 · 博客抓取任务</h2>
        <div class="top-actions">
          <button class="ghost-button" type="button" @click="goBack">返回</button>
        </div>
      </div>

      <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

      <section class="panel">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">抓取任务日志</h3>
            <p class="panel-subtitle">按时间查看管理员发起的博客抓取结果。</p>
          </div>
          <button class="ghost-button" type="button" :disabled="loading" @click="loadRuns">刷新</button>
        </div>

        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="items.length === 0" class="empty-state">暂无抓取任务。</div>

          <table v-else style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="text-align: left; border-bottom: 1px solid var(--border);">
                <th style="padding: 10px 8px;">学号</th>
                <th style="padding: 10px 8px;">状态</th>
                <th style="padding: 10px 8px;">发现</th>
                <th style="padding: 10px 8px;">保存</th>
                <th style="padding: 10px 8px;">失败</th>
                <th style="padding: 10px 8px;">开始时间</th>
                <th style="padding: 10px 8px;">结束时间</th>
                <th style="padding: 10px 8px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in items" :key="item.id" style="border-bottom: 1px solid var(--border);">
                <td style="padding: 10px 8px; font-weight: 700;">{{ item.student_id }}</td>
                <td style="padding: 10px 8px;">
                  <span :class="['badge', statusBadge(item.status)]">{{ item.status }}</span>
                </td>
                <td style="padding: 10px 8px;">{{ item.total_found }}</td>
                <td style="padding: 10px 8px;">{{ item.total_saved }}</td>
                <td style="padding: 10px 8px;">{{ item.total_failed }}</td>
                <td style="padding: 10px 8px;">{{ formatTime(item.started_at) }}</td>
                <td style="padding: 10px 8px;">{{ formatTime(item.finished_at) }}</td>
                <td style="padding: 10px 8px;">
                  <button class="ghost-button" type="button" @click="goUserBlogs(item.user_id)">查看该用户博客</button>
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
import { adminListAllBlogCrawlRuns } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const items = ref([]);
const loading = ref(false);
const localError = ref('');

const errorMessage = computed(() => localError.value);

function goBack() {
  router.push({ name: 'admin-users' });
}

function goUserBlogs(userId) {
  router.push({ name: 'admin-user-blogs', params: { userId: String(userId) } });
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? String(value) : dt.toLocaleString();
}

function statusBadge(value) {
  if (value === 'success') return 'ok';
  if (value === 'partial_success') return 'warn';
  if (value === 'failed') return 'error';
  return 'neutral';
}

async function loadRuns() {
  loading.value = true;
  localError.value = '';
  try {
    const list = await adminListAllBlogCrawlRuns(authStore.token);
    items.value = Array.isArray(list) ? list : [];
  } catch (e) {
    localError.value = e?.message || '加载抓取任务失败';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadRuns();
});
</script>

<style scoped>
.top-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.top-actions .ghost-button {
  height: 44px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
