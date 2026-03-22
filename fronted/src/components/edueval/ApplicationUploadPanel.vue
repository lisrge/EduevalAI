<template>
  <section class="panel edueval-panel-fill">
    <div class="panel-header">
      <div>
        <h2>批量上传申请书</h2>
        <p class="panel-subtitle">支持 PDF / DOCX / TXT / MD，上传后可自动评分。</p>
      </div>
    </div>

    <form class="upload-form edueval-panel-body" @submit.prevent="submitForm">
      <label class="field field-wide file-dropzone">
        <span>申请书文件</span>
        <input ref="fileInputRef" accept=".pdf,.docx,.txt,.md" type="file" multiple :disabled="submitting" @change="handleFileChange" />
        <small>可一次选择多份申请书。当前已选择 {{ files.length }} 份。</small>
      </label>

      <label class="field field-wide checkbox-field">
        <span>上传策略</span>
        <label class="checkbox-row">
          <input v-model="autoScore" type="checkbox" :disabled="submitting" />
          <span>上传后立即评分</span>
        </label>
      </label>

      <div v-if="files.length > 0" class="field field-wide">
        <span>待上传文件</span>
        <ul class="file-list">
          <li v-for="file in files" :key="file.name + '-' + file.size">{{ file.name }}</li>
        </ul>
      </div>

      <div class="form-actions field-wide">
        <button class="primary-button" type="submit" :disabled="submitting || files.length === 0">
          {{ submitting ? '上传处理中...' : uploadButtonText }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';

defineProps({
  submitting: {
    type: Boolean,
    default: false,
  },
});

const emit = defineEmits(['submit']);

const fileInputRef = ref(null);
const files = ref([]);
const autoScore = ref(true);
const uploadButtonText = computed(() => (files.value.length ? `开始上传 (${files.value.length})` : '开始上传'));

function handleFileChange(event) {
  files.value = Array.from(event?.target?.files ?? []);
}

function submitForm() {
  emit('submit', { files: files.value, autoScore: autoScore.value });

  files.value = [];
  autoScore.value = true;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
}
</script>
