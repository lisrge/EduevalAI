<template>
  <!-- 左侧边栏容器：边框改为更明确但依然极浅的灰色 #e2e8f0 -->
  <aside class="w-[220px] bg-[#f0f4f9] flex flex-col h-full overflow-hidden border-r border-[#f1f5f9]">
    
    <!-- 侧边栏头部：新建对话按钮 -->
    <div style="padding: 12px;">
      <button 
        @click="handleNewConversation"
        class="w-full bg-[#2563eb]/10 hover:bg-[#2563eb]/20 text-[#2563eb] font-black py-2 px-4 rounded-full flex items-center justify-center gap-2 transition-all active:scale-[0.98] border-none shadow-sm text-xs"
      >
        <Plus :size="16" stroke-width="3" />
        <span>新建对话</span>
      </button>
    </div>

    <!-- 历史会话列表 -->
    <div class="flex-1 overflow-y-auto scrollbar-hide" style="padding: 0 8px 12px 8px;">
      <!-- 遍历历史分组 -->
      <div v-for="(group, groupName) in historyGroups" :key="groupName" style="margin-bottom: 12px;">
        <!-- 分组标题 -->
        <h3 style="padding: 0 8px; margin-bottom: 4px;" class="text-[9px] font-black text-text-tertiary uppercase tracking-wider opacity-50">
          {{ groupName }}
        </h3>
        <!-- 会话项：浅灰色圆角矩形背景，图标标题同行 -->
        <div style="display: flex; flex-direction: column; gap: 4px;">
          <div 
            v-for="chat in group" 
            :key="chat.id"
            @click="handleSwitchConversation(chat.id)"
            class="group rounded-lg cursor-pointer transition-all duration-200 flex items-center"
            style="gap: 8px; padding: 8px 10px; background-color: #f1f5f9;"
            :style="currentConversationId === chat.id ? 'background-color: #e2e8f0; color: #2563eb;' : ''"
          >
            <!-- 左侧消息图标：强制同行对齐 -->
            <div class="shrink-0 flex items-center justify-center w-4 h-4">
              <Loader2 v-if="chat.loading" :size="12" class="animate-spin text-primary" />
              <MessageSquare v-else :size="12" :style="currentConversationId === chat.id ? 'color: #2563eb;' : 'color: #64748b;'" />
            </div>
            
            <!-- 内容区：单行 -->
            <div class="flex-1 min-w-0 flex items-center justify-between gap-2">
              <p class="text-[11px] font-bold truncate leading-none" :style="currentConversationId === chat.id ? 'color: #2563eb;' : 'color: #1e293b;'">{{ chat.title }}</p>
              <!-- 模型标签 -->
              <span v-if="!chat.loading" class="shrink-0 text-[7px] px-1 py-0.5 bg-white/50 text-slate-500 rounded font-black uppercase">
                {{ chat.model }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { Plus, MessageSquare, Loader2 } from 'lucide-vue-next';
import { useChatStore } from '../stores/chatStore';

const chatStore = useChatStore();
const { history, currentConversationId } = storeToRefs(chatStore);

const handleNewConversation = () => {
  chatStore.createNewConversation();
};

const handleSwitchConversation = (id) => {
  chatStore.switchConversation(id);
};

// 简单的按时间分组逻辑
const historyGroups = computed(() => {
  // 在这里可以实现更复杂的按“今日”、“本周”等分组的逻辑
  // 目前为了简单起见，直接返回一个分组
  return {
    '最近对话': history.value
  };
});

</script>

<style scoped>
/* 隐藏滚动条样式 */
.scrollbar-hide::-webkit-scrollbar {
  display: none;
}
.scrollbar-hide {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
