<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 14px;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 4px; gap: 12px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">后台管理 / 统一看板</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">汇总缺失材料、仓库风险、工作量异常和教师评分进度。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="ghost-button" type="button" style="width: auto;" :disabled="exporting" @click="downloadScores">
            {{ exporting ? '导出中...' : '导出成绩汇总' }}
          </button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goTeacherReviews">教师评分端</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="loadAll">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </div>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="display: flex; gap: 12px; align-items: end; flex-wrap: wrap;">
          <label style="min-width: 280px;">
            <div class="panel-subtitle">按作业筛选</div>
            <select v-model="selectedAssignmentId" class="edueval-input" style="width: 100%;" @change="loadSubmissions">
              <option value="">全部作业</option>
              <option v-for="item in assignments" :key="item.id" :value="String(item.id)">
                {{ item.course.name }} / 第{{ item.week_index }}周 / {{ item.title }}
              </option>
            </select>
          </label>
          <label style="min-width: 180px;">
            <div class="panel-subtitle">风险等级</div>
            <select v-model="selectedRiskLevel" class="edueval-input" style="width: 100%;">
              <option value="">全部</option>
              <option value="high">高风险</option>
              <option value="medium">中风险</option>
              <option value="low">低风险</option>
            </select>
          </label>
          <div class="panel-subtitle">
            共 {{ filteredSubmissions.length }} 份，完整 {{ completeCount }} 份，高风险 {{ highRiskCount }} 份。
          </div>
        </div>
      </section>

      <section class="dashboard-cards">
        <article class="dashboard-card high">
          <span>高风险</span>
          <strong>{{ highRiskCount }}</strong>
        </article>
        <article class="dashboard-card medium">
          <span>中风险</span>
          <strong>{{ mediumRiskCount }}</strong>
        </article>
        <article class="dashboard-card low">
          <span>低风险</span>
          <strong>{{ lowRiskCount }}</strong>
        </article>
        <article class="dashboard-card neutral">
          <span>评分未完成</span>
          <strong>{{ incompleteReviewCount }}</strong>
        </article>
      </section>

      <div v-if="errorMessage" class="panel" style="padding: 14px; color: #b91c1c;">
        {{ errorMessage }}
      </div>

      <section class="panel" style="min-height: 0;">
        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="filteredSubmissions.length === 0" class="empty-state">暂无提交记录。</div>

          <div v-else class="dashboard-list">
            <article v-for="item in filteredSubmissions" :key="item.id" class="dashboard-row">
              <div class="dashboard-main">
                <div class="dashboard-head">
                  <div>
                    <h3>{{ item.project_name || '未填写项目名' }}</h3>
                    <p>{{ item.group_name || '未填写小组' }} · {{ item.student_name || item.student_id }} · {{ item.student_id }}</p>
                  </div>
                  <span class="risk-pill" :class="riskClass(item.dashboard_risk_summary?.level)">
                    {{ riskLabel(item.dashboard_risk_summary?.level) }}
                  </span>
                </div>

                <div class="dashboard-metrics">
                  <span>状态 {{ item.status }} / {{ item.completeness_status }}</span>
                  <span>附件 {{ item.asset_count }}</span>
                  <span>成员 {{ item.member_count }}</span>
                  <span>代码 {{ item.code_analysis?.total_lines ?? '-' }}</span>
                  <span>评分 {{ item.teacher_score_summary?.score_count ?? 0 }}/{{ item.teacher_score_summary?.assigned_teacher_count ?? 0 }}</span>
                  <span>均分 {{ item.teacher_score_summary?.average_total_score ?? 0 }}</span>
                </div>

                <div class="risk-groups">
                  <div v-if="(item.dashboard_risk_summary?.missing_asset_types || []).length" class="risk-block">
                    <strong>缺失材料</strong>
                    <div class="tag-row">
                      <span v-for="flag in item.dashboard_risk_summary.missing_asset_types" :key="flag" class="tag missing">{{ flag }}</span>
                    </div>
                  </div>
                  <div v-if="(item.dashboard_risk_summary?.blog_risk_flags || []).length" class="risk-block">
                    <strong>博客风险</strong>
                    <div class="tag-row">
                      <span v-for="flag in item.dashboard_risk_summary.blog_risk_flags" :key="flag" class="tag blog">{{ flag }}</span>
                    </div>
                  </div>
                  <div v-if="(item.dashboard_risk_summary?.repo_risk_flags || []).length" class="risk-block">
                    <strong>仓库风险</strong>
                    <div class="tag-row">
                      <span v-for="flag in item.dashboard_risk_summary.repo_risk_flags" :key="flag" class="tag repo">{{ flag }}</span>
                    </div>
                  </div>
                  <div v-if="(item.dashboard_risk_summary?.teacher_risk_flags || []).length" class="risk-block">
                    <strong>评分风险</strong>
                    <div class="tag-row">
                      <span v-for="flag in item.dashboard_risk_summary.teacher_risk_flags" :key="flag" class="tag teacher">{{ flag }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="dashboard-actions">
                <button class="ghost-button" type="button" style="width: auto;" @click="goRepo(item)">仓库进度</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="goWorkload(item)">工作画像</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="goAssignments(item)">分配老师</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="goScore(item)">去评分</button>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { adminListSubmissionSummaries, exportTeacherScores, fetchAssignments } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const assignments = ref([]);
const submissions = ref([]);
const selectedAssignmentId = ref('');
const selectedRiskLevel = ref('');
const loading = ref(false);
const exporting = ref(false);
const errorMessage = ref('');

const filteredSubmissions = computed(() => {
  const level = selectedRiskLevel.value;
  if (!level) return submissions.value;
  return submissions.value.filter(item => String(item.dashboard_risk_summary?.level || 'low') === level);
});

const completeCount = computed(() => filteredSubmissions.value.filter(item => item.completeness_status === 'complete').length);
const highRiskCount = computed(() => submissions.value.filter(item => item.dashboard_risk_summary?.level === 'high').length);
const mediumRiskCount = computed(() => submissions.value.filter(item => item.dashboard_risk_summary?.level === 'medium').length);
const lowRiskCount = computed(() => submissions.value.filter(item => (item.dashboard_risk_summary?.level || 'low') === 'low').length);
const incompleteReviewCount = computed(() =>
  submissions.value.filter(item => {
    const summary = item.teacher_score_summary || {};
    return Number(summary.assigned_teacher_count || 0) > Number(summary.score_count || 0);
  }).length,
);

function goBack() {
  router.push({ name: 'admin-users' });
}

function goTeacherReviews() {
  router.push({ name: 'teacher-reviews' });
}

function goRepo(item) {
  router.push({ name: 'admin-repo-progress', params: { submissionId: String(item.id) } });
}

function goWorkload(item) {
  router.push({ name: 'admin-workload-summary', params: { submissionId: String(item.id) } });
}

function goAssignments(item) {
  router.push({ name: 'admin-teacher-assignments', params: { submissionId: String(item.id) } });
}

function goScore(item) {
  router.push({ name: 'teacher-reviews', query: { assignmentId: String(item.assignment_id), submissionId: String(item.id) } });
}

function riskClass(level) {
  if (level === 'high') return 'high';
  if (level === 'medium') return 'medium';
  return 'low';
}

function riskLabel(level) {
  if (level === 'high') return '高风险';
  if (level === 'medium') return '中风险';
  return '低风险';
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function downloadScores() {
  exporting.value = true;
  errorMessage.value = '';
  try {
    const blob = await exportTeacherScores(authStore.token, {
      format: 'xlsx',
      assignmentId: selectedAssignmentId.value || null,
    });
    triggerDownload(blob, 'teacher_scores.xlsx');
  } catch (error) {
    errorMessage.value = error?.message || '导出失败';
  } finally {
    exporting.value = false;
  }
}

async function loadAssignments() {
  const list = await fetchAssignments(authStore.token);
  assignments.value = Array.isArray(list) ? list : [];
}

async function loadSubmissions() {
  errorMessage.value = '';
  loading.value = true;
  try {
    const list = await adminListSubmissionSummaries(authStore.token, selectedAssignmentId.value || null);
    submissions.value = Array.isArray(list) ? list : [];
  } catch (error) {
    errorMessage.value = error?.message || '加载提交列表失败';
    submissions.value = [];
  } finally {
    loading.value = false;
  }
}

async function loadAll() {
  errorMessage.value = '';
  loading.value = true;
  try {
    await loadAssignments();
    const list = await adminListSubmissionSummaries(authStore.token, selectedAssignmentId.value || null);
    submissions.value = Array.isArray(list) ? list : [];
  } catch (error) {
    errorMessage.value = error?.message || '加载失败';
    submissions.value = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.dashboard-cards {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.dashboard-card {
  border-radius: 18px;
  padding: 16px;
  color: #111827;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.dashboard-card strong {
  display: block;
  font-size: 28px;
  margin-top: 6px;
}

.dashboard-card.high { background: #fff1f2; }
.dashboard-card.medium { background: #fff7ed; }
.dashboard-card.low { background: #ecfdf5; }
.dashboard-card.neutral { background: #eff6ff; }

.dashboard-list {
  display: grid;
  gap: 12px;
}

.dashboard-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 180px;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
}

.dashboard-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.dashboard-head h3 {
  margin: 0;
}

.dashboard-head p {
  margin: 6px 0 0;
  color: var(--text-secondary);
}

.dashboard-metrics {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-top: 10px;
  color: var(--text-secondary);
  font-size: 14px;
}

.risk-pill {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.risk-pill.high { background: #fee2e2; color: #b91c1c; }
.risk-pill.medium { background: #ffedd5; color: #c2410c; }
.risk-pill.low { background: #dcfce7; color: #166534; }

.risk-groups {
  display: grid;
  gap: 10px;
  margin-top: 12px;
}

.risk-block {
  display: grid;
  gap: 6px;
}

.tag-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag {
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
}

.tag.missing { background: #fee2e2; color: #b91c1c; }
.tag.blog { background: #ede9fe; color: #6d28d9; }
.tag.repo { background: #fef3c7; color: #92400e; }
.tag.teacher { background: #dbeafe; color: #1d4ed8; }

.dashboard-actions {
  display: grid;
  gap: 8px;
  align-content: start;
}

@media (max-width: 960px) {
  .dashboard-cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .dashboard-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .dashboard-cards {
    grid-template-columns: 1fr;
  }
}
</style>
