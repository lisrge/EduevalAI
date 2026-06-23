<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; display: grid; gap: 14px;">
      <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
        <div>
          <h2 style="margin: 0;">工作量汇总</h2>
          <p class="panel-subtitle" style="margin-top: 6px;">汇总 git、非 git、博客记录和个人陈述，生成成员工作画像。</p>
        </div>
        <div style="display: flex; gap: 10px; flex-wrap: wrap;">
          <button class="ghost-button" type="button" style="width: auto;" @click="loadAll">刷新</button>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>
      </div>

      <section class="panel" style="display: grid; gap: 8px;">
        <div style="font-weight: 700;">{{ summary?.project_name || '未填写项目名称' }}</div>
        <div class="panel-subtitle">小组：{{ summary?.group_name || '未填写小组' }}</div>
        <div class="panel-subtitle">仓库绑定：{{ summary?.has_repo_binding ? '已绑定' : '未绑定' }}</div>
        <div class="panel-subtitle">博客文章：{{ summary?.total_blog_posts ?? 0 }}</div>
        <div v-if="summary?.risk_flags?.length" class="panel-subtitle">风险提示：{{ summary.risk_flags.join(', ') }}</div>
      </section>

      <div v-if="errorMessage" class="panel" style="padding: 14px; color: #b91c1c;">{{ errorMessage }}</div>

      <section class="panel" style="display: grid; gap: 12px;">
        <div style="font-weight: 700;">成员工作量排名</div>
        <div v-if="!summary?.members?.length" class="panel-subtitle">暂无成员数据。</div>
        <div v-for="item in summary?.members || []" :key="item.student_id" class="panel" style="padding: 14px; display: grid; gap: 8px;">
          <div style="display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
            <strong>#{{ item.rank_order }} {{ item.student_name }} / {{ item.student_id }}</strong>
            <span style="font-weight: 700; color: #2563eb;">工作量指数 {{ item.workload_index }}</span>
          </div>
          <div class="panel-subtitle">
            角色：{{ item.project_role || '未填写' }} / 来源：{{ item.contribution_source }} / 博客 {{ item.blog_post_count }} 篇 / 工作项 {{ item.blog_work_item_count }}
          </div>
          <div class="panel-subtitle" v-if="item.blog_code_dump_count || item.blog_popular_science_count">
            纯代码倾向 {{ item.blog_code_dump_count }} / 科普 {{ item.blog_popular_science_count }}
          </div>
          <div>{{ item.summary_text }}</div>
          <ul v-if="item.work_items?.length" style="margin: 0; padding-left: 20px; line-height: 1.7;">
            <li v-for="workItem in item.work_items" :key="workItem">{{ workItem }}</li>
          </ul>
          <div class="form-actions" style="display: flex; gap: 10px; flex-wrap: wrap;">
            <button class="ghost-button" type="button" style="width: auto;" @click="goStudentView(item)">查看竖屏页</button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { fetchSubmissionWorkloadSummary } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const summary = ref(null);
const errorMessage = ref('');

function goBack() {
  router.push({ name: 'admin-submissions' });
}

function goStudentView(item) {
  router.push({ name: 'student-workload-summary', params: { submissionId: route.params.submissionId, studentId: item.student_id } });
}

async function loadAll() {
  errorMessage.value = '';
  try {
    summary.value = await fetchSubmissionWorkloadSummary(authStore.token, Number(route.params.submissionId || 0));
  } catch (error) {
    errorMessage.value = error?.message || '加载失败';
  }
}

onMounted(() => {
  loadAll();
});
</script>
