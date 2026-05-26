<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div class="blog-admin-shell">
      <section class="blog-hero">
        <div>
          <p class="hero-eyebrow">Blog Evidence</p>
          <h2>管理员博客取证台</h2>
          <p class="hero-copy">
            查看该用户的博客列表、抓取记录、正文预览、归档地址和人工审核状态。
          </p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" @click="goBack">返回用户列表</button>
        </div>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="blog-summary-grid">
        <article class="summary-card">
          <span>博客主页</span>
          <strong>{{ blogProfile.blog_home_url || '未配置' }}</strong>
        </article>
        <article class="summary-card">
          <span>抓取状态</span>
          <strong :style="{ color: crawlStatusColor(blogProfile.blog_crawl_status) }">
            {{ crawlStatusLabel(blogProfile.blog_crawl_status) }}
          </strong>
        </article>
        <article class="summary-card">
          <span>文章数量</span>
          <strong>{{ items.length }}</strong>
        </article>
        <article class="summary-card">
          <span>最近抓取</span>
          <strong>{{ formatTime(blogProfile.blog_last_crawled_at) }}</strong>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">博客配置与抓取</h3>
            <p class="panel-subtitle">支持填写 CSDN 用户名或完整主页地址，后端会自动规范化。</p>
          </div>
        </div>
        <div class="edueval-panel-body blog-toolbar">
          <button class="ghost-button" type="button" @click="openBlogProfileModal">编辑主页地址</button>
          <button class="primary-button" type="button" :disabled="crawling || !blogProfile.blog_home_url" @click="triggerCrawl">
            {{ crawling ? '抓取中...' : '开始抓取' }}
          </button>
          <button class="ghost-button" type="button" :disabled="loading" @click="loadAll">刷新</button>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">筛选与抓取记录</h3>
            <p class="panel-subtitle">按标题、审核状态和抓取状态快速定位文章。</p>
          </div>
        </div>
        <div class="edueval-panel-body filter-grid">
          <label class="field">
            <span>标题搜索</span>
            <input v-model.trim="filters.keyword" type="text" placeholder="搜索文章标题" />
          </label>
          <label class="field">
            <span>审核状态</span>
            <select v-model="filters.reviewStatus">
              <option value="all">全部</option>
              <option value="pending">待审核</option>
              <option value="normal">正常</option>
              <option value="abnormal">异常</option>
            </select>
          </label>
          <label class="field">
            <span>抓取状态</span>
            <select v-model="filters.captureStatus">
              <option value="all">全部</option>
              <option value="success">成功</option>
              <option value="partial">部分成功</option>
              <option value="failed">失败</option>
            </select>
          </label>
        </div>
        <div class="edueval-panel-body table-wrap">
          <div v-if="runItems.length === 0" class="empty-state">暂无抓取记录。</div>
          <table v-else class="admin-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>发现</th>
                <th>保存</th>
                <th>失败</th>
                <th>开始时间</th>
                <th>结束时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="run in runItems" :key="run.id">
                <td>{{ run.status }}</td>
                <td>{{ run.total_found }}</td>
                <td>{{ run.total_saved }}</td>
                <td>{{ run.total_failed }}</td>
                <td>{{ formatTime(run.started_at) }}</td>
                <td>{{ formatTime(run.finished_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="content-grid">
        <section class="panel list-panel">
          <div class="panel-header">
            <div>
              <h3 style="margin: 0;">博客列表</h3>
              <p class="panel-subtitle">当前结果 {{ filteredItems.length }} / {{ items.length }}</p>
            </div>
          </div>

          <div class="edueval-panel-body list-body">
            <div v-if="loading" class="empty-state">加载中...</div>
            <div v-else-if="filteredItems.length === 0" class="empty-state">暂无匹配博客。</div>
            <div v-else class="blog-card-stack">
              <article
                v-for="blog in filteredItems"
                :key="blog.id"
                class="blog-item-card"
                :class="{ active: selectedBlogId === blog.id }"
              >
                <div class="blog-item-title">{{ blog.title }}</div>
                <div class="muted-line">
                  发布时间 {{ formatTime(blog.published_at) }} · 抓取 {{ blog.capture_status }}
                </div>
                <div class="inline-stack" style="margin-top: 10px;">
                  <button class="ghost-button compact-button" type="button" @click="previewBlog(blog)">正文预览</button>
                  <button class="ghost-button compact-button" type="button" :disabled="!blog.has_html" @click="openArchiveModal(blog)">归档地址</button>
                  <button class="ghost-button compact-button" type="button" :disabled="!blog.has_screenshot" @click="openScreenshot(blog)">截图</button>
                  <a :href="blog.url" target="_blank" rel="noopener noreferrer" class="ghost-button compact-button origin-link">原文</a>
                </div>
                <div class="inline-stack" style="margin-top: 10px;">
                  <span :style="{ color: reviewColor(blog.review_status), fontWeight: 800 }">{{ reviewLabel(blog.review_status) }}</span>
                  <button class="ghost-button compact-button" type="button" @click="openReviewModal(blog, 'normal')">标记正常</button>
                  <button class="ghost-button compact-button danger-outline" type="button" @click="openReviewModal(blog, 'abnormal')">标记异常</button>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section class="panel preview-panel">
          <div class="panel-header">
            <div>
              <h3 style="margin: 0;">站内正文预览</h3>
              <p class="panel-subtitle">{{ previewDetail?.title || '选择一篇博客后在这里查看正文与摘要。' }}</p>
            </div>
            <button v-if="selectedBlogId" class="ghost-button compact-button" type="button" @click="clearPreview">清空</button>
          </div>
          <div class="edueval-panel-body preview-body">
            <div v-if="previewLoading" class="empty-state">加载中...</div>
            <div v-else-if="previewError" class="alert error">{{ previewError }}</div>
            <div v-else-if="!previewDetail" class="empty-state">请选择一篇博客查看正文预览。</div>
            <article v-else class="blog-reading-card">
              <header class="blog-reading-hero">
                <h1>{{ previewDetail.title }}</h1>
                <div class="blog-meta-row">
                  <span>{{ formatTime(previewDetail.published_at) }}</span>
                  <span>{{ previewDetail.capture_status }}</span>
                  <span>{{ reviewLabel(previewDetail.review_status) }}</span>
                </div>
                <p v-if="previewDetail.summary" class="blog-summary">{{ previewDetail.summary }}</p>
              </header>

              <div v-if="previewTags.length" class="blog-tag-row">
                <span v-for="tag in previewTags" :key="tag" class="badge neutral">#{{ tag }}</span>
              </div>

              <div v-if="hasPreviewHtml" class="blog-html-preview" v-html="previewDetail.content_preview_html"></div>

              <div v-else class="blog-content-stack">
                <section v-for="(section, index) in formattedSections" :key="`${index}-${section.title}`" class="blog-section">
                  <h4 v-if="section.title">{{ section.title }}</h4>
                  <p v-for="(paragraph, pIndex) in section.paragraphs" :key="`${index}-${pIndex}`">{{ paragraph }}</p>
                </section>
              </div>
            </article>
          </div>
        </section>
      </div>
    </div>

    <div v-if="archiveModal.visible" class="modal-mask" @click.self="closeArchiveModal">
      <div class="modal-card modal-card-wide">
        <div class="modal-header">
          <div>
            <h3>HTML 归档地址</h3>
            <p class="panel-subtitle">{{ archiveModal.title }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeArchiveModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>访问地址</span>
            <textarea :value="archiveModal.directUrl" rows="4" readonly></textarea>
          </label>
          <p class="panel-subtitle" style="margin: 0;">
            这个地址访问的是系统内保存的 HTML 归档，不是跳回 CSDN 的文章页。
          </p>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="copyArchiveUrl">复制地址</button>
          <button class="primary-button" type="button" @click="openArchiveDirect">打开归档</button>
        </div>
      </div>
    </div>

    <div v-if="blogProfileModal.visible" class="modal-mask" @click.self="closeBlogProfileModal">
      <div class="modal-card modal-card-wide">
        <div class="modal-header">
          <div>
            <h3>编辑博客主页</h3>
            <p class="panel-subtitle">支持用户名或完整主页地址</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeBlogProfileModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>博客主页</span>
            <input
              v-model.trim="blogProfileModal.blogHomeUrl"
              type="text"
              placeholder="例如 2301_82000924 或 https://blog.csdn.net/2301_82000924"
            />
          </label>
          <p class="panel-subtitle" style="margin: 0;">留空表示清空。后端会自动规范化为标准主页。</p>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeBlogProfileModal">取消</button>
          <button class="primary-button" type="button" :disabled="blogProfileModal.saving" @click="submitBlogProfile">
            {{ blogProfileModal.saving ? '保存中...' : '保存地址' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="reviewModal.visible" class="modal-mask" @click.self="closeReviewModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>{{ reviewModal.action === 'normal' ? '标记为正常' : '标记为异常' }}</h3>
            <p class="panel-subtitle">{{ reviewModal.blog?.title }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeReviewModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>审核备注</span>
            <textarea v-model.trim="reviewModal.reviewNote" rows="4" placeholder="填写人工审核说明"></textarea>
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeReviewModal">取消</button>
          <button class="primary-button" type="button" :disabled="reviewModal.saving" @click="submitReview">
            {{ reviewModal.saving ? '提交中...' : '提交审核' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { getServerBase } from '../services/eduevalApi';
import {
  adminFetchUserBlogDetail,
  adminFetchUserBlogScreenshot,
  adminGetUserBlogProfile,
  adminListUserBlogCrawlRuns,
  adminListUserBlogs,
  adminReviewUserBlog,
  adminTriggerUserBlogCrawl,
  adminUpdateUserBlogProfile,
} from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const userId = computed(() => String(route.params.userId || ''));

const items = ref([]);
const runItems = ref([]);
const blogProfile = ref({
  blog_home_url: '',
  blog_enabled: true,
  blog_crawl_status: 'idle',
  blog_last_crawled_at: null,
});
const filters = ref({
  keyword: '',
  reviewStatus: 'all',
  captureStatus: 'all',
});
const loading = ref(false);
const crawling = ref(false);
const localError = ref('');
const selectedBlogId = ref(null);
const previewDetail = ref(null);
const previewLoading = ref(false);
const previewError = ref('');
const archiveModal = ref({ visible: false, title: '', directUrl: '' });

const blogProfileModal = ref({
  visible: false,
  blogHomeUrl: '',
  saving: false,
});

const reviewModal = ref({
  visible: false,
  blog: null,
  action: 'normal',
  reviewNote: '',
  saving: false,
});

const errorMessage = computed(() => localError.value);
const filteredItems = computed(() => {
  const keyword = filters.value.keyword.toLowerCase();
  return items.value.filter(item => {
    if (filters.value.reviewStatus !== 'all' && String(item.review_status || '').toLowerCase() !== filters.value.reviewStatus) return false;
    if (filters.value.captureStatus === 'partial' && String(item.capture_status || '').toLowerCase() !== 'partial_success') return false;
    if (filters.value.captureStatus !== 'all' && filters.value.captureStatus !== 'partial' && String(item.capture_status || '').toLowerCase() !== filters.value.captureStatus) return false;
    if (!keyword) return true;
    return String(item.title || '').toLowerCase().includes(keyword);
  });
});

const previewTags = computed(() => {
  const summary = String(previewDetail.value?.summary || '');
  return Array.from(new Set((summary.match(/#([A-Za-z0-9_\u4e00-\u9fa5]+)/g) || []).map(item => item.replace(/^#/, ''))));
});

const hasPreviewHtml = computed(() => Boolean(String(previewDetail.value?.content_preview_html || '').trim()));

const formattedSections = computed(() => {
  const text = String(previewDetail.value?.content_text || '').trim();
  if (!text) return [];
  const cleaned = text
    .replace(/\s+/g, ' ')
    .replace(/([。！？；])(?=\S)/g, '$1\n')
    .replace(/(\d+\.)/g, '\n$1')
    .replace(/([一二三四五六七八九十]+、)/g, '\n$1')
    .trim();
  const chunks = cleaned.split('\n').map(item => item.trim()).filter(Boolean);
  const sections = [];
  let current = { title: '', paragraphs: [] };
  for (const chunk of chunks) {
    const isHeading = /^(\d+\.|[一二三四五六七八九十]+、)/.test(chunk) && chunk.length <= 42;
    if (isHeading && current.paragraphs.length) {
      sections.push(current);
      current = { title: chunk, paragraphs: [] };
      continue;
    }
    if (isHeading && !current.paragraphs.length && !current.title) {
      current.title = chunk;
      continue;
    }
    current.paragraphs.push(chunk);
    if (current.paragraphs.length >= 4) {
      sections.push(current);
      current = { title: '', paragraphs: [] };
    }
  }
  if (current.title || current.paragraphs.length) {
    sections.push(current);
  }
  return sections.length ? sections : [{ title: '', paragraphs: [text] }];
});

function goBack() {
  router.push({ name: 'admin-users' });
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function crawlStatusLabel(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'running') return '抓取中';
  if (v === 'success') return '成功';
  if (v === 'failed') return '失败';
  if (v === 'partial_success') return '部分成功';
  return '空闲';
}

function crawlStatusColor(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'running') return '#2563eb';
  if (v === 'success') return '#16a34a';
  if (v === 'failed') return '#ef4444';
  if (v === 'partial_success') return '#f59e0b';
  return 'var(--text-secondary)';
}

function reviewLabel(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'normal') return '正常';
  if (v === 'abnormal') return '异常';
  return '待审核';
}

function reviewColor(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'normal') return '#16a34a';
  if (v === 'abnormal') return '#ef4444';
  return '#f59e0b';
}

function triggerBlobOpen(blob) {
  const url = URL.createObjectURL(blob);
  window.open(url, '_blank', 'noopener,noreferrer');
  window.setTimeout(() => URL.revokeObjectURL(url), 10000);
}

function buildArchiveUrl(blogId) {
  const base = getServerBase();
  const token = encodeURIComponent(authStore.token || '');
  return `${base}/api/users/admin/users/${userId.value}/blogs/${blogId}/html?access_token=${token}`;
}

async function loadAll() {
  localError.value = '';
  loading.value = true;
  try {
    const [profile, list, runs] = await Promise.all([
      adminGetUserBlogProfile(authStore.token, userId.value),
      adminListUserBlogs(authStore.token, userId.value),
      adminListUserBlogCrawlRuns(authStore.token, userId.value),
    ]);
    blogProfile.value = profile || blogProfile.value;
    items.value = Array.isArray(list) ? list : [];
    runItems.value = Array.isArray(runs) ? runs : [];
  } catch (e) {
    localError.value = e?.message || '加载失败';
    items.value = [];
    runItems.value = [];
  } finally {
    loading.value = false;
  }
}

function openBlogProfileModal() {
  blogProfileModal.value = {
    visible: true,
    blogHomeUrl: blogProfile.value.blog_home_url || '',
    saving: false,
  };
}

function closeBlogProfileModal() {
  blogProfileModal.value = {
    visible: false,
    blogHomeUrl: '',
    saving: false,
  };
}

async function submitBlogProfile() {
  blogProfileModal.value.saving = true;
  try {
    await adminUpdateUserBlogProfile(authStore.token, userId.value, {
      blog_home_url: blogProfileModal.value.blogHomeUrl.trim(),
      blog_enabled: true,
    });
    await loadAll();
    closeBlogProfileModal();
  } catch (e) {
    localError.value = e?.message || '更新博客地址失败';
  } finally {
    blogProfileModal.value.saving = false;
  }
}

async function triggerCrawl() {
  crawling.value = true;
  localError.value = '';
  try {
    await adminTriggerUserBlogCrawl(authStore.token, userId.value);
    await loadAll();
  } catch (e) {
    localError.value = e?.message || '抓取失败';
  } finally {
    crawling.value = false;
  }
}

function clearPreview() {
  selectedBlogId.value = null;
  previewDetail.value = null;
  previewError.value = '';
  previewLoading.value = false;
}

async function previewBlog(blog) {
  selectedBlogId.value = blog.id;
  previewLoading.value = true;
  previewError.value = '';
  try {
    previewDetail.value = await adminFetchUserBlogDetail(authStore.token, userId.value, blog.id);
  } catch (e) {
    previewError.value = e?.message || '加载正文失败';
    previewDetail.value = null;
  } finally {
    previewLoading.value = false;
  }
}

async function openScreenshot(blog) {
  try {
    const blob = await adminFetchUserBlogScreenshot(authStore.token, userId.value, blog.id);
    triggerBlobOpen(blob);
  } catch (e) {
    localError.value = e?.message || '加载截图失败';
  }
}

function openArchiveModal(blog) {
  archiveModal.value = {
    visible: true,
    title: blog.title || 'HTML 归档',
    directUrl: buildArchiveUrl(blog.id),
  };
}

function closeArchiveModal() {
  archiveModal.value = { visible: false, title: '', directUrl: '' };
}

async function copyArchiveUrl() {
  try {
    await navigator.clipboard.writeText(archiveModal.value.directUrl);
  } catch (e) {
    localError.value = e?.message || '复制归档地址失败';
  }
}

function openArchiveDirect() {
  if (!archiveModal.value.directUrl) return;
  window.open(archiveModal.value.directUrl, '_blank', 'noopener,noreferrer');
}

function openReviewModal(blog, action) {
  reviewModal.value = {
    visible: true,
    blog,
    action,
    reviewNote: '',
    saving: false,
  };
}

function closeReviewModal() {
  reviewModal.value = {
    visible: false,
    blog: null,
    action: 'normal',
    reviewNote: '',
    saving: false,
  };
}

async function submitReview() {
  const blog = reviewModal.value.blog;
  if (!blog) return;
  reviewModal.value.saving = true;
  try {
    await adminReviewUserBlog(authStore.token, userId.value, blog.id, {
      review_status: reviewModal.value.action,
      review_note: reviewModal.value.reviewNote,
    });
    await loadAll();
    if (selectedBlogId.value === blog.id) {
      await previewBlog(blog);
    }
    closeReviewModal();
  } catch (e) {
    localError.value = e?.message || '审核失败';
  } finally {
    reviewModal.value.saving = false;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.blog-admin-shell {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 16px;
}

.blog-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 24px 26px;
  border-radius: 28px;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at top right, rgba(249, 115, 22, 0.22), transparent 28%),
    linear-gradient(135deg, #fff7ed 0%, #fff 44%, #f8fafc 100%);
}

.theme-dark .blog-hero {
  background:
    radial-gradient(circle at top right, rgba(255, 209, 138, 0.12), transparent 28%),
    linear-gradient(135deg, var(--surface) 0%, rgba(17, 27, 45, 0.92) 60%, rgba(106, 160, 255, 0.08) 100%);
}

.hero-eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #c2410c;
}

.theme-dark .hero-eyebrow {
  color: var(--badge-warn-text);
}

.blog-hero h2 {
  margin: 0;
  font-size: 32px;
}

.hero-copy {
  margin: 10px 0 0;
  max-width: 760px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.blog-summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.summary-card span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
}

.summary-card strong {
  display: block;
  margin-top: 8px;
  font-size: 20px;
  line-height: 1.4;
  word-break: break-word;
}

.blog-toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.table-wrap {
  overflow: auto;
}

.admin-table {
  width: 100%;
  border-collapse: collapse;
}

.admin-table th,
.admin-table td {
  padding: 12px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}

.content-grid {
  display: grid;
  grid-template-columns: minmax(340px, 460px) 1fr;
  gap: 16px;
  min-height: 0;
}

.list-panel,
.preview-panel {
  min-height: 0;
}

.list-body,
.preview-body {
  overflow: auto;
}

.blog-card-stack {
  display: grid;
  gap: 10px;
}

.blog-item-card {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.blog-item-card.active {
  border-color: #f97316;
  background: var(--badge-warn-bg);
}

.blog-item-title {
  font-size: 16px;
  font-weight: 800;
  line-height: 1.5;
}

.muted-line {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.inline-stack {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.compact-button,
.origin-link {
  width: auto;
  padding: 6px 10px;
}

.blog-reading-card {
  max-width: 920px;
  margin: 0 auto;
  background:
    radial-gradient(circle at top left, rgba(251, 191, 36, 0.16), transparent 22%),
    linear-gradient(180deg, var(--surface-soft) 0%, var(--surface) 100%);
  border: 1px solid var(--border);
  border-radius: 24px;
  padding: 28px;
}

.blog-reading-hero h1 {
  margin: 0 0 10px;
  font-size: 32px;
  line-height: 1.25;
}

.blog-meta-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.blog-summary {
  margin: 16px 0 0;
  padding: 14px 16px;
  background: var(--badge-warn-bg);
  border-left: 4px solid #f97316;
  border-radius: 12px;
}

.blog-tag-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin: 18px 0;
}

.blog-html-preview {
  line-height: 1.9;
  font-size: 15px;
}

.blog-html-preview :deep(h1),
.blog-html-preview :deep(h2),
.blog-html-preview :deep(h3),
.blog-html-preview :deep(h4) {
  margin: 20px 0 10px;
  color: #9a3412;
}

.theme-dark .blog-html-preview :deep(h1),
.theme-dark .blog-html-preview :deep(h2),
.theme-dark .blog-html-preview :deep(h3),
.theme-dark .blog-html-preview :deep(h4) {
  color: var(--badge-warn-text);
}

.blog-html-preview :deep(p),
.blog-html-preview :deep(li) {
  line-height: 1.9;
  margin: 0 0 12px;
}

.blog-html-preview :deep(pre) {
  overflow: auto;
  padding: 12px;
  border-radius: 12px;
  background: #111827;
  color: #f8fafc;
}

.blog-html-preview :deep(table.hljs-ln) {
  width: auto !important;
  table-layout: auto !important;
  border-collapse: collapse !important;
}

.blog-html-preview :deep(table.hljs-ln td) {
  border: 0 !important;
  padding: 0 !important;
  vertical-align: top !important;
}

.blog-html-preview :deep(.hljs-ln-n),
.blog-html-preview :deep(.hljs-ln-numbers) {
  text-align: right !important;
  padding-right: 10px !important;
  user-select: none;
  opacity: 0.6;
  white-space: nowrap;
}

.blog-html-preview :deep(.hljs-ln-n::before) {
  content: attr(data-line-number);
}

.blog-html-preview :deep(.hljs-ln-numbers .hljs-ln-line::before) {
  content: attr(data-line-number);
}

.blog-html-preview :deep(.hljs-ln-code) {
  padding-left: 12px !important;
}

.blog-html-preview :deep(img) {
  max-width: 100%;
  height: auto;
}

.blog-content-stack {
  display: grid;
  gap: 18px;
}

.blog-section {
  padding: 18px 18px 8px;
  border-radius: 18px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
}

.blog-section h4 {
  margin: 0 0 10px;
  font-size: 18px;
  color: #9a3412;
}

.theme-dark .blog-section h4 {
  color: var(--badge-warn-text);
}
.blog-section p {
  margin: 0 0 12px;
  line-height: 1.9;
  font-size: 15px;
}

.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 90;
  background: rgba(15, 23, 42, 0.58);
  display: grid;
  place-items: center;
  padding: 20px;
}

.modal-card {
  width: min(560px, 100%);
  max-height: 88vh;
  overflow: auto;
  background: var(--surface);
  border-radius: 24px;
  border: 1px solid var(--border);
  box-shadow: 0 30px 80px rgba(15, 23, 42, 0.18);
  padding: 20px;
  display: grid;
  gap: 16px;
}

.modal-card-wide {
  width: min(760px, 100%);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.modal-header h3 {
  margin: 0;
}

.modal-body {
  display: grid;
  gap: 12px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1100px) {
  .blog-summary-grid,
  .filter-grid,
  .content-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 820px) {
  .blog-summary-grid,
  .filter-grid,
  .content-grid {
    grid-template-columns: 1fr;
  }

  .blog-hero h2 {
    font-size: 26px;
  }
}
</style>
