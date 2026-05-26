<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 16px;">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">后台管理 / 博客总览</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">统计博客源、文章数量、代码倾向、科普文章和工作抽取结果。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="primary-button" type="button" style="width: auto;" :disabled="loading" @click="crawlAll">抓取全部</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="loadOverview">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </div>

      <div v-if="message" class="panel" style="padding: 12px; color: #166534;">{{ message }}</div>
      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="dashboard-cards">
        <article class="dashboard-card">
          <span>博客源</span>
          <strong>{{ overview?.total_sources ?? 0 }}</strong>
        </article>
        <article class="dashboard-card">
          <span>文章快照</span>
          <strong>{{ overview?.total_posts ?? 0 }}</strong>
        </article>
        <article class="dashboard-card">
          <span>纯代码倾向</span>
          <strong>{{ overview?.total_code_dump_posts ?? 0 }}</strong>
        </article>
        <article class="dashboard-card">
          <span>科普文章</span>
          <strong>{{ overview?.total_popular_science_posts ?? 0 }}</strong>
        </article>
      </section>

      <section class="panel" style="min-height: 0;">
        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="!(overview?.users || []).length" class="empty-state">当前没有博客数据。</div>

          <table v-else style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="text-align: left; border-bottom: 1px solid var(--border);">
                <th style="padding: 10px 8px;">学号</th>
                <th style="padding: 10px 8px;">博客源</th>
                <th style="padding: 10px 8px;">文章数</th>
                <th style="padding: 10px 8px;">项目组博客</th>
                <th style="padding: 10px 8px;">个人博客</th>
                <th style="padding: 10px 8px;">纯代码倾向</th>
                <th style="padding: 10px 8px;">科普</th>
                <th style="padding: 10px 8px;">工作项</th>
                <th style="padding: 10px 8px;">最近发布时间</th>
                <th style="padding: 10px 8px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in overview.users" :key="item.user_id" style="border-bottom: 1px solid var(--border);">
                <td style="padding: 10px 8px; font-weight: 700;">{{ item.student_id }}</td>
                <td style="padding: 10px 8px;">{{ item.active_source_count }} / {{ item.source_count }}</td>
                <td style="padding: 10px 8px;">{{ item.post_count }}</td>
                <td style="padding: 10px 8px;">{{ item.project_blog_count }}</td>
                <td style="padding: 10px 8px;">{{ item.personal_blog_count }}</td>
                <td style="padding: 10px 8px;">{{ item.code_dump_count }}</td>
                <td style="padding: 10px 8px;">{{ item.popular_science_count }}</td>
                <td style="padding: 10px 8px;">{{ item.work_item_count }}</td>
                <td style="padding: 10px 8px;">{{ formatDate(item.latest_published_at) }}</td>
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
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { crawlAllBlogSources, fetchBlogOverview } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const overview = ref(null);
const loading = ref(false);
const errorMessage = ref('');
const message = ref('');

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
    message.value = `全量抓取完成：源 ${result?.source_count ?? 0} 个，扫描 ${result?.crawled_count ?? 0} 篇，新增 ${result?.created_count ?? 0} 篇，更新 ${result?.updated_count ?? 0} 篇`;
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
