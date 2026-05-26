<template>
  <div class="workload-screen">
    <div class="workload-card">
      <div class="hero">
        <div class="eyebrow">Work Profile</div>
        <h1>{{ member?.student_name || '成员' }}</h1>
        <div class="meta">{{ member?.student_id || '-' }} · {{ member?.project_role || '未填写角色' }}</div>
      </div>

      <div class="score-ring">
        <div class="score-label">工作量指数</div>
        <div class="score-value">{{ member?.workload_index ?? '-' }}</div>
        <div class="score-rank">组内排名 #{{ member?.rank_order ?? '-' }}</div>
      </div>

      <div class="summary-block">
        <div class="block-title">工作摘要</div>
        <p>{{ member?.summary_text || '暂无摘要' }}</p>
      </div>

      <div class="summary-block">
        <div class="block-title">博客证据</div>
        <div class="evidence-list">
          <div class="evidence-item">
            <span>博客篇数</span>
            <strong>{{ member?.blog_post_count ?? 0 }}</strong>
          </div>
          <div class="evidence-item">
            <span>工作项抽取</span>
            <strong>{{ member?.blog_work_item_count ?? 0 }}</strong>
          </div>
          <div class="evidence-item">
            <span>纯代码倾向</span>
            <strong>{{ member?.blog_code_dump_count ?? 0 }}</strong>
          </div>
          <div class="evidence-item">
            <span>科普文章</span>
            <strong>{{ member?.blog_popular_science_count ?? 0 }}</strong>
          </div>
        </div>
      </div>

      <div class="summary-block">
        <div class="block-title">证据链</div>
        <div class="evidence-list">
          <div v-for="item in member?.evidence || []" :key="item.label" class="evidence-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </div>

      <div class="summary-block" v-if="errorMessage">
        <div class="block-title">错误</div>
        <p>{{ errorMessage }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';
import { fetchStudentWorkloadSummary } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();

const member = ref(null);
const errorMessage = ref('');

async function loadAll() {
  errorMessage.value = '';
  try {
    member.value = await fetchStudentWorkloadSummary(
      authStore.token,
      Number(route.params.submissionId || 0),
      String(route.params.studentId || ''),
    );
  } catch (error) {
    errorMessage.value = error?.message || '加载失败';
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.workload-screen {
  min-height: 100vh;
  padding: 24px 16px;
  background:
    radial-gradient(circle at top, rgba(34, 197, 94, 0.18), transparent 35%),
    linear-gradient(180deg, #f7fdf8 0%, #eef7ff 100%);
  display: flex;
  justify-content: center;
}

.workload-card {
  width: 100%;
  max-width: 420px;
  display: grid;
  gap: 16px;
}

.hero,
.summary-block,
.score-ring {
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 24px;
  padding: 20px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
}

.eyebrow {
  font-size: 12px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #0f766e;
}

h1 {
  margin: 8px 0 4px;
  font-size: 28px;
}

.meta,
.score-label,
.score-rank,
.block-title,
.evidence-item span {
  color: #475569;
}

.score-ring {
  text-align: center;
}

.score-value {
  font-size: 54px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1;
  margin: 6px 0;
}

.block-title {
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 10px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.summary-block p {
  margin: 0;
  color: #0f172a;
  line-height: 1.6;
}

.evidence-list {
  display: grid;
  gap: 10px;
}

.evidence-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.evidence-item strong {
  color: #0f172a;
  text-align: right;
}
</style>
