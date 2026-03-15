<template>
  <!-- 消息列表容器：移除 w-full，改用 flex-1 和 min-w-0，配合 overflow-x-hidden -->
  <div class="flex-1 h-full overflow-y-auto overflow-x-hidden p-2 md:p-6 space-y-6 bg-white scroll-smooth scrollbar-thin flex flex-col relative min-w-0" style="box-sizing: border-box;" ref="scrollContainer">
    <!-- 消息内容容器 -->
    <div class="flex-1 flex flex-col min-h-0 min-w-0">
      <!-- 遍历渲染消息 -->
      <MessageItem 
        v-for="(msg, index) in messages" 
        :key="index" 
        :message="msg" 
        :is-continuous="isContinuousMessage(index)"
      />
    </div>
    
    <!-- AI 思考中的加载状态，增加留白 -->
    <div v-if="loading" class="flex items-start gap-6 mt-12 px-2">
      <!-- 三点跳动动画：移除边框，使用背景色块 -->
      <div class="bg-ai-bubble px-6 py-4 rounded-[24px] rounded-tl-[4px] flex items-center gap-2 shadow-sm">
        <div class="w-1.5 h-1.5 bg-text-tertiary rounded-full animate-bounce [animation-duration:0.8s]"></div>
        <div class="w-1.5 h-1.5 bg-text-tertiary rounded-full animate-bounce [animation-duration:0.8s] [animation-delay:0.2s]"></div>
        <div class="w-1.5 h-1.5 bg-text-tertiary rounded-full animate-bounce [animation-duration:0.8s] [animation-delay:0.4s]"></div>
      </div>
    </div>

    <!-- 底部锚点：用于自动滚动到底部 -->
    <div ref="bottomAnchor" class="h-4"></div>
  </div>
</template>

<script setup>
import { defineProps, ref, watch, onMounted, nextTick } from 'vue';
import MessageItem from './MessageItem.vue';

/**
 * 属性定义
 */
const props = defineProps({
  messages: {
    type: Array,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
});

const scrollContainer = ref(null);
const bottomAnchor = ref(null);

/**
 * 判断是否为同一角色的连续消息
 * @param {number} index 当前消息索引
 * @returns {boolean}
 */
const isContinuousMessage = (index) => {
  if (index === 0) return false;
  // 如果当前消息标记了是停止后的第一条，强制不连续
  if (props.messages[index].isFirstAfterStop) return false;
  return props.messages[index].role === props.messages[index - 1].role;
};

/**
 * 自动滚动到底部
 */
const scrollToBottom = async () => {
  await nextTick();
  if (bottomAnchor.value) {
    bottomAnchor.value.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }
};

// 监听消息变化自动滚动
watch(() => props.messages, scrollToBottom, { deep: true });
watch(() => props.loading, (newVal) => { if (newVal) scrollToBottom(); });

onMounted(scrollToBottom);
</script>

<style scoped>
/* 自定义细滚动条 */
.scrollbar-thin::-webkit-scrollbar {
  width: 6px;
}
.scrollbar-thin::-webkit-scrollbar-track {
  background: transparent;
}
.scrollbar-thin::-webkit-scrollbar-thumb {
  background: #e2e8f0;
  border-radius: 10px;
}
.scrollbar-thin::-webkit-scrollbar-thumb:hover {
  background: #cbd5e1;
}
</style>
