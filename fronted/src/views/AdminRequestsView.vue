<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div class="request-shell">
      <section class="request-hero">
        <div>
          <p class="hero-eyebrow">审核中心</p>
          <h2>管理员待审核申请中心</h2>
          <p class="hero-copy">
            集中审核申请书重传和签名变更请求，避免在用户列表里逐条弹窗处理。
          </p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" @click="goBack">返回</button>
        </div>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">筛选条件</h3>
            <p class="panel-subtitle">按状态、类型和学号快速定位申请。</p>
          </div>
          <button class="ghost-button" type="button" :disabled="loading" @click="loadRequests">刷新</button>
        </div>
        <div class="edueval-panel-body filter-grid">
          <label class="field">
            <span>状态</span>
            <select v-model="filters.status" @change="loadRequests">
              <option value="pending">待审核</option>
              <option value="approved">已批准</option>
              <option value="rejected">已驳回</option>
            </select>
          </label>
          <label class="field">
            <span>申请类型</span>
            <select v-model="filters.type">
              <option value="all">全部</option>
              <option value="application_reupload">申请书重传</option>
              <option value="homework_resubmit">作业重新提交</option>
              <option value="signature_update">签名变更</option>
            </select>
          </label>
          <label class="field">
            <span>学号搜索</span>
            <input v-model.trim="filters.keyword" type="text" placeholder="搜索学号或备注" />
          </label>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">申请列表</h3>
            <p class="panel-subtitle">当前结果 {{ filteredItems.length }} / {{ items.length }}</p>
          </div>
        </div>

        <div class="edueval-panel-body table-wrap">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="filteredItems.length === 0" class="empty-state">暂无匹配申请。</div>

          <table v-else class="admin-table">
            <thead>
              <tr>
                <th>学号</th>
                <th>申请类型</th>
                <th>状态</th>
                <th>申请说明</th>
                <th>文件</th>
                <th>提交时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in filteredItems" :key="item.id">
                <td>
                  <div class="strong-line">{{ item.student_id }}</div>
                  <div class="muted-line">用户 ID {{ item.user_id }}</div>
                </td>
                <td>{{ typeLabel(item.request_type) }}</td>
                <td><span :class="['badge', statusBadge(item.status)]">{{ statusLabel(item.status) }}</span></td>
                <td class="note-cell">{{ item.request_note || '-' }}</td>
                <td>{{ item.file_name || '-' }}</td>
                <td>{{ formatTime(item.created_at) }}</td>
                <td>
                  <div class="inline-stack">
                    <button class="ghost-button compact-button" type="button" @click="goUser(item.user_id)">查看用户</button>
                    <button v-if="item.status === 'pending'" class="ghost-button compact-button" type="button" @click="openReviewModal(item, 'approved')">
                      批准
                    </button>
                    <button v-if="item.status === 'pending'" class="ghost-button compact-button danger-outline" type="button" @click="openReviewModal(item, 'rejected')">
                      驳回
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="reviewModal.visible" class="modal-mask" @click.self="closeReviewModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>{{ reviewModal.action === 'approved' ? '批准申请' : '驳回申请' }}</h3>
            <p class="panel-subtitle">
              {{ reviewModal.item ? `${reviewModal.item.student_id} · ${typeLabel(reviewModal.item.request_type)}` : '' }}
            </p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeReviewModal">关闭</button>
        </div>
        <div class="modal-body">
          <div class="review-summary">
            <strong>申请说明</strong>
            <p>{{ reviewModal.item?.request_note || '未填写备注' }}</p>
          </div>
          <label class="field">
            <span>审核备注</span>
            <textarea v-model.trim="reviewModal.reviewNote" rows="4" placeholder="填写审核说明"></textarea>
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
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { adminListAllRequests, adminReviewUserRequest } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const items = ref([]);
const loading = ref(false);
const localError = ref('');

const filters = ref({
  status: 'pending',
  type: 'all',
  keyword: '',
});

const reviewModal = ref({
  visible: false,
  item: null,
  action: 'approved',
  reviewNote: '',
  saving: false,
});

const errorMessage = computed(() => localError.value);
const filteredItems = computed(() => {
  const keyword = filters.value.keyword.toLowerCase();
  return items.value.filter(item => {
    if (filters.value.type !== 'all' && item.request_type !== filters.value.type) return false;
    if (!keyword) return true;
    const text = `${item.student_id} ${item.request_note || ''} ${item.file_name || ''}`.toLowerCase();
    return text.includes(keyword);
  });
});

function goBack() {
  router.push({ name: 'admin-users' });
}

function goUser(userId) {
  router.push({ name: 'admin-user-blogs', params: { userId: String(userId) } });
}

function typeLabel(value) {
  if (value === 'signature_update') return '签名变更';
  if (value === 'homework_resubmit') return '作业重新提交';
  return '申请书重传';
}

function statusLabel(value) {
  if (value === 'approved') return '已批准';
  if (value === 'rejected') return '已驳回';
  return '待审核';
}

function statusBadge(value) {
  if (value === 'approved') return 'ok';
  if (value === 'rejected') return 'error';
  return 'warn';
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? String(value) : dt.toLocaleString();
}

async function loadRequests() {
  loading.value = true;
  localError.value = '';
  try {
    const list = await adminListAllRequests(authStore.token, filters.value.status);
    items.value = Array.isArray(list) ? list : [];
  } catch (e) {
    localError.value = e?.message || '加载申请失败';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function openReviewModal(item, action) {
  reviewModal.value = {
    visible: true,
    item,
    action,
    reviewNote: action === 'approved' ? '管理员已批准' : '管理员已驳回',
    saving: false,
  };
}

function closeReviewModal() {
  reviewModal.value = {
    visible: false,
    item: null,
    action: 'approved',
    reviewNote: '',
    saving: false,
  };
}

async function submitReview() {
  const item = reviewModal.value.item;
  if (!item) return;
  reviewModal.value.saving = true;
  try {
    await adminReviewUserRequest(authStore.token, item.user_id, item.id, {
      status: reviewModal.value.action,
      review_note: reviewModal.value.reviewNote,
    });
    await loadRequests();
    closeReviewModal();
  } catch (e) {
    localError.value = e?.message || '审核失败';
  } finally {
    reviewModal.value.saving = false;
  }
}

onMounted(() => {
  loadRequests();
});
</script>

<style scoped>
.request-shell {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 16px;
}

.request-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 24px 26px;
  border-radius: 28px;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at top right, rgba(34, 197, 94, 0.18), transparent 28%),
    linear-gradient(135deg, #f7fee7 0%, #fff 44%, #eff6ff 100%);
}

.theme-dark .request-hero {
  background:
    radial-gradient(circle at top right, rgba(126, 226, 184, 0.12), transparent 28%),
    linear-gradient(135deg, var(--surface) 0%, rgba(17, 27, 45, 0.92) 60%, rgba(106, 160, 255, 0.08) 100%);
}

.hero-eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #15803d;
}

.theme-dark .hero-eyebrow {
  color: var(--badge-ok-text);
}

.request-hero h2 {
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

.hero-actions .ghost-button {
  height: 44px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
  vertical-align: top;
}

.strong-line {
  font-weight: 800;
}

.muted-line {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
}

.note-cell {
  max-width: 320px;
}

.inline-stack {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.compact-button {
  width: auto;
  padding: 6px 10px;
}

.badge.warn {
  background: var(--badge-warn-bg);
  color: var(--badge-warn-text);
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

.review-summary {
  padding: 14px 16px;
  border-radius: 16px;
  background: var(--alert-bg);
  border: 1px solid var(--border);
}

.review-summary strong {
  display: block;
  margin-bottom: 8px;
}

.review-summary p {
  margin: 0;
  line-height: 1.7;
}

@media (max-width: 860px) {
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .request-hero h2 {
    font-size: 26px;
  }
}
</style>
