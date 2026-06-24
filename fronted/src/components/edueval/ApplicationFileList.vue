<template>
  <section class="panel edueval-panel-fill">
    <div class="panel-header">
      <div>
        <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
          <h2>申请书列表</h2>
          <div class="badge neutral">{{ filteredItems.length }} / {{ items.length }}</div>
        </div>
      </div>
      <div class="action-grid" style="width: 100%;">
        <button class="ghost-button" type="button" @click="refreshList">刷新列表</button>
        <button v-if="allowScoring" class="ghost-button" type="button" :disabled="selectedIds.length === 0" @click="batchScore">
          批量评分
        </button>
        <button v-if="allowScoring" class="ghost-button danger-outline" type="button" :disabled="selectedIds.length === 0" @click="batchDelete">
          批量删除 ({{ selectedIds.length }})
        </button>
        <button v-if="allowScoring" class="ghost-button" type="button" @click="exportCsv">导出 CSV</button>
        <button v-if="allowScoring" class="ghost-button" type="button" @click="exportXlsx">导出 XLSX</button>
        <button class="ghost-button" type="button" :disabled="!canPreview" @click="previewSelected">预览申请书</button>
      </div>
    </div>

    <div class="edueval-panel-body" style="display: flex; flex-direction: column; gap: 10px; overflow: hidden;">
      <input
        v-model="searchText"
        class="search-input"
        type="text"
        :placeholder="allowScoring ? '搜索学生姓名、学号、项目名' : '搜索本组申请书'"
      />

      <div class="pill-row">
        <button type="button" class="pill" :class="{ active: activeTab === 'all' }" @click="activeTab = 'all'">
          全部 ({{ tabCounts.all }})
        </button>
        <button v-if="allowScoring" type="button" class="pill" :class="{ active: activeTab === 'scored' }" @click="activeTab = 'scored'">
          已评分 ({{ tabCounts.scored }})
        </button>
        <button v-if="allowScoring" type="button" class="pill" :class="{ active: activeTab === 'review' }" @click="activeTab = 'review'">
          待复核 ({{ tabCounts.review }})
        </button>
        <button type="button" class="pill" :class="{ active: activeTab === 'extract_failed' }" @click="activeTab = 'extract_failed'">
          处理失败 ({{ tabCounts.extract_failed }})
        </button>
      </div>

      <div v-if="firstError" class="alert error">{{ firstError }}</div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th v-if="allowScoring" style="width: 44px;">
                <input
                  type="checkbox"
                  :checked="allSelected"
                  :indeterminate.prop="someSelected && !allSelected"
                  @click.stop
                  @change="toggleAll($event.target.checked)"
                />
              </th>
              <th>{{ allowScoring ? '学生' : '文件名' }}</th>
              <th>项目名称</th>
              <th v-if="allowScoring">实用性</th>
              <th v-if="allowScoring">创新性</th>
              <th v-if="allowScoring">总分</th>
              <th>上传状态</th>
              <th v-if="allowScoring">复核</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="item in filteredItems"
              :key="item.localId"
              :class="{ selected: item.localId === selectedLocalId }"
              @click="$emit('select', item.localId)"
            >
              <td v-if="allowScoring">
                <input type="checkbox" :checked="selectedIdSet.has(item.localId)" @click.stop @change="toggleOne(item.localId, $event.target.checked)" />
              </td>
              <td>{{ primaryLabel(item) }}</td>
              <td>{{ projectLabel(item) }}</td>
              <td v-if="allowScoring">{{ scoreField(item, 'practicality_score') }}</td>
              <td v-if="allowScoring">{{ scoreField(item, 'innovation_score') }}</td>
              <td v-if="allowScoring">{{ scoreField(item, 'total_score') }}</td>
              <td>
                <span :class="['badge', uploadBadge(item.uploadStatus)]">{{ uploadLabel(item.uploadStatus) }}</span>
              </td>
              <td v-if="allowScoring">
                <span v-if="typeof resolvedScore(item)?.needs_human_review === 'boolean'" :class="['badge', resolvedScore(item).needs_human_review ? 'warn' : 'ok']">
                  {{ resolvedScore(item).needs_human_review ? '需复核' : '正常' }}
                </span>
                <span v-else class="empty-inline">-</span>
              </td>
              <td>
                <button
                  v-if="allowScoring"
                  class="table-button"
                  :disabled="item.uploadStatus !== 'uploaded' || item.scoreStatus === 'scoring'"
                  @click.stop="$emit('score', item.localId)"
                >
                  {{ item.scoreStatus === 'scoring' ? '评分中...' : '评分' }}
                </button>
                <div v-else class="student-action-row">
                  <button class="table-button" @click.stop="$emit('select', item.localId)">
                    查看详情
                  </button>
                  <button class="table-button" :disabled="!canPreviewItem(item)" @click.stop="$emit('preview', item.localId)">
                    预览申请书
                  </button>
                </div>
              </td>
            </tr>
            <tr v-if="filteredItems.length === 0">
              <td :colspan="allowScoring ? 9 : 4" class="empty-state">暂无数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  selectedLocalId: {
    type: String,
    default: null,
  },
  allowScoring: {
    type: Boolean,
    default: true,
  },
});

const emit = defineEmits(['select', 'score', 'preview', 'refresh', 'batch-score', 'batch-delete', 'export']);

const searchText = ref('');
const activeTab = ref('all');
const selectedIds = ref([]);

const selectedIdSet = computed(() => new Set(selectedIds.value));
const canPreview = computed(() => Boolean(props.selectedLocalId));

const tabCounts = computed(() => {
  const counts = { all: 0, scored: 0, review: 0, extract_failed: 0 };
  const list = Array.isArray(props.items) ? props.items : [];
  counts.all = list.length;
  list.forEach((item) => {
    const score = resolvedScore(item);
    const extractionStatus = item?.detail?.extraction?.status || item?.extraction?.status || '';
    if (item?.scoreStatus === 'scored') counts.scored += 1;
    if (score?.needs_human_review === true) counts.review += 1;
    if (extractionStatus === 'extract_failed' || item?.uploadStatus === 'failed') counts.extract_failed += 1;
  });
  return counts;
});

const filteredItems = computed(() => {
  const list = Array.isArray(props.items) ? props.items : [];
  const q = String(searchText.value || '').trim().toLowerCase();
  return list.filter((item) => {
    const application = item?.detail?.application || item?.application || null;
    const extractionStatus = item?.detail?.extraction?.status || item?.extraction?.status || '';
    const score = resolvedScore(item);

    if (activeTab.value === 'scored' && item?.scoreStatus !== 'scored') return false;
    if (activeTab.value === 'review' && score?.needs_human_review !== true) return false;
    if (activeTab.value === 'extract_failed' && !(extractionStatus === 'extract_failed' || item?.uploadStatus === 'failed')) return false;

    if (!q) return true;

    const haystack = [
      application?.student_name,
      application?.student_id,
      application?.project_title,
      item?.fileName,
    ]
      .filter(Boolean)
      .map(v => String(v).toLowerCase())
      .join(' ');

    return haystack.includes(q);
  });
});

const allSelected = computed(() => {
  if (!filteredItems.value.length) return false;
  const set = selectedIdSet.value;
  return filteredItems.value.every(item => set.has(item.localId));
});

const someSelected = computed(() => {
  if (!filteredItems.value.length) return false;
  const set = selectedIdSet.value;
  return filteredItems.value.some(item => set.has(item.localId));
});

const firstError = computed(() => {
  for (const item of filteredItems.value) {
    if (item?.error) return String(item.error);
  }
  return '';
});

function toggleOne(localId, checked) {
  const next = new Set(selectedIds.value);
  if (checked) next.add(localId);
  else next.delete(localId);
  selectedIds.value = Array.from(next);
}

function toggleAll(checked) {
  if (checked) {
    const next = new Set(selectedIds.value);
    filteredItems.value.forEach(item => next.add(item.localId));
    selectedIds.value = Array.from(next);
    return;
  }
  const next = new Set(selectedIds.value);
  filteredItems.value.forEach(item => next.delete(item.localId));
  selectedIds.value = Array.from(next);
}

function refreshList() {
  searchText.value = '';
  activeTab.value = 'all';
  emit('refresh');
}

function batchScore() {
  emit('batch-score', selectedIds.value);
}

function batchDelete() {
  emit('batch-delete', selectedIds.value);
  selectedIds.value = [];
}

function exportCsv() {
  emit('export', 'csv');
}

function exportXlsx() {
  emit('export', 'xlsx');
}

function previewSelected() {
  const localId = props.selectedLocalId || filteredItems.value?.[0]?.localId || null;
  if (localId) emit('preview', localId);
}

function canPreviewItem(item) {
  const application = item?.detail?.application || item?.application || null;
  return Boolean(application?.preview_url || application?.file_download_url);
}

function resolvedScore(item) {
  return item?.detail?.score || item?.score || null;
}

function primaryLabel(item) {
  const application = item?.detail?.application || item?.application || null;
  if (!props.allowScoring) return application?.file_name || item?.fileName || '-';
  const raw = (application?.student_name || '').trim();
  return raw && raw.toLowerCase() !== 'unknown' ? raw : '-';
}

function projectLabel(item) {
  const application = item?.detail?.application || item?.application || null;
  return application?.project_title || '-';
}

function scoreField(item, key) {
  const score = resolvedScore(item);
  const value = score?.[key];
  return value === 0 ? 0 : (value || '-');
}

function uploadLabel(status) {
  if (status === 'queued') return '排队';
  if (status === 'uploading') return '上传中';
  if (status === 'uploaded') return '完成';
  if (status === 'failed') return '失败';
  return status || '-';
}

function uploadBadge(status) {
  if (status === 'uploaded') return 'ok';
  if (status === 'failed') return 'error';
  if (status === 'uploading') return 'info';
  return 'neutral';
}
</script>

<style scoped>
.student-action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
</style>
