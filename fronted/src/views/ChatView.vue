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
        <main ref="chatPanelRef" class="flex-1 flex flex-col min-w-0 bg-white rounded-[24px] shadow-sm overflow-hidden relative h-full">
          <!-- 消息显示列表：直接作为 flex 子元素，并强制 w-full 和 overflow-hidden -->
          <div class="flex-1 min-h-0 min-w-0 overflow-hidden relative">
            <MessageList :messages="messages" :loading="loading" @action="onSendMessage" @file-select="onSelectFile" />
          </div>

          <!-- 底部操作区容器：固定白色背景，shrink-0 确保不被压缩，移除边框 -->
          <div class="shrink-0 flex flex-col bg-white pb-4 px-4 z-20 shadow-[0_-10px_20px_-5px_rgba(0,0,0,0.03)]">
            <!-- 技能切换栏 -->
            <SkillBar v-if="enableSkillBar" />
            <!-- 用户输入区域 -->
            <ChatInput @send="onSendMessage" @stop="onStopResponse" @upload="onUploadFiles" :loading="loading" />
          </div>
        </main>

        <aside v-if="selectedFile" class="w-[420px] flex flex-col gap-3 shrink-0 overflow-hidden pr-1">
          <div class="bg-[#f0f4f9] rounded-panel p-5 shadow-sm flex flex-col h-full overflow-hidden">
            <div class="flex items-center justify-between gap-3 mb-4">
              <div class="min-w-0">
                <div class="text-[11px] font-black uppercase tracking-widest text-text-tertiary">文件预览</div>
                <div class="text-[13px] font-black text-text-primary truncate">{{ selectedFile.name }}</div>
              </div>
              <button
                class="px-3 py-1.5 rounded-full border-none outline-none focus:outline-none focus:ring-0 text-[11px] font-black uppercase tracking-tighter shadow-sm transition-colors"
                style="background-color: rgba(224,231,255,0.9); color: rgba(37,99,235,0.85);"
                @click="chatStore.clearSelectedFile()"
              >
                关闭
              </button>
            </div>

            <div class="flex-1 min-h-0 bg-white rounded-[20px] shadow-sm overflow-hidden">
              <div v-if="selectedFile.kind === 'image'" class="w-full h-full flex items-center justify-center p-4 bg-white">
                <img :src="selectedFile.url" :alt="selectedFile.name" class="max-w-full max-h-full object-contain" />
              </div>
              <div v-else-if="selectedFile.kind === 'text'" class="w-full h-full overflow-auto p-4">
                <pre class="whitespace-pre-wrap break-words text-[12px] leading-relaxed font-medium text-text-primary" style="font-family: inherit; margin: 0;">{{ selectedFile.text }}</pre>
              </div>
              <div v-else class="w-full h-full flex items-center justify-center p-6 text-center">
                <div class="text-[12px] font-black text-text-tertiary">
                  暂不支持该文件类型预览
                </div>
              </div>
            </div>

            <div class="mt-4 flex items-center justify-between text-[10px] font-black uppercase tracking-widest text-text-tertiary opacity-70">
              <span>{{ selectedFile.kind }}</span>
              <span>{{ selectedFile.type || 'unknown' }}</span>
            </div>
          </div>
        </aside>

        <!-- 右侧功能面板：圆角容器 -->
        <aside v-else class="hidden xl:flex w-80 flex-col gap-4 shrink-0 overflow-y-auto pr-1">
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
import { onMounted, onUnmounted, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { Info, Sparkles, FileText } from 'lucide-vue-next';
import { useChatStore } from '../stores/chatStore';
import ChatSidebar from '../components/ChatSidebar.vue';
import ChatHeader from '../components/ChatHeader.vue';
import MessageList from '../components/MessageList.vue';
import SkillBar from '../components/SkillBar.vue';
import ChatInput from '../components/ChatInput.vue';

const chatStore = useChatStore();
const { messages, loading, currentModel, selectedFile } = storeToRefs(chatStore);

const enableSkillBar = false;

const isDragOverlayVisible = ref(false);
const hideOverlayTimer = ref(null);
const dragOverlayEl = ref(null);
const dragOverlayBoxEl = ref(null);
const chatPanelRef = ref(null);

onMounted(() => {
  chatStore.initialize();

  document.addEventListener('dragenter', onDragEnter, true);
  document.addEventListener('dragleave', onDragLeave, true);
  document.addEventListener('dragover', onDragOver, true);
  document.addEventListener('drop', onDrop, true);
  document.addEventListener('dragend', onDragEnd, true);
});

onUnmounted(() => {
  document.removeEventListener('dragenter', onDragEnter, true);
  document.removeEventListener('dragleave', onDragLeave, true);
  document.removeEventListener('dragover', onDragOver, true);
  document.removeEventListener('drop', onDrop, true);
  document.removeEventListener('dragend', onDragEnd, true);
  if (hideOverlayTimer.value) {
    clearTimeout(hideOverlayTimer.value);
    hideOverlayTimer.value = null;
  }
  if (dragOverlayEl.value) {
    dragOverlayEl.value.remove();
    dragOverlayEl.value = null;
  }
  dragOverlayBoxEl.value = null;
});

const onSendMessage = (text) => {
  chatStore.sendMessage(text);
};

const onStopResponse = () => {
  chatStore.stopGenerating();
};

const onUploadFiles = (files) => {
  chatStore.uploadFiles(files);
};

const onSelectFile = (fileId) => {
  chatStore.selectFile(fileId);
};

const ensureDragOverlay = () => {
  if (dragOverlayEl.value) return dragOverlayEl.value;

  const root = document.createElement('div');
  root.style.position = 'fixed';
  root.style.inset = '0';
  root.style.zIndex = '2147483647';
  root.style.pointerEvents = 'none';
  root.style.display = 'none';

  const box = document.createElement('div');
  box.style.position = 'absolute';
  box.style.boxSizing = 'border-box';
  box.style.inset = 'auto';
  box.style.borderRadius = '28px';
  box.style.border = '3px dashed rgba(37, 99, 235, 0.55)';
  box.style.background = 'rgba(191, 219, 254, 0.55)';
  box.style.display = 'flex';
  box.style.alignItems = 'center';
  box.style.justifyContent = 'center';

  const content = document.createElement('div');
  content.style.display = 'flex';
  content.style.flexDirection = 'column';
  content.style.alignItems = 'center';
  content.style.gap = '12px';
  content.style.color = 'rgba(29, 78, 216, 0.65)';

  const icon = document.createElement('div');
  icon.textContent = '📄';
  icon.style.fontSize = '44px';
  icon.style.lineHeight = '1';

  const text = document.createElement('div');
  text.textContent = '拖入以上传文件';
  text.style.fontSize = '14px';
  text.style.fontWeight = '900';
  text.style.letterSpacing = '-0.01em';

  content.appendChild(icon);
  content.appendChild(text);
  box.appendChild(content);
  root.appendChild(box);
  document.body.appendChild(root);

  dragOverlayEl.value = root;
  dragOverlayBoxEl.value = box;
  return root;
};

const updateOverlayBounds = () => {
  const box = dragOverlayBoxEl.value;
  if (!box) return;

  const rect = chatPanelRef.value?.getBoundingClientRect?.();
  const margin = 5;

  if (!rect) {
    box.style.top = `${margin}px`;
    box.style.left = `${margin}px`;
    box.style.right = `${margin}px`;
    box.style.bottom = `${margin}px`;
    box.style.width = 'auto';
    box.style.height = 'auto';
    return;
  }

  const width = Math.max(0, rect.width - margin * 2);
  const height = Math.max(0, rect.height - margin * 2);
  box.style.top = `${rect.top + margin}px`;
  box.style.left = `${rect.left + margin}px`;
  box.style.width = `${width}px`;
  box.style.height = `${height}px`;
  box.style.right = 'auto';
  box.style.bottom = 'auto';
};

const showOverlay = () => {
  if (hideOverlayTimer.value) {
    clearTimeout(hideOverlayTimer.value);
    hideOverlayTimer.value = null;
  }
  isDragOverlayVisible.value = true;
  const el = ensureDragOverlay();
  updateOverlayBounds();
  el.style.display = 'block';
};

const scheduleHideOverlay = () => {
  if (hideOverlayTimer.value) clearTimeout(hideOverlayTimer.value);
  hideOverlayTimer.value = setTimeout(() => {
    isDragOverlayVisible.value = false;
    if (dragOverlayEl.value) dragOverlayEl.value.style.display = 'none';
    hideOverlayTimer.value = null;
  }, 80);
};

const onDragEnter = (event) => {
  showOverlay();
};

const onDragLeave = (event) => {
  scheduleHideOverlay();
};

const onDragOver = (event) => {
  event.preventDefault();
  showOverlay();
};

const onDrop = (event) => {
  event.preventDefault();
  isDragOverlayVisible.value = false;
  if (dragOverlayEl.value) dragOverlayEl.value.style.display = 'none';
  if (hideOverlayTimer.value) {
    clearTimeout(hideOverlayTimer.value);
    hideOverlayTimer.value = null;
  }
  const files = event.dataTransfer?.files;
  if (files && files.length) {
    chatStore.uploadFiles(files);
  }
};

const onDragEnd = () => {
  isDragOverlayVisible.value = false;
  if (dragOverlayEl.value) dragOverlayEl.value.style.display = 'none';
  if (hideOverlayTimer.value) {
    clearTimeout(hideOverlayTimer.value);
    hideOverlayTimer.value = null;
  }
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
