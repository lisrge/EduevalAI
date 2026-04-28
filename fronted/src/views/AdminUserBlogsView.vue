<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: space-between; margin-bottom: 12px; gap: 12px; flex-wrap: wrap;">
        <h2 style="margin: 0;">后台管理 · 博客</h2>
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>

      <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

      <section class="panel" style="min-height: 0;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">用户 #{{ userId }} 的博客列表</h3>
            <p class="panel-subtitle">支持内嵌 Markdown 预览；博客内容与判定结果由后端接口提供。</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" :disabled="loading" @click="loadList">刷新</button>
        </div>

        <div class="edueval-panel-body" style="overflow: auto;">
          <div v-if="loading" class="empty-state">加载中...</div>
          <div v-else-if="items.length === 0" class="empty-state">暂无博客（等待后端接入爬虫接口）。</div>

          <table v-else style="width: 100%; border-collapse: collapse;">
            <thead>
              <tr style="text-align: left; border-bottom: 1px solid var(--border);">
                <th style="padding: 10px 8px;">标题</th>
                <th style="padding: 10px 8px;">链接</th>
                <th style="padding: 10px 8px;">状态</th>
                <th style="padding: 10px 8px;">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in items" :key="b.id" style="border-bottom: 1px solid var(--border);">
                <td style="padding: 10px 8px; font-weight: 700;">{{ b.title }}</td>
                <td style="padding: 10px 8px;">
                  <a
                    :href="b.url"
                    target="_blank"
                    rel="noopener noreferrer"
                    class="ghost-button"
                    style="width: auto; display: inline-flex;"
                    :style="{ opacity: b.url ? 1 : 0.5, pointerEvents: b.url ? 'auto' : 'none' }"
                  >
                    打开
                  </a>
                </td>
                <td style="padding: 10px 8px;">
                  <span :style="{ color: statusColor(b.status), fontWeight: 800 }">{{ statusLabel(b.status) }}</span>
                </td>
                <td style="padding: 10px 8px;">
                  <button
                    class="ghost-button"
                    type="button"
                    style="width: auto;"
                    :disabled="previewingId === b.id"
                    @click="previewBlog(b)"
                  >
                    预览 md
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
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
import { adminFetchUserBlogMarkdown, adminListUserBlogs } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const userId = computed(() => String(route.params.userId || ''));

const items = ref([]);
const loading = ref(false);
const localError = ref(null);
const previewingId = ref(null);

const errorMessage = computed(() => localError.value);

const previewTitle = ref('');
const previewMd = ref('');
const previewLoading = ref(false);
const previewError = ref('');

function goBack() {
  router.push({ name: 'admin-users' });
}

function statusLabel(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'normal') return '正常';
  if (v === 'abnormal') return '不正常';
  return status || '-';
}

function statusColor(status) {
  const v = String(status || '').toLowerCase();
  if (v === 'normal') return '#16a34a';
  if (v === 'abnormal') return '#ef4444';
  return 'var(--text-secondary)';
}

async function loadList() {
  localError.value = null;
  loading.value = true;
  try {
    const list = await adminListUserBlogs(authStore.token, userId.value);
    items.value = Array.isArray(list) ? list : [];
  } catch (e) {
    localError.value = e?.message || '加载失败';
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function clearPreview() {
  previewTitle.value = '';
  previewMd.value = '';
  previewError.value = '';
  previewLoading.value = false;
  previewingId.value = null;
}

async function previewBlog(b) {
  previewingId.value = b.id;
  previewTitle.value = b?.title || '';
  previewError.value = '';
  previewLoading.value = true;
  try {
    const md = await adminFetchUserBlogMarkdown(authStore.token, userId.value, b.id);
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
