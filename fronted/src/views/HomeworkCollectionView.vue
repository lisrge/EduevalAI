<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 14px; align-content: start;">
      <div style="display: flex; justify-content: space-between; align-items: center; gap: 10px;">
        <div>
          <h2 style="margin: 0;">作业收集</h2>
          <p class="panel-subtitle">前端占位版：后续可把本地存储替换为后端 API。</p>
        </div>
        <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; min-height: 0;">
        <section
          v-for="card in cards"
          :key="card.key"
          class="panel"
          style="display: flex; flex-direction: column; min-height: 250px;"
        >
          <div class="panel-header" style="margin-bottom: 10px;">
            <div>
              <h2 style="margin: 0; font-size: 20px;">{{ card.label }}</h2>
              <p class="panel-subtitle">支持上传并查看历史版本。</p>
            </div>
          </div>

          <div class="edueval-panel-body" style="display: grid; gap: 10px;">
            <div class="panel-subtitle" style="margin: 0;">
              最近上传：
              <span style="color: var(--text-primary);">
                {{ latestText(card.key) }}
              </span>
            </div>

            <div class="form-actions" style="margin-top: auto;">
              <button class="primary-button" type="button" @click="triggerUpload(card.key)">上传</button>
              <button class="ghost-button danger-outline" type="button" :disabled="!latestByType(card.key)" @click="removeLatest(card.key)">删除</button>
              <button class="ghost-button" type="button" @click="goHistory(card.key)">查看历史</button>
            </div>

            <input
              :ref="(el) => setFileInputRef(card.key, el)"
              type="file"
              :accept="card.accept"
              style="display: none;"
              @change="onFileChange(card.key, $event)"
            />
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { HOMEWORK_TYPES, addHistoryItem, getHistoryByType, removeHistoryItem } from '../services/homeworkHistoryStore';

const router = useRouter();
const cards = HOMEWORK_TYPES;
const fileInputRefs = reactive({});
const versionMap = ref({});

function refreshAll() {
  const next = {};
  cards.forEach((card) => {
    next[card.key] = getHistoryByType(card.key);
  });
  versionMap.value = next;
}

function goBack() {
  router.push({ name: 'applications' });
}

function setFileInputRef(typeKey, el) {
  if (!el) return;
  fileInputRefs[typeKey] = el;
}

function triggerUpload(typeKey) {
  const input = fileInputRefs[typeKey];
  if (!input) return;
  input.click();
}

function onFileChange(typeKey, event) {
  const file = event?.target?.files?.[0];
  if (!file) return;

  // TODO(backend): 替换为上传接口，成功后由后端返回版本记录。
  addHistoryItem(typeKey, file);
  refreshAll();

  if (event?.target) {
    event.target.value = '';
  }
}

function latestByType(typeKey) {
  const list = versionMap.value[typeKey];
  if (!Array.isArray(list) || list.length === 0) return null;
  return list[0];
}

function latestText(typeKey) {
  const item = latestByType(typeKey);
  if (!item) return '暂无';
  return `${item.name}（${formatBytes(item.size)}）`;
}

function removeLatest(typeKey) {
  const item = latestByType(typeKey);
  if (!item) return;
  // TODO(backend): 替换为删除接口，包含权限校验与真实文件删除。
  removeHistoryItem(typeKey, item.id);
  refreshAll();
}

function goHistory(typeKey) {
  router.push({ name: 'homework-history', params: { type: typeKey } });
}

function formatBytes(size) {
  const value = Number(size || 0);
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  if (value < 1024 * 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  return `${(value / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

refreshAll();
</script>
