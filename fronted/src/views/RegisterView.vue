<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />
    <div style="flex: 1; padding: 40px 20px; display: flex; align-items: center; justify-content: center;">
      <section class="panel" style="width: 520px; max-width: 100%;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h2 style="margin: 0;">注册</h2>
            <p class="panel-subtitle">注册需上传本人电子签名（图片）。</p>
          </div>
        </div>

        <div class="edueval-panel-body" style="overflow: visible;">
          <div class="field" style="margin-bottom: 12px;">
            <span>账号</span>
            <input v-model="studentId" type="text" inputmode="numeric" autocomplete="username" />
          </div>
          <div class="field" style="margin-bottom: 12px;">
            <span>姓名</span>
            <input v-model="realName" type="text" autocomplete="name" />
          </div>
          <div class="field" style="margin-bottom: 12px;">
            <span>密码</span>
            <input v-model="password" type="password" autocomplete="new-password" />
          </div>
          <div class="field" style="margin-bottom: 16px;">
            <span>电子签名（图片）</span>
            <div class="file-dropzone">
              <input ref="fileRef" type="file" accept="image/*" @change="onFileChange" />
              <small v-if="signatureFile">{{ signatureFile.name }}</small>
              <small v-else>支持 png/jpg 等图片格式。</small>
            </div>
          </div>

          <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">
            {{ errorMessage }}
          </div>

          <div class="form-actions" style="justify-content: flex-end;">
            <router-link class="ghost-button" :to="{ name: 'login' }">返回登录</router-link>
            <button class="primary-button" type="button" :disabled="authStore.loading" @click="submit">
              {{ authStore.loading ? '注册中...' : '注册' }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();

const studentId = ref('');
const realName = ref('');
const password = ref('');
const signatureFile = ref(null);
const fileRef = ref(null);
const localError = ref(null);

const errorMessage = computed(() => localError.value || authStore.error);

function onFileChange(event) {
  const file = event?.target?.files?.[0] || null;
  signatureFile.value = file;
}

function validate() {
  const sid = String(studentId.value || '').trim();
  if (!sid) return '请输入账号';
  if (sid.length > 50) return '账号不能超过50位';
  if (!String(realName.value || '').trim()) return '请输入姓名';
  if (!signatureFile.value) return '请上传电子签名图片';
  if (!String(signatureFile.value.type || '').startsWith('image/')) return '电子签名必须为图片格式';
  return null;
}

async function submit() {
  localError.value = validate();
  if (localError.value) return;

  try {
    await authStore.register({
      studentId: String(studentId.value || '').trim(),
      realName: String(realName.value || '').trim(),
      password: String(password.value || ''),
      signatureFile: signatureFile.value,
    });
    await authStore.login({
      studentId: String(studentId.value || '').trim(),
      password: String(password.value || ''),
      remember: false,
    });
    router.replace({ name: 'applications' });
  } catch (e) {
    localError.value = e?.message || '注册失败';
  } finally {
    if (fileRef.value) fileRef.value.value = '';
  }
}
</script>
