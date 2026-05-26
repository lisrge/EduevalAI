<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />

    <div style="padding: 20px; display: flex; justify-content: center;">
      <section class="panel" style="width: 820px; max-width: 100%;">
        <div class="panel-header">
          <div>
            <h2>个人空间</h2>
            <p class="panel-subtitle">查看学号、电子签名、密码与申请状态。</p>
          </div>
          <button class="ghost-button" type="button" style="width: auto;" @click="goBack">返回</button>
        </div>

        <div class="edueval-panel-body" style="overflow: visible; display: grid; gap: 18px;">
          <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

          <section class="detail-block">
            <h3>基本信息</h3>
            <dl class="detail-grid">
              <div>
                <dt>姓名</dt>
                <dd>{{ profile?.real_name || authStore.user?.real_name || '-' }}</dd>
              </div>
              <div>
                <dt>学号</dt>
                <dd>{{ profile?.student_id || authStore.user?.student_id || '-' }}</dd>
              </div>
              <div>
                <dt>注册时间</dt>
                <dd>{{ profile?.created_at ? new Date(profile.created_at).toLocaleString() : '-' }}</dd>
              </div>
              <div>
                <dt>重传授权</dt>
                <dd>{{ profile?.application_reupload_allowed ? '已允许一次重新上传' : '未授权' }}</dd>
              </div>
              <div>
                <dt>签名变更申请</dt>
                <dd>{{ profile?.pending_signature_request ? '审核中' : '无' }}</dd>
              </div>
              <div class="full-width">
                <dt>电子签名</dt>
                <dd>
                  <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                    <span class="badge neutral">{{ profile?.signature_file_name || '-' }}</span>
                    <a v-if="signatureUrl" class="ghost-button" :href="signatureUrl" target="_blank" rel="noopener noreferrer">查看原图</a>
                  </div>
                </dd>
              </div>
            </dl>
            <div v-if="signatureUrl" style="margin-top: 10px;">
              <img :src="signatureUrl" alt="signature" style="max-width: 280px; width: 100%; border: 1px solid var(--border); border-radius: 16px; background: var(--surface);" />
            </div>
          </section>

          <section v-if="!authStore.isAdmin" class="detail-block">
            <h3>申请修改电子签名</h3>
            <div class="upload-form" style="grid-template-columns: 1fr;">
              <label class="field">
                <span>新签名图片</span>
                <input type="file" accept="image/*" @change="onSignatureChange" />
              </label>
              <label class="field">
                <span>申请说明</span>
                <textarea v-model="signatureNote" rows="4" />
              </label>
            </div>
            <div class="form-actions" style="justify-content: flex-end; margin-top: 10px;">
              <button class="primary-button" type="button" :disabled="savingSignature || !signatureFile" @click="submitSignatureRequest">
                {{ savingSignature ? '提交中...' : '提交签名变更申请' }}
              </button>
            </div>
          </section>

          <section class="detail-block">
            <h3>修改密码</h3>
            <div class="upload-form" style="grid-template-columns: 1fr 1fr;">
              <label class="field">
                <span>旧密码</span>
                <input v-model="oldPassword" type="password" autocomplete="current-password" />
              </label>
              <label class="field">
                <span>新密码</span>
                <input v-model="newPassword" type="password" autocomplete="new-password" />
              </label>
            </div>
            <div class="form-actions" style="justify-content: flex-end; margin-top: 10px;">
              <button class="primary-button" type="button" :disabled="savingPassword" @click="submitPassword">
                {{ savingPassword ? '提交中...' : '修改密码' }}
              </button>
            </div>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { changeUserPassword, fetchUserProfile, fetchUserSignature, requestSignatureUpdate } from '../services/eduevalApi';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const profile = ref(null);
const signatureObjectUrl = ref('');
const signatureFile = ref(null);
const signatureNote = ref('');
const savingPassword = ref(false);
const savingSignature = ref(false);
const oldPassword = ref('');
const newPassword = ref('');
const localError = ref(null);

const errorMessage = computed(() => localError.value);
const signatureUrl = computed(() => signatureObjectUrl.value || '');

function goBack() {
  router.push({ name: authStore.isAdmin ? 'admin-users' : 'applications' });
}

async function loadProfile() {
  localError.value = null;
  try {
    profile.value = await fetchUserProfile(authStore.token);
  } catch (e) {
    localError.value = e?.message || '加载失败';
  }
}

async function loadSignature() {
  if (!authStore.token) return;
  try {
    const blob = await fetchUserSignature(authStore.token);
    if (signatureObjectUrl.value) {
      URL.revokeObjectURL(signatureObjectUrl.value);
    }
    signatureObjectUrl.value = URL.createObjectURL(blob);
  } catch (e) {
    if (signatureObjectUrl.value) {
      URL.revokeObjectURL(signatureObjectUrl.value);
      signatureObjectUrl.value = '';
    }
  }
}

function onSignatureChange(event) {
  signatureFile.value = event?.target?.files?.[0] || null;
}

async function submitPassword() {
  localError.value = null;
  if (!oldPassword.value || !newPassword.value) {
    localError.value = '请填写旧密码与新密码';
    return;
  }
  savingPassword.value = true;
  try {
    await changeUserPassword(authStore.token, { oldPassword: oldPassword.value, newPassword: newPassword.value });
    oldPassword.value = '';
    newPassword.value = '';
  } catch (e) {
    localError.value = e?.message || '修改失败';
  } finally {
    savingPassword.value = false;
  }
}

async function submitSignatureRequest() {
  if (!signatureFile.value) {
    localError.value = '请选择新签名图片';
    return;
  }
  savingSignature.value = true;
  localError.value = null;
  try {
    await requestSignatureUpdate(authStore.token, signatureFile.value, signatureNote.value);
    signatureFile.value = null;
    signatureNote.value = '';
    await loadProfile();
  } catch (e) {
    localError.value = e?.message || '提交签名变更申请失败';
  } finally {
    savingSignature.value = false;
  }
}

onMounted(() => {
  loadProfile();
  loadSignature();
});

onBeforeUnmount(() => {
  if (signatureObjectUrl.value) {
    URL.revokeObjectURL(signatureObjectUrl.value);
    signatureObjectUrl.value = '';
  }
});
</script>
