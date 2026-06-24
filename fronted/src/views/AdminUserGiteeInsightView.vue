<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div class="repo-insight-shell">
      <section class="repo-insight-hero">
        <div>
          <p class="hero-eyebrow">Gitee 代码观测台</p>
          <h1>{{ detail?.project_name || detail?.group_name || 'Gitee 代码统计' }}</h1>
          <p class="hero-copy">
            {{ detail?.group_name || '未分组' }} · {{ detail?.repo_url || '未配置仓库' }}
          </p>
          <p class="hero-meta">
            统计语言构成、总代码量与成员工作量，用于后续教师端 AI 打分参考。
          </p>
        </div>
        <div class="hero-actions">
          <button class="primary-button" type="button" :disabled="loading" @click="loadDetail(true)">
            {{ loading ? '提交中...' : '后台刷新分析' }}
          </button>
          <button class="ghost-button" type="button" @click="goBack">返回学生列表</button>
        </div>
      </section>

      <div v-if="message" class="alert success">{{ message }}</div>
      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section v-if="detail?.analysis_message || detail?.analysis_state !== 'ready'" class="panel">
        <div class="edueval-panel-body" style="padding-top: 18px; padding-bottom: 18px;">
          <div class="panel-subtitle">
            分析状态：{{ analysisStateLabel(detail?.analysis_state) }}
            <span v-if="detail?.analysis_stale">，当前先显示缓存结果</span>
          </div>
          <div class="panel-subtitle" style="margin-top: 6px;">
            {{ detail?.analysis_message || '后台正在预加载仓库详情，页面会自动刷新。' }}
          </div>
        </div>
      </section>

      <section class="stats-grid">
        <article class="stat-card">
          <span>总代码行</span>
          <strong>{{ detail?.code_summary?.total_lines ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span>源代码文件</span>
          <strong>{{ detail?.code_summary?.source_file_count ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span>估计体积</span>
          <strong>{{ formatKb(detail?.code_summary?.estimated_kb ?? 0) }}</strong>
        </article>
        <article class="stat-card">
          <span>同步状态</span>
          <strong>{{ translateRepoSyncStatus(detail?.sync_status) }}</strong>
        </article>
      </section>

      <section class="insight-grid">
        <article class="panel code-panel">
          <div class="panel-header">
            <div>
              <h3 style="margin: 0;">代码构成</h3>
              <p class="panel-subtitle">饼图按代码行数显示语言占比，颜色固定便于横向比较。</p>
            </div>
            <div class="panel-subtitle">
              更新时间 {{ formatTime(detail?.analysis_generated_at) }}
            </div>
          </div>

          <div class="edueval-panel-body code-panel-body">
            <div class="pie-card">
              <svg viewBox="0 0 220 220" class="pie-chart" aria-label="代码语言占比">
                <circle cx="110" cy="110" r="72" fill="none" stroke="rgba(148, 163, 184, 0.18)" stroke-width="32" />
                <circle
                  v-for="segment in pieSegments"
                  :key="segment.language"
                  cx="110"
                  cy="110"
                  r="72"
                  fill="none"
                  :stroke="segment.color"
                  stroke-width="32"
                  stroke-linecap="butt"
                  :stroke-dasharray="segment.dashArray"
                  :stroke-dashoffset="segment.dashOffset"
                  transform="rotate(-90 110 110)"
                />
                <text x="110" y="102" text-anchor="middle" class="pie-total-label">总代码</text>
                <text x="110" y="126" text-anchor="middle" class="pie-total-value">{{ detail?.code_summary?.total_lines ?? 0 }}</text>
              </svg>
            </div>

            <div class="language-list">
              <div v-if="!languageItems.length" class="empty-state">当前还没有可展示的语言统计。</div>
              <div v-for="item in languageItems" :key="item.language" class="language-row">
                <div class="language-label">
                  <span class="language-dot" :style="{ background: item.color }"></span>
                  <strong>{{ item.language }}</strong>
                </div>
                <div class="language-values">
                  <span>{{ item.lines }} 行</span>
                  <strong>{{ formatPercent(item.percent) }}</strong>
                </div>
              </div>
            </div>
          </div>
        </article>

        <article class="panel info-panel">
          <div class="panel-header">
            <div>
              <h3 style="margin: 0;">仓库摘要</h3>
              <p class="panel-subtitle">把 AI 后续可能参考的基础指标直接拉平展示。</p>
            </div>
          </div>
          <div class="edueval-panel-body info-grid">
            <div class="info-chip">
              <span>主语言</span>
              <strong>{{ detail?.code_summary?.dominant_language || '未知' }}</strong>
            </div>
            <div class="info-chip">
              <span>总文件数</span>
              <strong>{{ detail?.code_summary?.total_files ?? 0 }}</strong>
            </div>
            <div class="info-chip">
              <span>风险等级</span>
              <strong>{{ translateRiskLevel(detail?.code_summary?.risk_level) }}</strong>
            </div>
            <div class="info-chip">
              <span>绑定仓库</span>
              <strong>{{ repoLabel(detail?.repo_url) }}</strong>
            </div>
          </div>
          <div class="risk-tags">
            <span v-for="flag in detail?.risk_flags || []" :key="flag" class="badge warn">{{ translateRiskFlag(flag) }}</span>
            <span v-if="!(detail?.risk_flags || []).length" class="badge neutral">当前无额外风险标记</span>
          </div>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">成员工作量</h3>
            <p class="panel-subtitle">横条长度表示工作量占比，工作量默认按代码改动总行数估算。</p>
          </div>
          <div class="panel-subtitle">成员 {{ memberItems.length }} 人</div>
        </div>

        <div class="edueval-panel-body workload-list">
          <div v-if="loading && !memberItems.length" class="empty-state">加载中...</div>
          <div v-else-if="!memberItems.length" class="empty-state">当前没有可展示的成员工作量数据。</div>
          <article v-for="item in memberItems" :key="item.student_id" class="workload-card">
            <div class="workload-head">
              <div>
                <strong>{{ item.real_name || item.student_id }}</strong>
                <div class="muted-line">{{ item.student_id }} · {{ item.gitee_login || '未绑定 Gitee 昵称' }}</div>
              </div>
              <div class="workload-percent">{{ formatPercent(item.workload_percent) }}</div>
            </div>

            <div class="workload-track">
              <div class="workload-bar" :style="{ width: `${Math.max(item.workload_percent || 0, item.workload_percent > 0 ? 6 : 0)}%` }"></div>
            </div>

            <div class="workload-meta">
              <span>工作量 {{ item.workload_value }}</span>
              <span>提交 {{ item.commit_count }}</span>
              <span>+{{ item.additions }} / -{{ item.deletions }}</span>
              <span>文件 {{ item.changed_files }}</span>
            </div>
          </article>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { fetchAdminUserRepoInsight } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';
import { translateRepoSyncStatus, translateRiskFlag, translateRiskLevel } from '../utils/statusText';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const loading = ref(false);
const detail = ref(null);
const errorMessage = ref('');
const message = ref('');
let pollTimer = null;

const languageItems = computed(() => Array.isArray(detail.value?.code_summary?.languages) ? detail.value.code_summary.languages : []);
const memberItems = computed(() => Array.isArray(detail.value?.members) ? detail.value.members : []);

const pieSegments = computed(() => {
  const items = languageItems.value;
  const circumference = 2 * Math.PI * 72;
  let offset = 0;
  return items.map((item) => {
    const percent = Number(item.percent || 0);
    const arc = (percent / 100) * circumference;
    const segment = {
      language: item.language,
      color: item.color,
      dashArray: `${arc} ${Math.max(circumference - arc, 0)}`,
      dashOffset: -offset,
    };
    offset += arc;
    return segment;
  });
});

function formatPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '0%';
  return `${(Math.round(num * 10) / 10).toFixed(1).replace(/\.0$/, '')}%`;
}

function formatKb(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return '0 KB';
  return `${(Math.round(num * 10) / 10).toFixed(1).replace(/\.0$/, '')} KB`;
}

function repoLabel(url) {
  const value = String(url || '').trim();
  if (!value) return '未配置';
  try {
    const parts = new URL(value).pathname.split('/').filter(Boolean);
    return parts.slice(-2).join('/') || value;
  } catch (_) {
    return value;
  }
}

function formatTime(value) {
  if (!value) return '未生成';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '未生成';
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function analysisStateLabel(value) {
  return {
    ready: '已就绪',
    queued: '排队中',
    refreshing: '刷新中',
    missing: '待生成',
  }[value] || '待生成';
}

function clearPolling() {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
}

function shouldPoll(payload) {
  const state = String(payload?.analysis_state || '');
  return ['queued', 'refreshing', 'missing'].includes(state);
}

function schedulePolling(payload) {
  clearPolling();
  if (!shouldPoll(payload)) return;
  pollTimer = setTimeout(() => {
    loadDetail(false);
  }, 12000);
}

async function loadDetail(refresh = false) {
  loading.value = true;
  errorMessage.value = '';
  if (refresh) {
    message.value = '';
  }
  try {
    const payload = await fetchAdminUserRepoInsight(authStore.token, route.params.userId, { refresh });
    detail.value = payload;
    schedulePolling(payload);
    if (refresh) {
      message.value = payload?.analysis_message || '已提交后台刷新任务，页面会自动更新。';
    } else if (payload?.analysis_state !== 'ready' || payload?.analysis_stale) {
      message.value = payload?.analysis_message || '后台正在刷新仓库分析，页面会自动更新。';
    }
  } catch (error) {
    clearPolling();
    errorMessage.value = error?.message || '加载 Gitee 代码统计失败';
  } finally {
    loading.value = false;
  }
}

function goBack() {
  router.push({ name: 'admin-users' });
}

onMounted(() => {
  loadDetail(false);
});

onUnmounted(() => {
  clearPolling();
});
</script>

<style scoped>
.repo-insight-shell {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 16px;
}

.repo-insight-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  flex-wrap: wrap;
  padding: 24px 28px;
  border-radius: 30px;
  border: 1px solid rgba(37, 99, 235, 0.16);
  background:
    radial-gradient(circle at 12% 18%, rgba(37, 99, 235, 0.12), transparent 24%),
    radial-gradient(circle at 86% 22%, rgba(124, 58, 237, 0.16), transparent 28%),
    linear-gradient(135deg, #f8fbff 0%, #ffffff 42%, #f3f7ff 100%);
}

[data-web-theme="dark"] .repo-insight-hero {
  background:
    radial-gradient(circle at 12% 18%, rgba(37, 99, 235, 0.18), transparent 24%),
    radial-gradient(circle at 86% 22%, rgba(124, 58, 237, 0.24), transparent 28%),
    linear-gradient(135deg, rgba(15, 23, 42, 0.98) 0%, rgba(17, 24, 39, 0.98) 42%, rgba(30, 41, 59, 0.98) 100%);
}

.hero-eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #2563eb;
}

.repo-insight-hero h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.1;
}

.hero-copy,
.hero-meta {
  margin: 10px 0 0;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: flex-start;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.stat-card {
  display: grid;
  gap: 8px;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid var(--border);
  background: var(--surface);
}

.stat-card span {
  color: var(--text-secondary);
}

.stat-card strong {
  font-size: 28px;
  line-height: 1.1;
}

.insight-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 16px;
}

.code-panel-body {
  display: grid;
  grid-template-columns: minmax(240px, 320px) minmax(0, 1fr);
  gap: 18px;
  align-items: center;
}

.pie-card {
  display: flex;
  justify-content: center;
}

.pie-chart {
  width: 220px;
  height: 220px;
}

.pie-total-label {
  fill: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
}

.pie-total-value {
  fill: var(--text-primary);
  font-size: 26px;
  font-weight: 800;
}

.language-list {
  display: grid;
  gap: 12px;
}

.language-row {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.language-label,
.language-values {
  display: flex;
  gap: 10px;
  align-items: center;
}

.language-values {
  color: var(--text-secondary);
}

.language-dot {
  width: 12px;
  height: 12px;
  border-radius: 999px;
  box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.14);
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.info-chip {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.info-chip span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
}

.info-chip strong {
  display: block;
  margin-top: 8px;
  font-size: 18px;
  line-height: 1.4;
}

.risk-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  padding: 0 22px 22px;
}

.workload-list {
  display: grid;
  gap: 14px;
}

.workload-card {
  display: grid;
  gap: 12px;
  padding: 18px 20px;
  border-radius: 22px;
  border: 1px solid var(--border);
  background:
    linear-gradient(90deg, rgba(37, 99, 235, 0.05) 0%, rgba(124, 58, 237, 0.04) 100%),
    var(--surface);
}

.workload-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.workload-percent {
  font-size: 28px;
  font-weight: 800;
  color: #2563eb;
  line-height: 1;
}

.workload-track {
  height: 14px;
  border-radius: 999px;
  overflow: hidden;
  background: rgba(148, 163, 184, 0.18);
}

.workload-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2563eb 0%, #7c3aed 100%);
}

.workload-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

@media (max-width: 1100px) {
  .stats-grid,
  .info-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .insight-grid,
  .code-panel-body {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .stats-grid,
  .info-grid {
    grid-template-columns: 1fr;
  }

  .repo-insight-hero,
  .workload-head,
  .language-row {
    display: grid;
  }
}
</style>
