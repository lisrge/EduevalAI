<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; flex: 1; min-height: 0; display: flex; justify-content: center;">
      <section class="panel" style="width: 980px; max-width: 100%; min-height: 0; display: flex; flex-direction: column;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div style="min-width: 0;">
            <h2 style="margin: 0; word-break: break-word;">{{ pageTitle }}</h2>
            <p class="panel-subtitle" style="margin-top: 6px;">
              {{ saveHint }}
            </p>
          </div>

          <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
            <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
            <button class="ghost-button" type="button" style="width: auto;" :disabled="busy" @click="downloadDocx">下载 DOCX</button>
            <button class="primary-button" type="button" :disabled="busy" @click="uploadNow">上传</button>
            <button class="ghost-button danger-outline" type="button" style="width: auto;" :disabled="busy" @click="removeDraft">删除</button>
          </div>
        </div>

        <div v-if="successMessage" class="alert success" style="margin-bottom: 12px;">{{ successMessage }}</div>
        <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">{{ errorMessage }}</div>

        <div class="edueval-panel-body" style="overflow: auto; display: grid; gap: 18px;">
          <section class="detail-block">
            <h3>基本信息</h3>
            <div class="upload-form" style="grid-template-columns: 1fr;">
              <label class="field field-wide">
                <span>标题</span>
                <input v-model="draft.title" type="text" placeholder="请输入标题" />
              </label>
            </div>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>申请书内容（2026版）</h3>

            <div class="upload-form" style="grid-template-columns: 1fr 1fr;">
              <label class="field">
                <span>项目编号（申请人不必填写）</span>
                <input v-model="draft.content.project_number" type="text" placeholder="" />
              </label>
              <label class="field">
                <span>项目名称</span>
                <input v-model="draft.content.project_name" type="text" placeholder="" />
              </label>
              <label class="field">
                <span>团队负责人</span>
                <input v-model="draft.content.leader_name" type="text" placeholder="" />
              </label>
              <label class="field">
                <span>手机号码</span>
                <input v-model="draft.content.leader_phone" type="text" placeholder="" />
              </label>
              <label class="field">
                <span>项目开始日期</span>
                <input v-model="draft.content.start_date" type="date" />
              </label>
              <label class="field">
                <span>项目结束日期</span>
                <input v-model="draft.content.end_date" type="date" />
              </label>
              <label class="field field-wide">
                <span>项目目标</span>
                <textarea v-model="draft.content.project_goal" class="search-input" style="min-height: 120px; height: auto; padding: 12px 14px;" placeholder=""></textarea>
              </label>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px;">
              <h3 style="margin: 0;">技术要点（最多 5 个）</h3>
              <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
                <button class="ghost-button" type="button" style="width: auto;" :disabled="draft.content.tech_points.length >= 5" @click="addTechPoint">+ 添加</button>
              </div>
            </div>

            <div style="display: grid; gap: 10px;">
              <div
                v-for="(tp, idx) in draft.content.tech_points"
                :key="'tp-' + idx"
                style="display: flex; gap: 10px; align-items: center;"
              >
                <input v-model="draft.content.tech_points[idx]" class="search-input" style="height: 44px; padding: 10px 12px; flex: 1;" />
                <button
                  class="ghost-button danger-outline"
                  type="button"
                  style="width: auto;"
                  :disabled="draft.content.tech_points.length <= 1"
                  @click="removeTechPoint(idx)"
                >
                  删除
                </button>
              </div>
            </div>

            <div class="upload-form" style="grid-template-columns: 1fr 1fr;">
              <label class="field">
                <span>指导教师</span>
                <input v-model="draft.content.teacher" type="text" placeholder="（先不填）" />
              </label>
              <label class="field">
                <span>团队名称</span>
                <input v-model="draft.content.team_name" type="text" placeholder="" />
              </label>
            </div>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>参加人员（3-4人，第一行为负责人）</h3>

            <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
              <button class="ghost-button" type="button" style="width: auto;" :disabled="draft.content.participants.length >= 4" @click="addParticipant">+ 添加成员</button>
              <button class="ghost-button danger-outline" type="button" style="width: auto;" :disabled="draft.content.participants.length <= 3" @click="removeParticipant">移除最后一行</button>
            </div>

            <div style="overflow: auto;">
              <table style="width: 100%; border-collapse: collapse;">
                <thead>
                  <tr>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">姓名</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">学号</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">专业</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">手机号码</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">电子邮箱</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">项目分工</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">电子签名</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(p, idx) in draft.content.participants" :key="'p-' + idx">
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="p.name" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="p.student_id" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="p.major" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="p.phone" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="p.email" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="p.role" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <div style="display: grid; gap: 8px;">
                        <img
                          v-if="p.signature_data_url"
                          :src="p.signature_data_url"
                          alt="signature"
                          style="width: 140px; max-width: 100%; height: 70px; object-fit: contain; border: 1px solid var(--border); border-radius: 10px; background: var(--surface);"
                        />
                        <input
                          type="file"
                          accept="image/*"
                          @change="onParticipantSignatureChange(idx, $event)"
                        />
                        <button
                          v-if="p.signature_data_url"
                          class="ghost-button danger-outline"
                          type="button"
                          style="width: auto; justify-self: flex-start;"
                          @click="clearParticipantSignature(idx)"
                        >
                          清除
                        </button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <label class="field">
              <span>其他人员</span>
              <textarea v-model="draft.content.other_people" class="search-input" style="min-height: 80px; height: auto; padding: 12px 14px;"></textarea>
            </label>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>项目资料地址</h3>
            <div class="upload-form" style="grid-template-columns: 1fr;">
              <label class="field">
                <span>项目博客地址</span>
                <input v-model="draft.content.project_blog_url" type="text" />
              </label>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-top: 12px;">
              <h3 style="margin: 0;">成员个人博客地址</h3>
              <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
                <button class="ghost-button" type="button" style="width: auto;" :disabled="draft.content.member_blog_urls.length >= 10" @click="addMemberBlog">+ 添加</button>
              </div>
            </div>

            <div style="display: grid; gap: 10px;">
              <div
                v-for="(url, idx) in draft.content.member_blog_urls"
                :key="'blog-' + idx"
                style="display: flex; gap: 10px; align-items: center;"
              >
                <input v-model="draft.content.member_blog_urls[idx]" class="search-input" style="height: 44px; padding: 10px 12px; flex: 1;" />
                <button
                  class="ghost-button danger-outline"
                  type="button"
                  style="width: auto;"
                  :disabled="draft.content.member_blog_urls.length <= 1"
                  @click="removeMemberBlog(idx)"
                >
                  删除
                </button>
              </div>
            </div>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>项目介绍</h3>
            <textarea v-model="draft.content.project_intro" class="search-input" style="min-height: 180px; height: auto; padding: 12px 14px;"></textarea>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>实施计划</h3>
            <textarea v-model="draft.content.plan" class="search-input" style="min-height: 180px; height: auto; padding: 12px 14px;"></textarea>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>预期成果</h3>
            <textarea v-model="draft.content.expected_results" class="search-input" style="min-height: 140px; height: auto; padding: 12px 14px;"></textarea>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>指导教师评语</h3>
            <textarea v-model="draft.content.teacher_comment" class="search-input" style="min-height: 100px; height: auto; padding: 12px 14px;"></textarea>
          </section>

          <section v-if="docType === 'application'" class="detail-block">
            <h3>申请承诺日期</h3>
            <input v-model="draft.content.commitment_date" class="search-input" style="height: 44px; padding: 10px 12px;" type="date" />
          </section>

          <section v-if="docType === 'task'" class="detail-block">
            <h3>任务书内容</h3>
            <div class="upload-form" style="grid-template-columns: 1fr 1fr;">
              <label class="field">
                <span>项目名称</span>
                <input v-model="draft.content.project_name" type="text" />
              </label>
              <label class="field">
                <span>团队名称</span>
                <input v-model="draft.content.team_name" type="text" />
              </label>
              <label class="field">
                <span>负责人</span>
                <input v-model="draft.content.leader_name" type="text" />
              </label>
              <label class="field">
                <span>联系方式</span>
                <input v-model="draft.content.leader_phone" type="text" />
              </label>
              <label class="field">
                <span>开始日期</span>
                <input v-model="draft.content.start_date" type="date" />
              </label>
              <label class="field">
                <span>结束日期</span>
                <input v-model="draft.content.end_date" type="date" />
              </label>
            </div>

            <label class="field">
              <span>任务目标</span>
              <textarea v-model="draft.content.objectives" class="search-input" style="min-height: 120px; height: auto; padding: 12px 14px;"></textarea>
            </label>

            <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px;">
              <h3 style="margin: 0;">任务分解与分工</h3>
              <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
                <button class="ghost-button" type="button" style="width: auto;" @click="addRole">+ 添加分工</button>
              </div>
            </div>

            <div style="overflow: auto;">
              <table style="width: 100%; border-collapse: collapse;">
                <thead>
                  <tr>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">成员</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">职责</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">交付物</th>
                    <th style="padding: 8px; border-bottom: 1px solid var(--border); width: 90px;">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(r, idx) in draft.content.roles" :key="'r-' + idx">
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="r.name" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="r.responsibility" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="r.deliverable" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border); text-align: center;">
                      <button class="ghost-button danger-outline" type="button" style="width: auto;" @click="removeRole(idx)">删除</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div style="display: flex; justify-content: space-between; align-items: center; gap: 12px;">
              <h3 style="margin: 0;">阶段计划</h3>
              <div style="display: flex; gap: 10px; flex-wrap: wrap; justify-content: flex-end;">
                <button class="ghost-button" type="button" style="width: auto;" @click="addMilestone">+ 添加阶段</button>
              </div>
            </div>

            <div style="overflow: auto;">
              <table style="width: 100%; border-collapse: collapse;">
                <thead>
                  <tr>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">阶段</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">起止</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">工作内容</th>
                    <th style="text-align: left; padding: 8px; border-bottom: 1px solid var(--border);">阶段产出</th>
                    <th style="padding: 8px; border-bottom: 1px solid var(--border); width: 90px;">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(m, idx) in draft.content.milestones" :key="'m-' + idx">
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="m.phase" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
                        <input v-model="m.start" class="search-input" style="height: 40px; padding: 8px 10px;" type="date" />
                        <input v-model="m.end" class="search-input" style="height: 40px; padding: 8px 10px;" type="date" />
                      </div>
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="m.work" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border);">
                      <input v-model="m.deliverable" class="search-input" style="height: 40px; padding: 8px 10px;" />
                    </td>
                    <td style="padding: 8px; border-bottom: 1px solid var(--border); text-align: center;">
                      <button class="ghost-button danger-outline" type="button" style="width: auto;" @click="removeMilestone(idx)">删除</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <label class="field">
              <span>风险与应对</span>
              <textarea v-model="draft.content.risks" class="search-input" style="min-height: 100px; height: auto; padding: 12px 14px;"></textarea>
            </label>

            <label class="field">
              <span>验收标准</span>
              <textarea v-model="draft.content.acceptance" class="search-input" style="min-height: 100px; height: auto; padding: 12px 14px;"></textarea>
            </label>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { useAuthStore } from '../stores/authStore';
import {
  createApplicationDraft,
  createTaskDraft,
  deleteApplicationDraft,
  deleteTaskDraft,
  exportApplicationDraftDocx,
  exportTaskDraftDocx,
  fetchApplicationDraft,
  fetchTaskDraft,
  updateApplicationDraft,
  updateTaskDraft,
  uploadApplicationFile,
} from '../services/eduevalApi';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const localError = ref(null);
const localSuccess = ref(null);
const busy = ref(false);
const saveState = ref('idle');
const draftId = ref(null);
const initialized = ref(false);
const dirty = ref(false);

const docType = computed(() => {
  const t = String(route.params.type || '').toLowerCase();
  if (t === 'application' || t === 'task') return t;
  return 'application';
});

const pageTitle = computed(() => (docType.value === 'application' ? '填写申请书' : '填写任务书'));
const errorMessage = computed(() => localError.value);
const successMessage = computed(() => localSuccess.value);
const saveHint = computed(() => {
  if (saveState.value === 'saving') return '自动保存中...';
  if (saveState.value === 'saved') return '已自动保存';
  if (saveState.value === 'error') return '自动保存失败（请检查网络）';
  if (dirty.value) return '将自动保存草稿';
  return '';
});

function defaultApplicationContent() {
  return {
    project_number: '',
    project_name: '',
    leader_name: '',
    leader_phone: '',
    start_date: '',
    end_date: '',
    project_goal: '',
    tech_points: [''],
    teacher: '',
    team_name: '',
    participants: [
      { name: '', student_id: '', major: '', phone: '', email: '', role: '负责人', signature_data_url: '' },
      { name: '', student_id: '', major: '', phone: '', email: '', role: '', signature_data_url: '' },
      { name: '', student_id: '', major: '', phone: '', email: '', role: '', signature_data_url: '' },
    ],
    other_people: '',
    project_blog_url: '',
    member_blog_urls: [''],
    project_intro: '',
    plan: '',
    expected_results: '',
    teacher_comment: '',
    commitment_date: '',
  };
}

function defaultTaskContent() {
  return {
    project_name: '',
    team_name: '',
    leader_name: '',
    leader_phone: '',
    start_date: '',
    end_date: '',
    objectives: '',
    roles: [],
    milestones: [],
    risks: '',
    acceptance: '',
  };
}

const draft = reactive({
  title: docType.value === 'application' ? '未命名申请书' : '未命名任务书',
  status: 'draft',
  content: docType.value === 'application' ? defaultApplicationContent() : defaultTaskContent(),
});

function resetDraft(type, detail) {
  draft.title = detail?.title || (type === 'application' ? '未命名申请书' : '未命名任务书');
  draft.status = 'draft';
  draft.content = type === 'application' ? defaultApplicationContent() : defaultTaskContent();
  const src = detail?.content && typeof detail.content === 'object' ? detail.content : {};
  Object.keys(draft.content).forEach((k) => {
    if (src[k] !== undefined) draft.content[k] = src[k];
  });
  if (type === 'application') {
    if (!Array.isArray(draft.content.tech_points)) draft.content.tech_points = [''];
    draft.content.tech_points = draft.content.tech_points.filter(v => typeof v === 'string');
    if (draft.content.tech_points.length === 0) draft.content.tech_points = [''];
    if (draft.content.tech_points.length > 5) draft.content.tech_points = draft.content.tech_points.slice(0, 5);

    if (!Array.isArray(draft.content.member_blog_urls)) draft.content.member_blog_urls = [''];
    draft.content.member_blog_urls = draft.content.member_blog_urls.filter(v => typeof v === 'string');
    if (draft.content.member_blog_urls.length === 0) draft.content.member_blog_urls = [''];
    if (draft.content.member_blog_urls.length > 10) draft.content.member_blog_urls = draft.content.member_blog_urls.slice(0, 10);

    if (!Array.isArray(draft.content.participants)) draft.content.participants = [];
    while (draft.content.participants.length < 3) {
      draft.content.participants.push({ name: '', student_id: '', major: '', phone: '', email: '', role: '', signature_data_url: '' });
    }
    if (!draft.content.participants[0]?.role) draft.content.participants[0].role = '负责人';
    if (draft.content.participants.length > 4) draft.content.participants = draft.content.participants.slice(0, 4);

    draft.content.participants.forEach((p) => {
      if (!p || typeof p !== 'object') return;
      if (typeof p.signature_data_url !== 'string') p.signature_data_url = '';
    });
  }
  if (type === 'task') {
    if (!Array.isArray(draft.content.roles)) draft.content.roles = [];
    if (!Array.isArray(draft.content.milestones)) draft.content.milestones = [];
  }
}

function addTechPoint() {
  if (docType.value !== 'application') return;
  if (!Array.isArray(draft.content.tech_points)) draft.content.tech_points = [''];
  if (draft.content.tech_points.length >= 5) return;
  draft.content.tech_points.push('');
}

function removeTechPoint(idx) {
  if (docType.value !== 'application') return;
  if (!Array.isArray(draft.content.tech_points)) return;
  if (draft.content.tech_points.length <= 1) return;
  draft.content.tech_points.splice(idx, 1);
}

function addMemberBlog() {
  if (docType.value !== 'application') return;
  if (!Array.isArray(draft.content.member_blog_urls)) draft.content.member_blog_urls = [''];
  if (draft.content.member_blog_urls.length >= 10) return;
  draft.content.member_blog_urls.push('');
}

function removeMemberBlog(idx) {
  if (docType.value !== 'application') return;
  if (!Array.isArray(draft.content.member_blog_urls)) return;
  if (draft.content.member_blog_urls.length <= 1) return;
  draft.content.member_blog_urls.splice(idx, 1);
}

function onParticipantSignatureChange(idx, event) {
  if (docType.value !== 'application') return;
  const file = event?.target?.files?.[0] || null;
  if (!file) return;
  const reader = new FileReader();
  reader.onload = () => {
    const url = typeof reader.result === 'string' ? reader.result : '';
    if (!url) return;
    if (!draft.content.participants?.[idx]) return;
    draft.content.participants[idx].signature_data_url = url;
  };
  reader.readAsDataURL(file);
  if (event?.target) event.target.value = '';
}

function clearParticipantSignature(idx) {
  if (docType.value !== 'application') return;
  if (!draft.content.participants?.[idx]) return;
  draft.content.participants[idx].signature_data_url = '';
}

async function loadOrCreate() {
  localError.value = null;
  initialized.value = false;
  dirty.value = false;

  const type = docType.value;
  const id = route.params.id ? Number(route.params.id) : null;
  busy.value = true;
  try {
    if (id) {
      draftId.value = id;
      const detail = type === 'application'
        ? await fetchApplicationDraft(authStore.token, id)
        : await fetchTaskDraft(authStore.token, id);
      resetDraft(type, detail);
    } else {
      const created = type === 'application'
        ? await createApplicationDraft(authStore.token, { title: draft.title, content: draft.content })
        : await createTaskDraft(authStore.token, { title: draft.title, content: draft.content });
      draftId.value = created?.id || null;
      resetDraft(type, created);
      if (draftId.value) {
        router.replace({ name: 'document-edit', params: { type, id: String(draftId.value) } });
      }
    }
  } catch (e) {
    localError.value = e?.message || '加载失败';
  } finally {
    busy.value = false;
    initialized.value = true;
  }
}

let saveTimer = null;
let hintTimer = null;

async function saveNow() {
  if (!initialized.value) return;
  if (!draftId.value) return;
  const type = docType.value;
  saveState.value = 'saving';
  try {
    const payload = {
      title: draft.title,
      content: draft.content,
    };
    if (type === 'application') {
      await updateApplicationDraft(authStore.token, draftId.value, payload);
    } else {
      await updateTaskDraft(authStore.token, draftId.value, payload);
    }
    dirty.value = false;
    saveState.value = 'saved';
    if (hintTimer) clearTimeout(hintTimer);
    hintTimer = setTimeout(() => {
      saveState.value = 'idle';
    }, 1500);
  } catch (e) {
    saveState.value = 'error';
  }
}

function scheduleSave() {
  if (!initialized.value) return;
  dirty.value = true;
  if (saveTimer) clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    saveNow();
  }, 900);
}

watch(draft, () => {
  scheduleSave();
}, { deep: true });

function addParticipant() {
  if (docType.value !== 'application') return;
  if (draft.content.participants.length >= 4) return;
  draft.content.participants.push({ name: '', student_id: '', major: '', phone: '', email: '', role: '', signature_data_url: '' });
}

function removeParticipant() {
  if (docType.value !== 'application') return;
  if (draft.content.participants.length <= 3) return;
  draft.content.participants.pop();
}

function addRole() {
  if (docType.value !== 'task') return;
  draft.content.roles.push({ name: '', responsibility: '', deliverable: '' });
}

function removeRole(idx) {
  if (docType.value !== 'task') return;
  draft.content.roles.splice(idx, 1);
}

function addMilestone() {
  if (docType.value !== 'task') return;
  draft.content.milestones.push({ phase: '', start: '', end: '', work: '', deliverable: '' });
}

function removeMilestone(idx) {
  if (docType.value !== 'task') return;
  draft.content.milestones.splice(idx, 1);
}

function goBack() {
  router.push({ name: 'documents' });
}

async function downloadDocx() {
  if (!draftId.value) return;
  busy.value = true;
  localError.value = null;
  try {
    const blob = docType.value === 'application'
      ? await exportApplicationDraftDocx(authStore.token, draftId.value)
      : await exportTaskDraftDocx(authStore.token, draftId.value);
    const fileNameBase = (draft.title || (docType.value === 'application' ? '申请书' : '任务书')).trim() || (docType.value === 'application' ? '申请书' : '任务书');
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${fileNameBase}.docx`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch (e) {
    localError.value = e?.message || '下载失败';
  } finally {
    busy.value = false;
  }
}

async function uploadNow() {
  if (!draftId.value) return;
  busy.value = true;
  localError.value = null;
  localSuccess.value = null;
  try {
    await saveNow();
    const blob = docType.value === 'application'
      ? await exportApplicationDraftDocx(authStore.token, draftId.value)
      : await exportTaskDraftDocx(authStore.token, draftId.value);
    const fileNameBase = (draft.title || (docType.value === 'application' ? '申请书' : '任务书')).trim() || (docType.value === 'application' ? '申请书' : '任务书');
    const file = new File([blob], `${fileNameBase}.docx`, {
      type: blob?.type || 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    });
    const meta = docType.value === 'application'
      ? {
        student_name: draft.content?.leader_name,
        student_id: draft.content?.participants?.[0]?.student_id,
        project_title: draft.content?.project_name,
      }
      : {
        student_name: draft.content?.leader_name,
        student_id: '',
        project_title: draft.content?.project_name,
      };
    await uploadApplicationFile(authStore.token, file, meta);
    if (hintTimer) clearTimeout(hintTimer);
    saveState.value = 'saved';
    hintTimer = setTimeout(() => {
      saveState.value = 'idle';
    }, 1500);
    localSuccess.value = '上传成功';
    setTimeout(() => {
      localSuccess.value = null;
    }, 2000);
  } catch (e) {
    const msg = e?.message || String(e);
    if (msg.includes('duplicate application')) {
      localError.value = '不能上传相同的申请书';
    } else
    if (msg.includes('Failed to fetch') || msg.includes('NetworkError')) {
      localError.value = '上传失败：无法连接后端服务（请确认后端已启动且 8001 端口可访问）';
    } else {
      localError.value = msg || '上传失败';
    }
  } finally {
    busy.value = false;
  }
}

async function removeDraft() {
  if (!draftId.value) {
    goBack();
    return;
  }
  busy.value = true;
  localError.value = null;
  try {
    if (docType.value === 'application') {
      await deleteApplicationDraft(authStore.token, draftId.value);
    } else {
      await deleteTaskDraft(authStore.token, draftId.value);
    }
    router.replace({ name: 'documents' });
  } catch (e) {
    localError.value = e?.message || '删除失败';
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  loadOrCreate();
});

onBeforeUnmount(() => {
  if (!saveTimer) return;
  clearTimeout(saveTimer);
  saveTimer = null;
  if (hintTimer) {
    clearTimeout(hintTimer);
    hintTimer = null;
  }
});
</script>
