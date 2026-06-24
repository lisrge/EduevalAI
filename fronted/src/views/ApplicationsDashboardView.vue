<template>
  <div class="edueval-skin edueval-page">
    <ChatHeader />

    <div class="page-wrapper" style="display: grid; gap: 20px;">
      <section class="page-hero">
        <div>
          <p class="hero-eyebrow">学生工作台</p>
          <h2>申请书上传与材料预览</h2>
          <p class="hero-copy">左侧上传与查看材料，右侧查看详情，底部统一预览内容和生成结果。</p>
        </div>
        <div class="hero-actions">
          <span class="badge neutral">学生仅能查看本组申请书</span>
          <button
            v-if="!allowScoring"
            type="button"
            class="ghost-button"
            :disabled="reuploadModal.saving"
            @click="openReuploadModal"
          >
            {{ reuploadModal.saving ? '提交中...' : '申请重新上传' }}
          </button>
          <span v-if="allowScoring" class="badge ok">管理员可查看评分与批量操作</span>
        </div>
      </section>

      <div class="edueval-layout">
        <div class="edueval-left">
          <ApplicationUploadPanel
            class="edueval-panel-fill"
            style="min-height: 360px;"
            :submitting="hasPendingWork"
            :allow-scoring="allowScoring"
            @submit="onSubmitUpload"
          />
          <ApplicationFileList
            class="edueval-panel-fill"
            style="min-height: 720px;"
            :items="items"
            :selected-local-id="selectedLocalId"
            :allow-scoring="allowScoring"
            @select="onSelectItem"
            @score="onScoreItem"
            @refresh="onRefreshList"
            @batch-score="onBatchScore"
            @batch-delete="onBatchDelete"
            @export="onExport"
            @preview="onPreviewItem"
          />
        </div>
        <div class="edueval-right">
          <ScoreDetailPanel class="edueval-panel-fill" :item="selectedItem" :loading="isDetailLoading" :allow-scoring="allowScoring" @score="onScoreItem" />
        </div>
      </div>

      <ApplicationPreviewPanel class="edueval-panel-fill" :enabled="previewEnabled" :item="previewItem" />
    </div>

    <div v-if="reuploadModal.visible" class="asset-modal-overlay" @click.self="closeReuploadModal">
      <section class="asset-modal" style="max-width: 720px;">
        <div class="asset-modal-head">
          <div>
            <div class="hero-eyebrow">重新上传申请书</div>
            <h3 style="margin: 6px 0;">提交申请说明</h3>
            <p class="panel-subtitle">每个小组同时只能存在一条“重新上传”申请。管理员批准后会删除本组之前的申请书。</p>
          </div>
          <button class="modal-close-button" type="button" aria-label="关闭弹窗" :disabled="reuploadModal.saving" @click="closeReuploadModal">×</button>
        </div>
        <div class="edueval-panel-body" style="display: grid; gap: 12px;">
          <label class="field field-wide">
            <span>申请说明</span>
            <textarea v-model="reuploadModal.note" rows="5" placeholder="请说明重新上传原因（例如：文件错误、漏传、版本更新等）"></textarea>
          </label>
          <div class="form-actions field-wide" style="justify-content: flex-end;">
            <button class="primary-button" type="button" :disabled="reuploadModal.saving" @click="submitReuploadRequest">
              {{ reuploadModal.saving ? '提交中...' : '提交申请' }}
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
import { storeToRefs } from 'pinia';
import ChatHeader from '../components/ChatHeader.vue';
import ApplicationUploadPanel from '../components/edueval/ApplicationUploadPanel.vue';
import ApplicationFileList from '../components/edueval/ApplicationFileList.vue';
import ScoreDetailPanel from '../components/edueval/ScoreDetailPanel.vue';
import ApplicationPreviewPanel from '../components/edueval/ApplicationPreviewPanel.vue';
import { useApplicationStore } from '../stores/applicationStore';
import { useAuthStore } from '../stores/authStore';
import { buildExportUrl, fetchMyApplicationStatus, requestApplicationReupload } from '../services/eduevalApi';
import { subscribeLiveEvents } from '../services/liveEventStream';

const applicationStore = useApplicationStore();
const authStore = useAuthStore();
const { items, selectedLocalId, selectedItem, hasPendingWork, detailLoadingLocalId } = storeToRefs(applicationStore);

const allowScoring = computed(() => authStore.isAdmin);
const userStatus = ref(null);
const previewEnabled = ref(false);
const previewLocalId = ref(null);
const reuploadModal = ref({
  visible: false,
  note: '',
  saving: false,
});
const infoModal = ref({
  visible: false,
  title: '提示',
  message: '',
});
let unsubscribeLiveEvents = null;

const isDetailLoading = computed(() => Boolean(selectedLocalId.value) && detailLoadingLocalId.value === selectedLocalId.value);
const previewItem = computed(() => {
  const id = previewLocalId.value;
  return id ? items.value.find(item => item.localId === id) || null : null;
});

onMounted(async () => {
  await refreshStatus();
  await applicationStore.refreshFromServer();
  if (!allowScoring.value) {
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
  if (!message || message.event !== 'application_reupload_approved') return;
  const eventGroupId = Number(message?.payload?.group_id || 0);
  const currentGroupId = Number(authStore.user?.group_id || 0);
  if (eventGroupId > 0 && currentGroupId > 0 && eventGroupId !== currentGroupId) return;
  applicationStore.refreshFromServer({ reloadDetail: false });
}

async function refreshStatus() {
  if (allowScoring.value) {
    userStatus.value = null;
    return;
  }
  try {
    userStatus.value = await fetchMyApplicationStatus(authStore.token);
  } catch (e) {
    userStatus.value = null;
  }
}

async function onSubmitUpload(payload) {
  if (!allowScoring.value) {
    await refreshStatus();
    if (userStatus.value?.has_application) {
      openReuploadModal();
      return;
    }
  }
  applicationStore.enqueueBatch(payload);
  window.setTimeout(() => {
    refreshStatus();
  }, 1000);
}

function openReuploadModal() {
  if (!userStatus.value) {
    showInfoModal('暂时无法申请', '正在加载本组申请书状态，请稍后再试。');
    return;
  }
  if (!userStatus.value?.has_application) {
    showInfoModal('暂时无法申请', '本组还没有上传申请书，无需申请重新上传。');
    return;
  }
  if (userStatus.value?.pending_reupload_request) {
    showInfoModal('申请已提交', '本组已提交重新上传申请，请等待管理员审核。');
    return;
  }
  reuploadModal.value.visible = true;
  reuploadModal.value.note = '';
}

function closeReuploadModal() {
  if (reuploadModal.value.saving) return;
  reuploadModal.value.visible = false;
  reuploadModal.value.note = '';
}

function showInfoModal(title, message) {
  infoModal.value.visible = true;
  infoModal.value.title = title || '提示';
  infoModal.value.message = message || '';
}

function closeInfoModal() {
  infoModal.value.visible = false;
}

async function submitReuploadRequest() {
  if (reuploadModal.value.saving) return;
  reuploadModal.value.saving = true;
  try {
    await requestApplicationReupload(authStore.token, { request_note: reuploadModal.value.note || '' });
    reuploadModal.value.visible = false;
    reuploadModal.value.note = '';
    await refreshStatus();
    showInfoModal('提交成功', '已提交重新上传申请，请等待管理员审核。');
  } catch (e) {
    showInfoModal('提交失败', e?.message || '提交重新上传申请失败');
  } finally {
    reuploadModal.value.saving = false;
  }
}

function onSelectItem(localId) {
  applicationStore.select(localId);
}

function onScoreItem(localId) {
  if (allowScoring.value) applicationStore.scoreOne(localId);
}

function onRefreshList() {
  applicationStore.refreshFromServer();
  refreshStatus();
}

function onBatchScore(localIds) {
  if (allowScoring.value) applicationStore.batchScoreByLocalIds(localIds);
}

function onBatchDelete(localIds) {
  if (allowScoring.value) applicationStore.batchDeleteByLocalIds(localIds);
}

function onExport(format) {
  if (!allowScoring.value) return;
  const url = buildExportUrl(format);
  window.open(url, '_blank', 'noopener,noreferrer');
}

function onPreviewItem(localId) {
  previewEnabled.value = true;
  previewLocalId.value = localId;
}

watch(selectedLocalId, (next) => {
  if (previewEnabled.value && next) {
    previewLocalId.value = next;
  }
});
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
