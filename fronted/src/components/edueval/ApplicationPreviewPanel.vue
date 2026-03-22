<template>
  <section class="panel edueval-panel-fill" style="overflow: visible;">
    <div class="panel-header">
      <div>
        <h2>申请书预览</h2>
        <p class="panel-subtitle">在列表中选择文件后，点击“预览申请书”进行查看。</p>
      </div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
        <span v-if="fileName" class="badge neutral">{{ fileName }}</span>
        <a
          v-if="absolutePreviewUrl"
          class="ghost-button"
          :href="absolutePreviewUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          新窗口打开
        </a>
        <a
          v-else-if="absoluteDownloadUrl"
          class="ghost-button"
          :href="absoluteDownloadUrl"
          target="_blank"
          rel="noopener noreferrer"
        >
          下载原文件
        </a>
      </div>
    </div>

    <div class="edueval-panel-body">
      <div v-if="!enabled" class="empty-state">点击“预览申请书”后将在此处显示预览。</div>
      <div v-else-if="!item" class="empty-state">请先从申请书列表中选择一份申请书。</div>
      <div v-else-if="absolutePreviewUrl" style="height: 720px; min-height: 520px; resize: vertical; overflow: hidden;">
        <iframe
          :src="absolutePreviewUrl"
          title="application preview"
          style="width: 100%; height: 100%; border: 1px solid var(--border); border-radius: 16px; background: var(--surface);"
        />
      </div>
      <div v-else-if="absoluteDownloadUrl" class="empty-state">
        当前文件类型暂不支持在线预览，请使用“下载原文件”查看。
      </div>
      <div v-else class="empty-state">
        暂无可用预览链接。
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';
import { getServerBase } from '../../services/eduevalApi';

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

const fileName = computed(() => props.item?.fileName || '');

function toAbsoluteUrl(path) {
  if (!path) return '';
  const raw = String(path);
  if (raw.startsWith('http://') || raw.startsWith('https://')) return raw;
  return `${getServerBase()}${raw.startsWith('/') ? '' : '/'}${raw}`;
}

const previewPath = computed(() => {
  const application = props.item?.detail?.application || props.item?.application || null;
  return application?.preview_url || '';
});

const downloadPath = computed(() => {
  const application = props.item?.detail?.application || props.item?.application || null;
  return application?.file_download_url || '';
});

const absolutePreviewUrl = computed(() => toAbsoluteUrl(previewPath.value));
const absoluteDownloadUrl = computed(() => toAbsoluteUrl(downloadPath.value));
</script>
