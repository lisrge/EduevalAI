<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div class="group-shell">
      <section class="group-hero">
        <div>
          <p class="hero-eyebrow">分组管理</p>
          <h2>分组与成员管理</h2>
          <p class="hero-copy">
            分组列表只展示组长与项目标题。点击“查看详情”后，再查看该组成员并对成员进行改组。
          </p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" @click="goBack">返回</button>
        </div>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="stats-grid">
        <article class="stat-card">
          <span>已建分组</span>
          <strong>{{ groups.length }}</strong>
        </article>
        <article class="stat-card">
          <span>已配置组长</span>
          <strong>{{ groups.filter(item => item.leader_name).length }}</strong>
        </article>
        <article class="stat-card">
          <span>已分组用户</span>
          <strong>{{ groupedUsers.length }}</strong>
        </article>
        <article class="stat-card">
          <span>未分组用户</span>
          <strong>{{ ungroupedUsers.length }}</strong>
        </article>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">初始化与创建</h3>
            <p class="panel-subtitle">可一键补齐 1-86 组，也可单独创建某个组号。</p>
          </div>
          <div class="inline-stack">
            <button class="ghost-button" type="button" :disabled="bootstrapping" @click="bootstrapGroups">
              {{ bootstrapping ? '初始化中...' : '补齐 1-86 组' }}
            </button>
            <button class="ghost-button" type="button" :disabled="loading" @click="loadData">刷新</button>
          </div>
        </div>
        <div class="edueval-panel-body create-grid">
          <label class="field">
            <span>组号</span>
            <input v-model.number="form.group_number" type="number" min="1" max="200" />
          </label>
          <label class="field">
            <span>组长学号</span>
            <input v-model.trim="form.leader_student_id" type="text" placeholder="可留空，后续再设置" />
          </label>
          <label class="field">
            <span>说明</span>
            <input v-model.trim="form.description" type="text" placeholder="可选说明" />
          </label>
        </div>
        <div class="edueval-panel-body" style="padding-top: 0;">
          <div class="form-actions" style="justify-content: flex-end;">
            <button class="primary-button" type="button" :disabled="saving" @click="createGroup">
              {{ saving ? '创建中...' : '创建分组' }}
            </button>
          </div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">分组列表</h3>
            <p class="panel-subtitle">列表只展示组长和对应项目标题，成员在详情中查看。</p>
          </div>
          <div class="panel-subtitle">当前共 {{ groups.length }} 个组</div>
        </div>
        <div class="edueval-panel-body table-wrap">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="groups.length === 0" class="empty-state">暂无分组。</div>
          <table v-else class="admin-table">
            <thead>
              <tr>
                <th>组号</th>
                <th>显示名称</th>
                <th>组长姓名</th>
                <th>项目标题</th>
                <th>成员数</th>
                <th>说明</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="group in groups" :key="group.id">
                <td><strong>第 {{ group.group_number }} 组</strong></td>
                <td>{{ group.name }}</td>
                <td>{{ group.leader_name || '-' }}</td>
                <td class="wrap-cell">{{ group.leader_project_title || '-' }}</td>
                <td>{{ group.member_count }}</td>
                <td>{{ group.description || '-' }}</td>
                <td>
                  <div class="inline-stack">
                    <button class="ghost-button compact-button" type="button" @click="openGroupDetailModal(group)">
                      查看详情
                    </button>
                    <button class="ghost-button compact-button" type="button" @click="openEditModal(group)">
                      编辑
                    </button>
                    <button
                      class="ghost-button compact-button danger-button"
                      type="button"
                      :disabled="deletingGroupId === group.id"
                      @click="deleteGroup(group)"
                    >
                      {{ deletingGroupId === group.id ? '删除中...' : '删除' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <div>
            <h3 style="margin: 0;">未分组用户</h3>
            <p class="panel-subtitle">点击用户后可在弹窗中查看姓名、当前组和组项目标题，并直接改组。</p>
          </div>
          <div class="panel-subtitle">共 {{ ungroupedUsers.length }} 人</div>
        </div>
        <div class="edueval-panel-body">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="ungroupedUsers.length === 0" class="empty-state">当前没有未分组用户。</div>
          <div v-else class="member-list">
            <button
              v-for="user in ungroupedUsers"
              :key="user.id"
              class="member-chip"
              type="button"
              @click="openUserModal(user)"
            >
              {{ user.display_name || user.student_id }}
            </button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="editModal.visible" class="modal-mask" @click.self="closeEditModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>编辑第 {{ editModal.group?.group_number }} 组</h3>
            <p class="panel-subtitle">{{ editModal.group?.name }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeEditModal">关闭</button>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>组长学号</span>
            <input v-model.trim="editModal.leader_student_id" type="text" placeholder="留空表示清空组长" />
          </label>
          <label class="field">
            <span>说明</span>
            <textarea v-model.trim="editModal.description" rows="4" placeholder="填写该组说明"></textarea>
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeEditModal">取消</button>
          <button class="primary-button" type="button" :disabled="editModal.saving" @click="submitEditGroup">
            {{ editModal.saving ? '保存中...' : '保存修改' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="detailModal.visible" class="modal-mask" @click.self="closeGroupDetailModal">
      <div class="modal-card detail-modal">
        <div class="modal-header">
          <div>
            <h3>{{ detailModal.group?.name }}</h3>
            <p class="panel-subtitle">
              组长：{{ detailModal.group?.leader_name || '未设置' }}｜
              项目：{{ detailModal.group?.leader_project_title || '未设置' }}
            </p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeGroupDetailModal">关闭</button>
        </div>
        <div v-if="detailMembers.length === 0" class="empty-state">该组当前没有成员。</div>
        <div v-else class="detail-member-grid">
          <button
            v-for="member in detailMembers"
            :key="member.id"
            class="detail-member-card"
            type="button"
            @click="openUserModal(member)"
          >
            <strong>{{ member.display_name || member.student_id }}</strong>
            <span>{{ member.student_id }}</span>
            <span class="wrap-cell">{{ member.project_title || '未填写项目标题' }}</span>
          </button>
        </div>
      </div>
    </div>

    <div v-if="userModal.visible" class="modal-mask" @click.self="closeUserModal">
      <div class="modal-card">
        <div class="modal-header">
          <div>
            <h3>用户信息</h3>
            <p class="panel-subtitle">{{ userModal.user?.display_name || userModal.user?.student_id || '-' }}</p>
          </div>
          <button class="ghost-button compact-button" type="button" @click="closeUserModal">关闭</button>
        </div>
        <div class="detail-grid" v-if="userModal.user">
          <div class="detail-item">
            <span>姓名</span>
            <strong>{{ userModal.user.display_name || '-' }}</strong>
          </div>
          <div class="detail-item">
            <span>学号</span>
            <strong>{{ userModal.user.student_id }}</strong>
          </div>
          <div class="detail-item">
            <span>角色</span>
            <strong>{{ roleLabel(userModal.user.role) }}</strong>
          </div>
          <div class="detail-item">
            <span>所在分组</span>
            <strong>{{ userModal.user.group_name || '未分组' }}</strong>
          </div>
          <div class="detail-item">
            <span>组项目标题</span>
            <strong class="wrap-cell">{{ userModal.user.group_project_title || '未设置' }}</strong>
          </div>
          <div class="detail-item">
            <span>个人项目标题</span>
            <strong class="wrap-cell">{{ userModal.user.project_title || '未填写' }}</strong>
          </div>
        </div>
        <div class="modal-body">
          <label class="field">
            <span>调整所属分组</span>
            <select v-model="userModal.groupId">
              <option value="">未分组</option>
              <option v-for="group in groups" :key="group.id" :value="String(group.id)">
                {{ group.name }}
              </option>
            </select>
          </label>
        </div>
        <div class="modal-actions">
          <button class="ghost-button" type="button" @click="closeUserModal">取消</button>
          <button class="primary-button" type="button" :disabled="userModal.saving" @click="submitAssignUserGroup">
            {{ userModal.saving ? '保存中...' : '保存分组' }}
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
  adminBootstrapGroups,
  adminCreateGroup,
  adminDeleteGroup,
  adminListGroups,
  adminListUsers,
  adminUpdateGroup,
} from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const groups = ref([]);
const users = ref([]);
const loading = ref(false);
const saving = ref(false);
const bootstrapping = ref(false);
const deletingGroupId = ref(null);
const localError = ref('');
const form = ref({ group_number: 1, leader_student_id: '', description: '' });
const editModal = ref({
  visible: false,
  group: null,
  leader_student_id: '',
  description: '',
  saving: false,
});
const detailModal = ref({
  visible: false,
  group: null,
});
const userModal = ref({
  visible: false,
  user: null,
  groupId: '',
  saving: false,
});

const errorMessage = computed(() => localError.value);
const groupedUsers = computed(() => users.value.filter(item => item.group_id));
const ungroupedUsers = computed(() => users.value.filter(item => !item.group_id));
const userById = computed(() => {
  const mapping = new Map();
  users.value.forEach((item) => mapping.set(item.id, item));
  return mapping;
});
const detailMembers = computed(() => {
  if (!detailModal.value.group) return [];
  return users.value.filter(item => item.group_id === detailModal.value.group.id);
});

function goBack() {
  router.push({ name: 'admin-users' });
}

function roleLabel(role) {
  return role === 'admin' ? '管理员' : '普通用户';
}

function getLeaderStudentId(group) {
  if (!group?.leader_user_id) return '';
  return userById.value.get(group.leader_user_id)?.student_id || '';
}

async function loadData() {
  loading.value = true;
  localError.value = '';
  try {
    const [groupList, userList] = await Promise.all([
      adminListGroups(authStore.token),
      adminListUsers(authStore.token),
    ]);
    groups.value = Array.isArray(groupList) ? groupList : [];
    users.value = Array.isArray(userList) ? userList : [];
  } catch (e) {
    localError.value = e?.message || '加载分组信息失败';
    groups.value = [];
    users.value = [];
  } finally {
    loading.value = false;
  }
}

async function bootstrapGroups() {
  bootstrapping.value = true;
  localError.value = '';
  try {
    await adminBootstrapGroups(authStore.token, 86);
    await loadData();
  } catch (e) {
    localError.value = e?.message || '初始化分组失败';
  } finally {
    bootstrapping.value = false;
  }
}

async function createGroup() {
  saving.value = true;
  localError.value = '';
  try {
    await adminCreateGroup(authStore.token, form.value);
    form.value = { group_number: 1, leader_student_id: '', description: '' };
    await loadData();
  } catch (e) {
    localError.value = e?.message || '创建分组失败';
  } finally {
    saving.value = false;
  }
}

function openEditModal(group) {
  editModal.value = {
    visible: true,
    group,
    leader_student_id: getLeaderStudentId(group),
    description: group.description || '',
    saving: false,
  };
}

function closeEditModal() {
  editModal.value = {
    visible: false,
    group: null,
    leader_student_id: '',
    description: '',
    saving: false,
  };
}

async function submitEditGroup() {
  const group = editModal.value.group;
  if (!group) return;
  editModal.value.saving = true;
  localError.value = '';
  try {
    await adminUpdateGroup(authStore.token, group.id, {
      leader_student_id: editModal.value.leader_student_id,
      description: editModal.value.description,
    });
    await loadData();
    closeEditModal();
  } catch (e) {
    localError.value = e?.message || '更新分组失败';
  } finally {
    editModal.value.saving = false;
  }
}

function openGroupDetailModal(group) {
  detailModal.value = {
    visible: true,
    group,
  };
}

function closeGroupDetailModal() {
  detailModal.value = {
    visible: false,
    group: null,
  };
}

async function deleteGroup(group) {
  if (!group) return;
  const ok = window.confirm(`确认删除 ${group.name} 吗？该组下用户会被设为未分组。`);
  if (!ok) return;
  deletingGroupId.value = group.id;
  localError.value = '';
  try {
    await adminDeleteGroup(authStore.token, group.id);
    await loadData();
    if (detailModal.value.group?.id === group.id) closeGroupDetailModal();
    if (userModal.value.user?.group_id === group.id) closeUserModal();
  } catch (e) {
    localError.value = e?.message || '删除分组失败';
  } finally {
    deletingGroupId.value = null;
  }
}

function openUserModal(user) {
  userModal.value = {
    visible: true,
    user,
    groupId: user.group_id ? String(user.group_id) : '',
    saving: false,
  };
}

function closeUserModal() {
  userModal.value = {
    visible: false,
    user: null,
    groupId: '',
    saving: false,
  };
}

async function submitAssignUserGroup() {
  const user = userModal.value.user;
  if (!user) return;
  userModal.value.saving = true;
  localError.value = '';
  try {
    const groupId = userModal.value.groupId ? Number(userModal.value.groupId) : null;
    await adminAssignUserGroup(authStore.token, user.id, groupId);
    await loadData();
    const nextUser = users.value.find(item => item.id === user.id);
    if (nextUser) {
      openUserModal(nextUser);
    } else {
      closeUserModal();
    }
  } catch (e) {
    localError.value = e?.message || '调整用户分组失败';
  } finally {
    userModal.value.saving = false;
  }
}

onMounted(() => {
  loadData();
});
</script>

<style scoped>
.group-shell {
  padding: 20px;
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 16px;
}

.group-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 24px 26px;
  border-radius: 28px;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.18), transparent 28%),
    linear-gradient(135deg, #eff6ff 0%, #fff 44%, #f8fafc 100%);
}

.theme-dark .group-hero {
  background:
    radial-gradient(circle at top right, rgba(106, 160, 255, 0.12), transparent 28%),
    linear-gradient(135deg, var(--surface) 0%, rgba(17, 27, 45, 0.92) 60%, rgba(106, 160, 255, 0.08) 100%);
}

.hero-eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #1d4ed8;
}

.theme-dark .hero-eyebrow {
  color: var(--badge-info-text);
}

.group-hero h2 {
  margin: 0;
  font-size: 32px;
}

.hero-copy {
  margin: 10px 0 0;
  max-width: 760px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.hero-actions,
.inline-stack,
.member-list {
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
  font-size: 30px;
}

.create-grid {
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

.wrap-cell {
  white-space: normal;
  line-height: 1.6;
}

.compact-button {
  width: auto;
  padding: 6px 10px;
}

.member-chip,
.detail-member-card {
  border: 1px solid var(--border);
  background: var(--badge-info-bg);
  color: var(--badge-info-text);
  border-radius: 18px;
  padding: 10px 12px;
}

.detail-member-card {
  display: grid;
  gap: 6px;
  text-align: left;
}

.danger-button {
  color: var(--danger);
  border-color: var(--danger);
  background: var(--danger-bg);
}

.muted-line {
  color: var(--text-secondary);
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
  width: min(760px, 100%);
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

.detail-modal {
  width: min(860px, 100%);
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

.detail-grid,
.detail-member-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-item {
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid var(--border);
  background: var(--alert-bg);
}

.detail-item span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
}

.detail-item strong {
  display: block;
  margin-top: 6px;
}

@media (max-width: 980px) {
  .stats-grid,
  .create-grid,
  .detail-grid,
  .detail-member-grid {
    grid-template-columns: 1fr;
  }

  .group-hero h2 {
    font-size: 26px;
  }
}
</style>
