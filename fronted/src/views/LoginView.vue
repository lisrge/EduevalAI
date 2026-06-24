<template>
  <div class="edueval-skin edueval-page">
    <ChatHeader />
    <div class="page-wrapper" style="flex: 1; display: flex; align-items: center; justify-content: center;">
      <div class="auth-shell animate-fadeInUp">
        <div class="text-center" style="margin-bottom: 28px;">
          <div class="auth-badge">
            <img src="../assets/EduevalAI_logo.png" alt="Logo" style="width: 34px; height: 34px;" />
          </div>
          <h1 class="brand-title auth-title">Edueval AI</h1>
          <p class="auth-subtitle">登录后进入学生工作台、教师评分端或管理员控制台。</p>
        </div>

        <div class="card auth-card">
          <div style="display: grid; gap: 20px;">
            <div class="field">
              <label for="studentId"><span>学号</span></label>
              <input
                id="studentId"
                v-model="studentId"
                type="text"
                inputmode="numeric"
                autocomplete="username"
                class="input-field"
                placeholder="请输入您的学号"
              />
            </div>

            <div class="field">
              <label for="password"><span>密码</span></label>
              <input
                id="password"
                v-model="password"
                type="password"
                autocomplete="current-password"
                class="input-field"
                placeholder="请输入您的密码"
                @keyup.enter="submit"
              />
            </div>

            <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap;">
              <label style="display: inline-flex; align-items: center; gap: 10px; cursor: pointer; color: var(--text-secondary);">
                <input
                  v-model="rememberMe"
                  type="checkbox"
                />
                <span>记住登录状态</span>
              </label>
              <span class="badge neutral">支持管理员 / 老师 / 学生三种角色</span>
            </div>

            <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

            <div class="auth-actions" style="padding-top: 4px;">
              <router-link
                :to="{ name: 'register' }"
                class="btn-ghost text-center"
              >
                注册账户
              </router-link>
              <button
                type="button"
                :disabled="authStore.loading"
                @click="submit"
                class="btn-primary"
              >
                {{ authStore.loading ? '登录中...' : '登录' }}
              </button>
            </div>
          </div>
        </div>

        <div class="auth-footer text-center" style="margin-top: 18px; font-size: 14px;">
          首次使用？点击上方“注册账户”创建您的账号
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import ChatHeader from '../components/ChatHeader.vue'
import { useAuthStore } from '../stores/authStore'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const studentId = ref('')
const password = ref('')
const rememberMe = ref(false)
const localError = ref(null)

const errorMessage = computed(() => localError.value || authStore.error)

function validate() {
  const sid = String(studentId.value || '').trim()
  if (!sid) return '请输入学号'
  if (sid.length > 50) return '学号不能超过50位'
  if (!password.value) return '请输入密码'
  return null
}

async function submit() {
  localError.value = validate()
  if (localError.value) return

  try {
    await authStore.login({
      studentId: String(studentId.value || '').trim(),
      password: String(password.value),
      remember: Boolean(rememberMe.value)
    })
    const redirect = typeof route.query.redirect === 'string'
      ? route.query.redirect
      : (authStore.isAdmin ? '/admin/users' : '/')
    router.replace(redirect)
  } catch (e) {
    localError.value = e?.message || '登录失败，请检查学号和密码'
  }
}
</script>
