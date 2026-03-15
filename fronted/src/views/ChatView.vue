<template>
  <!-- 主界面容器：移除背景色，使边栏和导航栏直接贴边 -->
  <div class="flex h-screen bg-[#f0f4f9] text-text-primary overflow-hidden font-sans">
    
    <!-- 左侧边栏容器：直接对齐左侧和顶部 -->
    <div class="flex flex-col h-full shrink-0 shadow-sm">
      <ChatSidebar />
    </div>

    <!-- 中间主区域：垂直布局，包含导航栏和对话区 -->
    <div class="flex-1 flex flex-col min-w-0 bg-[#dee5ed] overflow-hidden">
      <!-- 顶部导航栏：对齐顶部 -->
      <ChatHeader />

      <!-- 主内容容器：使用 flex-1 和 min-h-0 强制内部收缩 -->
      <div class="flex-1 flex gap-2 p-1 md:p-2 overflow-hidden min-h-0 min-w-0">
        <!-- 中间主对话区：圆角面板，强制使用 flex-col 且 min-w-0 -->
        <main class="flex-1 flex flex-col min-w-0 bg-white rounded-[24px] shadow-sm overflow-hidden relative h-full">
          <!-- 消息显示列表：直接作为 flex 子元素，并强制 w-full 和 overflow-hidden -->
          <div class="flex-1 min-h-0 min-w-0 overflow-hidden relative">
            <MessageList :messages="messages" :loading="isLoading" />
          </div>

          <!-- 底部操作区容器：固定白色背景，shrink-0 确保不被压缩，移除边框 -->
          <div class="shrink-0 flex flex-col bg-white pb-4 px-4 z-20 shadow-[0_-10px_20px_-5px_rgba(0,0,0,0.03)]">
            <!-- 技能切换栏 -->
            <SkillBar />
            <!-- 用户输入区域 -->
            <ChatInput @send="onSendMessage" @stop="onStopResponse" :loading="isLoading" />
          </div>
        </main>

        <!-- 右侧功能面板：圆角容器 -->
        <aside class="hidden xl:flex w-80 flex-col gap-4 shrink-0 overflow-y-auto pr-1">
          <!-- 上部信息卡片 -->
          <div class="bg-[#f0f4f9] rounded-panel p-6 shadow-sm flex flex-col transition-all hover:shadow-card-hover">
            <h3 class="font-bold text-text-primary flex items-center gap-2 mb-6">
              <Info :size="20" class="text-primary" />
              <span class="tracking-tight">功能面板</span>
            </h3>
            
            <div class="space-y-8 flex-1">
              <!-- 当前模型详情：使用纯白背景作为色块对比 -->
              <section>
                <h4 class="text-[11px] font-bold text-text-tertiary uppercase mb-5 px-1 tracking-widest px-1">当前模型详情</h4>
                <div class="bg-white p-6 rounded-[24px] shadow-sm hover:shadow-md transition-all duration-300">
                  <div class="flex items-center gap-5 mb-5">
                    <div class="w-12 h-12 rounded-2xl bg-blue-50 flex items-center justify-center text-primary font-black shadow-inner">GPT</div>
                    <div>
                      <p class="text-sm font-black text-text-primary">GPT-4 Turbo</p>
                      <p class="text-[11px] text-green-500 font-black flex items-center gap-1.5 mt-1 uppercase tracking-tighter">
                        <span class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></span>
                        Operational
                      </p>
                    </div>
                  </div>
                  <p class="text-[13px] text-text-secondary leading-relaxed font-medium">
                    擅长复杂逻辑推理、创意写作以及多语言代码编写。
                  </p>
                </div>
              </section>

              <!-- 对话统计 -->
              <section>
                <h4 class="text-[11px] font-bold text-text-tertiary uppercase mb-5 px-1 tracking-widest px-1">实时统计</h4>
                <div class="grid grid-cols-2 gap-5">
                  <div class="bg-white p-5 rounded-[24px] text-center shadow-sm hover:shadow-md transition-all duration-300">
                    <p class="text-[10px] text-text-tertiary font-bold mb-2 uppercase tracking-widest">Messages</p>
                    <p class="text-2xl font-black text-primary">24</p>
                  </div>
                  <div class="bg-white p-5 rounded-[24px] text-center shadow-sm hover:shadow-md transition-all duration-300">
                    <p class="text-[10px] text-text-tertiary font-bold mb-2 uppercase tracking-widest">Tokens</p>
                    <p class="text-2xl font-black text-primary">1.2k</p>
                  </div>
                </div>
              </section>
            </div>
          </div>

          <!-- 下部辅助卡片：色块化展示 -->
          <div class="bg-[#f0f4f9] rounded-panel p-8 flex-1 flex flex-col items-center justify-center text-center transition-all hover:shadow-card-hover">
            <div class="w-12 h-12 bg-white rounded-full flex items-center justify-center mb-4 shadow-sm">
              <Sparkles :size="24" class="text-purple-500 opacity-60" />
            </div>
            <p class="text-xs text-text-tertiary font-bold leading-relaxed">
              更多智能插件与<br/>工作流功能即将上线
            </p>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { Info, Sparkles } from 'lucide-vue-next';
import ChatSidebar from '../components/ChatSidebar.vue';
import ChatHeader from '../components/ChatHeader.vue';
import MessageList from '../components/MessageList.vue';
import SkillBar from '../components/SkillBar.vue';
import ChatInput from '../components/ChatInput.vue';

/**
 * 页面全局状态管理
 */
const isLoading = ref(false);
const currentTimer = ref(null);
const wasInterrupted = ref(false); // 记录是否刚刚手动终止了输出

const messages = ref([
  {
    role: 'ai',
    model: 'GPT-4 Turbo',
    content: '你好！我是 ModelHub AI。我已经根据您的要求，将所有的黑色硬边框替换为了自然的冷色调色块区分。',
    thinking: '用户要求移除边框并使用统一的冷色调色块。我已将侧边栏设为浅冷灰，中间对话区保持纯白，整体大背景使用了深一点的冷灰色以拉开层级。'
  },
  {
    role: 'user',
    content: '现在的界面看起来非常现代且统一。侧边栏的颜色和中间区分得很清楚。'
  },
  {
    role: 'ai',
    model: 'GPT-4 Turbo',
    content: '是的！通过移除 1px 的边框并改用背景色深浅对比（Slate 50/100/200 系列），界面显得更加柔和且专业。侧边栏与中间对话区形成了鲜明的色块对比，同时保持了视觉风格的一致性。',
    sources: ['Modern UI Design Principles', 'Color Block Theory'],
    streaming: false
  }
]);

const onSendMessage = (text) => {
  messages.value.push({
    role: 'user',
    content: text,
    isFirstAfterStop: wasInterrupted.value // 标记这是在停止后的第一条消息
  });
  
  // 发送后重置中断状态
  wasInterrupted.value = false;
  isLoading.value = true;
  
  // 记录定时器，以便能够取消
  currentTimer.value = setTimeout(() => {
    isLoading.value = false;
    currentTimer.value = null;
    messages.value.push({
      role: 'ai',
      model: 'GPT-4 Turbo',
      content: '收到您的消息。界面优化后，阅读和交互体验是否感觉更加流畅了？',
      thinking: '继续保持专业且温和的语气进行互动。'
    });
  }, 2000);
};

/**
 * 处理停止响应逻辑
 */
const onStopResponse = () => {
  if (currentTimer.value) {
    clearTimeout(currentTimer.value);
    currentTimer.value = null;
    wasInterrupted.value = true; // 记录发生了一次手动终止
  }
  isLoading.value = false;
  // 这里可以添加实际停止 API 请求的逻辑
};
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;900&display=swap');

:root {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}

/* 确保全局无滚动条 */
body {
  overflow: hidden;
  margin: 0;
  padding: 0;
}
</style>
