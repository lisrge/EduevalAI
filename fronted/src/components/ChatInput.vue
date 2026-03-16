<template>
  <!-- 输入区域容器：去掉背景色，保持透明 -->
  <div class="shrink-0 relative z-20" style="padding: 10px 32px 12px 32px;">
    <div class="max-w-4xl mx-auto relative flex flex-col" style="gap: 12px;">
      
      <!-- 输入框主体：纯白背景，无边框，彻底去除选中效果 -->
      <div class="relative flex flex-col w-full bg-white rounded-[20px] shadow-sm overflow-hidden border-none">
        
        <!-- 文本输入框：固定高度，纯白背景，禁止任何高度变化 -->
        <textarea
          v-model="input"
          @keydown.enter.exact.prevent="handleAction"
          @keydown.shift.enter.stop
          :readonly="loading"
          :placeholder="loading ? 'AI思考中，请稍后……' : '有什么我可以帮您的？'"
          class="w-full resize-none bg-white border-none focus:ring-0 focus:outline-none outline-none text-text-primary text-[15px] leading-relaxed scrollbar-hide placeholder:text-text-tertiary font-medium h-[52px]"
          :class="loading ? 'cursor-not-allowed' : ''"
          style="padding: 14px 20px; box-shadow: none !important; border: none !important; height: 52px !important; background-color: white !important; opacity: 1 !important;"
          rows="1"
          ref="textareaRef"
        ></textarea>

        <!-- 输入框底部控制栏：强制白色背景，彻底与输入框融合 -->
        <div class="flex items-center justify-between bg-white" style="padding: 0 16px 12px 16px; background-color: white !important;">
          <!-- 左侧：功能按钮，明显的圆角矩形样式（强制使用 inline style 确保生效） -->
          <div class="flex items-center gap-2">
            <button 
              :disabled="loading"
              class="flex items-center justify-center px-4 py-1.5 text-primary transition-all duration-300 border-none" 
              :class="loading ? 'cursor-not-allowed' : 'hover:bg-[#c7d2fe]'"
              style="border-radius: 10px !important; background-color: #e0e7ff !important; opacity: 1 !important;"
              title="上传附件"
            >
              <Paperclip :size="18" />
            </button>
            <button 
              :disabled="loading"
              class="flex items-center justify-center px-4 py-1.5 text-primary transition-all duration-300 border-none" 
              :class="loading ? 'cursor-not-allowed' : 'hover:bg-[#c7d2fe]'"
              style="border-radius: 10px !important; background-color: #e0e7ff !important; opacity: 1 !important;"
              title="表情/常用语"
            >
              <Smile :size="18" />
            </button>
          </div>
          
          <!-- 右侧：模型选择与发送 -->
          <div class="flex items-center gap-2">
            <!-- 模型选择按钮：圆角矩形 -->
            <div class="relative">
              <button 
                @click="!loading && (showModelMenu = !showModelMenu)"
                :disabled="loading"
                class="flex items-center gap-3 px-4 py-1.5 text-primary transition-all text-[12px] font-bold border-none"
                :class="loading ? 'cursor-not-allowed' : 'hover:bg-[#c7d2fe]'"
                style="border-radius: 10px !important; background-color: #e0e7ff !important; opacity: 1 !important;"
              >
                <Cpu :size="14" />
                <span>{{ currentModel }}</span>
                <ChevronUp :size="14" :class="showModelMenu ? 'rotate-180' : ''" class="transition-transform" />
              </button>
              
              <!-- 模型选择菜单：圆角矩形 -->
              <div v-if="showModelMenu && !loading" class="absolute bottom-full mb-2 right-0 w-48 bg-white border border-[#e2e8f0] shadow-xl z-50 overflow-hidden animate-in fade-in slide-in-from-bottom-2 duration-200" style="border-radius: 12px !important;">
                <div 
                  v-for="model in models" 
                  :key="model.name"
                  @click="selectModel(model.name)"
                  class="w-full text-left px-4 py-2.5 text-[12px] font-bold cursor-pointer transition-colors"
                  :class="currentModel === model.name ? 'bg-primary/10 text-primary' : 'text-text-secondary hover:bg-gray-50'"
                >
                  {{ model.name }}
                </div>
              </div>
            </div>

            <span class="hidden md:block text-[9px] text-text-tertiary font-black uppercase tracking-[0.1em] opacity-40 mx-2">
              {{ loading ? 'AI 正在回复中...' : 'ENTER 发送 / SHIFT+ENTER 换行' }}
            </span>

            <!-- 发送/停止按钮：圆角矩形 -->
            <button 
              @click="handleAction"
              :disabled="!loading && !input.trim()"
              class="flex items-center justify-center px-5 py-1.5 transition-all duration-200 active:scale-90 border-none min-w-[56px]"
              :style="`border-radius: 10px !important; opacity: 1 !important; background-color: ${(!loading && !input.trim()) ? '#f9fafb' : '#e0e7ff'} !important;`"
              :class="loading 
                ? 'text-red-500 hover:bg-[#c7d2fe]' 
                : (input.trim() ? 'text-primary hover:bg-[#c7d2fe]' : 'text-gray-300 cursor-not-allowed')"
            >
              <Square v-if="loading" :size="18" fill="currentColor" />
              <Send v-else :size="18" />
            </button>
          </div>
        </div>
      </div>
      
      <!-- 底部安全提示 -->
      <p class="text-center text-[9px] text-text-tertiary font-black uppercase tracking-widest opacity-30">
        ModelHub may provide inaccurate info. verify important details.
      </p>
    </div>
  </div>
</template>

<script setup>
import { Paperclip, Send, Smile, Cpu, ChevronUp, Square } from 'lucide-vue-next';
import { ref, defineEmits } from 'vue';
import { storeToRefs } from 'pinia';
import { useChatStore } from '../stores/chatStore';

const chatStore = useChatStore();
const { loading, currentModel } = storeToRefs(chatStore);

// 输入内容响应式变量
const input = ref('');
// 文本框 DOM 引用
const textareaRef = ref(null);

// 模型选择状态
const showModelMenu = ref(false);
const models = ref([
  { name: 'GPT-4 Turbo' },
  { name: 'Claude 3.5 Sonnet' },
  { name: 'Gemini 1.5 Pro' },
]);

const selectModel = (name) => {
  currentModel.value = name;
  showModelMenu.value = false;
};

// 定义事件
const emit = defineEmits(['send', 'stop']);

/**
 * 处理发送逻辑
 */
const handleSend = () => {
  if (loading.value || !input.value.trim()) return;
  emit('send', input.value);
  input.value = '';
};

/**
 * 处理按钮点击逻辑（发送或停止）
 */
const handleAction = () => {
  if (loading.value) {
    emit('stop');
  } else {
    handleSend();
  }
};
</script>

<style scoped>
/* 隐藏滚动条 */
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
