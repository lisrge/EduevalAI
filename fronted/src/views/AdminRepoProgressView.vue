<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 14px;">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">仓库进度追踪</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">绑定 Gitee 仓库、映射成员身份，并支持按周自动同步。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="ghost-button" type="button" style="width: auto;" @click="loadAll">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </div>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="font-weight: 700;">提交信息</div>
        <div class="panel-subtitle">提交人：{{ submission?.student_name || submission?.student_id || '-' }}</div>
        <div class="panel-subtitle">项目：{{ submission?.project_name || '未填写项目名称' }}</div>
        <div class="panel-subtitle">小组：{{ submission?.group_name || '未填写小组' }}</div>
      </section>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
          <div>
            <div style="font-weight: 700;">Gitee 仓库绑定</div>
            <div class="panel-subtitle">支持公开仓库手动同步和定时周同步。</div>
          </div>
          <div v-if="schedulerStatus && authStore.isAdmin" class="panel-subtitle">
            调度器：{{ schedulerStatus.running ? '运行中' : '空闲' }} / 每周{{ weekdayLabel(schedulerStatus.weekday) }} {{ String(schedulerStatus.hour).padStart(2, '0') }}:00
          </div>
        </div>

        <label>
          <div class="panel-subtitle">仓库地址</div>
          <input v-model.trim="repoUrl" class="edueval-input" type="text" placeholder="https://gitee.com/owner/repo" />
        </label>
        <label>
          <div class="panel-subtitle">默认分支</div>
          <input v-model.trim="defaultBranch" class="edueval-input" type="text" placeholder="例如 master 或 main" />
        </label>

        <label v-if="binding" style="display: flex; align-items: center; gap: 10px;">
          <input v-model="autoSyncEnabled" type="checkbox" />
          <span>开启定时周同步</span>
        </label>

        <div class="form-actions" style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="primary-button" type="button" :disabled="loading" @click="saveBinding">保存绑定</button>
          <button class="ghost-button" type="button" :disabled="loading || !binding?.id" @click="saveAutoSync">保存自动同步</button>
          <button class="ghost-button" type="button" :disabled="loading || !binding?.id" @click="syncNow">立即同步</button>
          <button v-if="authStore.isAdmin" class="ghost-button" type="button" :disabled="loading" @click="runSchedulerNow">执行本周调度</button>
        </div>

        <div v-if="binding" class="panel-subtitle">
          当前状态：{{ binding.sync_status }}，最近手动/常规同步：{{ formatDate(binding.last_sync_at) }}，最近自动同步：{{ formatDate(binding.last_auto_sync_at) }}
          <span v-if="binding.last_error">，错误：{{ binding.last_error }}</span>
        </div>
        <div v-if="schedulerStatus?.last_result" class="panel-subtitle">
          调度结果：{{ schedulerStatus.last_result }}，最近运行：{{ formatDate(schedulerStatus.last_run_at) }}
        </div>
      </section>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
          <div>
            <div style="font-weight: 700;">成员映射与 git / 非 git 贡献</div>
            <div class="panel-subtitle">配置 git 作者名 / 邮箱别名，或标记为非 git 成员。</div>
          </div>
          <button class="primary-button" type="button" :disabled="loading" @click="saveMappings">保存映射</button>
        </div>

        <div v-for="member in memberMappings" :key="member.member_id" class="panel" style="padding: 12px; display: grid; gap: 10px;">
          <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
            <strong>{{ member.student_name }} / {{ member.student_id }}</strong>
            <span class="panel-subtitle">{{ member.project_role || '未填写角色' }}</span>
          </div>

          <div class="mapping-grid">
            <label>
              <div class="panel-subtitle">贡献来源</div>
              <select v-model="member.contribution_source" class="edueval-input">
                <option value="git">git</option>
                <option value="mixed">mixed</option>
                <option value="non_git">non_git</option>
              </select>
            </label>
            <label>
              <div class="panel-subtitle">git 作者名别名</div>
              <input v-model.trim="member.git_author_names_text" class="edueval-input" type="text" placeholder="多个值用逗号分隔" />
            </label>
            <label>
              <div class="panel-subtitle">git 邮箱别名</div>
              <input v-model.trim="member.git_author_emails_text" class="edueval-input" type="text" placeholder="多个值用逗号分隔" />
            </label>
          </div>

          <div class="panel-subtitle">
            匹配结果：{{ member.matched_commit_count }} commits，+{{ member.matched_additions }} / -{{ member.matched_deletions }}，涉及 {{ member.matched_changed_files }} 个文件
          </div>
          <div class="panel-subtitle">
            活跃周次：{{ member.matched_weeks?.join(', ') || '暂无' }}
          </div>
        </div>

        <div class="panel-subtitle" v-if="contributionSummary?.unmapped_authors?.length">
          未映射作者：{{ contributionSummary.unmapped_authors.join(', ') }}
        </div>
        <div class="panel-subtitle" v-if="contributionSummary?.non_git_members?.length">
          非 git 成员：{{ contributionSummary.non_git_members.join(', ') }}
        </div>
        <div class="panel-subtitle" v-if="contributionSummary?.risk_flags?.length">
          风险提示：{{ contributionSummary.risk_flags.join(', ') }}
        </div>
      </section>

      <div v-if="message || errorMessage" class="panel" style="padding: 14px;">
        <div v-if="message" style="color: #166534;">{{ message }}</div>
        <div v-if="errorMessage" style="color: #b91c1c; margin-top: 8px;">{{ errorMessage }}</div>
      </div>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="font-weight: 700;">每周进度统计</div>
        <div v-if="weeklyStats.length === 0" class="panel-subtitle">当前没有同步到 commit 数据。</div>
        <div v-else class="weekly-card-list">
          <article v-for="item in weeklyStats" :key="item.week_label" class="weekly-card">
            <div class="weekly-heading">
              <div>
                <strong>{{ item.week_label }}</strong>
                <span class="panel-subtitle">{{ item.week_start }} ~ {{ item.week_end }}</span>
              </div>
              <span class="progress-badge" :data-status="item.progress_status">{{ progressLabel(item.progress_status) }}</span>
            </div>
            <p class="weekly-summary">{{ item.work_summary }}</p>
            <div class="weekly-metrics">
              <span>{{ item.commit_count }} commits</span>
              <span>+{{ item.additions }} / -{{ item.deletions }}</span>
              <span>{{ item.changed_files }} 个文件</span>
            </div>
            <div v-for="member in item.members" :key="`${item.week_label}-${member.student_name}`" class="member-progress-row">
              <strong>{{ member.student_name }}</strong>
              <span>{{ member.work_summary }}</span>
              <small>{{ member.commit_count }} commits，+{{ member.additions }} / -{{ member.deletions }}</small>
            </div>
            <div v-if="item.unmapped_authors.length" class="panel-subtitle">未映射作者：{{ item.unmapped_authors.join(', ') }}</div>
            <div v-if="item.risk_flags.length" class="panel-subtitle">风险：{{ item.risk_flags.join(', ') }}</div>
          </article>
        </div>
      </section>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap;">
          <div>
            <div style="font-weight: 700;">按成员查看提交记录</div>
            <div class="panel-subtitle">查看每位成员的 commit、代码增删量和涉及文件数。</div>
          </div>
          <select v-model="selectedMemberKey" class="edueval-input" style="width: auto; min-width: 220px;">
            <option value="all">全部成员</option>
            <option v-for="member in memberCommitOverview.members" :key="member.member_id" :value="String(member.member_id)">
              {{ member.student_name }}（{{ member.commit_count }}）
            </option>
            <option value="unmapped">未映射作者（{{ memberCommitOverview.unmapped_commits.length }}）</option>
          </select>
        </div>

        <div v-if="selectedMemberHistory" class="member-total-grid">
          <span>提交 <strong>{{ selectedMemberHistory.commit_count }}</strong></span>
          <span>新增 <strong>+{{ selectedMemberHistory.additions }}</strong></span>
          <span>删除 <strong>-{{ selectedMemberHistory.deletions }}</strong></span>
          <span>文件 <strong>{{ selectedMemberHistory.changed_files }}</strong></span>
        </div>
        <div v-if="visibleMemberCommits.length === 0" class="panel-subtitle">当前筛选下没有提交。</div>
        <div v-for="item in visibleMemberCommits" :key="`member-${item.id}`" class="commit-detail-card">
          <div class="commit-detail-heading">
            <strong>{{ item.author_name || 'Unknown' }}</strong>
            <span>{{ formatDate(item.committed_at) }}</span>
          </div>
          <div>{{ item.message || '-' }}</div>
          <div class="panel-subtitle">+{{ item.additions }} / -{{ item.deletions }}，{{ item.changed_files }} 个文件，{{ item.commit_hash.slice(0, 10) }}</div>
          <a v-if="item.html_url" :href="item.html_url" target="_blank" rel="noopener noreferrer">在 Gitee 查看</a>
        </div>
      </section>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="font-weight: 700;">最近提交记录</div>
        <div v-if="commits.length === 0" class="panel-subtitle">当前没有提交快照。</div>
        <div v-for="item in commits" :key="item.id" class="panel" style="padding: 12px; display: grid; gap: 6px;">
          <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
            <strong>{{ item.author_name || 'Unknown' }}</strong>
            <span class="panel-subtitle">{{ formatDate(item.committed_at) }}</span>
          </div>
          <div class="panel-subtitle">{{ item.commit_hash }}</div>
          <div>{{ item.message || '-' }}</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import {
  fetchRepoCommits,
  fetchRepoMemberCommits,
  fetchRepoSchedulerStatus,
  fetchRepoWeeklyStats,
  fetchSubmissionDetail,
  fetchSubmissionRepoBinding,
  fetchSubmissionRepoContributions,
  runRepoSchedulerNow,
  syncRepoBinding,
  updateRepoBindingAutoSync,
  updateSubmissionRepoMemberMappings,
  upsertSubmissionRepoBinding,
} from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const submission = ref(null);
const binding = ref(null);
const schedulerStatus = ref(null);
const autoSyncEnabled = ref(true);
const weeklyStats = ref([]);
const commits = ref([]);
const memberCommitOverview = ref({ members: [], unmapped_commits: [] });
const selectedMemberKey = ref('all');
const contributionSummary = ref(null);
const memberMappings = ref([]);
const repoUrl = ref('');
const defaultBranch = ref('');
const loading = ref(false);
const message = ref('');
const errorMessage = ref('');

const selectedMemberHistory = computed(() => {
  if (selectedMemberKey.value === 'all' || selectedMemberKey.value === 'unmapped') return null;
  return memberCommitOverview.value.members.find(item => String(item.member_id) === selectedMemberKey.value) || null;
});

const visibleMemberCommits = computed(() => {
  if (selectedMemberKey.value === 'unmapped') return memberCommitOverview.value.unmapped_commits || [];
  if (selectedMemberHistory.value) return selectedMemberHistory.value.commits || [];
  return commits.value;
});

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function weekdayLabel(value) {
  const labels = { 1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '日' };
  return labels[Number(value)] || '?';
}

function progressLabel(value) {
  return { active: '进展活跃', steady: '稳定推进', limited: '进展较少' }[value] || '待判断';
}

function goBack() {
  router.push({ name: 'admin-submissions' });
}

function buildMemberMappingsFromSummary(summary, submissionDetail) {
  const byId = new Map((summary?.members || []).map(item => [item.member_id, item]));
  return (submissionDetail?.members || []).map((member) => {
    const matched = byId.get(member.id);
    return {
      member_id: member.id,
      student_name: member.student_name,
      student_id: member.student_id,
      project_role: member.project_role,
      contribution_source: matched?.contribution_source || member.contribution_source || 'mixed',
      git_author_names_text: (matched?.git_author_names || []).join(', '),
      git_author_emails_text: (matched?.git_author_emails || []).join(', '),
      matched_commit_count: matched?.matched_commit_count || 0,
      matched_additions: matched?.matched_additions || 0,
      matched_deletions: matched?.matched_deletions || 0,
      matched_changed_files: matched?.matched_changed_files || 0,
      matched_weeks: matched?.matched_weeks || [],
    };
  });
}

async function loadSchedulerStatus() {
  if (!authStore.isAdmin) return;
  schedulerStatus.value = await fetchRepoSchedulerStatus(authStore.token);
}

async function loadBindingAndStats() {
  const submissionId = Number(route.params.submissionId || 0);
  if (!submissionId) return;
  binding.value = await fetchSubmissionRepoBinding(authStore.token, submissionId);
  contributionSummary.value = await fetchSubmissionRepoContributions(authStore.token, submissionId);
  memberMappings.value = buildMemberMappingsFromSummary(contributionSummary.value, submission.value);
  repoUrl.value = binding.value?.repo_url || '';
  defaultBranch.value = binding.value?.default_branch || '';
  autoSyncEnabled.value = Boolean(binding.value?.auto_sync_enabled ?? true);
  if (!binding.value?.id) {
    weeklyStats.value = [];
    commits.value = [];
    memberCommitOverview.value = { members: [], unmapped_commits: [] };
    return;
  }
  weeklyStats.value = await fetchRepoWeeklyStats(authStore.token, binding.value.id);
  commits.value = await fetchRepoCommits(authStore.token, binding.value.id);
  memberCommitOverview.value = await fetchRepoMemberCommits(authStore.token, binding.value.id);
}

async function loadAll() {
  message.value = '';
  errorMessage.value = '';
  loading.value = true;
  try {
    const submissionId = Number(route.params.submissionId || 0);
    submission.value = await fetchSubmissionDetail(authStore.token, submissionId);
    await Promise.all([loadBindingAndStats(), loadSchedulerStatus()]);
  } catch (error) {
    errorMessage.value = error?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function saveBinding() {
  message.value = '';
  errorMessage.value = '';
  loading.value = true;
  try {
    const submissionId = Number(route.params.submissionId || 0);
    binding.value = await upsertSubmissionRepoBinding(authStore.token, submissionId, {
      repo_url: repoUrl.value,
      default_branch: defaultBranch.value,
    });
    autoSyncEnabled.value = Boolean(binding.value?.auto_sync_enabled ?? true);
    message.value = '仓库绑定已保存';
    await loadBindingAndStats();
  } catch (error) {
    errorMessage.value = error?.message || '保存失败';
  } finally {
    loading.value = false;
  }
}

async function saveAutoSync() {
  if (!binding.value?.id) return;
  message.value = '';
  errorMessage.value = '';
  loading.value = true;
  try {
    binding.value = await updateRepoBindingAutoSync(authStore.token, binding.value.id, autoSyncEnabled.value);
    autoSyncEnabled.value = Boolean(binding.value?.auto_sync_enabled);
    message.value = '自动同步设置已保存';
  } catch (error) {
    errorMessage.value = error?.message || '保存自动同步失败';
  } finally {
    loading.value = false;
  }
}

async function saveMappings() {
  message.value = '';
  errorMessage.value = '';
  loading.value = true;
  try {
    const submissionId = Number(route.params.submissionId || 0);
    contributionSummary.value = await updateSubmissionRepoMemberMappings(authStore.token, submissionId, {
      members: memberMappings.value.map(item => ({
        member_id: item.member_id,
        contribution_source: item.contribution_source,
        git_author_names: item.git_author_names_text,
        git_author_emails: item.git_author_emails_text,
      })),
    });
    memberMappings.value = buildMemberMappingsFromSummary(contributionSummary.value, submission.value);
    if (binding.value?.id) {
      weeklyStats.value = await fetchRepoWeeklyStats(authStore.token, binding.value.id);
    }
    message.value = '成员映射已保存';
  } catch (error) {
    errorMessage.value = error?.message || '保存映射失败';
  } finally {
    loading.value = false;
  }
}

async function syncNow() {
  if (!binding.value?.id) return;
  message.value = '';
  errorMessage.value = '';
  loading.value = true;
  try {
    const result = await syncRepoBinding(authStore.token, binding.value.id);
    binding.value = result?.binding || binding.value;
    autoSyncEnabled.value = Boolean(binding.value?.auto_sync_enabled);
    message.value = `同步完成，新抓取 ${result?.commit_count ?? 0} 条 commit`;
    await loadBindingAndStats();
  } catch (error) {
    errorMessage.value = error?.message || '同步失败';
  } finally {
    loading.value = false;
  }
}

async function runSchedulerNow() {
  message.value = '';
  errorMessage.value = '';
  loading.value = true;
  try {
    const result = await runRepoSchedulerNow(authStore.token);
    message.value = `周调度完成：扫描 ${result?.bindings_scanned ?? 0} 个仓库，同步 ${result?.bindings_synced ?? 0} 个，新增 ${result?.commits_inserted ?? 0} 条 commit`;
    await Promise.all([loadBindingAndStats(), loadSchedulerStatus()]);
  } catch (error) {
    errorMessage.value = error?.message || '执行周调度失败';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.mapping-grid {
  display: grid;
  grid-template-columns: 180px minmax(0, 1fr) minmax(0, 1fr);
  gap: 10px;
}

.member-total-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.member-total-grid span,
.commit-detail-card {
  padding: 12px;
  border-radius: 14px;
  background: var(--surface-soft);
  border: 1px solid var(--border);
}

.commit-detail-card {
  display: grid;
  gap: 6px;
}

.commit-detail-heading {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.weekly-card-list {
  display: grid;
  gap: 12px;
}

.weekly-card {
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface-soft);
}

.weekly-heading,
.weekly-heading > div,
.weekly-metrics {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.weekly-heading {
  justify-content: space-between;
}

.progress-badge {
  padding: 5px 10px;
  border-radius: 999px;
  background: #fef3c7;
  color: #92400e;
  font-size: 12px;
  font-weight: 700;
}

.progress-badge[data-status="active"] {
  background: #dcfce7;
  color: #166534;
}

.progress-badge[data-status="steady"] {
  background: #dbeafe;
  color: #1d4ed8;
}

.weekly-summary {
  margin: 12px 0;
  line-height: 1.65;
}

.weekly-metrics {
  color: var(--text-secondary);
  font-size: 13px;
}

.member-progress-row {
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) auto;
  gap: 12px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
}

.member-progress-row small {
  color: var(--text-secondary);
}

@media (max-width: 960px) {
  .mapping-grid {
    grid-template-columns: 1fr;
  }

  .member-progress-row {
    grid-template-columns: 1fr;
  }

  .member-total-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
