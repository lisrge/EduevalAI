<template>
  <div class="edueval-skin edueval-page">
    <ChatHeader />
    <div class="page-wrapper" style="flex: 1; display: flex; align-items: center; justify-content: center;">
      <div class="auth-shell animate-fadeInUp">
        <div class="text-center" style="margin-bottom: 28px;">
          <div class="auth-badge">
            <img src="../assets/EduevalAI_logo.png" alt="Logo" style="width: 34px; height: 34px;" />
          </div>
          <h1 class="brand-title auth-title">创建账户</h1>
          <p class="auth-subtitle">完成基础信息和电子签名上传后，即可进入学生工作台。</p>
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
              <label for="realName"><span>姓名</span></label>
              <input
                id="realName"
                v-model="realName"
                type="text"
                autocomplete="name"
                class="input-field"
                placeholder="请输入您的真实姓名"
              />
            </div>

            <div class="field">
              <label for="password"><span>密码</span></label>
              <input
                id="password"
                v-model="password"
                type="password"
                autocomplete="new-password"
                class="input-field"
                placeholder="设置您的密码"
              />
            </div>

            <div class="field">
              <span>电子签名</span>
              <div
                class="surface-card"
                style="border-style: dashed; border-width: 2px; text-align: center; cursor: pointer; padding: 28px 20px;"
                @click="$refs.fileInput.click()"
              >
                <input
                  ref="fileInput"
                  type="file"
                  accept="image/*"
                  @change="onFileChange"
                  class="hidden"
                />
                <div style="display: grid; justify-items: center; gap: 10px;">
                  <div style="width: 52px; height: 52px; border-radius: 999px; display: grid; place-items: center; background: var(--primary-soft);">
                    <svg class="w-6 h-6 text-primary" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path>
                    </svg>
                  </div>
                  <div v-if="signatureFile" style="font-size: 14px; font-weight: 700;">{{ signatureFile.name }}</div>
                  <div v-else>
                    <p style="margin: 0; font-size: 14px; font-weight: 700;">点击上传签名</p>
                    <p style="margin: 4px 0 0; font-size: 12px; color: var(--text-secondary);">支持 PNG、JPG 等图片格式</p>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="errorMessage" class="alert error">{{ errorMessage }}</div>

            <div class="auth-actions" style="padding-top: 4px;">
              <router-link
                :to="{ name: 'login' }"
                class="btn-ghost text-center"
              >
                返回登录
              </router-link>
              <button
                type="button"
                :disabled="authStore.loading"
                @click="submit"
                class="btn-primary"
              >
                {{ authStore.loading ? '注册中...' : '注册' }}
              </button>
            </div>
          </div>
        </div>

        <div class="auth-footer text-center" style="margin-top: 18px; font-size: 14px;">
          已有账户？点击“返回登录”进行登录
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import ChatHeader from '../components/ChatHeader.vue'
import { useAuthStore } from '../stores/authStore'

const authStore = useAuthStore()
const router = useRouter()

const studentId = ref('')
const realName = ref('')
const password = ref('')
const signatureFile = ref(null)
const fileInput = ref(null)
const localError = ref(null)

const errorMessage = computed(() => localError.value || authStore.error)

function onFileChange(event) {
  const file = event?.target?.files?.[0] || null
  signatureFile.value = file
}

function validate() {
  const sid = String(studentId.value || '').trim()
  if (!sid) return '请输入学号'
  if (sid.length > 50) return '学号不能超过50位'
  if (!String(realName.value || '').trim()) return '请输入姓名'
  if (!password.value) return '请设置密码'
  if (!signatureFile.value) return '请上传电子签名图片'
  if (!String(signatureFile.value.type || '').startsWith('image/')) return '电子签名必须为图片格式'
  return null
}

async function submit() {
  localError.value = validate()
  if (localError.value) return

  try {
    await authStore.register({
      studentId: String(studentId.value || '').trim(),
      realName: String(realName.value || '').trim(),
      password: String(password.value || ''),
      signatureFile: signatureFile.value
    })
    await authStore.login({
      studentId: String(studentId.value || '').trim(),
      password: String(password.value || ''),
      remember: false
    })
    router.replace({ name: 'applications' })
  } catch (e) {
    localError.value = e?.message || '注册失败'
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}
</script>
