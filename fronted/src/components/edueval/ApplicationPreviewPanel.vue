<template>
  <section class="panel edueval-panel-fill" style="overflow: visible;">
    <div class="panel-header">
      <div>
        <h2>申请书预览</h2>
        <p class="panel-subtitle">在列表中选择文件后，点击“预览申请书”进行查看。</p>
      </div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
        <span v-if="fileName" class="badge neutral">{{ fileName }}</span>
        <button
          v-if="previewObjectUrl"
          class="ghost-button"
          type="button"
          @click="openPreviewInNewWindow"
        >
          新窗口打开
        </button>
        <button
          v-if="downloadAvailable"
          class="ghost-button"
          type="button"
          :disabled="loading"
          @click="downloadOriginalFile"
        >
          下载原文件
        </button>
      </div>
    </div>

    <div class="edueval-panel-body">
      <div v-if="!enabled" class="empty-state">点击“预览申请书”后将在此处显示预览。</div>
      <div v-else-if="!item" class="empty-state">请先从申请书列表中选择一份申请书。</div>
      <div v-else-if="loading" class="empty-state">正在加载预览...</div>
      <div v-else-if="loadError" class="empty-state">{{ loadError }}</div>
      <div v-else-if="previewObjectUrl" style="height: 720px; min-height: 520px; resize: vertical; overflow: hidden;">
        <iframe
          :src="previewObjectUrl"
          title="application preview"
          style="width: 100%; height: 100%; border: 1px solid var(--border); border-radius: 16px; background: var(--surface);"
        />
      </div>
      <div v-else-if="downloadAvailable" class="empty-state">
        当前文件类型暂不支持在线预览，请使用“下载原文件”查看。
      </div>
      <div v-else class="empty-state">
        暂无可用预览链接。
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { fetchApplicationFileBlob, fetchApplicationPreviewBlob } from '../../services/eduevalApi';
import { useAuthStore } from '../../stores/authStore';

const props = defineProps({
  enabled: {
    type: Boolean,
    default: false,
  },
  item: {
    type: Object,
    default: null,
  },
});

const authStore = useAuthStore();
const previewObjectUrl = ref('');
const downloadObjectUrl = ref('');
const loading = ref(false);
const loadError = ref('');

const fileName = computed(() => props.item?.fileName || '');
const applicationId = computed(() => {
  const application = props.item?.detail?.application || props.item?.application || null;
  return application?.id || props.item?.applicationId || null;
});

const previewPath = computed(() => {
  const application = props.item?.detail?.application || props.item?.application || null;
  return application?.preview_url || '';
});

const downloadPath = computed(() => {
  const application = props.item?.detail?.application || props.item?.application || null;
  return application?.file_download_url || '';
});

const downloadAvailable = computed(() => Boolean(downloadPath.value && downloadObjectUrl.value));

function revokeObjectUrl(value) {
  if (value) {
    try {
      URL.revokeObjectURL(value);
    } catch (e) {
      // Ignore object URL cleanup failures.
    }
  }
}

function resetResources() {
  revokeObjectUrl(previewObjectUrl.value);
  revokeObjectUrl(downloadObjectUrl.value);
  previewObjectUrl.value = '';
  downloadObjectUrl.value = '';
}

async function loadPreviewResources() {
  resetResources();
  loadError.value = '';
  if (!props.enabled || !applicationId.value) return;
  loading.value = true;
  try {
    if (previewPath.value) {
      const blob = await fetchApplicationPreviewBlob(authStore.token, applicationId.value);
      previewObjectUrl.value = URL.createObjectURL(blob);
    }
    if (downloadPath.value) {
      const blob = await fetchApplicationFileBlob(authStore.token, applicationId.value);
      downloadObjectUrl.value = URL.createObjectURL(blob);
    }
  } catch (error) {
    loadError.value = error?.message || '加载申请书失败';
  } finally {
    loading.value = false;
  }
}

function openPreviewInNewWindow() {
  if (!previewObjectUrl.value) return;
  window.open(previewObjectUrl.value, '_blank', 'noopener,noreferrer');
}

function downloadOriginalFile() {
  if (!downloadObjectUrl.value) return;
  const link = document.createElement('a');
  link.href = downloadObjectUrl.value;
  link.download = fileName.value || 'application';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

watch(
  () => [props.enabled, applicationId.value, previewPath.value, downloadPath.value],
  () => {
    loadPreviewResources();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  resetResources();
});
</script>
