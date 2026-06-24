<template>
  <div class="edueval-skin edueval-page">
    <ChatHeader />

    <div class="page-wrapper asset-preview-page">
      <section class="asset-preview-hero">
        <div>
          <p class="hero-eyebrow">文件预览</p>
          <h2>{{ asset?.file_name || '文件预览' }}</h2>
          <p class="hero-copy">
            {{ previewInfo.label }} · {{ formatFileSize(asset?.file_size) }} · {{ assetTypeLabel(asset?.asset_type) }}
          </p>
        </div>
        <div class="asset-preview-actions">
          <button class="ghost-button" type="button" style="width: auto;" :disabled="downloading" @click="downloadCurrent">
            {{ downloading ? '下载中...' : '下载文件' }}
          </button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

      <section class="asset-preview-shell">
        <aside class="asset-preview-meta">
          <div class="meta-card">
            <span class="meta-label">文件类型</span>
            <strong>{{ previewInfo.label }}</strong>
          </div>
          <div class="meta-card">
            <span class="meta-label">上传时间</span>
            <strong>{{ formatTime(asset?.created_at) }}</strong>
          </div>
          <div class="meta-card">
            <span class="meta-label">上传状态</span>
            <strong>{{ assetStatusLabel(asset?.upload_status) }}</strong>
          </div>
          <div class="meta-card">
            <span class="meta-label">MIME</span>
            <strong>{{ asset?.mime_type || '未知' }}</strong>
          </div>
        </aside>

        <main class="asset-preview-stage">
          <div v-if="loading" class="preview-empty">正在加载文件...</div>

          <div v-else-if="(previewInfo.type === 'pdf' || previewInfo.type === 'presentation') && objectUrl" class="preview-frame-wrap">
            <iframe class="preview-frame" :src="objectUrl" title="pdf-preview"></iframe>
          </div>

          <div v-else-if="previewInfo.type === 'image' && objectUrl" class="image-preview-wrap">
            <img class="image-preview" :src="objectUrl" :alt="asset?.file_name || 'image-preview'" />
          </div>

          <div v-else-if="previewInfo.type === 'word'" class="document-preview-wrap">
            <div v-if="htmlContent" class="document-preview-html" v-html="htmlContent"></div>
            <div v-else class="preview-empty">
              当前 Word 文件暂不支持直接解析，已为你保留下载按钮。
            </div>
          </div>

          <div v-else-if="previewInfo.type === 'excel'" class="sheet-preview-wrap">
            <template v-if="sheetNames.length">
              <div class="sheet-tabs">
                <button
                  v-for="sheetName in sheetNames"
                  :key="sheetName"
                  type="button"
                  :class="['sheet-tab', { active: sheetName === activeSheetName }]"
                  @click="activeSheetName = sheetName"
                >
                  {{ sheetName }}
                </button>
              </div>
              <div class="sheet-table-wrap">
                <table>
                  <tbody>
                    <tr v-for="(row, rowIndex) in activeSheetRows" :key="`${activeSheetName}-${rowIndex}`">
                      <td v-for="(cell, cellIndex) in row" :key="`${activeSheetName}-${rowIndex}-${cellIndex}`">
                        {{ cell }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </template>
            <div v-else class="preview-empty">没有可显示的表格内容。</div>
          </div>

          <div v-else-if="previewInfo.type === 'video'" class="video-preview-wrap">
            <video
              ref="videoElement"
              class="video-js vjs-default-skin vjs-big-play-centered preview-video"
              controls
              preload="auto"
            ></video>
          </div>

          <div v-else-if="previewInfo.type === 'archive'" class="preview-empty preview-hint">
            <strong>压缩包不支持在线预览</strong>
            <span>浏览器会触发下载，你也可以点击上方“下载文件”保存到本地后查看。</span>
          </div>

          <div v-else class="preview-empty preview-hint">
            <strong>当前文件类型暂不支持在线预览</strong>
            <span>可以直接点击上方“下载文件”在本地打开。</span>
          </div>
        </main>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import * as XLSX from 'xlsx';
import mammoth from 'mammoth';
import videojs from 'video.js';
import 'video.js/dist/video-js.css';
import ChatHeader from '../components/ChatHeader.vue';
import { fetchSubmissionAssetBlob, fetchSubmissionAssetPreviewBlob, fetchSubmissionDetail } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';
import { detectSubmissionAssetPreview, downloadBlob, formatFileSize, needsServerSidePreview } from '../utils/submissionAssetPreview';
import { translateUploadStatus } from '../utils/statusText';

const route = useRoute();
const router = useRouter();
const authStore = useAuthStore();

const loading = ref(false);
const downloading = ref(false);
const errorMessage = ref('');
const submission = ref(null);
const asset = ref(null);
const objectUrl = ref('');
const htmlContent = ref('');
const sheetRows = ref({});
const activeSheetName = ref('');
const videoElement = ref(null);
let videoPlayer = null;

const previewInfo = computed(() => detectSubmissionAssetPreview(asset.value));
const sheetNames = computed(() => Object.keys(sheetRows.value || {}));
const activeSheetRows = computed(() => {
  const name = activeSheetName.value || sheetNames.value[0] || '';
  return Array.isArray(sheetRows.value?.[name]) ? sheetRows.value[name] : [];
});

function cleanupObjectUrl() {
  if (objectUrl.value) {
    URL.revokeObjectURL(objectUrl.value);
    objectUrl.value = '';
  }
}

function disposeVideoPlayer() {
  if (videoPlayer) {
    videoPlayer.dispose();
    videoPlayer = null;
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back();
    return;
  }
  router.push({ name: authStore.isAdmin ? 'admin-submissions' : 'homework' });
}

function formatTime(value) {
  if (!value) return '未知';
  try {
    return new Date(value).toLocaleString();
  } catch (error) {
    return String(value || '未知');
  }
}

function assetStatusLabel(status) {
  return translateUploadStatus(status);
}

function assetTypeLabel(assetType) {
  const value = String(assetType || '').trim().toLowerCase();
  if (!value) return '附件';
  if (value === 'report') return '报告';
  if (value === 'code_archive') return '代码压缩包';
  if (value === 'ppt') return 'PPT';
  if (value === 'video') return '演示视频';
  if (value === 'attachment') return '附件';
  return String(assetType || '附件');
}

async function downloadCurrent() {
  if (!asset.value?.id) return;
  downloading.value = true;
  errorMessage.value = '';
  try {
    const { blob } = await fetchSubmissionAssetBlob(authStore.token, asset.value.id);
    downloadBlob(blob, asset.value.file_name || 'download');
  } catch (error) {
    errorMessage.value = error?.message || '下载失败';
  } finally {
    downloading.value = false;
  }
}

async function loadPreviewData() {
  const submissionId = Number(route.params.submissionId || 0);
  const assetId = Number(route.params.assetId || 0);
  if (!submissionId || !assetId) {
    errorMessage.value = '预览参数无效';
    return;
  }

  loading.value = true;
  errorMessage.value = '';
  htmlContent.value = '';
  sheetRows.value = {};
  activeSheetName.value = '';
  cleanupObjectUrl();
  disposeVideoPlayer();

  try {
    submission.value = await fetchSubmissionDetail(authStore.token, submissionId);
    asset.value = Array.isArray(submission.value?.assets)
      ? submission.value.assets.find(item => Number(item.id) === assetId) || null
      : null;
    if (!asset.value) {
      throw new Error('未找到对应文件');
    }

    const previewType = previewInfo.value.type;
    const useServerPreview = previewType === 'presentation' || needsServerSidePreview(asset.value);
    const { blob } = useServerPreview
      ? await fetchSubmissionAssetPreviewBlob(authStore.token, assetId)
      : await fetchSubmissionAssetBlob(authStore.token, assetId);

    if (previewType === 'pdf' || previewType === 'image' || previewType === 'video' || previewType === 'presentation') {
      objectUrl.value = URL.createObjectURL(blob);
    } else if (previewType === 'word') {
      const extension = String(asset.value?.file_name || '').toLowerCase();
      if (extension.endsWith('.docx')) {
        const arrayBuffer = await blob.arrayBuffer();
        const result = await mammoth.convertToHtml({ arrayBuffer });
        htmlContent.value = result.value || '';
      }
    } else if (previewType === 'excel') {
      const arrayBuffer = await blob.arrayBuffer();
      const workbook = XLSX.read(arrayBuffer, { type: 'array' });
      const rowsBySheet = {};
      for (const name of workbook.SheetNames) {
        rowsBySheet[name] = XLSX.utils.sheet_to_json(workbook.Sheets[name], {
          header: 1,
          raw: false,
          blankrows: true,
        });
      }
      sheetRows.value = rowsBySheet;
      activeSheetName.value = workbook.SheetNames[0] || '';
    }

    if (previewType === 'video' && objectUrl.value) {
      await nextTick();
      if (videoElement.value) {
        videoPlayer = videojs(videoElement.value, {
          controls: true,
          preload: 'auto',
          fluid: true,
          controlBar: {
            pictureInPictureToggle: false,
          },
        });
        videoPlayer.src({
          src: objectUrl.value,
          type: asset.value?.mime_type || blob.type || 'video/mp4',
        });
      }
    }
  } catch (error) {
    errorMessage.value = error?.message || '加载预览失败';
  } finally {
    loading.value = false;
  }
}

watch(
  () => [route.params.submissionId, route.params.assetId],
  () => {
    loadPreviewData();
  },
);

onMounted(() => {
  loadPreviewData();
});

onBeforeUnmount(() => {
  cleanupObjectUrl();
  disposeVideoPlayer();
});
</script>

<style scoped>
.asset-preview-page {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 18px;
}

.asset-preview-hero {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 22px 24px;
  border-radius: 28px;
  border: 1px solid rgba(37, 99, 235, 0.14);
  background:
    radial-gradient(circle at top right, rgba(59, 130, 246, 0.12), transparent 38%),
    linear-gradient(145deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.95));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
}

.asset-preview-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.asset-preview-shell {
  min-height: 0;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  gap: 16px;
}

.asset-preview-meta {
  display: grid;
  gap: 12px;
  align-content: start;
}

.meta-card {
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: rgba(255, 255, 255, 0.84);
}

.meta-label {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}

.asset-preview-stage {
  min-height: 72vh;
  border-radius: 28px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background:
    linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(255, 255, 255, 0.98));
  box-shadow: 0 18px 40px rgba(15, 23, 42, 0.08);
  overflow: hidden;
}

.preview-empty {
  min-height: 72vh;
  display: grid;
  place-items: center;
  padding: 32px;
  text-align: center;
  color: var(--muted);
}

.preview-hint {
  gap: 8px;
}

.preview-frame-wrap,
.image-preview-wrap,
.document-preview-wrap,
.sheet-preview-wrap,
.video-preview-wrap {
  min-height: 72vh;
}

.preview-frame {
  width: 100%;
  height: 72vh;
  border: 0;
  background: #f8fafc;
}

.image-preview-wrap {
  display: grid;
  place-items: center;
  padding: 24px;
  background:
    linear-gradient(45deg, rgba(226, 232, 240, 0.38) 25%, transparent 25%),
    linear-gradient(-45deg, rgba(226, 232, 240, 0.38) 25%, transparent 25%),
    linear-gradient(45deg, transparent 75%, rgba(226, 232, 240, 0.38) 75%),
    linear-gradient(-45deg, transparent 75%, rgba(226, 232, 240, 0.38) 75%);
  background-size: 24px 24px;
  background-position: 0 0, 0 12px, 12px -12px, -12px 0;
}

.image-preview {
  max-width: 100%;
  max-height: 68vh;
  border-radius: 22px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.18);
}

.document-preview-wrap {
  overflow: auto;
  padding: 28px;
}

.document-preview-html {
  max-width: 920px;
  margin: 0 auto;
  padding: 32px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.98);
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.08);
}

.document-preview-html :deep(img) {
  max-width: 100%;
}

.sheet-preview-wrap {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
}

.sheet-tabs {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  padding: 18px 18px 0;
}

.sheet-tab {
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  padding: 8px 14px;
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
}

.sheet-tab.active {
  border-color: rgba(37, 99, 235, 0.24);
  background: rgba(219, 234, 254, 0.9);
  color: #1d4ed8;
}

.sheet-table-wrap {
  overflow: auto;
  padding: 18px;
}

.sheet-table-wrap table {
  width: max-content;
  min-width: 100%;
  border-collapse: collapse;
  background: rgba(255, 255, 255, 0.94);
}

.sheet-table-wrap td {
  min-width: 120px;
  padding: 10px 12px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  vertical-align: top;
}

.video-preview-wrap {
  padding: 18px;
}

.preview-video {
  width: 100%;
  min-height: 68vh;
  border-radius: 24px;
  overflow: hidden;
}

@media (max-width: 980px) {
  .asset-preview-shell {
    grid-template-columns: 1fr;
  }

  .asset-preview-hero {
    flex-direction: column;
  }

  .asset-preview-actions {
    width: 100%;
    justify-content: flex-start;
  }
}
</style>
