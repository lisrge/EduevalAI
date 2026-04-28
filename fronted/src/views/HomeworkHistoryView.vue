<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 14px; align-content: start;">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px;">
        <div>
          <h2 style="margin: 0;">{{ titleText }} 历史版本</h2>
          <p class="panel-subtitle">显示上传时间、文件大小；删除和详情为前端占位能力。</p>
        </div>
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>

      <section class="panel edueval-panel-fill">
        <div class="edueval-panel-body" style="display: grid; gap: 10px;">
          <div v-if="items.length === 0" class="empty-state">暂无历史版本。</div>

          <div v-else class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th style="width: 34%;">文件名</th>
                  <th style="width: 22%;">上传时间</th>
                  <th style="width: 14%;">文件大小</th>
                  <th style="width: 30%;">操作</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in items" :key="item.id">
                  <td>{{ item.name }}</td>
                  <td>{{ formatTime(item.uploadedAt) }}</td>
                  <td>{{ formatBytes(item.size) }}</td>
                  <td>
                    <div class="form-actions">
                      <button class="ghost-button danger-outline" type="button" @click="removeItem(item.id)">删除</button>
                      <button class="ghost-button" type="button" disabled title="后续接后端详情接口">查看文件详情</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { HOMEWORK_TYPES, getHistoryByType, removeHistoryItem } from '../services/homeworkHistoryStore';

const router = useRouter();
const route = useRoute();

const typeKey = computed(() => String(route.params.type || 'source'));
const typeMeta = computed(() => HOMEWORK_TYPES.find((item) => item.key === typeKey.value) || HOMEWORK_TYPES[0]);
const titleText = computed(() => typeMeta.value?.label || '文件');

const items = ref([]);

function refresh() {
  items.value = getHistoryByType(typeKey.value);
}

function goBack() {
  router.push({ name: 'homework' });
}

function removeItem(itemId) {
  // TODO(backend): 替换为历史版本删除接口，返回新的版本列表。
  removeHistoryItem(typeKey.value, itemId);
  refresh();
}

function formatTime(value) {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString();
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

refresh();
</script>
