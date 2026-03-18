<template>
  <!-- 消息项：锁定宽度，使用 box-sizing 确保 padding 不溢出 -->
  <div 
    class="flex group transition-all duration-500 ease-out overflow-hidden min-w-0 w-full" 
    :class="[
      message.role === 'user' ? 'justify-end' : 'justify-start'
    ]"
    :style="`padding: 4px 8px; margin-top: ${isContinuous ? '2px' : '20px'}; box-sizing: border-box;`"
  >
    <!-- 消息内容包装器：严格限制最大宽度 -->
    <div 
      class="flex max-w-[92%] md:max-w-[80%] gap-3 min-w-0"
      :class="message.role === 'user' ? 'flex-row-reverse' : 'flex-row'"
    >
      <!-- 头像显示：圆形纯色背景，无边框 -->
      <div class="shrink-0 mt-1">
        <div 
          v-if="!isContinuous"
          class="w-8 h-8 rounded-full flex items-center justify-center transition-transform group-hover:scale-105 duration-300 shadow-sm"
          :class="message.role === 'ai' ? 'bg-[#f0f4f9]' : 'bg-[#2563eb]/10'"
        >
          <Bot v-if="message.role === 'ai'" :size="16" class="text-primary" />
          <User v-else :size="16" class="text-primary" />
        </div>
        <div v-else class="w-8 h-8"></div>
      </div>

      <!-- 内容主体 -->
      <div class="flex flex-col gap-1.5 min-w-0" :class="message.role === 'user' ? 'items-end' : 'items-start'">
        <!-- 角色标签 -->
        <div v-if="!isContinuous" class="flex items-center gap-2 px-1">
          <span class="text-[9px] font-black text-text-tertiary uppercase tracking-widest opacity-60">
            {{ message.role === 'user' ? 'User' : (message.model || 'ModelHub AI') }}
          </span>
        </div>

        <!-- 消息气泡：强制换行，限制宽度 -->
        <div 
          class="text-[13px] leading-relaxed break-all overflow-wrap-anywhere transition-all duration-300 shadow-sm"
          :class="message.role === 'user' ? 'text-white' : 'text-text-primary'"
          :style="message.role === 'user' 
            ? 'background-color: #2563eb; color: #ffffff !important; border-radius: 16px 2px 16px 16px; padding: 10px 16px;' 
            : 'background-color: #f0f4f9; color: #1e293b !important; border-radius: 2px 16px 16px 16px; padding: 10px 16px;'"
        >
          <template v-if="message.type === 'tool_result'">
            <div class="flex items-center gap-2 font-black text-[11px] uppercase tracking-widest opacity-70" style="color: inherit !important;">
              <span>🔧</span>
              <span>{{ message.toolName || '工具' }}</span>
            </div>
            <pre class="whitespace-pre-wrap font-medium break-words mt-2" style="color: inherit !important; font-family: inherit; margin: 0;">{{ message.result }}</pre>
            <div v-if="message.actions?.length" class="flex flex-wrap gap-2 mt-3">
              <button
                v-for="(action, i) in message.actions"
                :key="i"
                class="px-3 py-1.5 rounded-full bg-white/70 hover:bg-white text-[11px] font-black text-primary uppercase tracking-tighter shadow-sm transition-colors"
                @click="emitAction(action.command)"
              >
                {{ action.label }}
              </button>
            </div>
          </template>

          <template v-else-if="message.type === 'intent_detected'">
            <div class="flex items-center gap-2 font-black text-[11px] uppercase tracking-widest opacity-70" style="color: inherit !important;">
              <span>🤔</span>
              <span>意图识别</span>
            </div>
            <div class="whitespace-pre-wrap font-medium break-words mt-2" style="color: inherit !important;">
              {{ message.message || message.content }}
            </div>
            <div v-if="message.actions?.length" class="flex flex-wrap gap-2 mt-3">
              <button
                v-for="(action, i) in message.actions"
                :key="i"
                class="px-3 py-1.5 rounded-full bg-white/70 hover:bg-white text-[11px] font-black text-primary uppercase tracking-tighter shadow-sm transition-colors"
                @click="emitAction(action.command)"
              >
                {{ action.label }}
              </button>
            </div>
          </template>

          <template v-else>
            <!-- 消息文本：强制换行 -->
            <div class="whitespace-pre-wrap font-medium break-words" style="color: inherit !important;">
              {{ message.content }}
            </div>
            
            <!-- 流式输出光标 -->
            <span v-if="message.streaming" class="inline-block w-1.5 h-4 bg-primary ml-1 animate-pulse align-middle"></span>
          </template>
        </div>

        <!-- 思考过程：色块化展示 -->
        <div v-if="message.thinking" class="w-full mt-2">
          <button 
            @click="showThinking = !showThinking"
            class="flex items-center gap-2 text-[11px] font-bold text-text-tertiary hover:text-primary transition-all py-1.5 px-2 group/think uppercase tracking-tighter"
          >
            <ChevronDown :size="14" :class="showThinking ? 'rotate-180 transition-transform' : 'transition-transform'" />
            <span class="group-hover/think:underline decoration-dotted underline-offset-4">Thought Process</span>
          </button>
          <div v-show="showThinking" class="mt-2 p-4 bg-sidebar-bg/60 border-l-4 border-primary/20 rounded-r-2xl text-[13px] text-text-secondary italic leading-relaxed shadow-inner">
            {{ message.thinking }}
          </div>
        </div>

        <!-- 信息来源标签 -->
        <div v-if="message.sources?.length" class="flex flex-wrap gap-2 mt-2 px-1">
          <div 
            v-for="(source, i) in message.sources" 
            :key="i"
            class="flex items-center gap-2 px-4 py-1.5 bg-blue-50 text-primary rounded-full text-[10px] font-black uppercase tracking-tighter hover:bg-blue-100 transition-colors cursor-pointer shadow-sm"
          >
            <FileText :size="12" />
            <span>{{ source }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, defineEmits, defineProps } from 'vue';
import { Bot, User, ChevronDown, FileText } from 'lucide-vue-next';

/**
 * 接收消息对象属性
 */
defineProps({
  message: {
    type: Object,
    required: true
  },
  isContinuous: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['action']);

const showThinking = ref(false);

const emitAction = (command) => {
  if (!command) return;
  emit('action', command);
};
</script>
