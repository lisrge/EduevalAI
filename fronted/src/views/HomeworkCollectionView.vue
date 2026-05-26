<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">作业提交</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">选择作业 → 填写小组信息与成员陈述 → 上传材料 → 提交。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="reloadAll">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </div>

      <div v-if="errorMessage" class="panel" style="padding: 14px; color: #b91c1c;">
        {{ errorMessage }}
      </div>
      <div v-if="message" class="panel" style="padding: 14px; color: #166534;">
        {{ message }}
      </div>

      <div style="min-height: 0; display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 14px;">
        <section class="panel" style="min-height: 0;">
          <div class="panel-header">
            <div>
              <h3 style="margin: 0;">作业列表</h3>
              <p class="panel-subtitle">请选择要提交的作业。</p>
            </div>
          </div>
          <div class="edueval-panel-body" style="overflow: auto;">
            <div v-if="loading && assignments.length === 0" class="empty-state">加载中...</div>
            <div v-else-if="assignments.length === 0" class="empty-state">暂无作业。</div>
            <button
              v-for="item in assignments"
              :key="item.id"
              type="button"
              class="panel"
              style="width: 100%; text-align: left; padding: 12px; margin-bottom: 10px; border-radius: 16px; cursor: pointer;"
              :disabled="loading"
              @click="selectAssignment(item)"
            >
              <div style="display: flex; justify-content: space-between; gap: 10px;">
                <div>
                  <div style="font-weight: 800;">{{ item.course.name }} · 第{{ item.week_index }}周</div>
                  <div>{{ item.title }}</div>
                  <div class="panel-subtitle" style="margin-top: 6px;">
                    我的状态：{{ item.my_submission_status || '未创建' }} / {{ item.my_completeness_status || '-' }}
                  </div>
                </div>
                <div class="panel-subtitle">
                  {{ requiredLabel(item.required_asset_types) }}
                </div>
              </div>
            </button>
          </div>
        </section>

        <section class="panel" style="min-height: 0;">
          <div class="panel-header" style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; flex-wrap: wrap;">
            <div>
              <h3 style="margin: 0;">提交详情</h3>
              <p class="panel-subtitle" v-if="activeAssignment">
                {{ activeAssignment.course.name }} · 第{{ activeAssignment.week_index }}周 · {{ activeAssignment.title }}
              </p>
            </div>
            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
              <button class="primary-button" type="button" style="width: auto;" :disabled="saving || !activeAssignment" @click="saveDraft">
                {{ saving ? '保存中...' : '保存草稿' }}
              </button>
              <button class="ghost-button" type="button" style="width: auto;" :disabled="finalizing || !submission" @click="finalize">
                {{ finalizing ? '提交中...' : '提交作业' }}
              </button>
            </div>
          </div>

          <div class="edueval-panel-body" style="overflow: auto;">
            <div v-if="!activeAssignment" class="empty-state">先从左侧选择一个作业。</div>
            <div v-else-if="loadingSubmission" class="empty-state">加载提交信息...</div>
            <template v-else>
              <div class="panel" style="padding: 12px; display: grid; gap: 10px;">
                <div class="panel-subtitle">
                  状态：{{ submission?.status || '未创建' }} / {{ submission?.completeness_status || '-' }}
                </div>
                <div v-if="(submission?.missing_asset_types || []).length" class="panel-subtitle" style="color: #b45309;">
                  缺失：{{ submission.missing_asset_types.join('，') }}
                </div>

                <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px;">
                  <label class="field">
                    <span>姓名</span>
                    <input v-model.trim="form.student_name" class="edueval-input" type="text" placeholder="例如 张三" />
                  </label>
                  <label class="field">
                    <span>小组</span>
                    <input v-model.trim="form.group_name" class="edueval-input" type="text" placeholder="例如 第1组" />
                  </label>
                  <label class="field">
                    <span>项目名</span>
                    <input v-model.trim="form.project_name" class="edueval-input" type="text" placeholder="例如 智能批改平台" />
                  </label>
                </div>
              </div>

              <div class="panel" style="padding: 12px; display: grid; gap: 10px; margin-top: 12px;">
                <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
                  <div>
                    <div style="font-weight: 800;">成员与个人陈述</div>
                    <div class="panel-subtitle">每个成员都需要填写个人陈述，否则无法提交。</div>
                  </div>
                  <button class="ghost-button" type="button" style="width: auto;" @click="addMember">添加成员</button>
                </div>

                <div v-if="form.members.length === 0" class="panel-subtitle">暂无成员，请添加。</div>
                <div v-for="(m, idx) in form.members" :key="idx" class="panel" style="padding: 12px; display: grid; gap: 10px;">
                  <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;">
                    <strong>成员 {{ idx + 1 }}</strong>
                    <button class="ghost-button danger-outline" type="button" style="width: auto;" :disabled="form.members.length <= 1" @click="removeMember(idx)">
                      删除
                    </button>
                  </div>
                  <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px;">
                    <label class="field">
                      <span>学号</span>
                      <input v-model.trim="m.student_id" class="edueval-input" type="text" placeholder="12位学号" />
                    </label>
                    <label class="field">
                      <span>姓名</span>
                      <input v-model.trim="m.student_name" class="edueval-input" type="text" placeholder="姓名" />
                    </label>
                    <label class="field">
                      <span>角色</span>
                      <input v-model.trim="m.project_role" class="edueval-input" type="text" placeholder="例如 后端/前端/组长" />
                    </label>
                  </div>
                  <label class="field">
                    <span>个人陈述</span>
                    <textarea v-model="m.personal_statement" class="edueval-input" rows="4" placeholder="描述本周/本阶段你做了什么、贡献点是什么。"></textarea>
                  </label>
                </div>
              </div>

              <div class="panel" style="padding: 12px; display: grid; gap: 10px; margin-top: 12px;">
                <div style="font-weight: 800;">材料上传</div>
                <div class="panel-subtitle">按作业要求上传对应材料。</div>

                <div v-if="(activeAssignment?.required_asset_types || []).length === 0" class="panel" style="padding: 12px; display: grid; gap: 10px;">
                  <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <strong>任意文件上传</strong>
                    <input type="file" :disabled="Boolean(uploadingType) && uploadingType === anyAssetType" @change="onUpload(anyAssetType, $event)" />
                  </div>
                  <div style="display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 10px; align-items: end;">
                    <label class="field">
                      <span>材料类型</span>
                      <input v-model.trim="anyAssetType" class="edueval-input" type="text" placeholder="例如 report / code_archive / ppt / video / attachment" />
                    </label>
                    <div class="panel-subtitle">材料类型用于区分版本，同类型多次上传会形成 v1/v2…</div>
                  </div>
                  <div v-if="(submission?.assets || []).length" class="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th style="width: 18%;">类型</th>
                          <th style="width: 52%;">文件</th>
                          <th style="width: 30%;">上传时间</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="asset in submission.assets" :key="asset.id">
                          <td>{{ asset.asset_type }}</td>
                          <td>
                            <a :href="asset.download_url" target="_blank" rel="noreferrer">{{ asset.file_name }}</a>
                          </td>
                          <td>{{ new Date(asset.created_at).toLocaleString() }}</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-else class="panel-subtitle">当前：未上传</div>
                </div>

                <div v-for="assetType in activeAssignment?.required_asset_types || []" :key="assetType" class="panel" style="padding: 12px; display: grid; gap: 10px;">
                  <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <strong>{{ assetTypeLabel(assetType) }}</strong>
                    <input type="file" :disabled="Boolean(uploadingType) && uploadingType === assetType" @change="onUpload(assetType, $event)" />
                  </div>
                  <div class="panel-subtitle" v-if="submission?.latest_assets?.[assetType]">
                    当前：<a :href="submission.latest_assets[assetType].download_url" target="_blank" rel="noreferrer">{{ submission.latest_assets[assetType].file_name }}</a>
                  </div>
                  <div class="panel-subtitle" v-else>当前：未上传</div>
                </div>
              </div>
            </template>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { useAuthStore } from '../stores/authStore';
import { fetchAssignments, fetchMyAssignmentSubmission, finalizeSubmission, uploadSubmissionAsset, upsertAssignmentSubmission } from '../services/eduevalApi';

const router = useRouter();
const authStore = useAuthStore();

const assignments = ref([]);
const activeAssignmentId = ref(null);
const activeAssignment = computed(() => assignments.value.find(item => Number(item.id) === Number(activeAssignmentId.value)) || null);
const submission = ref(null);
const form = ref({
  student_name: '',
  group_name: '',
  project_name: '',
  members: [],
});
const loading = ref(false);
const loadingSubmission = ref(false);
const saving = ref(false);
const finalizing = ref(false);
const uploadingType = ref('');
const anyAssetType = ref('attachment');
const errorMessage = ref('');
const message = ref('');

function goBack() {
  router.push({ name: authStore.isAdmin ? 'admin-users' : 'applications' });
}

function assetTypeLabel(assetType) {
  const v = String(assetType || '').toLowerCase();
  if (v === 'report') return '报告（report）';
  if (v === 'code_archive') return '代码压缩包（code_archive）';
  if (v === 'ppt') return 'PPT（ppt）';
  if (v === 'video') return '演示视频（video）';
  return String(assetType || '');
}

function requiredLabel(types) {
  const list = Array.isArray(types) ? types : [];
  if (list.length === 0) return '';
  return `必传：${list.map(assetTypeLabel).join('，')}`;
}

function applySubmissionToForm(payload) {
  const me = authStore.user || {};
  form.value = {
    student_name: payload?.student_name || me.real_name || me.student_id || '',
    group_name: payload?.group_name || '',
    project_name: payload?.project_name || '',
    members: Array.isArray(payload?.members) && payload.members.length > 0
      ? payload.members.map(item => ({
        student_id: String(item.student_id || ''),
        student_name: String(item.student_name || ''),
        project_role: item.project_role || '',
        personal_statement: item.personal_statement || '',
      }))
      : [
        {
          student_id: String(me.student_id || ''),
          student_name: String(me.real_name || me.student_id || ''),
          project_role: '',
          personal_statement: '',
        },
      ],
  };
}

function addMember() {
  form.value.members.push({ student_id: '', student_name: '', project_role: '', personal_statement: '' });
}

function removeMember(idx) {
  if (form.value.members.length <= 1) return;
  form.value.members.splice(idx, 1);
}

async function reloadAll() {
  loading.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const list = await fetchAssignments(authStore.token);
    assignments.value = Array.isArray(list) ? list : [];
    if (!activeAssignmentId.value && assignments.value.length > 0) {
      await selectAssignment(assignments.value[0]);
    }
  } catch (e) {
    assignments.value = [];
    errorMessage.value = e?.message || '加载作业失败';
  } finally {
    loading.value = false;
  }
}

async function loadSubmission(assignmentId) {
  loadingSubmission.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const data = await fetchMyAssignmentSubmission(authStore.token, assignmentId);
    submission.value = data || null;
    applySubmissionToForm(submission.value);
  } catch (e) {
    submission.value = null;
    errorMessage.value = e?.message || '加载提交信息失败';
  } finally {
    loadingSubmission.value = false;
  }
}

async function selectAssignment(item) {
  if (!item?.id) return;
  activeAssignmentId.value = Number(item.id);
  await loadSubmission(activeAssignmentId.value);
}

async function saveDraft() {
  const assignmentId = activeAssignmentId.value;
  if (!assignmentId) return;
  saving.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const payload = {
      student_name: form.value.student_name,
      group_name: form.value.group_name,
      project_name: form.value.project_name,
      members: (form.value.members || []).map(m => ({
        student_id: String(m.student_id || '').trim(),
        student_name: String(m.student_name || '').trim(),
        project_role: String(m.project_role || '').trim() || null,
        personal_statement: String(m.personal_statement || '').trim() || null,
      })),
    };
    const data = await upsertAssignmentSubmission(authStore.token, assignmentId, payload);
    submission.value = data || null;
    applySubmissionToForm(submission.value);
    message.value = '草稿已保存';
    await reloadAll();
  } catch (e) {
    errorMessage.value = e?.message || '保存失败';
  } finally {
    saving.value = false;
  }
}

async function onUpload(assetType, event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  const nextType = String(assetType || '').trim() || 'attachment';
  uploadingType.value = nextType;
  errorMessage.value = '';
  message.value = '';
  try {
    if (!submission.value?.id) {
      const assignmentId = activeAssignmentId.value;
      if (!assignmentId) throw new Error('请先选择一个作业');
      const payload = {
        student_name: form.value.student_name,
        group_name: form.value.group_name,
        project_name: form.value.project_name,
        members: (form.value.members || []).map(m => ({
          student_id: String(m.student_id || '').trim(),
          student_name: String(m.student_name || '').trim(),
          project_role: String(m.project_role || '').trim() || null,
          personal_statement: String(m.personal_statement || '').trim() || null,
        })),
      };
      const data = await upsertAssignmentSubmission(authStore.token, assignmentId, payload);
      submission.value = data || null;
      applySubmissionToForm(submission.value);
    }
    if (!submission.value?.id) {
      throw new Error('创建提交失败，请稍后重试');
    }
    const resp = await uploadSubmissionAsset(authStore.token, submission.value.id, nextType, file);
    submission.value = resp?.submission || submission.value;
    applySubmissionToForm(submission.value);
    message.value = `${assetTypeLabel(nextType)} 上传成功`;
    await reloadAll();
  } catch (e) {
    errorMessage.value = e?.message || '上传失败';
  } finally {
    uploadingType.value = '';
    if (event?.target) event.target.value = '';
  }
}

async function finalize() {
  if (!submission.value?.id) return;
  finalizing.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const resp = await finalizeSubmission(authStore.token, submission.value.id);
    submission.value = resp?.submission || submission.value;
    applySubmissionToForm(submission.value);
    message.value = '提交成功';
    await reloadAll();
  } catch (e) {
    errorMessage.value = e?.message || '提交失败';
  } finally {
    finalizing.value = false;
  }
}

onMounted(() => {
  reloadAll();
});
</script>
