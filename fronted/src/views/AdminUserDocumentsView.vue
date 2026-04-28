<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap;">
        <h2 style="margin: 0;">后台管理 · {{ typeLabel }}</h2>
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>

      <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

      <section class="panel" style="min-height: 0;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">用户 #{{ userId }} 的{{ typeLabel }}列表</h3>
            <p class="panel-subtitle">支持内嵌 Markdown 预览与 docx 导出。</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="loadList">刷新</button>
        </div>

        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="items.length === 0" class="empty-state">暂无{{ typeLabel }}。</div>

          <div v-else style="display: grid; gap: 10px;">
            <article v-for="item in items" :key="item.id" class="panel" style="padding: 14px; border-radius: 16px;">
              <div style="display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap;">
                <div style="min-width: 0;">
                  <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                    <strong style="font-size: 16px; line-height: 1.2; word-break: break-word;">{{ item.title }}</strong>
                    <span :class="['badge', item.status === 'draft' ? 'neutral' : 'ok']">{{ item.status === 'draft' ? '草稿' : '完成' }}</span>
                  </div>
                  <div class="panel-subtitle" style="margin: 6px 0 0;">
                    最近更新：{{ formatTime(item.updated_at) }}
                  </div>
                </div>

                <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end;">
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto;"
                    :disabled="previewingId === item.id"
                    @click="previewMarkdown(item)"
                  >
                    预览 md
                  </button>
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto;"
                    :disabled="downloadingId === item.id"
                    @click="downloadDocx(item)"
                  >
                    下载 docx
                  </button>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section v-if="previewTitle" class="panel" style="min-height: 0; margin-top: 16px;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">内嵌预览（md）</h3>
            <p class="panel-subtitle">{{ previewTitle }}</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" @click="clearPreview">关闭</button>
        </div>
        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="previewLoading" class="empty-state">加载中...</div>
          <div v-else-if="previewError" class="alert error">{{ previewError }}</div>
          <pre v-else class="panel" style="margin: 0; padding: 14px; border-radius: 16px; white-space: pre-wrap; word-break: break-word;">{{ previewMd }}</pre>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import {
  adminExportApplicationDraftDocx,
  adminExportTaskDraftDocx,
  adminFetchApplicationDraftMarkdown,
  adminFetchTaskDraftMarkdown,
  adminListUserApplicationDrafts,
  adminListUserTaskDrafts,
} from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const userId = computed(() => String(route.params.userId || ''));
const docType = computed(() => String(route.params.type || ''));

const items = ref([]);
const loading = ref(false);
const downloadingId = ref(null);
const previewingId = ref(null);
const localError = ref(null);

const errorMessage = computed(() => localError.value);
const typeLabel = computed(() => (docType.value === 'task' ? '任务书' : '申请书'));

const previewTitle = ref('');
const previewMd = ref('');
const previewLoading = ref(false);
const previewError = ref('');

function goBack() {
  router.push({ name: 'admin-users' });
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'document.docx';
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function loadList() {
  localError.value = null;
  loading.value = true;
  try {
    const list = docType.value === 'task'
      ? await adminListUserTaskDrafts(authStore.token, userId.value)
      : await adminListUserApplicationDrafts(authStore.token, userId.value);
    items.value = Array.isArray(list) ? list : [];
  } catch (e) {
    localError.value = e?.message || '加载失败';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

async function downloadDocx(item) {
  downloadingId.value = item.id;
  localError.value = null;
  try {
    const blob = docType.value === 'task'
      ? await adminExportTaskDraftDocx(authStore.token, userId.value, item.id)
      : await adminExportApplicationDraftDocx(authStore.token, userId.value, item.id);
    const nameBase = (item?.title || typeLabel.value).trim() || typeLabel.value;
    triggerDownload(blob, `${nameBase}.docx`);
  } catch (e) {
    localError.value = e?.message || '下载失败';
  } finally {
    downloadingId.value = null;
  }
}

function clearPreview() {
  previewTitle.value = '';
  previewMd.value = '';
  previewError.value = '';
  previewLoading.value = false;
  previewingId.value = null;
}

async function previewMarkdown(item) {
  previewingId.value = item.id;
  previewTitle.value = item?.title || '';
  previewError.value = '';
  previewLoading.value = true;
  try {
    const md = docType.value === 'task'
      ? await adminFetchTaskDraftMarkdown(authStore.token, userId.value, item.id)
      : await adminFetchApplicationDraftMarkdown(authStore.token, userId.value, item.id);
    previewMd.value = md || '';
  } catch (e) {
    previewError.value = e?.message || '加载失败';
    previewMd.value = '';
  } finally {
    previewLoading.value = false;
    previewingId.value = null;
  }
}

onMounted(() => {
  loadList();
});
</script>
