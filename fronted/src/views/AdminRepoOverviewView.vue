<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div class="repo-overview-shell">
      <section class="repo-hero">
        <div>
          <p class="hero-eyebrow">Gitee 仓库总览</p>
          <h2>Gitee 仓库总览</h2>
          <p class="hero-copy">
            按组查看仓库同步状态，并展示组内每个成员的提交次数、代码增删量、文件变更量和活跃周次。
          </p>
        </div>
        <div class="hero-actions">
          <button class="primary-button" type="button" :disabled="loading || syncing" @click="syncCurrentGroup">
            {{ syncingGroup ? '同步中...' : '同步当前筛选组' }}
          </button>
          <button class="primary-button" type="button" :disabled="loading || syncing" @click="syncAll">
            {{ syncingAll ? '同步中...' : '一键同步全部仓库' }}
          </button>
          <button class="ghost-button" type="button" :disabled="loading || syncing" @click="loadAll">刷新</button>
          <button class="ghost-button" type="button" @click="goBack">返回</button>
        </div>
      </section>

      <div v-if="message" class="alert success">{{ message }}</div>
      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="stats-grid">
        <article class="stat-card">
          <span>Gitee 用户</span>
          <strong>{{ userItems.length }}</strong>
        </article>
        <article class="stat-card">
          <span>有仓库绑定的组</span>
          <strong>{{ activeRepoCount }}</strong>
        </article>
        <article class="stat-card">
          <span>累计提交数</span>
          <strong>{{ totalCommits }}</strong>
        </article>
        <article class="stat-card">
          <span>风险标记</span>
          <strong>{{ summary.risk_flags?.length || 0 }}</strong>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">筛选</h3>
            <p class="panel-subtitle">先按组筛选，再对当前组执行同步。</p>
          </div>
        </div>
        <div class="edueval-panel-body filter-grid">
          <label class="field">
            <span>小组</span>
            <select v-model="filters.groupName">
              <option value="all">全部小组</option>
              <option v-for="name in groupOptions" :key="name" :value="name">{{ name }}</option>
            </select>
          </label>
          <label class="field">
            <span>同步状态</span>
            <select v-model="filters.syncStatus">
              <option value="all">全部</option>
              <option value="synced">已同步</option>
              <option value="failed">同步失败</option>
              <option value="never_bound">未绑定仓库</option>
              <option value="never_synced">未同步</option>
              <option value="group_repo_only">仅填写了组仓库</option>
            </select>
          </label>
          <label class="field">
            <span>贡献来源</span>
            <select v-model="filters.contributionSource">
              <option value="all">全部</option>
              <option value="git">仅 Git</option>
              <option value="mixed">Git + 非 Git</option>
              <option value="non_git">非 Git</option>
            </select>
          </label>
          <label class="field keyword-field">
            <span>关键词</span>
            <input
              v-model.trim="filters.keyword"
              type="text"
              placeholder="学号 / 姓名 / 项目名 / 仓库"
            />
          </label>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">风险报告</h3>
            <p class="panel-subtitle">这里展示仓库缺失、未同步、作者未映射等风险。</p>
          </div>
        </div>
        <div class="edueval-panel-body">
          <div v-if="!summary.risk_flags?.length" class="empty-state" style="padding: 0;">当前没有聚合风险标记。</div>
          <div v-else class="tag-row">
            <span v-for="flag in summary.risk_flags" :key="flag" class="badge warn">{{ translateRiskFlag(flag) }}</span>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">成员进度总览</h3>
            <p class="panel-subtitle">同步按组执行，展示按成员统计。</p>
          </div>
          <div class="panel-subtitle">当前结果 {{ filteredItems.length }} / {{ userItems.length }}</div>
        </div>

        <div class="edueval-panel-body table-wrap">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="!filteredItems.length" class="empty-state">当前没有可展示的 Gitee 数据。</div>
          <table v-else class="admin-table">
            <thead>
              <tr>
                <th>用户</th>
                <th>项目 / 小组</th>
                <th>仓库</th>
                <th>同步状态</th>
                <th>提交数</th>
                <th>新增 / 删除</th>
                <th>文件数</th>
                <th>活跃周次</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredItems" :key="`${item.user_id}-${item.student_id}`">
                <td>
                  <div class="strong-line">{{ item.student_name || item.display_name || '-' }}</div>
                  <div class="muted-line">{{ item.student_id || '-' }}</div>
                  <div class="muted-line">{{ item.project_role || '-' }} / {{ translateContributionSource(item.contribution_source) }}</div>
                </td>
                <td>
                  <div class="strong-line">{{ item.project_name || '-' }}</div>
                  <div class="muted-line">{{ item.group_name || '-' }}</div>
                </td>
                <td>
                  <a
                    v-if="item.repo_url"
                    :href="item.repo_url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="origin-link"
                  >
                    {{ repoLabel(item.repo_url) }}
                  </a>
                  <span v-else class="muted-line">未绑定</span>
                </td>
                <td>
                  <div class="strong-line">{{ translateRepoSyncStatus(item.sync_status) }}</div>
                  <div class="muted-line">{{ formatTime(item.last_sync_at) }}</div>
                </td>
                <td>{{ item.matched_commit_count }}</td>
                <td>+{{ item.matched_additions }} / -{{ item.matched_deletions }}</td>
                <td>{{ item.matched_changed_files }}</td>
                <td>{{ item.matched_weeks?.join(', ') || '-' }}</td>
                <td>
                  <button
                    class="ghost-button compact-button"
                    type="button"
                    :disabled="!item.submission_id"
                    @click="goSubmissionRepo(item.submission_id)"
                  >
                    查看仓库页
                  </button>
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
import {
  adminListUsers,
  fetchRepoMemberProgress,
  runAllRepoBindings,
  runSelectedRepoBindings,
} from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';
import { translateContributionSource, translateRepoSyncStatus, translateRiskFlag } from '../utils/statusText';

const authStore = useAuthStore();
const router = useRouter();

const summary = ref({ total_members: 0, total_submissions: 0, risk_flags: [], items: [] });
const users = ref([]);
const loading = ref(false);
const syncingAll = ref(false);
const syncingGroup = ref(false);
const errorMessage = ref('');
const message = ref('');

const syncing = computed(() => syncingAll.value || syncingGroup.value);

const filters = ref({
  keyword: '',
  groupName: 'all',
  syncStatus: 'all',
  contributionSource: 'all',
});

const userItems = computed(() => {
  const progressByStudentId = new Map((summary.value.items || []).map(item => [String(item.student_id || ''), item]));
  return (users.value || [])
    .filter(item => String(item.gitee_url || '').trim())
    .map(user => {
      const progress = progressByStudentId.get(String(user.student_id || '')) || null;
      return {
        user_id: user.id,
        group_id: user.group_id || null,
        student_id: user.student_id,
        student_name: user.display_name || '',
        display_name: user.display_name || '',
        group_name: user.group_name || '',
        project_name: user.project_title || progress?.project_name || '',
        repo_url: user.gitee_url || progress?.repo_url || '',
        submission_id: progress?.submission_id || null,
        binding_id: progress?.binding_id || null,
        project_role: progress?.project_role || '',
        contribution_source: progress?.contribution_source || 'mixed',
        sync_status: progress?.sync_status || 'group_repo_only',
        last_sync_at: progress?.last_sync_at || null,
        matched_commit_count: Number(progress?.matched_commit_count || 0),
        matched_additions: Number(progress?.matched_additions || 0),
        matched_deletions: Number(progress?.matched_deletions || 0),
        matched_changed_files: Number(progress?.matched_changed_files || 0),
        matched_weeks: Array.isArray(progress?.matched_weeks) ? progress.matched_weeks : [],
      };
    });
});

const groupOptions = computed(() => {
  return [...new Set(userItems.value.map(item => String(item.group_name || '').trim()).filter(Boolean))].sort((a, b) =>
    a.localeCompare(b, 'zh-CN'),
  );
});

const filteredItems = computed(() => {
  const keyword = String(filters.value.keyword || '').trim().toLowerCase();
  return userItems.value.filter(item => {
    if (filters.value.groupName !== 'all' && String(item.group_name || '') !== filters.value.groupName) return false;
    if (filters.value.syncStatus !== 'all' && String(item.sync_status || '') !== filters.value.syncStatus) return false;
    if (
      filters.value.contributionSource !== 'all' &&
      String(item.contribution_source || '') !== filters.value.contributionSource
    ) {
      return false;
    }
    if (!keyword) return true;
    return [item.student_name, item.student_id, item.project_name, item.group_name, item.repo_url].some(value =>
      String(value || '').toLowerCase().includes(keyword),
    );
  });
});

const selectedSubmissionIds = computed(() => {
  return [...new Set(filteredItems.value.map(item => Number(item.submission_id || 0)).filter(Boolean))];
});

const selectedGroupIds = computed(() => {
  return [...new Set(filteredItems.value.map(item => Number(item.group_id || 0)).filter(Boolean))];
});

const totalCommits = computed(() => userItems.value.reduce((sum, item) => sum + Number(item.matched_commit_count || 0), 0));

const activeRepoCount = computed(() => {
  const ids = new Set(userItems.value.map(item => Number(item.submission_id || 0)).filter(Boolean));
  return ids.size;
});

function repoLabel(url) {
  const parts = String(url || '').split('/').filter(Boolean);
  return parts.slice(-2).join('/') || url;
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function goBack() {
  router.push({ name: 'admin-users' });
}

function goSubmissionRepo(submissionId) {
  router.push({ name: 'admin-repo-progress', params: { submissionId: String(submissionId) } });
}

async function loadAll() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const [progress, userList] = await Promise.all([fetchRepoMemberProgress(authStore.token), adminListUsers(authStore.token)]);
    summary.value = progress || { total_members: 0, total_submissions: 0, risk_flags: [], items: [] };
    users.value = Array.isArray(userList) ? userList : [];
  } catch (error) {
    errorMessage.value = error?.message || '加载 Gitee 总览失败';
  } finally {
    loading.value = false;
  }
}

async function syncAll() {
  syncingAll.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const result = await runAllRepoBindings(authStore.token);
    message.value = `已处理 ${result.total_bindings || 0} 个仓库，成功 ${result.success_count || 0} 个，失败 ${result.failed_count || 0} 个。`;
    await loadAll();
  } catch (error) {
    errorMessage.value = error?.message || '批量同步 Gitee 仓库失败';
  } finally {
    syncingAll.value = false;
  }
}

async function syncCurrentGroup() {
  const submissionIds = selectedSubmissionIds.value;
  const groupIds = selectedGroupIds.value;
  if (!submissionIds.length && !groupIds.length) {
    errorMessage.value = '当前筛选结果下没有可同步的小组仓库。';
    message.value = '';
    return;
  }

  syncingGroup.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const result = await runSelectedRepoBindings(authStore.token, { submissionIds, groupIds });
    const groupLabel = filters.value.groupName === 'all' ? '当前筛选结果' : `小组 ${filters.value.groupName}`;
    message.value = `${groupLabel} 已处理 ${result.total_bindings || 0} 个仓库，成功 ${result.success_count || 0} 个，失败 ${result.failed_count || 0} 个。`;
    await loadAll();
  } catch (error) {
    errorMessage.value = error?.message || '按组同步 Gitee 仓库失败';
  } finally {
    syncingGroup.value = false;
  }
}

onMounted(() => {
  loadAll();
});
</script>

<style scoped>
.repo-overview-shell {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 16px;
}

.repo-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 24px 26px;
  border-radius: 28px;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.18), transparent 28%),
    linear-gradient(135deg, #eff6ff 0%, #fff 44%, #f8fafc 100%);
}

.hero-eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #1d4ed8;
}

.repo-hero h2 {
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

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.stat-card {
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.stat-card span {
  display: block;
  color: var(--text-secondary);
  font-size: 13px;
}

.stat-card strong {
  display: block;
  margin-top: 8px;
  font-size: 20px;
  line-height: 1.4;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
}

.keyword-field {
  grid-column: span 1;
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
  vertical-align: top;
}

.tag-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.strong-line {
  font-weight: 700;
}

.muted-line {
  margin-top: 4px;
  color: var(--text-secondary);
  font-size: 12px;
}

.compact-button,
.origin-link {
  width: auto;
  padding: 6px 10px;
}

.success {
  color: #166534;
}

@media (max-width: 1080px) {
  .stats-grid,
  .filter-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 640px) {
  .stats-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }
}
</style>
