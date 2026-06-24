<template>
  <div class="edueval-skin edueval-page">
    <ChatHeader />

    <div class="page-wrapper" style="flex: 1; min-height: 0; display: grid; gap: 16px;">
      <section class="page-hero">
        <div>
          <p class="hero-eyebrow">后台管理看板</p>
          <h2>后台管理 / 统一看板</h2>
          <p class="hero-copy">汇总缺失材料、仓库风险、工作量异常和教师评分进度，作为管理员统一入口。</p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" style="width: auto;" :disabled="exporting" @click="downloadScores">
            {{ exporting ? '导出中...' : '导出成绩汇总' }}
          </button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goTeacherReviews">教师评分端</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="loadAll">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </section>

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

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="panel" style="min-height: 0;">
        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="filteredSubmissions.length === 0" class="empty-state">暂无提交记录。</div>

          <div v-else class="dashboard-list">
            <article v-for="item in filteredSubmissions" :key="item.id" :class="['dashboard-row', riskCardClass(item.dashboard_risk_summary?.level)]">
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
                  <span>状态 {{ translateSubmissionStatus(item.status) }} / {{ translateCompletenessStatus(item.completeness_status) }}</span>
                  <span>上传 {{ uploadStateLabel(item.upload_state) }}</span>
                  <span>附件 {{ item.asset_count }}</span>
                  <span>成员 {{ item.member_count }}</span>
                  <span>代码 {{ item.code_analysis?.total_lines ?? '-' }}</span>
                  <span>评分 {{ item.teacher_score_summary?.score_count ?? 0 }}/{{ item.teacher_score_summary?.assigned_teacher_count ?? 0 }}</span>
                  <span>A均分 {{ item.teacher_score_summary?.average_group_total_score ?? 0 }}</span>
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
                      <span v-for="flag in item.dashboard_risk_summary.blog_risk_flags" :key="flag" class="tag blog">{{ translateRiskFlag(flag) }}</span>
                    </div>
                  </div>
                  <div v-if="(item.dashboard_risk_summary?.repo_risk_flags || []).length" class="risk-block">
                    <strong>仓库风险</strong>
                    <div class="tag-row">
                      <span v-for="flag in item.dashboard_risk_summary.repo_risk_flags" :key="flag" class="tag repo">{{ translateRiskFlag(flag) }}</span>
                    </div>
                  </div>
                  <div v-if="(item.dashboard_risk_summary?.teacher_risk_flags || []).length" class="risk-block">
                    <strong>评分风险</strong>
                    <div class="tag-row">
                      <span v-for="flag in item.dashboard_risk_summary.teacher_risk_flags" :key="flag" class="tag teacher">{{ translateRiskFlag(flag) }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <div class="dashboard-actions">
                <button class="ghost-button" type="button" style="width: auto;" @click="goRepo(item)">仓库进度</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="goWorkload(item)">工作画像</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="openAssets(item)">查看材料</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="goAssignments(item)">分配老师</button>
                <button class="ghost-button" type="button" style="width: auto;" @click="goScore(item)">去评分</button>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>

    <div v-if="assetModalOpen" class="asset-modal-overlay" @click.self="closeAssets">
      <section class="asset-modal">
        <div class="asset-modal-head">
          <div>
            <div class="hero-eyebrow">提交文件</div>
            <h3>{{ assetModalTitle }}</h3>
            <p class="panel-subtitle">{{ assetModalSubtitle }}</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" @click="closeAssets">关闭</button>
        </div>

        <div v-if="assetLoading" class="empty-state">加载文件中...</div>
        <div v-else-if="assetErrorMessage" class="alert error">{{ assetErrorMessage }}</div>
        <SubmissionAssetPanel
          v-else-if="assetDetail"
          :submission-id="assetDetail.id"
          :assets="assetDetail.assets"
          title="提交文件"
          description="管理员可在这里预览 PDF、图片、Office、PPT、视频，并下载全部材料。"
        />
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import SubmissionAssetPanel from '../components/SubmissionAssetPanel.vue';
import { adminListSubmissionSummaries, exportTeacherScores, fetchAssignments, fetchSubmissionDetail } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';
import { translateCompletenessStatus, translateRiskFlag, translateSubmissionStatus } from '../utils/statusText';

const authStore = useAuthStore();
const router = useRouter();

const assignments = ref([]);
const submissions = ref([]);
const selectedAssignmentId = ref('');
const selectedRiskLevel = ref('');
const loading = ref(false);
const exporting = ref(false);
const errorMessage = ref('');
const assetModalOpen = ref(false);
const assetLoading = ref(false);
const assetDetail = ref(null);
const assetErrorMessage = ref('');
const assetModalTitle = ref('');
const assetModalSubtitle = ref('');

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

async function openAssets(item) {
  if (!item?.id) return;
  assetModalOpen.value = true;
  assetLoading.value = true;
  assetErrorMessage.value = '';
  assetDetail.value = null;
  assetModalTitle.value = item.project_name || '未填写项目名';
  assetModalSubtitle.value = `${item.group_name || '未填写小组'} · ${item.student_name || item.student_id}`;
  try {
    assetDetail.value = await fetchSubmissionDetail(authStore.token, item.id);
  } catch (error) {
    assetErrorMessage.value = error?.message || '加载文件失败';
  } finally {
    assetLoading.value = false;
  }
}

function closeAssets() {
  assetModalOpen.value = false;
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

function riskCardClass(level) {
  if (level === 'high') return 'risk-card-high';
  if (level === 'medium') return 'risk-card-medium';
  return 'risk-card-low';
}

function uploadStateLabel(value) {
  const v = String(value || '').toLowerCase();
  if (v === 'failed') return '失败';
  if (v === 'uploading') return '上传中';
  return '正常';
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

.dashboard-row.risk-card-low {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(236, 253, 245, 0.9);
}

.dashboard-row.risk-card-medium {
  border-color: rgba(245, 158, 11, 0.3);
  background: rgba(255, 247, 237, 0.94);
}

.dashboard-row.risk-card-high {
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(254, 242, 242, 0.94);
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

.asset-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 50;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.48);
  backdrop-filter: blur(8px);
}

.asset-modal {
  width: min(1080px, calc(100vw - 24px));
  max-height: 88vh;
  overflow: auto;
  padding: 24px;
  border-radius: 28px;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.12), transparent 32%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 250, 252, 0.98));
  box-shadow: 0 24px 48px rgba(15, 23, 42, 0.18);
}

.asset-modal-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
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
