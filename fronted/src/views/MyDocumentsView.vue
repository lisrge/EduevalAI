<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0;">
      <div style="display: flex; justify-content: flex-end; margin-bottom: 12px;">
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>
      <div v-if="successMessage" class="alert success" style="margin-bottom: 12px;">{{ successMessage }}</div>
      <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; min-height: 0;">
        <section class="panel" style="min-height: 0; display: flex; flex-direction: column;">
          <div class="panel-header" style="margin-bottom: 10px;">
            <div>
              <h2 style="margin: 0;">我的申请书</h2>
              <p class="panel-subtitle">自动保存草稿，可随时上传。</p>
            </div>
            <button class="primary-button" type="button" @click="createNew('application')">+ 新建申请书</button>
          </div>

          <div class="edueval-panel-body" style="overflow: auto;">
            <div v-if="loadingApplications" class="empty-state">加载中...</div>
            <div v-else-if="applications.length === 0" class="empty-state">暂无申请书。</div>
            <div v-else style="display: grid; gap: 10px;">
              <article
                v-for="item in applications"
                :key="'a-' + item.id"
                class="panel"
                style="padding: 14px; border-radius: 16px; cursor: pointer;"
                @click="openEditor('application', item.id)"
              >
                <div style="display: flex; justify-content: space-between; gap: 12px; align-items: flex-start;">
                  <div style="min-width: 0;">
                    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                      <strong style="font-size: 16px; line-height: 1.2; word-break: break-word;">{{ item.title }}</strong>
                      <span :class="['badge', item.status === 'draft' ? 'neutral' : 'ok']">{{ item.status === 'draft' ? '草稿' : '完成' }}</span>
                    </div>
                    <div class="panel-subtitle" style="margin: 6px 0 0;">
                      最近更新：{{ formatTime(item.updated_at) }}
                    </div>
                  </div>

                  <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end;" @click.stop>
                    <button class="ghost-button" type="button" style="width: auto;" @click="openEditor('application', item.id)">查看/修改</button>
                    <button class="ghost-button" type="button" style="width: auto;" @click="uploadDraft('application', item)">上传</button>
                    <button class="ghost-button danger-outline" type="button" style="width: auto;" @click="removeDraft('application', item)">删除</button>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </section>

        <section class="panel" style="min-height: 0; display: flex; flex-direction: column;">
          <div class="panel-header" style="margin-bottom: 10px;">
            <div>
              <h2 style="margin: 0;">我的任务书</h2>
              <p class="panel-subtitle">任务书与申请书分开管理。</p>
            </div>
            <button class="primary-button" type="button" @click="createNew('task')">+ 新建任务书</button>
          </div>

          <div class="edueval-panel-body" style="overflow: auto;">
            <div v-if="loadingTasks" class="empty-state">加载中...</div>
            <div v-else-if="tasks.length === 0" class="empty-state">暂无任务书。</div>
            <div v-else style="display: grid; gap: 10px;">
              <article
                v-for="item in tasks"
                :key="'t-' + item.id"
                class="panel"
                style="padding: 14px; border-radius: 16px; cursor: pointer;"
                @click="openEditor('task', item.id)"
              >
                <div style="display: flex; justify-content: space-between; gap: 12px; align-items: flex-start;">
                  <div style="min-width: 0;">
                    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                      <strong style="font-size: 16px; line-height: 1.2; word-break: break-word;">{{ item.title }}</strong>
                      <span :class="['badge', item.status === 'draft' ? 'neutral' : 'ok']">{{ item.status === 'draft' ? '草稿' : '完成' }}</span>
                    </div>
                    <div class="panel-subtitle" style="margin: 6px 0 0;">
                      最近更新：{{ formatTime(item.updated_at) }}
                    </div>
                  </div>

                  <div style="display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end;" @click.stop>
                    <button class="ghost-button" type="button" style="width: auto;" @click="openEditor('task', item.id)">查看/修改</button>
                    <button class="ghost-button" type="button" style="width: auto;" @click="uploadDraft('task', item)">上传</button>
                    <button class="ghost-button danger-outline" type="button" style="width: auto;" @click="removeDraft('task', item)">删除</button>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { useAuthStore } from '../stores/authStore';
import {
  deleteApplicationDraft,
  deleteTaskDraft,
  exportApplicationDraftDocx,
  exportTaskDraftDocx,
  fetchApplicationDraft,
  fetchTaskDraft,
  listApplicationDrafts,
  listTaskDrafts,
  uploadApplicationFile,
} from '../services/eduevalApi';

const authStore = useAuthStore();
const router = useRouter();

const applications = ref([]);
const tasks = ref([]);
const loadingApplications = ref(false);
const loadingTasks = ref(false);
const localError = ref(null);
const localSuccess = ref(null);
const uploadingId = ref(null);

const errorMessage = computed(() => localError.value);
const successMessage = computed(() => localSuccess.value);

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function openEditor(type, id) {
  router.push({ name: 'document-edit', params: { type, id: String(id) } });
}

function createNew(type) {
  router.push({ name: 'document-new', params: { type } });
}

function goBack() {
  router.push({ name: 'applications' });
}

async function loadAll() {
  localError.value = null;
  loadingApplications.value = true;
  loadingTasks.value = true;
  try {
    const [a, t] = await Promise.all([
      listApplicationDrafts(authStore.token),
      listTaskDrafts(authStore.token),
    ]);
    applications.value = Array.isArray(a) ? a : [];
    tasks.value = Array.isArray(t) ? t : [];
  } catch (e) {
    localError.value = e?.message || '加载失败';
  } finally {
    loadingApplications.value = false;
    loadingTasks.value = false;
  }
}

async function removeDraft(type, item) {
  localError.value = null;
  try {
    if (type === 'application') {
      await deleteApplicationDraft(authStore.token, item.id);
    } else {
      await deleteTaskDraft(authStore.token, item.id);
    }
    await loadAll();
  } catch (e) {
    localError.value = e?.message || '删除失败';
  }
}

async function uploadDraft(type, item) {
  localError.value = null;
  localSuccess.value = null;
  uploadingId.value = `${type}:${item?.id}`;
  try {
    const detail = type === 'application'
      ? await fetchApplicationDraft(authStore.token, item.id)
      : await fetchTaskDraft(authStore.token, item.id);

    const blob = type === 'application'
      ? await exportApplicationDraftDocx(authStore.token, item.id)
      : await exportTaskDraftDocx(authStore.token, item.id);

    const fileNameBase = (item?.title || (type === 'application' ? '申请书' : '任务书')).trim() || (type === 'application' ? '申请书' : '任务书');
    const file = new File([blob], `${fileNameBase}.docx`, {
      type: blob?.type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    const content = detail?.content || {};
    const meta = type === 'application'
      ? {
        student_name: content?.leader_name,
        student_id: content?.participants?.[0]?.student_id,
        project_title: content?.project_name,
      }
      : {
        student_name: content?.leader_name,
        student_id: '',
        project_title: content?.project_name,
      };
    await uploadApplicationFile(authStore.token, file, meta);
    localSuccess.value = '上传成功';
    setTimeout(() => {
      localSuccess.value = null;
    }, 2000);
  } catch (e) {
    const msg = e?.message || String(e);
    if (msg.includes('duplicate application')) {
      localError.value = '不能上传相同的申请书';
    } else
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
      localError.value = '上传失败：无法连接后端服务（请确认后端已启动且 8001 端口可访问）';
    } else {
      localError.value = msg || '上传失败';
    }
  } finally {
    uploadingId.value = null;
  }
}

onMounted(() => {
  loadAll();
});
</script>
