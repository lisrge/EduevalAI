<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 16px;">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">后台管理 / 博客总览</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">仅归档创新实训项目相关博客；每篇文章必须具有页面截图。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="primary-button" type="button" style="width: auto;" :disabled="loading" @click="crawlAll">抓取全部</button>
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="retryIncomplete">重抓未完成</button>
          <button class="primary-button" type="button" style="width: auto;" :disabled="loading" @click="crawlFailedNew">重抓失败/未抓取</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="exportCsv">导出CSV</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="loadOverview">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </div>

      <div style="display: flex; gap: 10px; align-items: center;">
        <input v-model="searchText" type="text" placeholder="搜索学号..." style="width: 200px; padding: 6px 10px;" @input="onSearch" />
        <span v-if="searchText" style="color: #666;">筛选结果: {{ filteredUsers.length }} / {{ (overview?.users || []).length }}</span>
      </div>

      <div v-if="message" class="panel" style="padding: 12px; color: #166534;">{{ message }}</div>
      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="dashboard-cards">
        <article class="dashboard-card">
          <span>少于 8 篇</span>
          <strong>{{ overview?.incomplete_user_count ?? 0 }}</strong>
        </article>
        <article class="dashboard-card">
          <span>抓取失败</span>
          <strong>{{ overview?.failed_user_count ?? 0 }}</strong>
        </article>
        <article class="dashboard-card">
          <span>短期集中发表</span>
          <strong>{{ overview?.burst_posting_user_count ?? 0 }}</strong>
        </article>
        <article class="dashboard-card">
          <span>抽取工作项</span>
          <strong>{{ totalWorkItems }}</strong>
        </article>
      </section>

      <section class="panel" style="min-height: 0;">
        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="!filteredUsers.length && !searchText" class="empty-state">当前没有博客数据。</div>
          <div v-else-if="!filteredUsers.length && searchText" class="empty-state">没有匹配 "{{ searchText }}" 的用户。</div>

          <table v-else style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="text-align: left; border-bottom: 1px solid var(--border);">
                <th style="padding: 10px 8px;">学号</th>
                <th style="padding: 10px 8px;">博客源</th>
                <th style="padding: 10px 8px;">文章数</th>
                <th style="padding: 10px 8px;">扫描数</th>
                <th style="padding: 10px 8px;">项目组博客</th>
                <th style="padding: 10px 8px;">个人博客</th>
                <th style="padding: 10px 8px;">纯代码倾向</th>
                <th style="padding: 10px 8px;">科普</th>
                <th style="padding: 10px 8px;">工作项</th>
                <th style="padding: 10px 8px;">最近发布时间</th>
                <th style="padding: 10px 8px;">最近8篇跨度</th>
                <th style="padding: 10px 8px;">低质量</th>
                <th style="padding: 10px 8px;">状态/标记</th>
                <th style="padding: 10px 8px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredUsers" :key="item.user_id" style="border-bottom: 1px solid var(--border);">
                <td style="padding: 10px 8px; font-weight: 700;">{{ item.student_id }}</td>
                <td style="padding: 10px 8px;">{{ item.active_source_count }} / {{ item.source_count }}</td>
                <td style="padding: 10px 8px;">{{ item.post_count }}</td>
                <td style="padding: 10px 8px;">{{ item.scanned_blog_count }}</td>
                <td style="padding: 10px 8px;">{{ item.project_blog_count }}</td>
                <td style="padding: 10px 8px;">{{ item.personal_blog_count }}</td>
                <td style="padding: 10px 8px;">{{ item.code_dump_count }}</td>
                <td style="padding: 10px 8px;">{{ item.popular_science_count }}</td>
                <td style="padding: 10px 8px;">{{ item.work_item_count }}</td>
                <td style="padding: 10px 8px;">{{ formatDate(item.latest_published_at) }}</td>
                <td style="padding: 10px 8px;">{{ item.recent_eight_span_days == null ? '-' : `${item.recent_eight_span_days} 天` }}</td>
                <td style="padding: 10px 8px;">{{ item.low_quality_count }}</td>
                <td style="padding: 10px 8px;">
                  <div>{{ crawlStatusLabel(item.crawl_status) }}</div>
                  <div v-for="flag in item.risk_flags" :key="flag" class="risk-flag">{{ riskLabel(flag) }}</div>
                </td>
                <td style="padding: 10px 8px;">
                  <button class="ghost-button" type="button" style="width: auto;" @click="goUserBlogs(item)">查看</button>
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
import { crawlAllBlogSources, crawlFailedOrNewUsers, fetchBlogOverview, retryIncompleteBlogUsers } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const overview = ref(null);
const loading = ref(false);
const errorMessage = ref('');
const message = ref('');
const searchText = ref('');
const totalWorkItems = computed(() => (overview.value?.users || []).reduce((sum, item) => sum + Number(item.work_item_count || 0), 0));
const filteredUsers = computed(() => {
  if (!searchText.value.trim()) return overview.value?.users || [];
  const q = searchText.value.trim().toLowerCase();
  return (overview.value?.users || []).filter(u => String(u.student_id || '').toLowerCase().includes(q));
});

function goBack() {
  router.push({ name: 'admin-users' });
}

function goUserBlogs(item) {
  router.push({ name: 'admin-user-blogs', params: { userId: String(item.user_id) } });
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function crawlStatusLabel(value) {
  return { queued: '排队中', running: '抓取中', success: '成功', partial_success: '部分失败', failed: '失败', idle: '未抓取' }[String(value || '').toLowerCase()] || String(value || '-');
}

function riskLabel(value) {
  return {
    blog_count_below_8: '少于8篇',
    blog_url_missing: '未填写博客地址',
    published_time_missing: '发表时间缺失',
    eight_posts_within_1_week: '8篇集中在1周内',
    eight_posts_within_2_weeks: '8篇集中在2周内',
    code_only_blog_present: '存在纯代码博客',
    empty_popular_science_present: '存在空泛科普博客',
    crawl_failed_retry_required: '抓取失败，需重试',
  }[value] || value;
}

async function loadOverview() {
  loading.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    overview.value = await fetchBlogOverview(authStore.token);
  } catch (error) {
    errorMessage.value = error?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function crawlAll() {
  loading.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const result = await crawlAllBlogSources(authStore.token);
    message.value = `已加入后台抓取队列：${result?.queued_count ?? 0} 个用户。可前往“博客抓取记录”查看进度。`;
    await loadOverview();
  } catch (error) {
    errorMessage.value = error?.message || '抓取失败';
  } finally {
    loading.value = false;
  }
}

async function retryIncomplete() {
  loading.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const result = await retryIncompleteBlogUsers(authStore.token);
    message.value = `已重新排队 ${result?.queued_count ?? 0} 个用户；另有 ${result?.missing_blog_url_user_ids?.length ?? 0} 个用户未填写博客地址。`;
    await loadOverview();
  } catch (error) {
    errorMessage.value = error?.message || '重新抓取失败';
  } finally {
    loading.value = false;
  }
}

async function exportCsv() {
  try {
    const token = authStore.token;
    const base = new URL(import.meta.env?.VUE_APP_EDUEVAL_API_BASE || window.location.origin + '/api');
    const resp = await fetch(`${base.origin}/api/users/admin/blogs/export-csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!resp.ok) throw new Error('导出失败');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'blog_metrics.csv';
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    errorMessage.value = e?.message || '导出失败';
  }
}

function onSearch() {
  // reactive, no-op needed
}

async function crawlFailedNew() {
  loading.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const result = await crawlFailedOrNewUsers(authStore.token);
    const count = Array.isArray(result) ? result.length : (result?.queued_count ?? 0);
    message.value = `已加入后台抓取队列：${count} 个用户（仅包含从未抓取或上次失败的用户）。`;
    await loadOverview();
  } catch (error) {
    errorMessage.value = error?.message || '抓取失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadOverview();
});
</script>

<style scoped>
.dashboard-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-card {
  padding: 16px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.dashboard-card strong {
  display: block;
  margin-top: 6px;
  font-size: 28px;
}

.risk-flag {
  display: inline-block;
  margin: 3px 4px 0 0;
  padding: 3px 7px;
  border-radius: 999px;
  background: #fee2e2;
  color: #991b1b;
  font-size: 11px;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .dashboard-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .dashboard-cards {
    grid-template-columns: 1fr;
  }
}
</style>
