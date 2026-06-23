<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />
    <main class="import-shell">
      <header class="import-header">
        <div>
          <h2>申请书 / 任务书批量导入</h2>
          <p class="panel-subtitle">每组上传一份申请书和一份任务书。系统先解析预览，确认后再创建组和成员账号。</p>
        </div>
        <button class="ghost-button" type="button" @click="router.push({ name: 'admin-users' })">返回</button>
      </header>

      <section class="panel upload-panel">
        <input type="file" multiple accept=".docx,.pdf,.txt,.md" :disabled="loading" @change="selectFiles" />
        <div class="panel-subtitle">已选择 {{ files.length }} 个文件</div>
        <button class="primary-button" type="button" :disabled="loading || !files.length" @click="previewImport">
          {{ loading ? '解析中...' : '上传并解析' }}
        </button>
      </section>

      <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>
      <div v-if="message" class="panel" style="color: #166534;">{{ message }}</div>

      <section v-if="preview" class="panel" style="display: grid; gap: 14px;">
        <div class="import-header">
          <div>
            <strong>解析批次 #{{ preview.batch_id }}</strong>
            <div class="panel-subtitle">识别 {{ preview.groups.length }} 个组，文件 {{ preview.files.length }} 份</div>
          </div>
          <button class="primary-button" type="button" :disabled="loading || committed" @click="commitImport">确认创建组和用户</button>
        </div>

        <article v-for="group in preview.groups" :key="group.group_key" class="group-card">
          <div class="group-title">
            <strong>{{ group.team_name || '未命名组' }} · {{ group.project_name }}</strong>
            <span>{{ group.members.length }} 人</span>
          </div>
          <div class="edit-grid">
            <label>项目名称<input v-model.trim="group.project_name" class="edueval-input" /></label>
            <label>组名<input v-model.trim="group.team_name" class="edueval-input" /></label>
            <label>组长学号<input v-model.trim="group.leader_student_id" class="edueval-input" /></label>
            <label>Gitee<input v-model.trim="group.gitee_url" class="edueval-input" /></label>
          </div>
          <table>
            <thead><tr><th>姓名</th><th>学号</th><th>角色</th><th>个人博客</th></tr></thead>
            <tbody>
              <tr v-for="member in group.members" :key="member.student_id">
                <td><input v-model.trim="member.name" class="edueval-input" /></td>
                <td><input v-model.trim="member.student_id" class="edueval-input" /></td>
                <td><input v-model.trim="member.role" class="edueval-input" /></td>
                <td><input v-model.trim="member.blog_url" class="edueval-input" /></td>
              </tr>
            </tbody>
          </table>
          <div v-if="group.warnings.length" class="warning">{{ group.warnings.map(warningLabel).join('；') }}</div>
        </article>
      </section>

      <section v-if="credentials.length" class="panel">
        <div class="import-header">
          <strong>新账号初始密码（仅本次显示）</strong>
          <button class="ghost-button" type="button" @click="downloadCredentials">导出 CSV</button>
        </div>
        <table><thead><tr><th>姓名</th><th>学号</th><th>初始密码</th></tr></thead>
          <tbody><tr v-for="item in credentials" :key="item.student_id"><td>{{ item.real_name }}</td><td>{{ item.student_id }}</td><td>{{ item.initial_password }}</td></tr></tbody>
        </table>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { commitDocumentImport, previewDocumentImport } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const router = useRouter();
const authStore = useAuthStore();
const files = ref([]);
const preview = ref(null);
const credentials = ref([]);
const loading = ref(false);
const committed = ref(false);
const errorMessage = ref('');
const message = ref('');

function selectFiles(event) { files.value = Array.from(event.target.files || []); }
function warningLabel(value) { return { missing_application_document: '缺少申请书', duplicate_application_documents: '存在重复申请书（按同一组处理）', missing_task_document: '缺少任务书', duplicate_task_documents: '存在重复任务书（按同一组处理）', no_members_parsed: '未识别成员', leader_not_identified: '未识别组长', member_blog_url_missing: '成员博客地址不完整' }[value] || value; }

async function previewImport() {
  loading.value = true; errorMessage.value = ''; message.value = ''; committed.value = false; credentials.value = [];
  try { preview.value = await previewDocumentImport(authStore.token, files.value); }
  catch (error) { errorMessage.value = error?.message || '解析失败'; }
  finally { loading.value = false; }
}

async function commitImport() {
  loading.value = true; errorMessage.value = '';
  try {
    const result = await commitDocumentImport(authStore.token, preview.value.batch_id, preview.value.groups);
    credentials.value = result.credentials || [];
    committed.value = true;
    message.value = `导入完成：新建组 ${result.created_group_count} 个，更新/去重组 ${result.updated_group_count} 个，新建账号 ${credentials.value.length} 个。`;
  } catch (error) { errorMessage.value = error?.message || '导入失败'; }
  finally { loading.value = false; }
}

function downloadCredentials() {
  const escape = value => `"${String(value || '').replaceAll('"', '""')}"`;
  const rows = [['姓名', '学号', '初始密码'], ...credentials.value.map(item => [item.real_name, item.student_id, item.initial_password])];
  const blob = new Blob([`\ufeff${rows.map(row => row.map(escape).join(',')).join('\n')}`], { type: 'text/csv;charset=utf-8' });
  const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = '初始账号.csv'; anchor.click(); URL.revokeObjectURL(url);
}
</script>

<style scoped>
.import-shell { padding: 20px; display: grid; gap: 16px; }
.import-header, .group-title { display: flex; justify-content: space-between; gap: 12px; align-items: center; flex-wrap: wrap; }
.import-header h2 { margin: 0; }
.upload-panel { display: grid; gap: 12px; }
.edit-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.edit-grid label { display: grid; gap: 5px; }
.group-card { padding: 16px; border: 1px solid var(--border); border-radius: 18px; display: grid; gap: 10px; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 9px; text-align: left; border-bottom: 1px solid var(--border); }
.warning { color: #b45309; }
@media (max-width: 760px) { .edit-grid { grid-template-columns: 1fr; } }
</style>
