import { acceptHMRUpdate, defineStore } from 'pinia';
import { computed, ref } from 'vue';
import {
  batchDeleteApplications,
  batchScoreApplications,
  fetchApplicationDetail,
  fetchApplications,
  scoreApplication,
  uploadApplicationFile,
} from '../services/eduevalApi';
import { useAuthStore } from './authStore';

function generateUniqueId() {
  return Math.random().toString(36).substring(2, 9);
}

function generateLocalId() {
  return `app_${Date.now()}_${generateUniqueId()}`;
}

function inferFileType(file) {
  const name = String(file?.name || '');
  const parts = name.split('.');
  if (parts.length < 2) return '';
  return parts[parts.length - 1].toLowerCase();
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const idx = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  const size = value / Math.pow(1024, idx);
  return `${size.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

export const useApplicationStore = defineStore('applications', () => {
  const items = ref([]);
  const selectedLocalId = ref(null);
  const queue = ref([]);
  const activeWorkers = ref(0);
  const detailLoadingLocalId = ref(null);
  const listLoading = ref(false);

  const maxConcurrent = ref(2);

  const selectedItem = computed(() => items.value.find(item => item.localId === selectedLocalId.value) || null);
  const hasPendingWork = computed(() => queue.value.length > 0 || activeWorkers.value > 0);

  function getItem(localId) {
    return items.value.find(item => item.localId === localId) || null;
  }

  function updateItem(localId, patch) {
    const idx = items.value.findIndex(item => item.localId === localId);
    if (idx === -1) return;
    items.value[idx] = { ...items.value[idx], ...patch };
  }

  function ensureServerItem(summary) {
    const applicationId = summary?.id ?? null;
    if (!applicationId) return null;

    const existingIdx = items.value.findIndex(item => item.applicationId === applicationId);
    const patch = {
      applicationId,
      application: {
        id: summary.id,
        student_name: summary.student_name,
        student_id: summary.student_id,
        project_title: summary.project_title,
        file_name: summary.file_name,
        file_type: summary.file_type,
        file_download_url: summary.file_download_url,
        preview_url: summary.preview_url,
        score_status: summary.score_status,
        created_at: summary.created_at,
        updated_at: summary.updated_at,
      },
      score: {
        practicality_score: summary.practicality_score,
        innovation_score: summary.innovation_score,
        total_score: summary.total_score,
        needs_human_review: summary.needs_human_review,
      },
      uploadStatus: 'uploaded',
      scoreStatus: summary.score_status === 'scored' ? 'scored' : 'idle',
      fileName: summary.file_name || `application_${summary.id}`,
      fileSize: 0,
      fileSizeLabel: '',
      fileType: summary.file_type || '',
      error: null,
    };

    if (existingIdx !== -1) {
      items.value[existingIdx] = { ...items.value[existingIdx], ...patch };
      return items.value[existingIdx].localId;
    }

    const localId = `server_${applicationId}`;
    items.value.unshift({
      localId,
      file: null,
      autoScore: false,
      extraction: null,
      detail: null,
      createdAt: Date.now(),
      ...patch,
    });
    return localId;
  }

  function enqueueBatch({ files = [], autoScore = true } = {}) {
    const authStore = useAuthStore();
    const fileList = Array.from(files || []);
    const createdLocalIds = [];

    fileList.forEach((file) => {
      const localId = generateLocalId();
      createdLocalIds.push(localId);
      items.value.unshift({
        localId,
        file,
        fileName: file.name,
        fileSize: file.size,
        fileSizeLabel: formatFileSize(file.size),
        fileType: inferFileType(file),
        uploadStatus: 'queued',
        scoreStatus: autoScore && authStore.isAdmin ? 'queued' : 'idle',
        autoScore: Boolean(autoScore) && authStore.isAdmin,
        applicationId: null,
        application: null,
        extraction: null,
        score: null,
        detail: null,
        error: null,
        createdAt: Date.now(),
      });
      queue.value.push(localId);
    });

    if (!selectedLocalId.value && createdLocalIds.length) {
      selectedLocalId.value = createdLocalIds[0];
    }

    pumpQueue();
  }

  function pumpQueue() {
    while (activeWorkers.value < maxConcurrent.value && queue.value.length) {
      const nextId = queue.value.shift();
      if (!nextId) break;
      const item = getItem(nextId);
      if (!item || item.uploadStatus !== 'queued') continue;
      activeWorkers.value += 1;
      processOne(nextId).finally(() => {
        activeWorkers.value -= 1;
        pumpQueue();
      });
    }
  }

  async function processOne(localId) {
    const item = getItem(localId);
    if (!item) return;

    updateItem(localId, { uploadStatus: 'uploading', error: null });

    try {
      const authStore = useAuthStore();
      const payload = await uploadApplicationFile(authStore.token, item.file);
      const applicationId = payload?.application?.id ?? null;
      updateItem(localId, {
        uploadStatus: 'uploaded',
        applicationId,
        application: payload?.application || null,
        extraction: payload?.extraction || null,
      });

      if (selectedLocalId.value === localId) {
        loadDetail(localId);
      }

      if (item.autoScore && applicationId) {
        await scoreOne(localId);
      }
    } catch (error) {
      updateItem(localId, {
        uploadStatus: 'failed',
        scoreStatus: item.autoScore ? 'failed' : 'idle',
        error: error?.message || String(error),
      });
    }
  }

  async function loadDetail(localId) {
    const item = getItem(localId);
    if (!item?.applicationId) return;
    if (detailLoadingLocalId.value === localId) return;

    detailLoadingLocalId.value = localId;
    try {
      const authStore = useAuthStore();
      const detail = await fetchApplicationDetail(authStore.token, item.applicationId);
      updateItem(localId, {
        detail,
        application: detail?.application || item.application,
        extraction: detail?.extraction || item.extraction,
        score: detail?.score || item.score,
      });
    } catch (error) {
      updateItem(localId, { error: error?.message || String(error) });
    } finally {
      if (detailLoadingLocalId.value === localId) {
        detailLoadingLocalId.value = null;
      }
    }
  }

  async function scoreOne(localId) {
    const authStore = useAuthStore();
    if (!authStore.isAdmin) return;
    const item = getItem(localId);
    if (!item?.applicationId) return;
    if (item.scoreStatus === 'scoring') return;

    updateItem(localId, { scoreStatus: 'scoring', error: null });
    try {
      const payload = await scoreApplication(authStore.token, item.applicationId);
      updateItem(localId, {
        scoreStatus: 'scored',
        score: payload?.score || item.score,
      });
      if (selectedLocalId.value === localId) {
        loadDetail(localId);
      }
    } catch (error) {
      updateItem(localId, { scoreStatus: 'failed', error: error?.message || String(error) });
    }
  }

  async function refreshFromServer(options = {}) {
    if (listLoading.value) return;
    const reloadDetail = options.reloadDetail !== false;
    const syncSelection = options.syncSelection !== false;
    listLoading.value = true;
    try {
      const authStore = useAuthStore();
      const list = await fetchApplications(authStore.token);
      if (Array.isArray(list)) {
        const serverIds = new Set();
        const localIds = [];
        list.forEach((summary) => {
          if (summary?.id) serverIds.add(summary.id);
          const localId = ensureServerItem(summary);
          if (localId) localIds.push(localId);
        });
        items.value = items.value.filter(item => item.file || !item.applicationId || serverIds.has(item.applicationId));
        if (syncSelection && (!selectedLocalId.value || !items.value.some(item => item.localId === selectedLocalId.value))) {
          selectedLocalId.value = localIds[0] || items.value[0]?.localId || null;
        }
        if (reloadDetail && selectedLocalId.value) {
          await loadDetail(selectedLocalId.value);
        }
      }
    } finally {
      listLoading.value = false;
    }
  }

  async function batchScoreByLocalIds(localIds = []) {
    const authStore = useAuthStore();
    if (!authStore.isAdmin) return;
    const targets = Array.from(new Set(localIds))
      .map(id => getItem(id))
      .filter(Boolean)
      .filter(item => Boolean(item.applicationId))
      .map(item => item.applicationId);

    if (!targets.length) return;

    try {
      const payload = await batchScoreApplications(authStore.token, targets);
      const results = payload?.results || [];
      results.forEach((r) => {
        const applicationId = r?.application_id;
        if (!applicationId) return;
        const idx = items.value.findIndex(item => item.applicationId === applicationId);
        if (idx === -1) return;
        items.value[idx] = {
          ...items.value[idx],
          scoreStatus: r?.success ? 'scored' : 'failed',
          score: r?.score || items.value[idx].score,
          error: r?.success ? null : (r?.error || items.value[idx].error),
        };
      });
    } catch (error) {
      const msg = error?.message || String(error);
      localIds.forEach((id) => {
        const item = getItem(id);
        if (!item) return;
        updateItem(id, { error: msg });
      });
    }
  }

  async function batchDeleteByLocalIds(localIds = []) {
    const authStore = useAuthStore();
    const targets = Array.from(new Set(localIds))
      .map(id => getItem(id))
      .filter(Boolean)
      .filter(item => Boolean(item.applicationId))
      .map(item => item.applicationId);

    if (!targets.length) return;

    await batchDeleteApplications(authStore.token, targets);
    items.value = items.value.filter(item => !targets.includes(item.applicationId));
    if (selectedLocalId.value && !items.value.some(item => item.localId === selectedLocalId.value)) {
      selectedLocalId.value = items.value[0]?.localId || null;
    }
  }

  function select(localId) {
    selectedLocalId.value = localId;
    loadDetail(localId);
  }

  return {
    items,
    selectedLocalId,
    selectedItem,
    hasPendingWork,
    detailLoadingLocalId,
    listLoading,
    enqueueBatch,
    select,
    scoreOne,
    loadDetail,
    refreshFromServer,
    batchScoreByLocalIds,
    batchDeleteByLocalIds,
  };
});

if (module.hot) {
  module.hot.accept(acceptHMRUpdate(useApplicationStore, module.hot));
}
