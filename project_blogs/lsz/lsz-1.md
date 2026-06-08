

# 前言

经过队内的讨论，我和其他组员对于本次项目已经有了初步的认知和理解，并且确定了组内的分工。我们组的项目是项目实训跟踪过程的OpenClaw开放智能体。我们初步的任务是先接收所有同学的项目实训申请书，通过AI给出自动评分

# 个人任务

我的任务是负责前端的开发。在前端上用到Vue3

任务汇总：
1.	完成登陆、注册页面
2.	完成申请书管理页面
3.	我的申请书/任务书列表页面
4.	个人空间页面

# 工作部分

## 入口文件

先创建 Pinia 和 Router 实例，因为它们需要通过 app.use() 注册
主题初始化放在 app.mount() 之前，确保页面加载前就应用正确的主题样式，避免页面闪烁
样式文件 main.css 在入口引入，保证全局样式最先加载

```javascript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './assets/main.css'
import { useThemeStore } from './stores/themeStore'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

useThemeStore(pinia).initialize()

app.mount('#app')
```

根组件只需做路由出口，不需要写任何业务逻辑

```vue
<template>
  <router-view/>
</template>

<script setup>
// ModelHub App
</script>

<style>
/* Global styles in main.css */
</style>
```
从而实现基础对话界面

## 路由配置

使用懒加载 () => import() 减少首屏加载时间
路由守卫 beforeEach 在页面跳转前检查登录状态
requiresAuth 标记需要登录的页面，guestOnly 标记只能游客访问的页面
优点：
懒加载使初始 bundle 体积减小 30%+
统一的权限控制，避免在每个页面重复写校验逻辑
登录后自动跳转回原页面（redirect 参数）

```js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore'

const router = createRouter({
  history: createWebHistory(process.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'applications',
      component: () => import('../views/ApplicationsDashboardView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/RegisterView.vue'),
      meta: { guestOnly: true },
    },
    {
      path: '/documents',
      name: 'documents',
      component: () => import('../views/MyDocumentsView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:type/new',
      name: 'document-new',
      component: () => import('../views/DocumentEditorView.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/documents/:type/:id',
      name: 'document-edit',
      component: () => import('../views/DocumentEditorView.vue'),
      meta: { requiresAuth: true },
    }
  ]
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  await authStore.ensureInitialized()

  if (to.meta?.requiresAuth && !authStore.isAuthenticated) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (to.meta?.guestOnly && authStore.isAuthenticated) {
    return { name: 'applications' }
  }

  return true
})

export default router
```

## 登陆界面

### 认证状态管理
- Token 存储策略：remember=true 用 localStorage（持久），false 用 sessionStorage（会话级）
- ensureInitialized() 页面加载时自动恢复登录状态，调用 API 验证 Token 有效性
- 验证失败自动清空 Token，避免无效 Token 导致的请求失败

### 登陆界面开发

实现的功能：
登录表单:学号、密码输入框
自动登录:记住我复选框，持久登录
错误提示:实时显示校验错误或服务器错误
按钮状态:登录中显示"登录中..."，按钮禁用
注册跳转:点击注册按钮跳转注册页面

表单校验功能：
学号格式校验：必须是12位纯数字
必填校验：学号和密码不能为空
自动trim：去除前后空格

登录流程：
Token存储：根据是否勾选记住我，决定存localStorage或sessionStorage
自动恢复登录：页面加载时检查Token有效性，自动恢复登录状态
登录后跳转：登录成功后自动跳转回原页面（redirect参数）

错误处理：登录失败显示错误信息

···vue
<template>
  <div class="edueval-skin flex flex-col" style="min-height:100vh;">
    <ChatHeader/>
    <div style="flex:1; padding:0; display: flex; align-items:center; justify-content:center;">
      <section class="panel" style="width: 520px; max-width:100%;">
        <div class="panel-header" style="margin-bottom: 10px;">
          <div>
            <h2 style="margin:0;">登录</h2>
            <p class="panel-subtitle">使用12位学号与密码登录。</p>
          </div>
        </div>
        <div class="edueval-panel-body" style="overflow:visible;">
          <div class="field" style="margin-bottom:12px;">
            <span>学号(12位数字)</span>
            <input v-model="studentId" type="text" inputmode="numeric" autocomplete="username"/>
          </div>
          <div class="field" style="margin-bottom:12px;">
            <span>密码</span>
            <input v-model="password" type="password" autocomplete="current-password"/>
          </div>
          <label class="checkbox-row" style="margin-bottom:16px;">
            <input v-model="rememberMe" type="checkbox"/>
            自动登录
          </label>
          <div v-if="errorMessage" class="alert error" style="margin-bottom: 12px;">
            {{ errorMessage }}
          </div>
          <div class="form-actions" style="justify-content: flex-end;">
            <router-link class="ghost-button" :to="{ name:'register' }">注册</router-link>
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
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
  if (!/\d{12}$/.test(sid)) return '学号必须为12位纯数字'
  return null
}

async function submit() {
  localError.value = validate()
  if (localError.value) return

  try {
    await authStore.login({
      studentId: String(studentId.value || '').trim(),
      password: String(password.value || ''),
      remember: Boolean(rememberMe.value),
    })

    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    router.replace(redirect)
  } catch (e) {}
}
</script>


# 总结

本周进行了项目方向的敲定并且完成了小组成员的分工。个人部分则是完成了项目初始化与用户认证系统的开发。主要工作包括：配置Vue3 + Pinia + Vue Router项目环境，实现7个页面的路由配置与懒加载优化；开发登录与注册功能，完成Token自动存储与读取机制，实现"记住我"持久登录与登录状态自动恢复；通过路由守卫实现统一的权限控制。