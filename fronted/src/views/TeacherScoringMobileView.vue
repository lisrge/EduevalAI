<template>
  <div class="teacher-mobile-page">
    <header class="teacher-mobile-header">
      <div>
        <div class="eyebrow">教师评分</div>
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
            <div class="queue-score">A均分 {{ formatScore(item.aggregate.average_group_total_score || 0) }}</div>
          </div>
        </button>
      </section>

      <section class="review-panel">
        <div v-if="loadingReview" class="empty-state">加载评分详情...</div>
        <div v-else-if="!review" class="empty-state">从左侧选择一个提交开始评分。</div>
        <template v-else>
          <div class="review-hero">
            <div>
              <div class="eyebrow">提交记录 #{{ review.submission.id }}</div>
              <h2>{{ review.submission.project_name || '未填写项目名' }}</h2>
              <p>{{ review.submission.group_name || '未填写小组' }} · {{ review.submission.student_name }} · {{ review.submission.student_id }}</p>
              <p>分配老师：{{ review.assigned_teachers?.map(t => t.teacher_student_id).join('，') || '未指定' }}</p>
            </div>
            <div class="aggregate-card">
              <div>已评分 {{ review.aggregate.score_count }} / 分配 {{ review.aggregate.assigned_teacher_count }}</div>
              <strong>{{ formatScore(review.aggregate.average_group_total_score) }}</strong>
              <span>小组 A 均分</span>
            </div>
          </div>

          <div class="meta-grid">
            <article class="meta-card">
              <span>状态</span>
              <strong>{{ translateSubmissionStatus(review.submission.status) }} / {{ translateCompletenessStatus(review.submission.completeness_status) }}</strong>
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
            <article class="meta-card">
              <span>成员 C 均分</span>
              <strong>{{ formatScore(review.aggregate.average_total_score) }}</strong>
            </article>
            <article class="meta-card">
              <span>五分制均分</span>
              <strong>{{ formatScore(review.aggregate.average_five_scale_score) }}</strong>
            </article>
          </div>

          <section class="asset-preview-section">
            <div class="section-title">提交材料</div>
            <SubmissionAssetPanel
              :submission-id="review.submission.id"
              :assets="review.submission.assets"
              title="作业文件"
              description="教师可直接预览 PDF、图片、Word、Excel、PPT、视频，也可以下载到本地。"
            />
          </section>

          <section class="member-panel">
            <div class="section-title">成员与工作量</div>
            <article
              v-for="member in review.workload.members"
              :key="member.student_id"
              class="member-card member-card--interactive"
              role="button"
              tabindex="0"
              @click="openMemberModal(member)"
              @keydown.enter.prevent="openMemberModal(member)"
              @keydown.space.prevent="openMemberModal(member)"
            >
              <div class="member-row">
                <div>
                  <strong>{{ member.student_name }}</strong>
                  <div class="member-meta">{{ member.student_id }} · {{ member.project_role || '未填写角色' }} · {{ translateContributionSource(member.contribution_source) }}</div>
                </div>
                <span class="member-rank">#{{ member.rank_order }} / {{ member.workload_index }}</span>
              </div>
              <div class="member-stats">
                <span class="member-stat-pill">Git {{ getEvidenceValue(member, 'Git commits', '0') }} 次</span>
                <span class="member-stat-pill">新增 {{ getEvidenceValue(member, 'Git additions', '0') }} 行</span>
                <span class="member-stat-pill">博客 {{ member.blog_post_count || 0 }} 篇</span>
                <span class="member-stat-pill">工作项 {{ member.blog_work_item_count || 0 }} 条</span>
              </div>
              <p class="member-teaser">{{ truncateText(member.summary_text, 84) }}</p>
              <div class="member-actions">
                <button class="ghost-button" type="button" style="width: auto;" @click.stop="openMemberBlogs(member)">
                  查看博客
                </button>
                <span class="member-hint">点击卡片查看工作详情</span>
              </div>
            </article>
          </section>

          <!-- 博客总览 -->
          <section v-if="review.blog_summary && review.blog_summary.member_blogs?.length" class="blog-summary-panel">
            <div class="section-title">博客总览</div>
            <div class="blog-summary-cards">
              <div class="summary-card">
                <div class="summary-value">{{ review.blog_summary.total_blog_count }}</div>
                <div class="summary-label">总博客数</div>
              </div>
              <div class="summary-card risk">
                <div class="summary-value">{{ review.blog_summary.total_low_quality_count }}</div>
                <div class="summary-label">低质量博客</div>
              </div>
            </div>
          </section>

          <section class="score-panel">
            <div class="section-title">小组评分 A</div>
            <div v-if="review.ai_recommendation?.group" class="teacher-ai-card">
              <div class="teacher-ai-head">
                <strong>AI 推荐</strong>
                <span>{{ review.ai_recommendation.source_model || '规则推荐' }}</span>
              </div>
              <div class="teacher-ai-grid">
                <div class="teacher-ai-item">
                  <span>展示度与完整性</span>
                  <strong>{{ review.ai_recommendation.group.project_display_score }}</strong>
                </div>
                <div class="teacher-ai-item">
                  <span>项目创新性</span>
                  <strong>{{ review.ai_recommendation.group.project_innovation_score }}</strong>
                </div>
                <div class="teacher-ai-item">
                  <span>关键亮点</span>
                  <strong>{{ review.ai_recommendation.group.key_highlight_score }}</strong>
                </div>
                <div class="teacher-ai-item">
                  <span>推荐 A 分</span>
                  <strong>{{ formatScore(review.ai_recommendation.group.group_total_score) }}</strong>
                </div>
              </div>
              <p class="teacher-ai-reason">{{ review.ai_recommendation.group.reason || review.ai_recommendation.overview }}</p>
            </div>
            <div class="score-grid">
              <label v-for="field in groupScoreFields" :key="field.key" class="score-input-card">
                <span>{{ field.label }}</span>
                <small>{{ field.weight }}</small>
                <input v-model.number="form[field.key]" type="number" min="0" max="100" class="edueval-input" :disabled="!review.assigned_to_me && !authStore.isAdmin" />
              </label>
            </div>
            <label class="comment-box">
              <span>教师总评</span>
              <textarea v-model="form.comment" class="edueval-input" rows="5" placeholder="填写教师评语、风险点和建议。" :disabled="!review.assigned_to_me && !authStore.isAdmin"></textarea>
            </label>
            <div class="score-actions">
              <div class="total-box">
                <span>A 分</span>
                <strong>{{ formatScore(groupTotalScore) }}</strong>
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

    <div v-if="memberModal" class="teacher-modal-overlay" @click.self="closeMemberModal">
      <section class="teacher-member-modal">
        <button class="teacher-member-modal-close" type="button" @click="closeMemberModal">×</button>
        <div class="teacher-member-modal-head">
          <div class="eyebrow">成员画像</div>
          <h3>{{ memberModal.student_name }}</h3>
          <p>{{ memberModal.student_id }} · {{ memberModal.project_role || '未填写角色' }} · {{ translateContributionSource(memberModal.contribution_source) }}</p>
        </div>

        <div class="teacher-member-modal-stats">
          <article class="teacher-member-stat-card">
            <span>Git 提交</span>
            <strong>{{ getEvidenceValue(memberModal, 'Git commits', '0') }}</strong>
          </article>
          <article class="teacher-member-stat-card">
            <span>新增行数</span>
            <strong>{{ getEvidenceValue(memberModal, 'Git additions', '0') }}</strong>
          </article>
          <article class="teacher-member-stat-card">
            <span>博客篇数</span>
            <strong>{{ memberModal.blog_post_count || 0 }}</strong>
          </article>
          <article class="teacher-member-stat-card">
            <span>工作项</span>
            <strong>{{ memberModal.blog_work_item_count || 0 }}</strong>
          </article>
        </div>

        <section class="teacher-member-modal-section">
          <div class="teacher-member-modal-label">工作概要</div>
          <p class="teacher-member-modal-summary">{{ memberModal.summary_text || '暂无工作概要。' }}</p>
        </section>

        <section v-if="memberModal.work_items?.length" class="teacher-member-modal-section">
          <div class="teacher-member-modal-label">识别出的工作项</div>
          <ul class="teacher-member-modal-list">
            <li v-for="item in memberModal.work_items" :key="item">{{ item }}</li>
          </ul>
        </section>

        <section v-if="displayEvidence(memberModal).length" class="teacher-member-modal-section">
          <div class="teacher-member-modal-label">核验信息</div>
          <div class="teacher-member-evidence-grid">
            <div v-for="item in displayEvidence(memberModal)" :key="`${item.label}-${item.value}`" class="teacher-member-evidence-item">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </section>

        <section class="teacher-member-modal-section">
          <div class="teacher-member-modal-label">个人概述</div>
          <div class="teacher-member-personal-box">
            {{ memberModal.personal_statement || '该成员未填写个人概述。' }}
          </div>
        </section>

        <section class="teacher-member-modal-section">
          <div class="teacher-member-modal-label">个人评分 B</div>
          <div v-if="getMemberRecommendation(memberModal)" class="teacher-ai-card">
            <div class="teacher-ai-head">
              <strong>AI 推荐</strong>
              <span>现场展示默认 100</span>
            </div>
            <div class="teacher-ai-grid">
              <div class="teacher-ai-item">
                <span>个人工作难度</span>
                <strong>{{ getMemberRecommendation(memberModal).personal_work_difficulty_score }}</strong>
              </div>
              <div class="teacher-ai-item">
                <span>现场展示效果</span>
                <strong>{{ getMemberRecommendation(memberModal).live_demo_score }}</strong>
              </div>
              <div class="teacher-ai-item">
                <span>推荐 B 分</span>
                <strong>{{ formatScore(getMemberRecommendation(memberModal).personal_total_score) }}</strong>
              </div>
              <div class="teacher-ai-item">
                <span>推荐最终分</span>
                <strong>{{ formatScore(getMemberRecommendation(memberModal).final_score) }}</strong>
              </div>
            </div>
            <p class="teacher-ai-reason">{{ getMemberRecommendation(memberModal).reason || 'AI 已结合博客、分工、代码和工作项给出推荐值。' }}</p>
          </div>
          <div class="teacher-member-score-grid">
            <label class="score-input-card">
              <span>个人工作难度</span>
              <small>30%</small>
              <input v-model.number="ensureMemberForm(memberModal.student_id).personal_work_difficulty_score" type="number" min="0" max="100" class="edueval-input" :disabled="!review.assigned_to_me && !authStore.isAdmin" />
            </label>
            <label class="score-input-card">
              <span>现场展示效果</span>
              <small>10%</small>
              <input v-model.number="ensureMemberForm(memberModal.student_id).live_demo_score" type="number" min="0" max="100" class="edueval-input" :disabled="!review.assigned_to_me && !authStore.isAdmin" />
            </label>
          </div>
          <label class="comment-box">
            <span>成员备注</span>
            <textarea v-model="ensureMemberForm(memberModal.student_id).comment" class="edueval-input" rows="3" placeholder="补充该成员个人表现、答辩表现或风险点。" :disabled="!review.assigned_to_me && !authStore.isAdmin"></textarea>
          </label>
          <div class="teacher-member-score-totals">
            <div class="total-box">
              <span>本评委 B 分</span>
              <strong>{{ formatScore(getMemberPersonalTotal(memberModal.student_id)) }}</strong>
            </div>
            <div class="total-box total-box--accent">
              <span>本评委 C 分 = min(A, B)</span>
              <strong>{{ formatScore(getMemberFinalTotal(memberModal.student_id)) }}</strong>
            </div>
            <div class="total-box">
              <span>汇总 B 均分</span>
              <strong>{{ formatScore(getMemberAggregate(memberModal.student_id)?.average_personal_score || 0) }}</strong>
            </div>
            <div class="total-box total-box--accent">
              <span>汇总 C 分</span>
              <strong>{{ formatScore(getMemberAggregate(memberModal.student_id)?.capped_final_score || 0) }}</strong>
            </div>
            <div class="total-box">
              <span>五分制</span>
              <strong>{{ getMemberAggregate(memberModal.student_id)?.five_scale_score ?? 0 }}</strong>
            </div>
          </div>
        </section>

        <div class="teacher-member-modal-actions">
          <button class="ghost-button" type="button" style="width: auto;" @click="closeMemberModal">关闭</button>
          <button class="primary-button" type="button" @click="openMemberBlogs(memberModal)">查看该成员博客</button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import SubmissionAssetPanel from '../components/SubmissionAssetPanel.vue';
import { fetchAssignments, fetchTeacherReviewQueue, fetchTeacherSubmissionReview, saveTeacherSubmissionScore } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';
import { translateCompletenessStatus, translateContributionSource, translateSubmissionStatus } from '../utils/statusText';

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
const memberModal = ref(null);
const form = ref({
  project_display_score: 80,
  project_innovation_score: 80,
  key_highlight_score: 80,
  member_scores: [],
  comment: '',
});

const groupScoreFields = [
  { key: 'project_display_score', label: '项目展示度和完整性', weight: '50%' },
  { key: 'project_innovation_score', label: '项目创新性', weight: '30%' },
  { key: 'key_highlight_score', label: '关键亮点', weight: '20%' },
];

const groupTotalScore = computed(() => calcGroupTotal(form.value));

const nextSubmissionId = computed(() => {
  const idx = queue.value.findIndex(item => String(item.submission.id) === String(activeSubmissionId.value || ''));
  if (idx < 0 || idx >= queue.value.length - 1) return null;
  return queue.value[idx + 1].submission.id;
});

function clampScore(value, fallback = 0) {
  const num = Number(value);
  if (!Number.isFinite(num)) return fallback;
  return Math.max(0, Math.min(100, Math.round(num)));
}

function calcGroupTotal(payload) {
  return (clampScore(payload?.project_display_score) * 0.5)
    + (clampScore(payload?.project_innovation_score) * 0.3)
    + (clampScore(payload?.key_highlight_score) * 0.2);
}

function calcPersonalTotal(item) {
  return ((clampScore(item?.personal_work_difficulty_score) * 30) + (clampScore(item?.live_demo_score, 100) * 10)) / 40;
}

function formatScore(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '0';
  return (Math.round(num * 10) / 10).toFixed(1).replace(/\.0$/, '');
}

function ensureMemberForm(studentId, studentName = '') {
  const sid = String(studentId || '').trim();
  if (!sid) return { student_id: '', student_name: '', personal_work_difficulty_score: 0, live_demo_score: 100, comment: '' };
  if (!Array.isArray(form.value.member_scores)) {
    form.value.member_scores = [];
  }
  let item = form.value.member_scores.find(entry => String(entry.student_id) === sid);
  if (!item) {
    const recommended = review.value?.ai_recommendation?.members?.find(entry => String(entry.student_id) === sid);
    item = {
      student_id: sid,
      student_name: studentName || recommended?.student_name || '',
      personal_work_difficulty_score: Number(recommended?.personal_work_difficulty_score ?? 0),
      live_demo_score: Number(recommended?.live_demo_score ?? 100),
      comment: '',
    };
    form.value.member_scores.push(item);
  }
  if (!item.student_name && studentName) {
    item.student_name = studentName;
  }
  return item;
}

function getMemberRecommendation(member) {
  if (!member?.student_id) return null;
  return review.value?.ai_recommendation?.members?.find(item => String(item.student_id) === String(member.student_id)) || null;
}

function getMemberPersonalTotal(studentId) {
  return calcPersonalTotal(ensureMemberForm(studentId));
}

function getMemberFinalTotal(studentId) {
  return Math.min(groupTotalScore.value, getMemberPersonalTotal(studentId));
}

function getMemberAggregate(studentId) {
  return review.value?.member_aggregates?.find(item => String(item.student_id) === String(studentId)) || null;
}

function getEvidenceValue(member, label, fallback = '-') {
  const list = Array.isArray(member?.evidence) ? member.evidence : [];
  const matched = list.find(item => String(item?.label || '') === String(label || ''));
  const value = String(matched?.value ?? '').trim();
  return value || fallback;
}

function displayEvidence(member) {
  const list = Array.isArray(member?.evidence) ? member.evidence : [];
  return list
    .filter(item => String(item?.label || '') !== '个人陈述')
    .map(item => ({
      ...item,
      label: {
        'Git commits': 'Git 提交次数',
        'Git additions': 'Git 新增行数',
        'Git deletions': 'Git 删除行数',
        'Git changed files': 'Git 变更文件数',
        'Blog posts': '博客篇数',
        'Work items': '工作项数量',
      }[String(item?.label || '')] || item?.label,
    }));
}

function formatDate(dateStr) {
  if (!dateStr) return '-';
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
  } catch {
    return '-';
  }
}

function truncateText(text, maxLen = 100) {
  if (!text) return '';
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + '...';
}

function openMemberModal(member) {
  ensureMemberForm(member?.student_id, member?.student_name || '');
  memberModal.value = member || null;
}

function closeMemberModal() {
  memberModal.value = null;
}

function openMemberBlogs(member) {
  if (!member?.student_id || !activeSubmissionId.value) return;
  router.push({
    name: 'teacher-member-blogs',
    params: {
      submissionId: String(activeSubmissionId.value),
      studentId: String(member.student_id),
    },
    query: {
      ...(selectedAssignmentId.value ? { assignmentId: selectedAssignmentId.value } : {}),
    },
  });
}

function handleEsc(event) {
  if (event.key === 'Escape' && memberModal.value) {
    closeMemberModal();
  }
}

function goAdmin() {
  router.push({ name: 'admin-submissions' });
}

async function doLogout() {
  await authStore.logout();
  router.replace({ name: 'login' });
}

function applyReviewToForm(payload) {
  const myScore = payload?.my_score;
  const recommendedGroup = payload?.ai_recommendation?.group || {};
  const recommendedMembers = Array.isArray(payload?.ai_recommendation?.members) ? payload.ai_recommendation.members : [];
  form.value = {
    project_display_score: Number(myScore?.project_display_score ?? recommendedGroup.project_display_score ?? 80),
    project_innovation_score: Number(myScore?.project_innovation_score ?? recommendedGroup.project_innovation_score ?? 80),
    key_highlight_score: Number(myScore?.key_highlight_score ?? recommendedGroup.key_highlight_score ?? 80),
    member_scores: (Array.isArray(myScore?.member_scores) && myScore.member_scores.length
      ? myScore.member_scores
      : recommendedMembers
    ).map(item => ({
      student_id: String(item.student_id || ''),
      student_name: item.student_name || '',
      personal_work_difficulty_score: Number(item.personal_work_difficulty_score ?? 0),
      live_demo_score: Number(item.live_demo_score ?? 100),
      comment: item.comment || '',
    })),
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
    closeMemberModal();
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
    const submitPayload = {
      project_display_score: clampScore(form.value.project_display_score),
      project_innovation_score: clampScore(form.value.project_innovation_score),
      key_highlight_score: clampScore(form.value.key_highlight_score),
      member_scores: (Array.isArray(form.value.member_scores) ? form.value.member_scores : []).map(item => ({
        student_id: String(item.student_id || ''),
        personal_work_difficulty_score: clampScore(item.personal_work_difficulty_score),
        live_demo_score: clampScore(item.live_demo_score, 100),
        comment: item.comment || '',
      })),
      comment: form.value.comment || '',
    };
    const payload = await saveTeacherSubmissionScore(authStore.token, activeSubmissionId.value, submitPayload);
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
  window.addEventListener('keydown', handleEsc);
  reloadAll();
});

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleEsc);
});
</script>

<style scoped>
.teacher-mobile-page {
  min-height: 100vh;
  padding: 18px;
  color: var(--text-primary);
  background:
    radial-gradient(circle at top left, rgba(245, 158, 11, 0.16), transparent 28%),
    radial-gradient(circle at top right, rgba(61, 99, 221, 0.12), transparent 26%),
    linear-gradient(180deg, rgba(255, 249, 240, 0.92) 0%, rgba(246, 248, 253, 0.96) 100%);
}

.teacher-mobile-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
  padding: 22px 24px;
  border: 1px solid var(--border);
  border-radius: 24px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}

.teacher-mobile-header h1 {
  margin: 6px 0 4px;
  font-size: 28px;
}

.teacher-mobile-header p,
.eyebrow {
  margin: 0;
  color: var(--text-secondary);
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
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: var(--surface);
  box-shadow: var(--shadow-sm);
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
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 16px;
  box-shadow: var(--shadow-sm);
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
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 12px;
  background: var(--surface-soft);
  text-align: left;
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.queue-card.active {
  border-color: var(--border-strong);
  box-shadow: 0 0 0 4px rgba(61, 99, 221, 0.12);
}

.queue-title {
  font-weight: 700;
  color: var(--text-primary);
}

.queue-meta,
.member-meta,
.queue-score {
  font-size: 13px;
  color: var(--text-secondary);
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
  background: var(--warning-soft);
  color: var(--badge-warn-text);
}

.queue-badge.done {
  background: var(--success-soft);
  color: var(--success);
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
.member-work-items {
  margin: 10px 0 0;
  padding-left: 20px;
  line-height: 1.6;
}

.score-panel {
  background: linear-gradient(180deg, var(--surface-soft) 0%, var(--surface) 100%);
  border: 1px solid var(--border-strong);
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
  color: var(--badge-warn-text);
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
  color: var(--text-secondary);
}

.member-panel,
.score-panel {
  display: grid;
  gap: 12px;
}

.asset-preview-section {
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.96));
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
  color: var(--text-secondary);
}

.member-card--interactive {
  cursor: pointer;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}

.member-card--interactive:hover,
.member-card--interactive:focus-visible {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-md);
  outline: none;
}

.member-rank {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: var(--primary-soft);
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
}

.member-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.member-stat-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 10px;
  border-radius: 999px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  font-size: 12px;
}

.member-teaser {
  margin-top: 12px;
}

.member-actions {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
  margin-top: 14px;
}

.member-hint {
  font-size: 12px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.score-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.teacher-member-score-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.teacher-ai-card {
  display: grid;
  gap: 12px;
  margin-bottom: 14px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(59, 130, 246, 0.18);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.95) 0%, rgba(255, 255, 255, 0.92) 100%);
}

[data-web-theme="dark"] .teacher-ai-card {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.96) 0%, rgba(22, 33, 56, 0.96) 100%);
}

.teacher-ai-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 13px;
}

.teacher-ai-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.teacher-ai-item {
  padding: 12px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.teacher-ai-item span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
}

.teacher-ai-item strong {
  display: block;
  margin-top: 8px;
  font-size: 24px;
  line-height: 1.1;
}

.teacher-ai-reason {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.7;
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
  color: var(--text-secondary);
}

.total-box strong {
  font-size: 28px;
  color: var(--primary);
}

.total-box--accent strong {
  color: var(--danger);
}

.teacher-alert {
  margin-bottom: 12px;
  color: #b91c1c;
  background: rgba(254, 226, 226, 0.86);
  border: 1px solid rgba(239, 68, 68, 0.2);
  border-radius: 14px;
  padding: 12px;
}

.teacher-modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(8, 15, 32, 0.56);
  backdrop-filter: blur(8px);
}

.teacher-member-modal {
  position: relative;
  width: min(760px, calc(100vw - 24px));
  max-height: min(88vh, 920px);
  overflow: auto;
  padding: 28px;
  border-radius: 28px;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at top right, rgba(61, 99, 221, 0.16), transparent 28%),
    linear-gradient(180deg, var(--surface) 0%, rgba(247, 250, 255, 0.98) 100%);
  box-shadow: var(--shadow-md);
}

[data-web-theme="dark"] .teacher-member-modal {
  background:
    radial-gradient(circle at top right, rgba(125, 162, 255, 0.18), transparent 28%),
    linear-gradient(180deg, rgba(19, 28, 47, 0.98) 0%, rgba(22, 33, 56, 1) 100%);
}

.teacher-member-modal-close {
  position: absolute;
  top: 18px;
  right: 18px;
  width: 38px;
  height: 38px;
  border: 0;
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}

.teacher-member-modal-head {
  display: grid;
  gap: 6px;
  margin-bottom: 18px;
}

.teacher-member-modal-head p {
  margin: 0;
  color: var(--text-secondary);
}

.teacher-member-modal-stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 18px;
}

.teacher-member-stat-card,
.teacher-member-evidence-item {
  padding: 14px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.teacher-member-stat-card span,
.teacher-member-evidence-item span,
.teacher-member-modal-label {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.teacher-member-stat-card strong,
.teacher-member-evidence-item strong {
  display: block;
  margin-top: 8px;
  font-size: 24px;
  line-height: 1.1;
  color: var(--text-primary);
}

.teacher-member-modal-section {
  display: grid;
  gap: 10px;
  margin-bottom: 18px;
}

.teacher-member-modal-summary {
  margin: 0;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.5);
  line-height: 1.8;
  color: var(--text-primary);
}

[data-web-theme="dark"] .teacher-member-modal-summary {
  background: rgba(15, 23, 42, 0.42);
}

.teacher-member-personal-box {
  min-height: 152px;
  padding: 18px 20px;
  border-radius: 20px;
  border: 1px solid var(--border);
  background: rgba(255, 255, 255, 0.56);
  line-height: 1.85;
  color: var(--text-primary);
  white-space: pre-wrap;
}

[data-web-theme="dark"] .teacher-member-personal-box {
  background: rgba(15, 23, 42, 0.48);
}

.teacher-member-modal-list {
  margin: 0;
  padding-left: 20px;
  line-height: 1.7;
}

.teacher-member-evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
}

.teacher-member-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.teacher-member-score-totals {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
}

/* 博客相关样式 */
.member-blogs-section {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}

.blogs-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.low-quality-badge {
  font-size: 12px;
  color: var(--danger);
  background: var(--danger-soft);
  padding: 4px 10px;
  border-radius: 999px;
}

.blogs-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.blog-item {
  display: block;
  text-decoration: none;
  background: var(--surface-soft);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 10px;
  transition: all 0.2s;
}

.blog-item:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}

.blog-title {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
  margin-bottom: 4px;
}

.blog-meta {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.blog-risk {
  color: var(--danger);
  font-weight: 600;
  background: var(--danger-soft);
  padding: 2px 8px;
  border-radius: 999px;
}

.blog-summary {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
  line-height: 1.5;
}

.no-blogs {
  font-size: 12px;
  color: var(--text-muted);
  padding: 8px 0;
}

.blog-summary-panel {
  background: linear-gradient(180deg, rgba(255, 250, 240, 0.9) 0%, var(--surface) 100%);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 14px;
}

.blog-summary-cards {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.summary-card {
  background: var(--surface-soft);
  border-radius: 12px;
  padding: 12px;
  text-align: center;
  border: 1px solid var(--border);
}

.summary-card.risk {
  border-color: rgba(239, 68, 68, 0.24);
  background: rgba(254, 242, 242, 0.76);
}

.summary-value {
  font-size: 28px;
  font-weight: 700;
  color: var(--primary);
  line-height: 1;
}

.summary-card.risk .summary-value {
  color: var(--danger);
}

.summary-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

@media (max-width: 960px) {
  .teacher-mobile-layout {
    grid-template-columns: 1fr;
  }

  .meta-grid,
  .score-grid,
  .teacher-member-score-grid,
  .teacher-ai-grid {
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
  .score-grid,
  .teacher-member-score-grid,
  .teacher-ai-grid,
  .teacher-member-modal-stats,
  .teacher-member-evidence-grid {
    grid-template-columns: 1fr;
  }

  .member-actions {
    align-items: stretch;
  }
}

@media (max-width: 480px) {
  .teacher-mobile-page {
    padding: 10px;
    font-size: 14px;
  }

  .teacher-mobile-header {
    padding: 14px;
    border-radius: 18px;
  }

  .teacher-mobile-header h1 {
    font-size: 22px;
  }

  .teacher-toolbar {
    padding: 12px;
    border-radius: 16px;
  }

  .queue-panel,
  .review-panel {
    padding: 12px;
    border-radius: 16px;
  }

  .queue-card {
    padding: 10px;
    border-radius: 14px;
  }

  .review-hero h2 {
    font-size: 20px;
  }

  .aggregate-card {
    padding: 12px;
  }

  .aggregate-card strong {
    font-size: 28px;
  }

  .meta-card,
  .member-card,
  .score-panel,
  .asset-preview-section {
    padding: 12px;
    border-radius: 16px;
  }

  .teacher-ai-card {
    padding: 12px;
    border-radius: 16px;
  }

  .teacher-ai-item {
    padding: 10px;
    border-radius: 14px;
  }

  .teacher-ai-item strong {
    font-size: 20px;
  }

  .total-box strong {
    font-size: 22px;
  }

  .teacher-member-modal {
    padding: 18px;
    border-radius: 20px;
  }

  .teacher-member-modal-close {
    top: 12px;
    right: 12px;
    width: 34px;
    height: 34px;
    font-size: 20px;
  }

  .teacher-member-stat-card,
  .teacher-member-evidence-item {
    padding: 12px;
    border-radius: 16px;
  }

  .teacher-member-stat-card strong,
  .teacher-member-evidence-item strong {
    font-size: 20px;
  }

  .teacher-member-modal-summary,
  .teacher-member-personal-box {
    padding: 14px;
    border-radius: 16px;
  }

  :deep(.primary-button),
  :deep(.ghost-button),
  :deep(.danger-button) {
    padding: 10px 12px;
    font-size: 14px;
  }

  :deep(select),
  :deep(input[type='text']),
  :deep(input[type='number']),
  :deep(textarea) {
    font-size: 14px;
  }
}
</style>
