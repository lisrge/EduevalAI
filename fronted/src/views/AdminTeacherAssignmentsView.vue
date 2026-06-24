<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: grid; gap: 14px;">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">后台管理 / 教师分配</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">为当前提交分配评审老师，并查看评分进度。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="ghost-button" type="button" style="width: auto;" @click="goScore">去评分端</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回总览</button>
        </div>
      </div>

      <div v-if="errorMessage" class="panel" style="padding: 14px; color: #b91c1c;">{{ errorMessage }}</div>

      <section class="panel" style="display: grid; gap: 12px;">
        <div v-if="loading" class="empty-state">加载中...</div>
        <template v-else-if="submission">
          <div>
            <h3 style="margin: 0 0 6px;">{{ submission.project_name || '未填写项目名' }}</h3>
            <p class="panel-subtitle" style="margin: 0;">
              {{ submission.group_name || '未填写小组' }} · {{ submission.student_name }} · {{ submission.student_id }}
            </p>
          </div>

          <div style="display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;">
            <div class="panel" style="padding: 12px;">
              <div class="panel-subtitle">已分配老师</div>
              <div style="font-size: 24px; font-weight: 800;">{{ assignmentState?.assigned_teachers?.length || 0 }}</div>
            </div>
            <div class="panel" style="padding: 12px;">
              <div class="panel-subtitle">已评分人数</div>
              <div style="font-size: 24px; font-weight: 800;">{{ assignmentState?.aggregate?.score_count || 0 }}</div>
            </div>
            <div class="panel" style="padding: 12px;">
              <div class="panel-subtitle">平均总分</div>
              <div style="font-size: 24px; font-weight: 800;">{{ assignmentState?.aggregate?.average_total_score || 0 }}</div>
            </div>
          </div>
        </template>
      </section>

      <section class="panel">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h3 style="margin: 0;">可分配老师</h3>
            <p class="panel-subtitle">教师和管理员都可以加入评审。</p>
          </div>
          <button class="primary-button" type="button" style="width: auto;" :disabled="saving || loading" @click="saveAssignments">
            {{ saving ? '保存中...' : '保存分配' }}
          </button>
        </div>

        <div v-if="teachers.length === 0" class="empty-state">当前没有可分配老师。</div>
        <div v-else style="display: grid; gap: 10px;">
          <label
            v-for="teacher in teachers"
            :key="teacher.id"
            class="panel"
            style="padding: 12px; display: flex; justify-content: space-between; align-items: center; gap: 12px;"
          >
            <div>
              <div style="font-weight: 700;">{{ teacher.student_id }}</div>
              <div class="panel-subtitle">{{ normalizedRoleLabel(teacher.role) }}</div>
            </div>
            <input v-model="selectedTeacherIds" type="checkbox" :value="teacher.id" />
          </label>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { adminListUsers, fetchSubmissionDetail, fetchTeacherAssignmentState, updateTeacherAssignments } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const submission = ref(null);
const assignmentState = ref(null);
const teachers = ref([]);
const selectedTeacherIds = ref([]);
const loading = ref(false);
const saving = ref(false);
const errorMessage = ref('');

function normalizedRoleLabel(role) {
  const value = String(role || '').toLowerCase();
  if (value === 'admin') return '管理员';
  if (value === 'teacher') return '教师';
  return '普通用户';
}

function goBack() {
  router.push({ name: 'admin-submissions' });
}

function goScore() {
  if (!submission.value) return;
  router.push({
    name: 'teacher-reviews',
    query: {
      assignmentId: String(submission.value.assignment_id),
      submissionId: String(submission.value.id),
    },
  });
}

async function loadPage() {
  loading.value = true;
  errorMessage.value = '';
  try {
    const submissionId = Number(route.params.submissionId || 0);
    const [detail, state, users] = await Promise.all([
      fetchSubmissionDetail(authStore.token, submissionId),
      fetchTeacherAssignmentState(authStore.token, submissionId),
      adminListUsers(authStore.token),
    ]);
    submission.value = detail || null;
    assignmentState.value = state || null;
    teachers.value = (Array.isArray(users) ? users : []).filter(item => ['teacher', 'admin'].includes(String(item.role || '').toLowerCase()));
    selectedTeacherIds.value = (state?.assigned_teachers || [])
      .map(item => Number(item.teacher_user_id || 0))
      .filter(value => value > 0);
  } catch (error) {
    errorMessage.value = error?.message || '加载失败';
  } finally {
    loading.value = false;
  }
}

async function saveAssignments() {
  saving.value = true;
  errorMessage.value = '';
  try {
    const submissionId = Number(route.params.submissionId || 0);
    const normalizedTeacherIds = Array.from(new Set(
      (Array.isArray(selectedTeacherIds.value) ? selectedTeacherIds.value : [])
        .map(item => Number(item || 0))
        .filter(value => value > 0),
    ));
    const payload = await updateTeacherAssignments(authStore.token, submissionId, normalizedTeacherIds);
    assignmentState.value = payload || assignmentState.value;
    selectedTeacherIds.value = (payload?.assigned_teachers || [])
      .map(item => Number(item.teacher_user_id || 0))
      .filter(value => value > 0);
  } catch (error) {
    errorMessage.value = error?.message || '保存失败';
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  loadPage();
});
</script>
