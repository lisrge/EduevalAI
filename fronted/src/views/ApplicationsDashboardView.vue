<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; display: flex; flex-direction: column; gap: 20px;">
      <div class="edueval-layout">
          <div class="edueval-left">
            <ApplicationUploadPanel class="edueval-panel-fill" style="min-height: 420px;" :submitting="hasPendingWork" :allow-scoring="allowScoring" @submit="onSubmitUpload" />
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
import { buildExportUrl } from '../services/eduevalApi';

const applicationStore = useApplicationStore();
const authStore = useAuthStore();
const { items, selectedLocalId, selectedItem, hasPendingWork, detailLoadingLocalId } = storeToRefs(applicationStore);

const allowScoring = computed(() => authStore.isAdmin);

const previewEnabled = ref(false);
const previewLocalId = ref(null);

const isDetailLoading = computed(() => {
  return Boolean(selectedLocalId.value) && detailLoadingLocalId.value === selectedLocalId.value;
});

const previewItem = computed(() => {
  const id = previewLocalId.value;
  if (!id) return null;
  return items.value.find(item => item.localId === id) || null;
});

onMounted(() => {
  applicationStore.refreshFromServer();
});

function onSubmitUpload(payload) {
  applicationStore.enqueueBatch(payload);
}

function onSelectItem(localId) {
  applicationStore.select(localId);
}

function onScoreItem(localId) {
  if (!allowScoring.value) return;
  applicationStore.scoreOne(localId);
}

function onRefreshList() {
  applicationStore.refreshFromServer();
}

function onBatchScore(localIds) {
  if (!allowScoring.value) return;
  applicationStore.batchScoreByLocalIds(localIds);
}

function onBatchDelete(localIds) {
  applicationStore.batchDeleteByLocalIds(localIds);
}

function onExport(format) {
  const url = buildExportUrl(format);
  window.open(url, '_blank', 'noopener,noreferrer');
}

function onPreviewItem(localId) {
  previewEnabled.value = true;
  previewLocalId.value = localId;
}

watch(selectedLocalId, (next) => {
  if (!previewEnabled.value) return;
  if (!next) return;
  previewLocalId.value = next;
});
</script>
