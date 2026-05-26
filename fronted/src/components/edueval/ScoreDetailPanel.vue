<template>
  <section class="panel edueval-panel-fill" style="align-self: stretch;">
    <div class="panel-header">
      <div>
        <h2>{{ allowScoring ? '评分详情' : '申请书详情' }}</h2>
        <p class="panel-subtitle">
          {{ allowScoring ? '管理员可查看评分与复核信息' : '学生仅可查看自己的申请书基础信息与处理状态' }}
        </p>
      </div>
      <button
        v-if="item && allowScoring"
        class="primary-button"
        :disabled="!item.applicationId || item.scoreStatus === 'scoring'"
        @click="$emit('score', item.localId)"
      >
        {{ item?.scoreStatus === 'scoring' ? '评分中...' : '重新评分' }}
      </button>
    </div>

    <div class="edueval-panel-body">
      <div v-if="loading" class="empty-state">加载详情中...</div>
      <div v-else-if="!item" class="empty-state">请选择一份申请书查看详情。</div>
      <div v-else class="detail-stack">
        <p v-if="item.error" class="feedback error">{{ item.error }}</p>

        <section class="detail-block">
          <h3>申请信息</h3>
          <dl class="detail-grid">
            <div v-if="allowScoring">
              <dt>学生</dt>
              <dd>{{ (item.application?.student_name || item.detail?.application?.student_name) ?? '-' }}</dd>
            </div>
            <div v-if="allowScoring">
              <dt>学号</dt>
              <dd>{{ (item.application?.student_id || item.detail?.application?.student_id) ?? '-' }}</dd>
            </div>
            <div class="full-width">
              <dt>项目名称</dt>
              <dd>{{ (item.application?.project_title || item.detail?.application?.project_title) ?? '-' }}</dd>
            </div>
            <div class="full-width">
              <dt>文件名</dt>
              <dd>{{ item.fileName ?? '-' }}</dd>
            </div>
          </dl>
        </section>

        <section class="detail-block">
          <h3>状态</h3>
          <div style="display: flex; gap: 10px; flex-wrap: wrap;">
            <span :class="['badge', uploadBadge(item.uploadStatus)]">上传：{{ uploadLabel(item.uploadStatus) }}</span>
            <span v-if="allowScoring" :class="['badge', scoreBadge(item.scoreStatus)]">评分：{{ scoreLabel(item.scoreStatus) }}</span>
          </div>
        </section>

        <section class="detail-block">
          <h3>文本提取</h3>
          <p>{{ item?.detail?.extraction?.status || item?.extraction?.status || '-' }}</p>
        </section>

        <section v-if="allowScoring" class="detail-block">
          <h3>AI 评分结果</h3>
          <div v-if="!resolvedScore" class="empty-inline">尚未评分。</div>
          <template v-else>
            <div class="score-cards">
              <article class="score-card">
                <span>总分</span>
                <strong>{{ resolvedScore.total_score }}</strong>
              </article>
              <article class="score-card">
                <span>实用性</span>
                <strong>{{ resolvedScore.practicality_score }}</strong>
              </article>
              <article class="score-card">
                <span>创新性</span>
                <strong>{{ resolvedScore.innovation_score }}</strong>
              </article>
            </div>

            <div class="reason-block" style="margin-top: 10px;">
              <h4>复核</h4>
              <p>{{ resolvedScore.needs_human_review ? '需复核' : '正常' }}</p>
            </div>

            <div v-if="resolvedScore.practicality_reason" class="reason-block">
              <h4>实用性理由</h4>
              <p>{{ resolvedScore.practicality_reason }}</p>
            </div>
            <div v-if="resolvedScore.innovation_reason" class="reason-block">
              <h4>创新性理由</h4>
              <p>{{ resolvedScore.innovation_reason }}</p>
            </div>
            <div v-if="resolvedScore.strengths" class="reason-block">
              <h4>优点</h4>
              <p>{{ resolvedScore.strengths }}</p>
            </div>
            <div v-if="resolvedScore.weaknesses" class="reason-block">
              <h4>不足</h4>
              <p>{{ resolvedScore.weaknesses }}</p>
            </div>
          </template>
        </section>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue';

const props = defineProps({
  item: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  allowScoring: {
    type: Boolean,
    default: true,
  },
});

defineEmits(['score']);

const resolvedScore = computed(() => props.item?.detail?.score || props.item?.score || null);

function uploadLabel(status) {
  if (status === 'queued') return '排队';
  if (status === 'uploading') return '上传中';
  if (status === 'uploaded') return '完成';
  if (status === 'failed') return '失败';
  return status || '-';
}

function scoreLabel(status) {
  if (status === 'idle') return '未开始';
  if (status === 'queued') return '排队';
  if (status === 'scoring') return '评分中';
  if (status === 'scored') return '完成';
  if (status === 'failed') return '失败';
  return status || '-';
}

function uploadBadge(status) {
  if (status === 'uploaded') return 'ok';
  if (status === 'failed') return 'error';
  if (status === 'uploading') return 'info';
  return 'neutral';
}

function scoreBadge(status) {
  if (status === 'scored') return 'ok';
  if (status === 'failed') return 'error';
  if (status === 'scoring') return 'info';
  return 'neutral';
}
</script>
