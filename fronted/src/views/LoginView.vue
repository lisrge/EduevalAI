<template>
  <div class="edueval-skin flex flex-col" style="min-height: 100vh;">
    <ChatHeader />
    <div style="flex: 1; padding: 40px 20px; display: flex; align-items: center; justify-content: center;">
      <section class="panel" style="width: 520px; max-width: 100%;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h2 style="margin: 0;">登录</h2>
            <p class="panel-subtitle">使用 12 位学号与密码登录。</p>
          </div>
        </div>

        <div class="edueval-panel-body" style="overflow: visible;">
          <div class="field" style="margin-bottom: 12px;">
            <span>学号（12 位数字）</span>
            <input v-model="studentId" type="text" inputmode="numeric" autocomplete="username" />
          </div>
          <div class="field" style="margin-bottom: 12px;">
            <span>密码</span>
            <input v-model="password" type="password" autocomplete="current-password" />
          </div>

          <label class="checkbox-row" style="margin-bottom: 16px;">
            <input v-model="rememberMe" type="checkbox" />
            自动登录
          </label>

          <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">
            {{ errorMessage }}
          </div>

          <div class="form-actions" style="justify-content: flex-end;">
            <router-link class="ghost-button" :to="{ name: 'register' }">注册</router-link>
            <button class="primary-button" type="button" :disabled="authStore.loading" @click="submit">
              {{ authStore.loading ? '登录中...' : '登录' }}
            </button>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import ChatHeader from '../components/ChatHeader.vue';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const router = useRouter();
const route = useRoute();

const studentId = ref('');
const password = ref('');
const rememberMe = ref(false);
const localError = ref(null);

const errorMessage = computed(() => localError.value || authStore.error);

function validate() {
  const sid = String(studentId.value || '').trim();
  if (!/^\d{12}$/.test(sid)) return '学号必须为 12 位纯数字';
  return null;
}

async function submit() {
  localError.value = validate();
  if (localError.value) return;

  try {
    await authStore.login({
      studentId: String(studentId.value || '').trim(),
      password: String(password.value || ''),
      remember: Boolean(rememberMe.value),
    });
    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : (authStore.isAdmin ? '/admin/users' : '/');
    router.replace(redirect);
  } catch (e) {
    localError.value = e?.message || '登录失败';
  }
}
</script>
