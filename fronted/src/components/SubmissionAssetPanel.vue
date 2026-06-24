<template>
  <section class="asset-panel">
    <div class="asset-panel-head">
      <div>
        <div class="asset-panel-title">{{ title }}</div>
        <div class="panel-subtitle">{{ description }}</div>
      </div>
      <div class="panel-subtitle">共 {{ uploadedAssets.length }} 个文件</div>
    </div>

    <div v-if="uploadedAssets.length === 0" class="empty-state asset-panel-empty">
      暂无可预览的已上传文件。
    </div>

    <div v-else class="asset-panel-grid">
      <article v-for="asset in uploadedAssets" :key="asset.id" class="asset-item-card">
        <div class="asset-item-top">
          <div>
            <div class="asset-item-name">{{ asset.file_name }}</div>
            <div class="panel-subtitle">{{ assetTypeLabel(asset.asset_type) }} · {{ previewTypeLabel(asset) }}</div>
          </div>
          <span class="asset-item-version">v{{ asset.version_no }}</span>
        </div>

        <div class="asset-item-meta">
          <span>{{ formatAssetSize(asset.file_size) }}</span>
          <span>{{ formatDateTime(asset.created_at) }}</span>
        </div>

        <div class="asset-item-actions">
          <button class="ghost-button compact-button" type="button" :disabled="!canPreviewAsset(asset)" @click="openPreview(asset)">
            {{ canPreviewAsset(asset) ? '预览' : '不可预览' }}
          </button>
          <button class="ghost-button compact-button" type="button" :disabled="downloadingAssetId === asset.id" @click="downloadAsset(asset)">
            {{ downloadingAssetId === asset.id ? '下载中...' : '下载' }}
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';
import { fetchSubmissionAssetBlob } from '../services/eduevalApi';
import { detectSubmissionAssetPreview, downloadBlob, formatFileSize } from '../utils/submissionAssetPreview';

const props = defineProps({
  submissionId: {
    type: [String, Number],
    required: true,
  },
  assets: {
    type: Array,
    default: () => [],
  },
  title: {
    type: String,
    default: '提交材料',
  },
  description: {
    type: String,
    default: '可预览支持的文件，也可以直接下载到本地。',
  },
});

const authStore = useAuthStore();
const router = useRouter();
const downloadingAssetId = ref(null);

const uploadedAssets = computed(() => {
  const list = Array.isArray(props.assets) ? props.assets : [];
  return [...list]
    .filter(item => String(item?.upload_status || '').toLowerCase() === 'uploaded')
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());
});

function assetTypeLabel(assetType) {
  const v = String(assetType || '').toLowerCase();
  if (v === 'report') return '报告';
  if (v === 'code_archive') return '代码压缩包';
  if (v === 'ppt') return 'PPT';
  if (v === 'video') return '演示视频';
  return String(assetType || '');
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
  if (!value) return '未知时间';
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return String(value || '未知时间');
  }
}

function openPreview(asset) {
  if (!asset?.id || !canPreviewAsset(asset)) return;
  router.push({
    name: 'submission-asset-preview',
    params: {
      submissionId: String(props.submissionId),
      assetId: String(asset.id),
    },
  });
}

async function downloadAsset(asset) {
  if (!asset?.id) return;
  downloadingAssetId.value = asset.id;
  try {
    const { blob } = await fetchSubmissionAssetBlob(authStore.token, asset.id);
    downloadBlob(blob, asset.file_name || 'download');
  } finally {
    downloadingAssetId.value = null;
  }
}
</script>

<style scoped>
.asset-panel {
  display: grid;
  gap: 12px;
}

.asset-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
  flex-wrap: wrap;
}

.asset-panel-title {
  font-weight: 800;
}

.asset-panel-empty {
  min-height: 120px;
}

.asset-panel-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 12px;
}

.asset-item-card {
  display: grid;
  gap: 12px;
  padding: 14px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.08), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.96));
}

.asset-item-top {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.asset-item-name {
  font-weight: 700;
  word-break: break-word;
}

.asset-item-version {
  white-space: nowrap;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(219, 234, 254, 0.92);
  color: #1d4ed8;
  font-size: 12px;
}

.asset-item-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: var(--text-secondary);
  font-size: 13px;
}

.asset-item-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
</style>
