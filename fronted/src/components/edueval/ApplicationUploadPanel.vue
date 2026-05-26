<template>
  <section class="panel edueval-panel-fill">
    <div class="panel-header">
      <div>
        <h2>申请书上传</h2>
        <p class="panel-subtitle">支持 PDF / DOCX / TXT / MD。学生仅可查看自己的申请书，不显示评分。</p>
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
        <span>上传策略</span>
        <label v-if="allowScoring" class="checkbox-row">
          <input v-model="autoScore" type="checkbox" :disabled="submitting" />
          <span>上传后立即评分</span>
        </label>
        <span v-else class="panel-subtitle">普通用户没有评分查看与评分触发权限。</span>
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
const autoScore = ref(true);

const uploadButtonText = computed(() => (files.value.length ? `开始上传 (${files.value.length})` : '开始上传'));

function handleFileChange(event) {
  files.value = Array.from(event?.target?.files ?? []);
}

function submitForm() {
  emit('submit', { files: files.value, autoScore: props.allowScoring ? autoScore.value : false });
  files.value = [];
  autoScore.value = true;
  if (fileInputRef.value) {
    fileInputRef.value.value = '';
  }
}
</script>
