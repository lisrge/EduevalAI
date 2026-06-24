<template>
  <section class="panel edueval-panel-fill">
    <div class="panel-header">
      <div>
        <h2>申请书上传</h2>
        <p class="panel-subtitle">支持 PDF / DOCX / TXT / MD。学生仅可查看本组申请书，不显示评分。</p>
      </div>
    </div>

    <form class="upload-form edueval-panel-body" @submit.prevent="submitForm">
      <label class="field field-wide file-dropzone">
        <span>申请书文件</span>
        <input
          ref="fileInputRef"
          accept=".pdf,.docx,.txt,.md"
          type="file"
          multiple
          :disabled="submitting"
          @change="handleFileChange"
        />
        <small>当前已选择 {{ files.length }} 份文件。</small>
      </label>

      <div v-if="statusMessage" class="alert error field-wide">
        {{ statusMessage }}
      </div>

      <label class="field field-wide checkbox-field">
        <span>评分策略</span>
        <span class="panel-subtitle">上传后自动评分默认开启（后台处理）。</span>
      </label>

      <div v-if="files.length > 0" class="field field-wide">
        <span>待上传文件</span>
        <ul class="file-list">
          <li v-for="file in files" :key="file.name + '-' + file.size">{{ file.name }}</li>
        </ul>
      </div>

      <div class="form-actions field-wide">
        <button class="primary-button" type="submit" :disabled="submitting || files.length === 0">
          {{ submitting ? '处理中...' : uploadButtonText }}
        </button>
      </div>
    </form>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  submitting: {
    type: Boolean,
    default: false,
  },
  allowScoring: {
    type: Boolean,
    default: true,
  },
  statusMessage: {
    type: String,
    default: '',
  },
});

const emit = defineEmits(['submit']);

const fileInputRef = ref(null);
const files = ref([]);

const uploadButtonText = computed(() => (files.value.length ? `开始上传 (${files.value.length})` : '开始上传'));

function handleFileChange(event) {
  files.value = Array.from(event?.target?.files ?? []);
}

function submitForm() {
  emit('submit', { files: files.value, autoScore: true });
  files.value = [];
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
}
</script>

<style scoped>
.checkbox-field {
  align-items: start;
}

.checkbox-row {
  display: inline-flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: fit-content;
  margin-top: 6px;
}

.checkbox-row input {
  margin: 0;
}
</style>
