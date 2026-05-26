<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; display: flex; flex-direction: column; gap: 20px;">
      <div v-if="statusBlock" class="alert error">
        {{ statusBlock }}
      </div>

      <div class="edueval-layout">
        <div class="edueval-left">
          <ApplicationUploadPanel
            class="edueval-panel-fill"
            style="min-height: 360px;"
            :submitting="hasPendingWork"
            :allow-scoring="allowScoring"
            :status-message="uploadStatusMessage"
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
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import ChatHeader from '../components/ChatHeader.vue';
import ApplicationUploadPanel from '../components/edueval/ApplicationUploadPanel.vue';
import ApplicationFileList from '../components/edueval/ApplicationFileList.vue';
import ScoreDetailPanel from '../components/edueval/ScoreDetailPanel.vue';
import ApplicationPreviewPanel from '../components/edueval/ApplicationPreviewPanel.vue';
import { useApplicationStore } from '../stores/applicationStore';
import { useAuthStore } from '../stores/authStore';
import { buildExportUrl, fetchMyApplicationStatus, requestApplicationReupload } from '../services/eduevalApi';

const applicationStore = useApplicationStore();
const authStore = useAuthStore();
const { items, selectedLocalId, selectedItem, hasPendingWork, detailLoadingLocalId } = storeToRefs(applicationStore);

const allowScoring = computed(() => authStore.isAdmin);
const userStatus = ref(null);
const statusBlock = ref('');
const previewEnabled = ref(false);
const previewLocalId = ref(null);

const isDetailLoading = computed(() => Boolean(selectedLocalId.value) && detailLoadingLocalId.value === selectedLocalId.value);
const previewItem = computed(() => {
  const id = previewLocalId.value;
  return id ? items.value.find(item => item.localId === id) || null : null;
});

const uploadStatusMessage = computed(() => {
  if (allowScoring.value) return '';
  if (!userStatus.value) return '';
  if (!userStatus.value.has_application) return '';
  if (userStatus.value.application_reupload_allowed) {
    return '管理员已批准你重新上传一次申请书，本次上传成功后授权会自动用尽。';
  }
  if (userStatus.value.pending_reupload_request) {
    return '你已经提交过重新上传申请，等待管理员审核。';
  }
  return '你已经上传过申请书。如需重新上传，请先向管理员提交申请。';
});

onMounted(async () => {
  await refreshStatus();
  applicationStore.refreshFromServer();
});

async function refreshStatus() {
  if (allowScoring.value) {
    userStatus.value = null;
    statusBlock.value = '';
    return;
  }
  try {
    userStatus.value = await fetchMyApplicationStatus(authStore.token);
    statusBlock.value = '';
  } catch (e) {
    statusBlock.value = e?.message || '加载用户状态失败';
  }
}

async function onSubmitUpload(payload) {
  if (!allowScoring.value && userStatus.value?.has_application && !userStatus.value?.application_reupload_allowed) {
    const note = window.prompt('你已经上传过申请书。如需重新上传，请填写申请说明并提交给管理员。', '');
    if (note !== null) {
      try {
        await requestApplicationReupload(authStore.token, { request_note: note });
        await refreshStatus();
      } catch (e) {
        statusBlock.value = e?.message || '提交重新上传申请失败';
      }
    }
    return;
  }
  applicationStore.enqueueBatch(payload);
  window.setTimeout(() => {
    refreshStatus();
  }, 1000);
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
