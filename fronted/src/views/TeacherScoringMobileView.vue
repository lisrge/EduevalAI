<template>
  <div class="teacher-mobile-page">
    <header class="teacher-mobile-header">
      <div>
        <div class="eyebrow">Teacher Review</div>
        <h1>教师移动评分端</h1>
        <p>默认只看分配给自己的提交，未分配时不允许评分。</p>
      </div>
      <div class="header-actions">
        <button class="ghost-button" type="button" style="width: auto;" @click="reloadAll">刷新</button>
        <button v-if="authStore.isAdmin" class="ghost-button" type="button" style="width: auto;" @click="goAdmin">总览</button>
        <button class="ghost-button" type="button" style="width: auto;" @click="doLogout">退出登录</button>
      </div>
    </header>

    <section class="teacher-toolbar">
      <label>
        <span>作业</span>
        <select v-model="selectedAssignmentId" class="edueval-input" @change="loadQueue">
          <option value="">全部已提交作业</option>
          <option v-for="item in assignments" :key="item.id" :value="String(item.id)">
            {{ item.course.name }} / 第{{ item.week_index }}周 / {{ item.title }}
          </option>
        </select>
      </label>

      <label>
        <span>筛选</span>
        <select v-model="reviewedFilter" class="edueval-input" @change="loadQueue">
          <option value="">全部</option>
          <option value="false">待我评分</option>
          <option value="true">我已评分</option>
        </select>
      </label>
    </section>

    <div v-if="errorMessage" class="teacher-alert">{{ errorMessage }}</div>

    <main class="teacher-mobile-layout">
      <section class="queue-panel">
        <div class="queue-panel-header">
          <strong>评分队列</strong>
          <span>{{ queue.length }} 份</span>
        </div>
        <div v-if="loadingQueue" class="empty-state">加载中...</div>
        <div v-else-if="queue.length === 0" class="empty-state">当前没有可评分提交。</div>
        <button
          v-for="item in queue"
          :key="item.submission.id"
          type="button"
          class="queue-card"
          :class="{ active: String(item.submission.id) === String(activeSubmissionId || '') }"
          @click="selectSubmission(item.submission.id)"
        >
          <div class="queue-main">
            <div class="queue-title">{{ item.submission.project_name || '未填写项目名' }}</div>
            <div class="queue-meta">{{ item.submission.group_name || '未填写小组' }} · {{ item.submission.student_name }}</div>
            <div class="queue-meta">分配：{{ item.assigned_teachers?.map(t => t.teacher_student_id).join('，') || '未指定' }}</div>
          </div>
          <div class="queue-side">
            <div class="queue-badge" :class="item.reviewed_by_me ? 'done' : 'todo'">
              {{ item.reviewed_by_me ? '已评' : '待评' }}
            </div>
            <div class="queue-score">均分 {{ item.aggregate.average_total_score || 0 }}</div>
          </div>
        </button>
      </section>

      <section class="review-panel">
        <div v-if="loadingReview" class="empty-state">加载评分详情...</div>
        <div v-else-if="!review" class="empty-state">从左侧选择一个提交开始评分。</div>
        <template v-else>
          <div class="review-hero">
            <div>
              <div class="eyebrow">Submission {{ review.submission.id }}</div>
              <h2>{{ review.submission.project_name || '未填写项目名' }}</h2>
              <p>{{ review.submission.group_name || '未填写小组' }} · {{ review.submission.student_name }} · {{ review.submission.student_id }}</p>
              <p>分配老师：{{ review.assigned_teachers?.map(t => t.teacher_student_id).join('，') || '未指定' }}</p>
            </div>
            <div class="aggregate-card">
              <div>已评分 {{ review.aggregate.score_count }} / 分配 {{ review.aggregate.assigned_teacher_count }}</div>
              <strong>{{ review.aggregate.average_total_score }}</strong>
              <span>平均总分</span>
            </div>
          </div>

          <div class="meta-grid">
            <article class="meta-card">
              <span>状态</span>
              <strong>{{ review.submission.status }} / {{ review.submission.completeness_status }}</strong>
            </article>
            <article class="meta-card">
              <span>附件</span>
              <strong>{{ review.submission.asset_count }} 个</strong>
            </article>
            <article class="meta-card">
              <span>成员</span>
              <strong>{{ review.submission.member_count }} 人</strong>
            </article>
            <article class="meta-card">
              <span>代码行数</span>
              <strong>{{ review.submission.code_analysis?.total_lines ?? '-' }}</strong>
            </article>
          </div>

          <section class="member-panel">
            <div class="section-title">成员与工作量</div>
            <article v-for="member in review.workload.members" :key="member.student_id" class="member-card">
              <div class="member-row">
                <strong>{{ member.student_name }}</strong>
                <span>#{{ member.rank_order }} / {{ member.workload_index }}</span>
              </div>
              <div class="member-meta">{{ member.student_id }} · {{ member.project_role || '未填写角色' }} · {{ member.contribution_source }}</div>
              <p>{{ member.summary_text }}</p>
            </article>
          </section>

          <section class="score-panel">
            <div class="section-title">我的评分</div>
            <div class="score-grid">
              <label v-for="field in scoreFields" :key="field.key" class="score-input-card">
                <span>{{ field.label }}</span>
                <input v-model.number="form[field.key]" type="number" min="0" max="10" class="edueval-input" :disabled="!review.assigned_to_me && !authStore.isAdmin" />
              </label>
            </div>
            <label class="comment-box">
              <span>评语</span>
              <textarea v-model="form.comment" class="edueval-input" rows="5" placeholder="填写教师评语、风险点和建议。" :disabled="!review.assigned_to_me && !authStore.isAdmin"></textarea>
            </label>
            <div class="score-actions">
              <div class="total-box">
                <span>总分</span>
                <strong>{{ totalScore }}</strong>
              </div>
              <button class="primary-button" type="button" :disabled="saving || (!review.assigned_to_me && !authStore.isAdmin)" @click="saveScore">
                {{ saving ? '提交中...' : '提交评分' }}
              </button>
              <button class="ghost-button" type="button" style="width: auto;" :disabled="!nextSubmissionId" @click="selectSubmission(nextSubmissionId)">
                下一份
              </button>
            </div>
          </section>
        </template>
      </section>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchAssignments, fetchTeacherReviewQueue, fetchTeacherSubmissionReview, saveTeacherSubmissionScore } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const assignments = ref([]);
const queue = ref([]);
const review = ref(null);
const loadingQueue = ref(false);
const loadingReview = ref(false);
const saving = ref(false);
const errorMessage = ref('');
const selectedAssignmentId = ref('');
const reviewedFilter = ref('');
const activeSubmissionId = ref('');
const form = ref({
  innovation_score: 8,
  completeness_score: 8,
  code_quality_score: 8,
  demo_score: 8,
  contribution_score: 8,
  comment: '',
});

const scoreFields = [
  { key: 'innovation_score', label: '创新性' },
  { key: 'completeness_score', label: '完整性' },
  { key: 'code_quality_score', label: '代码质量' },
  { key: 'demo_score', label: '演示效果' },
  { key: 'contribution_score', label: '个人贡献' },
];

const totalScore = computed(() =>
  scoreFields.reduce((sum, item) => sum + Number(form.value[item.key] || 0), 0),
);

const nextSubmissionId = computed(() => {
  const idx = queue.value.findIndex(item => String(item.submission.id) === String(activeSubmissionId.value || ''));
  if (idx < 0 || idx >= queue.value.length - 1) return null;
  return queue.value[idx + 1].submission.id;
});

function goAdmin() {
  router.push({ name: 'admin-submissions' });
}

async function doLogout() {
  await authStore.logout();
  router.replace({ name: 'login' });
}

function applyReviewToForm(payload) {
  const myScore = payload?.my_score;
  form.value = {
    innovation_score: Number(myScore?.innovation_score ?? 8),
    completeness_score: Number(myScore?.completeness_score ?? 8),
    code_quality_score: Number(myScore?.code_quality_score ?? 8),
    demo_score: Number(myScore?.demo_score ?? 8),
    contribution_score: Number(myScore?.contribution_score ?? 8),
    comment: myScore?.comment || '',
  };
}

async function loadAssignments() {
  const data = await fetchAssignments(authStore.token);
  assignments.value = Array.isArray(data) ? data : [];
}

async function loadQueue() {
  loadingQueue.value = true;
  errorMessage.value = '';
  try {
    const list = await fetchTeacherReviewQueue(authStore.token, selectedAssignmentId.value || null, reviewedFilter.value || null);
    queue.value = Array.isArray(list) ? list : [];
    const requestedId = route.query.submissionId ? String(route.query.submissionId) : '';
    const firstId = queue.value[0]?.submission?.id ? String(queue.value[0].submission.id) : '';
    const targetId = queue.value.some(item => String(item.submission.id) === requestedId) ? requestedId : firstId;
    if (targetId) {
      await selectSubmission(targetId, false);
    } else {
      activeSubmissionId.value = '';
      review.value = null;
    }
  } catch (error) {
    errorMessage.value = error?.message || '加载评分队列失败';
    queue.value = [];
  } finally {
    loadingQueue.value = false;
  }
}

async function selectSubmission(submissionId, updateQuery = true) {
  if (!submissionId) return;
  loadingReview.value = true;
  errorMessage.value = '';
  try {
    const payload = await fetchTeacherSubmissionReview(authStore.token, submissionId);
    review.value = payload || null;
    activeSubmissionId.value = String(submissionId);
    applyReviewToForm(payload);
    if (updateQuery) {
      router.replace({
        name: 'teacher-reviews',
        query: {
          ...(selectedAssignmentId.value ? { assignmentId: selectedAssignmentId.value } : {}),
          submissionId: String(submissionId),
        },
      });
    }
  } catch (error) {
    errorMessage.value = error?.message || '加载评分详情失败';
  } finally {
    loadingReview.value = false;
  }
}

async function saveScore() {
  if (!activeSubmissionId.value) return;
  saving.value = true;
  errorMessage.value = '';
  try {
    const payload = await saveTeacherSubmissionScore(authStore.token, activeSubmissionId.value, form.value);
    review.value = payload?.review || review.value;
    applyReviewToForm(review.value);
    await loadQueue();
  } catch (error) {
    errorMessage.value = error?.message || '保存评分失败';
  } finally {
    saving.value = false;
  }
}

async function reloadAll() {
  await loadAssignments();
  await loadQueue();
}

watch(
  () => route.query.assignmentId,
  (value) => {
    selectedAssignmentId.value = value ? String(value) : '';
  },
  { immediate: true },
);

onMounted(() => {
  reloadAll();
});
</script>

<style scoped>
.teacher-mobile-page {
  min-height: 100vh;
  padding: 18px;
  background:
    radial-gradient(circle at top left, rgba(255, 214, 165, 0.55), transparent 28%),
    linear-gradient(180deg, #fff8ef 0%, #f4efe6 100%);
}

.teacher-mobile-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.teacher-mobile-header h1 {
  margin: 6px 0 4px;
  font-size: 28px;
}

.teacher-mobile-header p,
.eyebrow {
  margin: 0;
  color: #6b7280;
}

.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 12px;
}

.header-actions,
.teacher-toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.teacher-toolbar {
  margin-bottom: 16px;
}

.teacher-toolbar label,
.comment-box,
.score-input-card {
  display: grid;
  gap: 6px;
}

.teacher-mobile-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
}

.queue-panel,
.review-panel {
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 20px;
  padding: 16px;
  box-shadow: 0 16px 40px rgba(15, 23, 42, 0.06);
}

.queue-panel {
  display: grid;
  gap: 10px;
  align-content: start;
}

.queue-panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.queue-card {
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 16px;
  padding: 12px;
  background: #fff;
  text-align: left;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.queue-card.active {
  border-color: #d97706;
  box-shadow: 0 0 0 3px rgba(217, 119, 6, 0.12);
}

.queue-title {
  font-weight: 700;
  color: #111827;
}

.queue-meta,
.member-meta,
.queue-score {
  font-size: 13px;
  color: #6b7280;
}

.queue-side {
  display: grid;
  justify-items: end;
  gap: 8px;
}

.queue-badge {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.queue-badge.todo {
  background: #fff7ed;
  color: #c2410c;
}

.queue-badge.done {
  background: #ecfdf5;
  color: #047857;
}

.review-panel {
  display: grid;
  gap: 16px;
}

.review-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.review-hero h2 {
  margin: 6px 0;
  font-size: 26px;
}

.review-hero p,
.section-title {
  margin: 0;
}

.aggregate-card,
.meta-card,
.member-card,
.score-panel {
  background: #fffdf8;
  border: 1px solid rgba(245, 158, 11, 0.18);
  border-radius: 16px;
}

.aggregate-card {
  min-width: 180px;
  padding: 14px;
  display: grid;
  gap: 4px;
  text-align: center;
}

.aggregate-card strong {
  font-size: 34px;
  line-height: 1;
  color: #b45309;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.meta-card {
  padding: 12px;
  display: grid;
  gap: 4px;
}

.meta-card span {
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: #6b7280;
}

.member-panel,
.score-panel {
  display: grid;
  gap: 12px;
}

.member-card,
.score-panel {
  padding: 14px;
}

.member-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
}

.member-card p {
  margin: 8px 0 0;
  color: #374151;
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.score-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.total-box {
  display: grid;
  gap: 4px;
}

.total-box span {
  color: #6b7280;
}

.total-box strong {
  font-size: 28px;
  color: #92400e;
}

.teacher-alert {
  margin-bottom: 12px;
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.86);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 14px;
  padding: 12px;
}

@media (max-width: 960px) {
  .teacher-mobile-layout {
    grid-template-columns: 1fr;
  }

  .meta-grid,
  .score-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .teacher-mobile-page {
    padding: 12px;
  }

  .teacher-mobile-header,
  .review-hero {
    grid-template-columns: 1fr;
    display: grid;
  }

  .meta-grid,
  .score-grid {
    grid-template-columns: 1fr;
  }
}
</style>
