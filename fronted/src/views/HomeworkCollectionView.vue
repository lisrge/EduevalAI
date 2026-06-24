<template>
  <div class="edueval-skin edueval-page">
    <ChatHeader />

    <div class="page-wrapper" style="flex: 1; min-height: 0; display: grid; gap: 16px;">
      <section class="page-hero">
        <div>
          <p class="hero-eyebrow">作业提交</p>
          <h2>作业提交</h2>
          <p class="hero-copy">选择作业，填写小组信息与成员陈述，上传材料后再完成提交。</p>
        </div>
        <div class="hero-actions">
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="reloadAll">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>
      <div v-if="message" class="alert success">{{ message }}</div>

      <div class="homework-layout">
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
              :class="['assignment-card', uploadStateClass(item.my_upload_state), { active: Number(item.id) === Number(activeAssignmentId) }]"
              :disabled="loading"
              @click="selectAssignment(item)"
            >
              <div style="display: flex; justify-content: space-between; gap: 10px;">
                <div>
                  <div style="font-weight: 800;">{{ item.course.name }} · 第{{ item.week_index }}周</div>
                  <div>{{ item.title }}</div>
                  <div class="panel-subtitle" style="margin-top: 6px;">
                    我的状态：{{ translateSubmissionStatus(item.my_submission_status) }} / {{ translateCompletenessStatus(item.my_completeness_status) }}
                  </div>
                  <div class="panel-subtitle" style="margin-top: 4px;">
                    上传状态：{{ uploadStateLabel(item.my_upload_state) }}
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
              <button
                class="ghost-button"
                type="button"
                style="width: auto;"
                :disabled="resubmitModal.saving"
                @click="openResubmitModal"
              >
                {{ resubmitModal.saving ? '提交中...' : '申请重新提交' }}
              </button>
            </div>
          </div>

          <div class="edueval-panel-body" style="overflow: auto;">
            <div v-if="!activeAssignment" class="empty-state">先从左侧选择一个作业。</div>
            <div v-else-if="loadingSubmission" class="empty-state">加载提交信息...</div>
            <template v-else>
              <div :class="['surface-card', 'submission-status-card', uploadStateClass(submission?.upload_state)]" style="display: grid; gap: 10px;">
                <div class="panel-subtitle">
                  状态：{{ translateSubmissionStatus(submission?.status) }} / {{ translateCompletenessStatus(submission?.completeness_status) }}
                </div>
                <div class="panel-subtitle">
                  上传状态：{{ uploadStateLabel(submission?.upload_state) }}
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

              <div class="surface-card" style="display: grid; gap: 10px; margin-top: 12px;">
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

              <div class="surface-card" style="display: grid; gap: 10px; margin-top: 12px;">
                <div style="font-weight: 800;">材料上传</div>
                <div class="panel-subtitle">按作业要求上传对应材料。</div>

                <div v-if="(activeAssignment?.required_asset_types || []).length === 0" class="panel" style="padding: 12px; display: grid; gap: 10px;">
                  <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <strong>任意文件上传</strong>
                    <input
                      type="file"
                      :accept="assetTypeAccept(effectiveAnyAssetType)"
                      :disabled="Boolean(uploadingType) && uploadingType === effectiveAnyAssetType"
                      @change="onUpload(effectiveAnyAssetType, $event)"
                    />
                  </div>
                  <div v-if="uploadJobs[effectiveAnyAssetType]" :class="['upload-progress-card', uploadStateClass(uploadJobs[effectiveAnyAssetType].state)]">
                    <div class="upload-progress-head">
                      <strong>{{ uploadStageLabel(uploadJobs[effectiveAnyAssetType].status) }}</strong>
                      <span>{{ uploadJobs[effectiveAnyAssetType].percent }}%</span>
                    </div>
                    <div class="upload-progress-bar">
                      <span :style="{ width: `${uploadJobs[effectiveAnyAssetType].percent}%` }"></span>
                    </div>
                    <div class="panel-subtitle">
                      {{ uploadJobs[effectiveAnyAssetType].detail || uploadJobs[effectiveAnyAssetType].fileName || '准备上传' }}
                    </div>
                  </div>
                  <div style="display: grid; grid-template-columns: 240px 240px minmax(0, 1fr); gap: 10px; align-items: end;">
                    <label class="field">
                      <span>材料类型</span>
                      <select v-model="anyAssetTypeSelected" class="edueval-input">
                        <option value="report">报告</option>
                        <option value="code_archive">代码压缩包</option>
                        <option value="ppt">PPT</option>
                        <option value="video">演示视频</option>
                        <option value="attachment">附件</option>
                        <option value="custom">自定义</option>
                      </select>
                    </label>
                    <label v-if="anyAssetTypeSelected === 'custom'" class="field">
                      <span>自定义类型</span>
                      <input v-model.trim="customAnyAssetType" class="edueval-input" type="text" placeholder="例如：readme / screenshot / dataset" />
                    </label>
                    <div class="panel-subtitle">材料类型用于区分版本，同类型多次上传会形成 v1/v2…</div>
                  </div>
                  <div v-if="(submission?.assets || []).length" class="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th style="width: 18%;">类型</th>
                          <th style="width: 40%;">文件</th>
                          <th style="width: 18%;">状态</th>
                          <th style="width: 24%;">上传时间</th>
                          <th style="width: 18%;">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="asset in submission.assets" :key="asset.id">
                          <td>{{ asset.asset_type }}</td>
                          <td>{{ asset.file_name }}</td>
                          <td>{{ assetStatusLabel(asset.upload_status) }}</td>
                          <td>{{ formatDateTime(asset.created_at) }}</td>
                          <td>
                            <div class="asset-inline-actions">
                              <button class="ghost-button compact-button" type="button" :disabled="!canPreviewAsset(asset)" @click="openAssetPreview(asset)">
                                预览
                              </button>
                              <button class="ghost-button compact-button" type="button" :disabled="downloadingAssetId === asset.id" @click="downloadAsset(asset)">
                                {{ downloadingAssetId === asset.id ? '下载中...' : '下载' }}
                              </button>
                            </div>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div v-else class="panel-subtitle">当前：未上传</div>
                </div>

                <div v-if="(activeAssignment?.required_asset_types || []).length" class="panel" style="padding: 12px; display: grid; gap: 10px;">
                  <div style="display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center;">
                    <strong>按类型上传</strong>
                    <input
                      type="file"
                      :accept="assetTypeAccept(selectedRequiredAssetType)"
                      :disabled="Boolean(uploadingType) && uploadingType === selectedRequiredAssetType"
                      @change="onUpload(selectedRequiredAssetType, $event)"
                    />
                  </div>
                  <div style="display: grid; grid-template-columns: 240px minmax(0, 1fr); gap: 10px; align-items: end;">
                    <label class="field">
                      <span>材料类型</span>
                      <select v-model="selectedRequiredAssetType" class="edueval-input">
                        <option v-for="item in (activeAssignment?.required_asset_types || [])" :key="item" :value="item">
                          {{ assetTypeLabel(item) }}
                        </option>
                      </select>
                    </label>
                    <div class="panel-subtitle">
                      必传列表：{{ (activeAssignment?.required_asset_types || []).map(assetTypeLabel).join('，') }}
                    </div>
                  </div>

                  <div v-if="uploadJobs[selectedRequiredAssetType]" :class="['upload-progress-card', uploadStateClass(uploadJobs[selectedRequiredAssetType].state)]">
                    <div class="upload-progress-head">
                      <strong>{{ uploadStageLabel(uploadJobs[selectedRequiredAssetType].status) }}</strong>
                      <span>{{ uploadJobs[selectedRequiredAssetType].percent }}%</span>
                    </div>
                    <div class="upload-progress-bar">
                      <span :style="{ width: `${uploadJobs[selectedRequiredAssetType].percent}%` }"></span>
                    </div>
                    <div class="panel-subtitle">
                      {{ uploadJobs[selectedRequiredAssetType].detail || uploadJobs[selectedRequiredAssetType].fileName || '准备上传' }}
                    </div>
                  </div>

                  <div class="panel-subtitle" v-if="submission?.latest_assets?.[selectedRequiredAssetType]">
                    当前：
                    <button class="link-button" type="button" @click="openAssetPreview(submission.latest_assets[selectedRequiredAssetType])">
                      {{ submission.latest_assets[selectedRequiredAssetType].file_name }}
                    </button>
                    （{{ assetStatusLabel(submission.latest_assets[selectedRequiredAssetType].upload_status) }}）
                  </div>
                  <div class="panel-subtitle" v-else>当前：未上传</div>
                </div>
              </div>

              <div class="surface-card" style="display: grid; gap: 14px; margin-top: 12px;">
                <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; align-items: flex-start;">
                  <div>
                    <div style="font-weight: 800;">已上传文件总览</div>
                    <div class="panel-subtitle">这里会展示这个作业下所有历史上传文件，可直接预览或下载。</div>
                  </div>
                  <div class="panel-subtitle">共 {{ uploadedAssets.length }} 个文件</div>
                </div>

                <div v-if="uploadedAssets.length === 0" class="empty-state asset-empty-state">
                  还没有已上传成功的文件。
                </div>

                <div v-else class="asset-gallery">
                  <article v-for="asset in uploadedAssets" :key="asset.id" class="asset-card">
                    <div class="asset-card-top">
                      <div>
                        <div class="asset-card-title">{{ asset.file_name }}</div>
                        <div class="panel-subtitle">
                          {{ assetTypeLabel(asset.asset_type) }} · {{ previewTypeLabel(asset) }}
                        </div>
                      </div>
                      <span class="asset-status-badge" :class="uploadStateClass(asset.upload_status)">
                        {{ assetStatusLabel(asset.upload_status) }}
                      </span>
                    </div>

                    <div class="asset-meta-grid">
                      <div class="asset-meta-item">
                        <span>大小</span>
                        <strong>{{ formatAssetSize(asset.file_size) }}</strong>
                      </div>
                      <div class="asset-meta-item">
                        <span>版本</span>
                        <strong>v{{ asset.version_no }}</strong>
                      </div>
                      <div class="asset-meta-item">
                        <span>时间</span>
                        <strong>{{ formatDateTime(asset.created_at) }}</strong>
                      </div>
                    </div>

                    <div class="asset-card-actions">
                      <button class="ghost-button compact-button" type="button" :disabled="!canPreviewAsset(asset)" @click="openAssetPreview(asset)">
                        {{ canPreviewAsset(asset) ? '打开预览' : '不可预览' }}
                      </button>
                      <button class="ghost-button compact-button" type="button" :disabled="downloadingAssetId === asset.id" @click="downloadAsset(asset)">
                        {{ downloadingAssetId === asset.id ? '下载中...' : '下载到本地' }}
                      </button>
                    </div>
                  </article>
                </div>
              </div>
            </template>
          </div>
        </section>
      </div>
    </div>

    <div v-if="resubmitModal.visible" class="asset-modal-overlay" @click.self="closeResubmitModal">
      <section class="asset-modal" style="max-width: 720px;">
        <div class="asset-modal-head">
          <div>
            <div class="hero-eyebrow">重新提交作业</div>
            <h3 style="margin: 6px 0;">提交申请说明</h3>
            <p class="panel-subtitle">每个小组、每份作业同时只能存在一条“重新提交”申请。管理员批准后会删除本组该作业的旧提交记录。</p>
          </div>
          <button class="modal-close-button" type="button" aria-label="关闭弹窗" :disabled="resubmitModal.saving" @click="closeResubmitModal">×</button>
        </div>
        <div class="edueval-panel-body" style="display: grid; gap: 12px;">
          <label class="field field-wide">
            <span>申请说明</span>
            <textarea v-model="resubmitModal.note" rows="5" placeholder="请说明重新提交原因（例如：漏传文件、版本更新、需要补充材料等）"></textarea>
          </label>
          <div class="form-actions field-wide" style="justify-content: flex-end;">
            <button class="primary-button" type="button" :disabled="resubmitModal.saving" @click="submitResubmitRequest">
              {{ resubmitModal.saving ? '提交中...' : '提交申请' }}
            </button>
          </div>
        </div>
      </section>
    </div>

    <div v-if="infoModal.visible" class="asset-modal-overlay" @click.self="closeInfoModal">
      <section class="asset-modal" style="max-width: 560px;">
        <div class="asset-modal-head">
          <div>
            <div class="hero-eyebrow">{{ infoModal.title }}</div>
            <h3 style="margin: 6px 0;">操作提示</h3>
          </div>
          <button class="modal-close-button" type="button" aria-label="关闭弹窗" @click="closeInfoModal">×</button>
        </div>
        <div class="edueval-panel-body" style="display: grid; gap: 12px;">
          <div class="panel-subtitle" style="font-size: 14px; line-height: 1.7; color: var(--text-primary);">
            {{ infoModal.message }}
          </div>
          <div class="form-actions field-wide" style="justify-content: flex-end;">
            <button class="primary-button" type="button" @click="closeInfoModal">知道了</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { useAuthStore } from '../stores/authStore';
import { checkChunkFile, fetchAssignments, fetchMyAssignmentSubmission, fetchMyHomeworkStatus, fetchSubmissionAssetBlob, finalizeSubmission, mergeChunkFile, requestHomeworkResubmit, uploadChunkPart, upsertAssignmentSubmission } from '../services/eduevalApi';
import { subscribeLiveEvents } from '../services/liveEventStream';
import { computeFileMd5 } from '../utils/fileMd5';
import { detectSubmissionAssetPreview, downloadBlob, formatFileSize } from '../utils/submissionAssetPreview';
import { translateCompletenessStatus, translateSubmissionStatus, translateUploadStatus } from '../utils/statusText';

const router = useRouter();
const authStore = useAuthStore();
const DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024;
const MAX_CONCURRENT_CHUNKS = 5;
const CHUNK_RETRY_LIMIT = 3;

const assignments = ref([]);
const activeAssignmentId = ref(null);
const activeAssignment = computed(() => assignments.value.find(item => Number(item.id) === Number(activeAssignmentId.value)) || null);
const submission = ref(null);
const homeworkStatus = ref(null);
const resubmitModal = ref({
  visible: false,
  note: '',
  saving: false,
});
const infoModal = ref({
  visible: false,
  title: '提示',
  message: '',
});
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
const uploadJobs = ref({});
const anyAssetTypeSelected = ref('attachment');
const customAnyAssetType = ref('attachment');
const effectiveAnyAssetType = computed(() => {
  if (anyAssetTypeSelected.value === 'custom') {
    return String(customAnyAssetType.value || '').trim() || 'attachment';
  }
  return String(anyAssetTypeSelected.value || '').trim() || 'attachment';
});
const selectedRequiredAssetType = ref('');
const errorMessage = ref('');
const message = ref('');
const downloadingAssetId = ref(null);
const uploadedAssets = computed(() => {
  const list = Array.isArray(submission.value?.assets) ? submission.value.assets : [];
  return [...list]
    .filter(item => String(item?.upload_status || '').toLowerCase() === 'uploaded')
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
});
let unsubscribeLiveEvents = null;

function goBack() {
  router.push({ name: authStore.isAdmin ? 'admin-users' : 'applications' });
}

function assetTypeLabel(assetType) {
  const v = String(assetType || '').toLowerCase();
  if (v === 'report') return '报告';
  if (v === 'code_archive') return '代码压缩包';
  if (v === 'ppt') return 'PPT';
  if (v === 'video') return '演示视频';
  if (v === 'attachment') return '附件';
  return String(assetType || '');
}

function assetTypeAccept(assetType) {
  const v = String(assetType || '').toLowerCase();
  if (v === 'report') return '.pdf,.doc,.docx';
  if (v === 'code_archive') return '.zip,.rar,.7z';
  if (v === 'ppt') return '.ppt,.pptx,.pps,.ppsx,.pdf';
  if (v === 'video') return 'video/*';
  if (v === 'attachment') return '';
  return '';
}

function requiredLabel(types) {
  const list = Array.isArray(types) ? types : [];
  if (list.length === 0) return '';
  return `必传：${list.map(assetTypeLabel).join('，')}`;
}

function normalizeUploadState(value) {
  const v = String(value || '').toLowerCase();
  if (v === 'failed') return 'failed';
  if (v === 'uploading' || v === 'hashing' || v === 'resuming' || v === 'merging') return 'uploading';
  return 'normal';
}

function uploadStateClass(value) {
  return `upload-state-${normalizeUploadState(value)}`;
}

function uploadStateLabel(value) {
  const v = normalizeUploadState(value);
  if (v === 'failed') return '上传失败';
  if (v === 'uploading') return '上传中';
  return '正常';
}

function uploadStageLabel(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'hashing') return '计算 MD5 中';
  if (v === 'resuming') return '断点续传中';
  if (v === 'merging') return '服务端合并中';
  if (v === 'success') return '上传完成';
  if (v === 'failed') return '上传失败';
  return '上传中';
}

function assetStatusLabel(status) {
  return translateUploadStatus(status);
}

function canPreviewAsset(asset) {
  return detectSubmissionAssetPreview(asset).canPreview;
}

function previewTypeLabel(asset) {
  return detectSubmissionAssetPreview(asset).label;
}

function formatAssetSize(value) {
  return formatFileSize(value);
}

function formatDateTime(value) {
  if (!value) return '未知';
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return String(value || '未知');
  }
}

function openAssetPreview(asset) {
  if (!asset?.id || !submission.value?.id || !canPreviewAsset(asset)) return;
  router.push({
    name: 'submission-asset-preview',
    params: {
      submissionId: String(submission.value.id),
      assetId: String(asset.id),
    },
  });
}

async function downloadAsset(asset) {
  if (!asset?.id) return;
  downloadingAssetId.value = asset.id;
  errorMessage.value = '';
  try {
    const { blob } = await fetchSubmissionAssetBlob(authStore.token, asset.id);
    downloadBlob(blob, asset.file_name || 'download');
  } catch (e) {
    errorMessage.value = e?.message || '下载失败';
  } finally {
    downloadingAssetId.value = null;
  }
}

function setUploadJob(assetType, patch) {
  const key = String(assetType || '').trim() || 'attachment';
  uploadJobs.value = {
    ...uploadJobs.value,
    [key]: {
      percent: 0,
      status: 'uploading',
      state: 'uploading',
      detail: '',
      fileName: '',
      ...uploadJobs.value[key],
      ...patch,
    },
  };
}

function buildDraftPayload() {
  return {
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

async function reloadAll(options = {}) {
  const silent = Boolean(options.silent);
  const refreshDetail = options.refreshDetail !== false;
  loading.value = true;
  if (!silent) {
    errorMessage.value = '';
    message.value = '';
  }
  try {
    const list = await fetchAssignments(authStore.token);
    assignments.value = Array.isArray(list) ? list : [];
    const currentAssignment = assignments.value.find(item => Number(item.id) === Number(activeAssignmentId.value)) || null;
    if (refreshDetail && currentAssignment) {
      await loadSubmission(currentAssignment.id, { silent: true });
    } else if (refreshDetail && !activeAssignmentId.value && assignments.value.length > 0) {
      await selectAssignment(assignments.value[0]);
    } else if (refreshDetail && !currentAssignment) {
      activeAssignmentId.value = assignments.value[0]?.id || null;
      if (activeAssignmentId.value) {
        await loadSubmission(activeAssignmentId.value, { silent: true });
      } else {
        submission.value = null;
        homeworkStatus.value = null;
        applySubmissionToForm(null);
      }
    }
  } catch (e) {
    assignments.value = [];
    submission.value = null;
    homeworkStatus.value = null;
    if (!silent) {
      errorMessage.value = e?.message || '加载作业失败';
    }
  } finally {
    loading.value = false;
  }
}

async function loadSubmission(assignmentId, options = {}) {
  const silent = Boolean(options.silent);
  loadingSubmission.value = true;
  if (!silent) {
    errorMessage.value = '';
    message.value = '';
  }
  try {
    const data = await fetchMyAssignmentSubmission(authStore.token, assignmentId);
    submission.value = data || null;
    applySubmissionToForm(submission.value);
    homeworkStatus.value = await fetchMyHomeworkStatus(authStore.token, assignmentId);
  } catch (e) {
    submission.value = null;
    homeworkStatus.value = null;
    applySubmissionToForm(null);
    if (!silent) {
      errorMessage.value = e?.message || '加载提交信息失败';
    }
  } finally {
    loadingSubmission.value = false;
  }
}

watch(
  () => activeAssignment.value?.required_asset_types,
  nextValue => {
    const list = Array.isArray(nextValue) ? nextValue : [];
    if (!list.length) return;
    if (!selectedRequiredAssetType.value || !list.includes(selectedRequiredAssetType.value)) {
      selectedRequiredAssetType.value = list[0];
    }
  },
  { immediate: true }
);

function openResubmitModal() {
  if (!activeAssignmentId.value) {
    showInfoModal('暂时无法申请', '请先从左侧选择一个作业。');
    return;
  }
  if (loadingSubmission.value) {
    showInfoModal('暂时无法申请', '提交信息加载中，请稍后再试。');
    return;
  }
  if (!submission.value) {
    showInfoModal('暂时无法申请', '本组还没有该作业的提交记录，请先保存草稿或上传文件后再申请。');
    return;
  }
  if (String(submission.value?.status || '').toLowerCase() !== 'submitted') {
    showInfoModal('暂时无法申请', '当前作业尚未正式提交，请先点击“提交作业”后再申请重新提交。');
    return;
  }
  if (homeworkStatus.value?.pending_resubmit_request) {
    showInfoModal('申请已提交', '本组已提交重新提交申请，请等待管理员审核。');
    return;
  }
  errorMessage.value = '';
  resubmitModal.value.visible = true;
  resubmitModal.value.note = '';
}

function closeResubmitModal() {
  if (resubmitModal.value.saving) return;
  resubmitModal.value.visible = false;
  resubmitModal.value.note = '';
}

function showInfoModal(title, message) {
  infoModal.value.visible = true;
  infoModal.value.title = title || '提示';
  infoModal.value.message = message || '';
}

function closeInfoModal() {
  infoModal.value.visible = false;
}

async function submitResubmitRequest() {
  const assignmentId = activeAssignmentId.value;
  if (!assignmentId) return;
  if (resubmitModal.value.saving) return;
  resubmitModal.value.saving = true;
  errorMessage.value = '';
  try {
    await requestHomeworkResubmit(authStore.token, assignmentId, { request_note: resubmitModal.value.note || '' });
    resubmitModal.value.visible = false;
    resubmitModal.value.note = '';
    homeworkStatus.value = await fetchMyHomeworkStatus(authStore.token, assignmentId);
    showInfoModal('提交成功', '已提交重新提交申请，请等待管理员审核。');
  } catch (e) {
    showInfoModal('提交失败', e?.message || '提交申请失败');
  } finally {
    resubmitModal.value.saving = false;
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
  if (String(submission.value?.status || '').toLowerCase() === 'submitted') {
    await loadSubmission(assignmentId, { silent: true });
    if (String(submission.value?.status || '').toLowerCase() === 'submitted') {
      openResubmitModal();
      return;
    }
  }
  saving.value = true;
  errorMessage.value = '';
  message.value = '';
  try {
    const data = await upsertAssignmentSubmission(authStore.token, assignmentId, buildDraftPayload());
    submission.value = data || null;
    applySubmissionToForm(submission.value);
    await reloadAll();
    message.value = '草稿已保存';
  } catch (e) {
    errorMessage.value = e?.message || '保存失败';
  } finally {
    saving.value = false;
  }
}

async function ensureSubmissionExists() {
  if (submission.value?.id) return submission.value;
  const assignmentId = activeAssignmentId.value;
  if (!assignmentId) throw new Error('请先选择一个作业');
  const data = await upsertAssignmentSubmission(authStore.token, assignmentId, buildDraftPayload());
  submission.value = data || null;
  applySubmissionToForm(submission.value);
  if (!submission.value?.id) {
    throw new Error('创建提交失败，请稍后重试');
  }
  return submission.value;
}

async function uploadChunksWithConcurrency({ assetType, file, uploadId, chunkSize, totalChunks, uploadedParts }) {
  const pendingParts = [];
  for (let partNumber = 1; partNumber <= totalChunks; partNumber += 1) {
    if (!uploadedParts.has(partNumber)) pendingParts.push(partNumber);
  }
  if (pendingParts.length === 0) return;

  let currentIndex = 0;
  let thrownError = null;

  async function worker() {
    while (currentIndex < pendingParts.length && !thrownError) {
      const partNumber = pendingParts[currentIndex];
      currentIndex += 1;
      const start = (partNumber - 1) * chunkSize;
      const end = Math.min(start + chunkSize, file.size);
      const blob = file.slice(start, end);
      let uploaded = false;
      let lastError = null;
      for (let attempt = 1; attempt <= CHUNK_RETRY_LIMIT; attempt += 1) {
        try {
          const resp = await uploadChunkPart(authStore.token, {
            uploadId,
            partNumber,
            chunk: blob,
          });
          uploaded = true;
          uploadedParts.add(partNumber);
          const uploadedCount = Number(resp?.session?.uploaded_count || uploadedParts.size);
          setUploadJob(assetType, {
            status: 'uploading',
            state: 'uploading',
            percent: Math.min(100, Math.round((uploadedCount / totalChunks) * 100)),
            detail: `已上传 ${uploadedCount}/${totalChunks} 个分片`,
          });
          break;
        } catch (error) {
          lastError = error;
        }
      }
      if (!uploaded) {
        thrownError = lastError || new Error(`分片 ${partNumber} 上传失败`);
      }
    }
  }

  const workerCount = Math.min(MAX_CONCURRENT_CHUNKS, pendingParts.length);
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  if (thrownError) throw thrownError;
}

async function onUpload(assetType, event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  if (String(submission.value?.status || '').toLowerCase() === 'submitted') {
    if (activeAssignmentId.value) {
      await loadSubmission(activeAssignmentId.value, { silent: true });
    }
    if (String(submission.value?.status || '').toLowerCase() === 'submitted') {
      openResubmitModal();
      return;
    }
  }
  const nextType = String(assetType || '').trim() || 'attachment';
  uploadingType.value = nextType;
  errorMessage.value = '';
  message.value = '';
  try {
    const currentSubmission = await ensureSubmissionExists();
    if (String(currentSubmission?.status || '').toLowerCase() === 'submitted') {
      openResubmitModal();
      return;
    }
    setUploadJob(nextType, {
      status: 'hashing',
      state: 'uploading',
      percent: 0,
      fileName: file.name,
      detail: '计算 MD5 中 0%',
    });
    const localTotalChunks = Math.max(Math.ceil(file.size / DEFAULT_CHUNK_SIZE), 1);
    const md5 = await computeFileMd5(file, {
      chunkSize: DEFAULT_CHUNK_SIZE,
      onProgress: ({ percent }) => {
        setUploadJob(nextType, {
          status: 'hashing',
          state: 'uploading',
          percent: 0,
          fileName: file.name,
          detail: `计算 MD5 中 ${percent}%`,
        });
      },
    });
    const checkResp = await checkChunkFile(authStore.token, {
      submission_id: currentSubmission.id,
      asset_type: nextType,
      file_name: file.name,
      file_size: file.size,
      md5,
      total_chunks: localTotalChunks,
      chunk_size: DEFAULT_CHUNK_SIZE,
      mime_type: file.type || null,
    });
    if (checkResp?.instant_upload) {
      submission.value = checkResp?.submission || submission.value;
      applySubmissionToForm(submission.value);
      setUploadJob(nextType, {
        status: 'success',
        state: 'normal',
        percent: 100,
        fileName: file.name,
        detail: '服务器已存在相同文件，已直接完成秒传',
      });
      await reloadAll();
      message.value = `${assetTypeLabel(nextType)} 秒传成功`;
      return;
    }

    const session = checkResp?.session;
    if (!session?.upload_id) {
      throw new Error('创建分片上传会话失败');
    }

    const serverChunkSize = Number(checkResp?.chunk_size || DEFAULT_CHUNK_SIZE);
    const totalChunks = Math.max(Math.ceil(file.size / serverChunkSize), 1);
    const uploadedParts = new Set(Array.isArray(session?.uploaded_parts) ? session.uploaded_parts.map(item => Number(item)) : []);
    setUploadJob(nextType, {
      status: uploadedParts.size > 0 ? 'resuming' : 'uploading',
      state: 'uploading',
      percent: Math.round((uploadedParts.size / totalChunks) * 100),
      fileName: file.name,
      detail: uploadedParts.size > 0
        ? `检测到已上传 ${uploadedParts.size}/${totalChunks} 个分片，继续续传`
        : `开始上传 0/${totalChunks} 个分片`,
    });

    await uploadChunksWithConcurrency({
      assetType: nextType,
      file,
      uploadId: session.upload_id,
      chunkSize: serverChunkSize,
      totalChunks,
      uploadedParts,
    });

    setUploadJob(nextType, {
      status: 'merging',
      state: 'uploading',
      percent: 100,
      fileName: file.name,
      detail: '所有分片已上传，等待服务器合并校验',
    });
    const resp = await mergeChunkFile(authStore.token, {
      upload_id: session.upload_id,
      md5,
    });
    submission.value = resp?.submission || submission.value;
    applySubmissionToForm(submission.value);
    setUploadJob(nextType, {
      status: 'success',
      state: 'normal',
      percent: 100,
      fileName: file.name,
      detail: '上传完成，MD5 校验通过',
    });
    await reloadAll();
    message.value = `${assetTypeLabel(nextType)} 上传成功`;
  } catch (e) {
    setUploadJob(nextType, {
      status: 'failed',
      state: 'failed',
      detail: e?.message || '上传失败',
    });
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
    await reloadAll();
    message.value = '提交成功';
  } catch (e) {
    errorMessage.value = e?.message || '提交失败';
  } finally {
    finalizing.value = false;
  }
}

onMounted(() => {
  reloadAll();
  if (!authStore.isAdmin) {
    unsubscribeLiveEvents = subscribeLiveEvents(authStore.token, handleLiveEvent);
  }
});

onBeforeUnmount(() => {
  if (typeof unsubscribeLiveEvents === 'function') {
    unsubscribeLiveEvents();
    unsubscribeLiveEvents = null;
  }
});

function handleLiveEvent(message) {
  if (!message || message.event !== 'homework_resubmit_approved') return;
  const eventGroupId = Number(message?.payload?.group_id || 0);
  const currentGroupId = Number(authStore.user?.group_id || 0);
  if (eventGroupId > 0 && currentGroupId > 0 && eventGroupId !== currentGroupId) return;
  reloadAll({ silent: true, refreshDetail: false });
}
</script>

<style scoped>
.modal-close-button {
  width: 36px;
  height: 36px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  color: var(--text-primary);
  font-size: 24px;
  line-height: 1;
  cursor: pointer;
}

.modal-close-button:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
</style>

<style scoped>
.homework-layout {
  min-height: 0;
  display: grid;
  grid-template-columns: 360px minmax(0, 1fr);
  gap: 16px;
}

.assignment-card {
  width: 100%;
  margin-bottom: 10px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface-soft);
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease;
}

.assignment-card.active {
  border-color: rgba(37, 99, 235, 0.45);
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}

.assignment-card:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-sm);
}

.submission-status-card {
  transition: border-color 0.2s ease, background 0.2s ease;
}

.upload-progress-card {
  display: grid;
  gap: 8px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid var(--border);
}

.upload-progress-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.upload-progress-bar {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.2);
  overflow: hidden;
}

.upload-progress-bar span {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #3b82f6, #2563eb);
  transition: width 0.2s ease;
}

.upload-state-normal {
  border-color: rgba(34, 197, 94, 0.24);
  background: rgba(236, 253, 245, 0.82);
}

.upload-state-uploading {
  border-color: rgba(59, 130, 246, 0.28);
  background: rgba(239, 246, 255, 0.88);
}

.upload-state-failed {
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(254, 242, 242, 0.92);
}

.upload-state-normal .upload-progress-bar span {
  background: linear-gradient(90deg, #22c55e, #16a34a);
}

.upload-state-failed .upload-progress-bar span {
  background: linear-gradient(90deg, #ef4444, #dc2626);
}

.asset-inline-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.link-button {
  padding: 0;
  border: 0;
  background: transparent;
  color: #2563eb;
  cursor: pointer;
  font: inherit;
  text-decoration: underline;
}

.asset-empty-state {
  min-height: 120px;
}

.asset-gallery {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
}

.asset-card {
  display: grid;
  gap: 14px;
  padding: 16px;
  border-radius: 20px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.08), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.96));
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.06);
}

.asset-card-top {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.asset-card-title {
  font-weight: 800;
  word-break: break-word;
}

.asset-status-badge {
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1;
  white-space: nowrap;
}

.asset-meta-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.asset-meta-item {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(226, 232, 240, 0.92);
}

.asset-meta-item span {
  font-size: 12px;
  color: var(--muted);
}

.asset-card-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

@media (max-width: 960px) {
  .homework-layout {
    grid-template-columns: 1fr;
  }

  .asset-meta-grid {
    grid-template-columns: 1fr;
  }
}
</style>
