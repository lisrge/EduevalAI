<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div class="admin-shell">
      <section class="admin-hero">
        <div>
          <p class="hero-eyebrow">Admin Console</p>
          <h2>管理员用户与博客管理</h2>
          <p class="hero-copy">
            在一个页面里处理用户权限、分组、博客取证入口和待审核申请。
          </p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" @click="goSubmissionsDashboard">统一看板</button>
          <button class="ghost-button" type="button" @click="goBlogOverview">博客总览</button>
          <button class="ghost-button" type="button" @click="goGroups">分组管理</button>
          <button class="ghost-button" type="button" @click="goRequests">待审核申请</button>
          <button class="ghost-button" type="button" @click="goBlogRuns">抓取任务</button>
          <button class="ghost-button" type="button" @click="goBack">返回</button>
        </div>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>
      <div v-if="successMessage" class="alert" style="color: #166534;">{{ successMessage }}</div>
      <div style="display: flex; justify-content: flex-end;">
        <button class="primary-button" type="button" style="width: auto;" @click="router.push({ name: 'admin-document-import' })">批量导入申请书/任务书</button>
      </div>

      <section class="stats-grid">
        <article class="stat-card">
          <span>用户总数</span>
          <strong>{{ users.length }}</strong>
        </article>
        <article class="stat-card">
          <span>已分组用户</span>
          <strong>{{ groupedUserCount }}</strong>
        </article>
        <article class="stat-card">
          <span>已配置博客</span>
          <strong>{{ blogConfiguredCount }}</strong>
        </article>
        <article class="stat-card">
          <span>待抓取勾选</span>
          <strong>{{ selectedCrawlUsers.length }}</strong>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">筛选与批量操作</h3>
            <p class="panel-subtitle">先过滤目标用户，再执行批量抓取。</p>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button
              class="ghost-button"
              type="button"
              :disabled="loading || batchCrawling || selectedCrawlUsers.length === 0"
              @click="crawlSelectedUsers"
            >
              {{ batchCrawling ? '批量抓取中...' : `抓取所选用户博客 (${selectedCrawlUsers.length})` }}
            </button>
            <button class="ghost-button" type="button" :disabled="loading" @click="loadUsers">刷新</button>
          </div>
        </div>

        <div class="edueval-panel-body filter-grid">
          <label class="field">
            <span>学号/博客搜索</span>
            <input v-model.trim="filters.keyword" type="text" placeholder="搜索学号或博客地址" />
          </label>
          <label class="field">
            <span>角色</span>
            <select v-model="filters.role">
              <option value="all">全部角色</option>
              <option value="admin">管理员</option>
              <option value="teacher">老师</option>
              <option value="user">学生</option>
            </select>
          </label>
          <label class="field">
            <span>组号</span>
            <select v-model="filters.groupId">
              <option value="all">全部分组</option>
              <option value="ungrouped">未分组</option>
              <option v-for="group in groups" :key="group.id" :value="String(group.id)">
                第 {{ group.group_number }} 组
              </option>
            </select>
          </label>
          <label class="field">
            <span>博客配置</span>
            <select v-model="filters.blogConfig">
              <option value="all">全部</option>
              <option value="configured">已配置博客</option>
              <option value="missing">未配置博客</option>
            </select>
          </label>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">用户列表</h3>
            <p class="panel-subtitle">点击操作按钮进入精细化处理。</p>
          </div>
          <div class="panel-subtitle">当前结果 {{ filteredUsers.length }} / {{ users.length }}</div>
        </div>

        <div class="edueval-panel-body table-wrap">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="filteredUsers.length === 0" class="empty-state">没有匹配条件的用户。</div>

          <table v-else class="admin-table">
            <thead>
              <tr>
                <th style="width: 44px;">
                  <input
                    type="checkbox"
                    :checked="allVisibleSelectableChecked"
                    :indeterminate.prop="someVisibleSelectableChecked && !allVisibleSelectableChecked"
                    @change="toggleVisibleSelectable($event.target.checked)"
                  />
                </th>
                <th>学号</th>
                <th>分组</th>
                <th>博客主页</th>
                <th>Gitee仓库</th>
                <th>抓取状态</th>
                <th>用户申请</th>
                <th>博客统计</th>
                <th>草稿</th>
                <th>权限</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="u in filteredUsers" :key="u.id">
                <td>
                  <input
                    type="checkbox"
                    :disabled="!u.blog_home_url"
                    :checked="selectedCrawlUserIdSet.has(u.id)"
                    @change="toggleSelectedUser(u.id, $event.target.checked)"
                  />
                </td>
                <td>
                  <div class="strong-line">{{ u.student_id }}</div>
                  <div class="muted-line">{{ u.display_name || '未设置姓名' }}</div>
                  <div class="inline-stack" style="margin-top: 8px;">
                    <button class="ghost-button compact-button" type="button" @click="openBasicProfileModal(u)">
                      编辑资料
                    </button>
                  </div>
                  <div class="muted-line">创建于 {{ formatTime(u.created_at) }}</div>
                </td>
                <td>
                  <div class="inline-stack">
                    <span class="badge neutral">{{ u.group_number ? `第 ${u.group_number} 组` : '未分组' }}</span>
                    <span v-if="u.group_leader_name" class="badge neutral">组长 {{ u.group_leader_name }}</span>
                    <button class="ghost-button compact-button" type="button" @click="openGroupModal(u)">
                      分配
                    </button>
                  </div>
                </td>
                <td>
                  <div class="blog-cell">
                    <span class="truncate-block">{{ u.blog_home_url || '未配置' }}</span>
                    <button class="ghost-button compact-button" type="button" @click="openBlogModal(u)">
                      编辑
                    </button>
                  </div>
                </td>
                <td>
                  <a v-if="u.gitee_url" :href="u.gitee_url" target="_blank" class="origin-link" style="font-size:12px;">{{ u.gitee_url.split('/').pop() || 'Gitee' }}</a>
                  <span v-else style="color:#999;font-size:12px;">-</span>
                </td>
                <td>
                  <div class="inline-stack">
                    <span :style="{ color: crawlStatusColor(u.blog_crawl_status), fontWeight: 800 }">
                      {{ crawlStatusLabel(u.blog_crawl_status) }}
                    </span>
                    <button
                      class="ghost-button compact-button"
                      type="button"
                      :disabled="!u.blog_home_url || crawlingId === u.id || batchCrawling"
                      @click="crawlBlogs(u)"
                    >
                      抓取
                    </button>
                    <button class="ghost-button compact-button" type="button" :disabled="!u.blog_home_url" @click="goBlogs(u)">
                      查看博客
                    </button>
                  </div>
                  <div class="muted-line">{{ formatTime(u.blog_last_crawled_at) }}</div>
                </td>
                <td>
                  <div class="inline-stack">
                    <span class="badge neutral">重传待审 {{ u.pending_reupload_request_count || 0 }}</span>
                    <span class="badge neutral">签名待审 {{ u.pending_signature_request_count || 0 }}</span>
                  </div>
                  <div class="inline-stack" style="margin-top: 8px;">
                    <span :class="['badge', u.application_reupload_allowed ? 'ok' : 'neutral']">
                      {{ u.application_reupload_allowed ? '可重传一次' : '未授权重传' }}
                    </span>
                    <button class="ghost-button compact-button" type="button" @click="openRequestModal(u)">
                      审核申请
                    </button>
                  </div>
                </td>
                <td>
                  <button
                    class="ghost-button compact-button"
                    type="button"
                    :disabled="blogTotal(u) === 0 && !u.blog_home_url"
                    @click="goBlogs(u)"
                  >
                    <span style="color: #16a34a; font-weight: 800;">{{ u.blog?.normal ?? 0 }}</span>
                    <span style="opacity: 0.55; padding: 0 6px;">/</span>
                    <span style="color: #ef4444; font-weight: 800;">{{ u.blog?.abnormal ?? 0 }}</span>
                  </button>
                </td>
                <td>
                  <div class="inline-stack">
                    <button
                      class="ghost-button compact-button"
                      type="button"
                      :disabled="Number(u.application_draft_count || 0) === 0"
                      @click="goDocuments(u, 'application')"
                    >
                      申请书 {{ Number(u.application_draft_count || 0) }}
                    </button>
                    <button
                      class="ghost-button compact-button"
                      type="button"
                      :disabled="Number(u.task_draft_count || 0) === 0"
                      @click="goDocuments(u, 'task')"
                    >
                      任务书 {{ Number(u.task_draft_count || 0) }}
                    </button>
                  </div>
                </td>
                <td>
                  <button
                    class="ghost-button compact-button"
                    type="button"
                    :disabled="savingId === u.id || isRootAdmin(u) || isMe(u)"
                    @click="openRoleModal(u)"
                  >
                    {{ isRootAdmin(u) ? '初始管理员' : roleLabel(u.role) }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div v-if="roleModal.visible" class="modal-mask" @click.self="closeRoleModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>修改用户权限</h3>
            <p class="panel-subtitle">{{ roleModal.user?.student_id }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeRoleModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>目标角色</span>
            <select v-model="roleModal.nextRole">
              <option value="user">学生</option>
              <option value="teacher">老师</option>
              <option value="admin">管理员</option>
            </select>
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeRoleModal">取消</button>
          <button class="primary-button" type="button" :disabled="savingId === roleModal.user?.id" @click="submitRoleChange">
            保存
          </button>
        </div>
      </div>
    </div>

    <div v-if="basicProfileModal.visible" class="modal-mask" @click.self="closeBasicProfileModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>编辑用户资料</h3>
            <p class="panel-subtitle">{{ basicProfileModal.user?.student_id }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeBasicProfileModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>用户姓名</span>
            <input v-model.trim="basicProfileModal.realName" type="text" placeholder="填写用户真实姓名" />
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeBasicProfileModal">取消</button>
          <button class="primary-button" type="button" :disabled="basicProfileModal.saving" @click="submitBasicProfileChange">
            {{ basicProfileModal.saving ? '保存中...' : '保存资料' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="groupModal.visible" class="modal-mask" @click.self="closeGroupModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>分配用户分组</h3>
            <p class="panel-subtitle">{{ groupModal.user?.student_id }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeGroupModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>分组</span>
            <select v-model="groupModal.groupId">
              <option value="">清空分组</option>
              <option v-for="group in groups" :key="group.id" :value="String(group.id)">
                {{ `第 ${group.group_number} 组${group.leader_name ? ` · 组长 ${group.leader_name}` : ''}` }}
              </option>
            </select>
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeGroupModal">取消</button>
          <button class="primary-button" type="button" :disabled="groupModal.saving" @click="submitGroupChange">
            {{ groupModal.saving ? '保存中...' : '保存分组' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="blogModal.visible" class="modal-mask" @click.self="closeBlogModal">
      <div class="modal-card modal-card-wide">
        <div class="modal-header">
          <div>
            <h3>编辑博客主页</h3>
            <p class="panel-subtitle">{{ blogModal.user?.student_id }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeBlogModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>CSDN 用户名或完整主页地址</span>
            <input v-model.trim="blogModal.blogHomeUrl" type="text" placeholder="例如 2301_82000924 或 https://blog.csdn.net/2301_82000924" />
          </label>
          <p class="panel-subtitle" style="margin: 0;">
            留空表示清空配置。后端会自动规范化为标准的博客主页地址。
          </p>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeBlogModal">取消</button>
          <button class="primary-button" type="button" :disabled="blogModal.saving" @click="submitBlogProfile">
            {{ blogModal.saving ? '保存中...' : '保存地址' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="requestModal.visible" class="modal-mask" @click.self="closeRequestModal">
      <div class="modal-card modal-card-xl">
        <div class="modal-header">
          <div>
            <h3>审核用户申请</h3>
            <p class="panel-subtitle">{{ requestModal.user?.student_id }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeRequestModal">关闭</button>
        </div>
        <div class="modal-body">
          <div v-if="requestModal.loading" class="empty-state">加载中...</div>
          <div v-else-if="requestModal.items.length === 0" class="empty-state">当前没有待审核申请。</div>
          <div v-else class="request-stack">
            <article v-for="item in requestModal.items" :key="item.id" class="request-card">
              <div class="request-card-head">
                <div>
                  <strong>#{{ item.id }} {{ typeLabel(item.request_type) }}</strong>
                  <div class="muted-line">{{ formatTime(item.created_at) }}</div>
                </div>
                <span class="badge warn">{{ statusLabel(item.status) }}</span>
              </div>
              <p class="request-note">{{ item.request_note || '未填写备注' }}</p>
              <div class="request-card-foot">
                <span class="muted-line">{{ item.file_name || '无附加文件' }}</span>
                <div class="inline-stack">
                  <button class="ghost-button compact-button" type="button" @click="openRequestReviewModal(item, 'approved')">
                    批准
                  </button>
                  <button class="ghost-button compact-button danger-outline" type="button" @click="openRequestReviewModal(item, 'rejected')">
                    驳回
                  </button>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>
    </div>

    <div v-if="requestReviewModal.visible" class="modal-mask" @click.self="closeRequestReviewModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>{{ requestReviewModal.action === 'approved' ? '批准申请' : '驳回申请' }}</h3>
            <p class="panel-subtitle">#{{ requestReviewModal.item?.id }} {{ requestReviewModal.item ? typeLabel(requestReviewModal.item.request_type) : '' }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeRequestReviewModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>审核备注</span>
            <textarea v-model.trim="requestReviewModal.reviewNote" rows="4" placeholder="填写审核说明"></textarea>
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeRequestReviewModal">取消</button>
          <button class="primary-button" type="button" :disabled="requestReviewModal.saving" @click="submitRequestReview">
            {{ requestReviewModal.saving ? '提交中...' : '提交审核' }}
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
import {
  adminAssignUserGroup,
  adminListGroups,
  adminListUserRequests,
  adminListUsers,
  adminReviewUserRequest,
  adminTriggerBatchBlogCrawl,
  adminTriggerUserBlogCrawl,
  adminUpdateUserBlogProfile,
  adminUpdateUserBasicProfile,
  adminUpdateUserRole,
} from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const users = ref([]);
const groups = ref([]);
const loading = ref(false);
const savingId = ref(null);
const crawlingId = ref(null);
const batchCrawling = ref(false);
const selectedCrawlUserIds = ref([]);
const localError = ref('');
const successMessage = ref('');

const filters = ref({
  keyword: '',
  role: 'all',
  groupId: 'all',
  blogConfig: 'all',
});

const roleModal = ref({
  visible: false,
  user: null,
  nextRole: 'user',
});

const basicProfileModal = ref({
  visible: false,
  user: null,
  realName: '',
  saving: false,
});

const groupModal = ref({
  visible: false,
  user: null,
  groupId: '',
  saving: false,
});

const blogModal = ref({
  visible: false,
  user: null,
  blogHomeUrl: '',
  saving: false,
});

const requestModal = ref({
  visible: false,
  user: null,
  items: [],
  loading: false,
});

const requestReviewModal = ref({
  visible: false,
  item: null,
  action: 'approved',
  reviewNote: '',
  saving: false,
});

const errorMessage = computed(() => localError.value);
const selectedCrawlUserIdSet = computed(() => new Set(selectedCrawlUserIds.value));
const groupedUserCount = computed(() => users.value.filter(item => item.group_id).length);
const blogConfiguredCount = computed(() => users.value.filter(item => item.blog_home_url).length);

const filteredUsers = computed(() => {
  const keyword = filters.value.keyword.toLowerCase();
  return users.value.filter(item => {
    if (filters.value.role !== 'all' && String(item.role || '').toLowerCase() !== filters.value.role) return false;

    if (filters.value.groupId === 'ungrouped' && item.group_id) return false;
    if (filters.value.groupId !== 'all' && filters.value.groupId !== 'ungrouped' && String(item.group_id || '') !== filters.value.groupId) return false;

    if (filters.value.blogConfig === 'configured' && !item.blog_home_url) return false;
    if (filters.value.blogConfig === 'missing' && item.blog_home_url) return false;

    if (!keyword) return true;
    const text = `${item.student_id} ${item.display_name || ''} ${item.project_title || ''} ${item.blog_home_url || ''} ${item.group_name || ''} ${item.group_number || ''} ${item.group_leader_name || ''} ${item.group_project_title || ''}`.toLowerCase();
    return text.includes(keyword);
  });
});

const visibleSelectableUsers = computed(() => filteredUsers.value.filter(item => Boolean(item.blog_home_url)));
const selectedCrawlUsers = computed(() => visibleSelectableUsers.value.filter(item => selectedCrawlUserIdSet.value.has(item.id)));
const allVisibleSelectableChecked = computed(() => visibleSelectableUsers.value.length > 0 && selectedCrawlUsers.value.length === visibleSelectableUsers.value.length);
const someVisibleSelectableChecked = computed(() => selectedCrawlUsers.value.length > 0);

function roleLabel(role) {
  const value = String(role || '').toLowerCase();
  if (value === 'admin') return '管理员';
  if (value === 'teacher') return '老师';
  return '学生';
}

function crawlStatusLabel(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'queued') return '排队中';
  if (v === 'running') return '抓取中';
  if (v === 'success') return '成功';
  if (v === 'partial_success') return '部分失败';
  if (v === 'failed') return '失败';
  return '空闲';
}

function crawlStatusColor(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'queued') return '#7c3aed';
  if (v === 'running') return '#2563eb';
  if (v === 'success') return '#16a34a';
  if (v === 'partial_success') return '#d97706';
  if (v === 'failed') return '#ef4444';
  return 'var(--text-secondary)';
}

function typeLabel(value) {
  return value === 'signature_update' ? '签名变更' : '申请书重传';
}

function statusLabel(value) {
  if (value === 'approved') return '已批准';
  if (value === 'rejected') return '已驳回';
  return '待审核';
}

function formatTime(value) {
  if (!value) return '未执行';
  const dt = new Date(value);
  return Number.isNaN(dt.getTime()) ? String(value) : dt.toLocaleString();
}

function isRootAdmin(user) {
  return Boolean(user?.is_root_admin);
}

function isMe(user) {
  return Number(user?.id || 0) === Number(authStore.user?.id || 0);
}

function blogTotal(user) {
  return Number(user?.blog?.normal || 0) + Number(user?.blog?.abnormal || 0);
}

function goBack() {
  router.push({ name: 'profile' });
}

function goRequests() {
  router.push({ name: 'admin-requests' });
}

function goBlogRuns() {
  router.push({ name: 'admin-blog-runs' });
}

function goSubmissionsDashboard() {
  router.push({ name: 'admin-submissions' });
}

function goBlogOverview() {
  router.push({ name: 'admin-blog-overview' });
}

function goGroups() {
  router.push({ name: 'admin-groups' });
}

function goDocuments(user, type) {
  router.push({ name: 'admin-user-documents', params: { userId: String(user.id), type } });
}

function goBlogs(user) {
  router.push({ name: 'admin-user-blogs', params: { userId: String(user.id) } });
}

async function loadUsers() {
  localError.value = '';
  loading.value = true;
  try {
    const [userList, groupList] = await Promise.all([
      adminListUsers(authStore.token),
      adminListGroups(authStore.token),
    ]);
    users.value = Array.isArray(userList) ? userList : [];
    groups.value = Array.isArray(groupList) ? groupList : [];
    const validIds = new Set(users.value.filter(item => item.blog_home_url).map(item => item.id));
    selectedCrawlUserIds.value = selectedCrawlUserIds.value.filter(id => validIds.has(id));
  } catch (e) {
    localError.value = e?.message || '加载失败';
    users.value = [];
  } finally {
    loading.value = false;
  }
}

function toggleSelectedUser(userId, checked) {
  const next = new Set(selectedCrawlUserIds.value);
  if (checked) next.add(userId);
  else next.delete(userId);
  selectedCrawlUserIds.value = Array.from(next);
}

function toggleVisibleSelectable(checked) {
  const next = new Set(selectedCrawlUserIds.value);
  visibleSelectableUsers.value.forEach(item => {
    if (checked) next.add(item.id);
    else next.delete(item.id);
  });
  selectedCrawlUserIds.value = Array.from(next);
}

function openRoleModal(user) {
  if (isRootAdmin(user)) return;
  roleModal.value = {
    visible: true,
    user,
    nextRole: String(user?.role || '').toLowerCase() === 'admin' ? 'user' : 'admin',
  };
}

function closeRoleModal() {
  roleModal.value = { visible: false, user: null, nextRole: 'user' };
}

function openBasicProfileModal(user) {
  basicProfileModal.value = {
    visible: true,
    user,
    realName: user?.display_name || '',
    saving: false,
  };
}

function closeBasicProfileModal() {
  basicProfileModal.value = {
    visible: false,
    user: null,
    realName: '',
    saving: false,
  };
}

async function submitBasicProfileChange() {
  const user = basicProfileModal.value.user;
  if (!user) return;
  basicProfileModal.value.saving = true;
  localError.value = '';
  try {
    const updated = await adminUpdateUserBasicProfile(authStore.token, user.id, {
      real_name: basicProfileModal.value.realName,
    });
    users.value = users.value.map(item => (item.id === user.id ? updated : item));
    closeBasicProfileModal();
  } catch (e) {
    localError.value = e?.message || '更新用户资料失败';
  } finally {
    basicProfileModal.value.saving = false;
  }
}

async function submitRoleChange() {
  const user = roleModal.value.user;
  if (!user) return;
  savingId.value = user.id;
  try {
    const resp = await adminUpdateUserRole(authStore.token, user.id, roleModal.value.nextRole);
    users.value = users.value.map(item => (item.id === user.id ? { ...item, role: resp?.role || roleModal.value.nextRole } : item));
    closeRoleModal();
  } catch (e) {
    localError.value = e?.message || '修改失败';
  } finally {
    savingId.value = null;
  }
}

function openGroupModal(user) {
  groupModal.value = {
    visible: true,
    user,
    groupId: user?.group_id ? String(user.group_id) : '',
    saving: false,
  };
}

function closeGroupModal() {
  groupModal.value = {
    visible: false,
    user: null,
    groupId: '',
    saving: false,
  };
}

async function submitGroupChange() {
  const user = groupModal.value.user;
  if (!user) return;
  groupModal.value.saving = true;
  try {
    await adminAssignUserGroup(authStore.token, user.id, groupModal.value.groupId ? Number(groupModal.value.groupId) : null);
    await loadUsers();
    closeGroupModal();
  } catch (e) {
    localError.value = e?.message || '分组分配失败';
  } finally {
    groupModal.value.saving = false;
  }
}

function openBlogModal(user) {
  blogModal.value = {
    visible: true,
    user,
    blogHomeUrl: user?.blog_home_url || '',
    saving: false,
  };
}

function closeBlogModal() {
  blogModal.value = {
    visible: false,
    user: null,
    blogHomeUrl: '',
    saving: false,
  };
}

async function submitBlogProfile() {
  const user = blogModal.value.user;
  if (!user) return;
  blogModal.value.saving = true;
  try {
    await adminUpdateUserBlogProfile(authStore.token, user.id, {
      blog_home_url: blogModal.value.blogHomeUrl.trim(),
      blog_enabled: true,
    });
    await loadUsers();
    closeBlogModal();
  } catch (e) {
    localError.value = e?.message || '更新博客地址失败';
  } finally {
    blogModal.value.saving = false;
  }
}

async function openRequestModal(user) {
  requestModal.value = {
    visible: true,
    user,
    items: [],
    loading: true,
  };
  try {
    const list = await adminListUserRequests(authStore.token, user.id);
    requestModal.value.items = (Array.isArray(list) ? list : []).filter(item => item.status === 'pending');
  } catch (e) {
    localError.value = e?.message || '加载申请失败';
    requestModal.value.items = [];
  } finally {
    requestModal.value.loading = false;
  }
}

function closeRequestModal() {
  requestModal.value = {
    visible: false,
    user: null,
    items: [],
    loading: false,
  };
}

function openRequestReviewModal(item, action) {
  requestReviewModal.value = {
    visible: true,
    item,
    action,
    reviewNote: action === 'approved' ? 'approved by admin' : 'rejected by admin',
    saving: false,
  };
}

function closeRequestReviewModal() {
  requestReviewModal.value = {
    visible: false,
    item: null,
    action: 'approved',
    reviewNote: '',
    saving: false,
  };
}

async function submitRequestReview() {
  const item = requestReviewModal.value.item;
  if (!item) return;
  requestReviewModal.value.saving = true;
  try {
    await adminReviewUserRequest(authStore.token, item.user_id, item.id, {
      status: requestReviewModal.value.action,
      review_note: requestReviewModal.value.reviewNote,
    });
    await loadUsers();
    if (requestModal.value.user?.id === item.user_id) {
      await openRequestModal(requestModal.value.user);
    }
    closeRequestReviewModal();
  } catch (e) {
    localError.value = e?.message || '审核申请失败';
  } finally {
    requestReviewModal.value.saving = false;
  }
}

async function crawlBlogs(user) {
  successMessage.value = '';
  if (!user?.blog_home_url) {
    localError.value = '该用户未配置博客主页地址';
    return;
  }
  crawlingId.value = user.id;
  try {
    await adminTriggerUserBlogCrawl(authStore.token, user.id);
    localError.value = '';
    successMessage.value = '已加入后台抓取队列，可在博客抓取记录中查看进度。';
    await loadUsers();
  } catch (e) {
    localError.value = e?.message || '抓取失败';
  } finally {
    crawlingId.value = null;
  }
}

async function crawlSelectedUsers() {
  if (!selectedCrawlUsers.value.length) return;
  successMessage.value = '';
  batchCrawling.value = true;
  localError.value = '';
  try {
    const runs = await adminTriggerBatchBlogCrawl(authStore.token, selectedCrawlUsers.value.map(item => item.id));
    successMessage.value = `已加入后台抓取队列：${runs?.length || 0} 个用户，可在博客抓取记录中查看进度。`;
    await loadUsers();
  } catch (e) {
    localError.value = e?.message || '批量抓取失败';
  } finally {
    batchCrawling.value = false;
  }
}

onMounted(() => {
  loadUsers();
});
</script>

<style scoped>
.admin-shell {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 16px;
}

.admin-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  flex-wrap: wrap;
  padding: 24px 26px;
  border: 1px solid var(--border);
  border-radius: 28px;
  background:
    radial-gradient(circle at top right, rgba(251, 191, 36, 0.28), transparent 30%),
    linear-gradient(135deg, #fffaf0 0%, #ffffff 46%, #eef6ff 100%);
}

.theme-dark .admin-hero {
  background:
    radial-gradient(circle at top right, rgba(251, 191, 36, 0.12), transparent 30%),
    linear-gradient(135deg, var(--surface) 0%, rgba(17, 27, 45, 0.92) 60%, rgba(106, 160, 255, 0.08) 100%);
}

.hero-eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #c2410c;
}

.theme-dark .hero-eyebrow {
  color: var(--badge-warn-text);
}

.admin-hero h2 {
  margin: 0;
  font-size: 32px;
  line-height: 1.15;
}

.hero-copy {
  margin: 10px 0 0;
  max-width: 720px;
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
  border: 1px solid var(--border);
  border-radius: 22px;
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
  font-size: 30px;
  line-height: 1;
}

.filter-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  vertical-align: top;
  border-bottom: 1px solid var(--border);
}

.strong-line {
  font-weight: 800;
}

.muted-line {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-secondary);
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

.blog-cell {
  display: grid;
  gap: 8px;
}

.truncate-block {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  word-break: break-all;
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

.modal-card-wide {
  width: min(760px, 100%);
}

.modal-card-xl {
  width: min(920px, 100%);
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

.request-stack {
  display: grid;
  gap: 12px;
}

.request-card {
  padding: 16px;
  border-radius: 18px;
  border: 1px solid var(--border);
  background: var(--surface-soft);
}

.request-card-head,
.request-card-foot {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.request-note {
  margin: 12px 0;
  line-height: 1.7;
}

@media (max-width: 1100px) {
  .stats-grid,
  .filter-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .stats-grid,
  .filter-grid {
    grid-template-columns: 1fr;
  }

  .admin-hero h2 {
    font-size: 26px;
  }
}
</style>
