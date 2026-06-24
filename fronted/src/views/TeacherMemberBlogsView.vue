<template>
  <div class="teacher-member-blogs-page edueval-skin">
    <div class="page-wrapper teacher-member-shell">
      <section class="page-hero teacher-member-hero">
        <div>
          <p class="hero-eyebrow">教师评分 / 成员博客</p>
          <h1>{{ detail?.student_name || '成员博客' }}</h1>
          <p class="hero-copy">
            {{ detail?.project_name || '未填写项目名' }} · {{ detail?.group_name || '未填写小组' }} · {{ detail?.student_id || route.params.studentId }}
          </p>
          <p class="panel-subtitle">按发布时间从旧到新展示，摘要优先使用系统已生成内容，缺失时由当前配置的 DeepSeek 模型补全。</p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" @click="goBack">返回评分端</button>
          <button class="primary-button" type="button" :disabled="loading" @click="loadBlogs">
            {{ loading ? '刷新中...' : '刷新列表' }}
          </button>
        </div>
      </section>

      <div v-if="errorMessage" class="teacher-member-alert">{{ errorMessage }}</div>

      <section class="panel teacher-member-summary">
        <div>
          <div class="summary-label">博客总数</div>
          <strong>{{ detail?.total_blog_count ?? 0 }}</strong>
        </div>
        <div>
          <div class="summary-label">排序方式</div>
          <strong>发布时间升序</strong>
        </div>
      </section>

      <section class="teacher-member-list">
        <article v-if="loading" class="panel teacher-blog-card teacher-blog-card--loading">
          正在加载博客列表...
        </article>
        <article v-else-if="!blogs.length" class="panel teacher-blog-card teacher-blog-card--empty">
          当前成员还没有可展示的博客记录。
        </article>
        <article
          v-for="blog in blogs"
          :key="blog.id"
          class="panel teacher-blog-card"
          :class="{ 'teacher-blog-card--abnormal': isAbnormalBlog(blog) }"
        >
          <div class="teacher-blog-main">
            <div class="teacher-blog-head">
              <div>
                <h2>{{ blog.title || '未命名博客' }}</h2>
                <div class="teacher-blog-meta">
                  <span>{{ formatDate(blog.published_at || blog.created_at) }}</span>
                  <span>{{ blog.word_count || 0 }} 字</span>
                  <span class="badge neutral">{{ blog.category || 'unknown' }}</span>
                  <span v-if="blog.is_mostly_code" class="badge warn">代码偏多</span>
                  <span v-if="isAbnormalBlog(blog)" class="badge danger-soft">异常</span>
                </div>
              </div>
              <a v-if="blog.url" class="ghost-button teacher-blog-link" :href="blog.url" target="_blank" rel="noopener noreferrer">打开原文</a>
            </div>
            <p class="teacher-blog-summary">{{ blog.summary_text || '暂无摘要' }}</p>
          </div>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchTeacherMemberBlogs } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const errorMessage = ref('');
const detail = ref(null);

const blogs = computed(() => (Array.isArray(detail.value?.blogs) ? detail.value.blogs : []));

function formatDate(dateStr) {
  if (!dateStr) return '未记录时间';
  try {
    return new Date(dateStr).toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '未记录时间';
  }
}

function isAbnormalBlog(blog) {
  return String(blog?.status || '').toLowerCase() === 'abnormal';
}

function goBack() {
  router.push({
    name: 'teacher-reviews',
    query: {
      submissionId: String(route.params.submissionId || ''),
      ...(route.query.assignmentId ? { assignmentId: String(route.query.assignmentId) } : {}),
    },
  });
}

async function loadBlogs() {
  loading.value = true;
  errorMessage.value = '';
  try {
    detail.value = await fetchTeacherMemberBlogs(
      authStore.token,
      route.params.submissionId,
      route.params.studentId,
    );
  } catch (error) {
    errorMessage.value = error?.message || '加载成员博客失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadBlogs();
});
</script>

<style scoped>
.teacher-member-blogs-page {
  min-height: 100vh;
}

.teacher-member-shell {
  display: grid;
  gap: 18px;
}

.teacher-member-hero {
  align-items: center;
}

.teacher-member-summary {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.teacher-member-summary strong {
  display: block;
  margin-top: 6px;
  font-size: 28px;
  line-height: 1.1;
}

.summary-label {
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.teacher-member-list {
  display: grid;
  gap: 14px;
}

.teacher-blog-card {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}

.teacher-blog-card--abnormal {
  background: rgba(254, 226, 226, 0.68);
  border-color: rgba(239, 68, 68, 0.22);
}

.teacher-blog-card--loading,
.teacher-blog-card--empty {
  grid-template-columns: 1fr;
  color: var(--text-secondary);
}

.teacher-blog-main {
  display: grid;
  gap: 12px;
}

.teacher-blog-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.teacher-blog-head h2 {
  margin: 0;
  font-size: 22px;
}

.teacher-blog-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: var(--text-secondary);
  font-size: 13px;
}

.teacher-blog-link {
  width: auto;
  white-space: nowrap;
}

.teacher-blog-summary {
  margin: 0;
  padding: 16px 18px;
  border-radius: 18px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  line-height: 1.75;
  color: var(--text-primary);
}

.teacher-member-alert {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(254, 226, 226, 0.88);
  border: 1px solid rgba(239, 68, 68, 0.22);
  color: #b91c1c;
}

@media (max-width: 720px) {
  .teacher-member-summary,
  .teacher-blog-card {
    grid-template-columns: 1fr;
  }

  .teacher-blog-head {
    display: grid;
  }
}
</style>
