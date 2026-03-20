import { defineStore, acceptHMRUpdate } from 'pinia';
import { ref, computed } from 'vue';
import { detectIntent } from '../utils/intent';
import { executeOrganizeFiles, previewOrganizeFiles } from '../services/tools';
import { INTENTS, TOOL_NAMES } from '../constants/intents';

// 模拟 API
const mockApi = {
  chat: (content) => {
    return new Promise(resolve => {
      setTimeout(() => {
        resolve({
          role: 'ai',
          model: 'GPT-4 Turbo',
          content: `这是对“${content}”的模拟回复。`,
          thinking: '我正在模拟一个 API 调用来生成这个回复。'
        });
      }, 1500);
    });
  }
};

function generateUniqueId() {
  return Math.random().toString(36).substring(2, 9);
}

function generateFileId() {
  return `file_${Date.now()}_${generateUniqueId()}`;
}

function formatFileSize(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const idx = Math.min(units.length - 1, Math.floor(Math.log(value) / Math.log(1024)));
  const size = value / Math.pow(1024, idx);
  return `${size.toFixed(idx === 0 ? 0 : 1)} ${units[idx]}`;
}

function inferFileKind(file) {
  const name = String(file?.name || '').toLowerCase();
  const type = String(file?.type || '').toLowerCase();
  if (type.startsWith('image/')) return 'image';
  if (type.startsWith('text/')) return 'text';
  if (/\.(txt|md|json|csv|log|yaml|yml)$/i.test(name)) return 'text';
  return 'unknown';
}

function readFileAsText(file, maxChars) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      resolve(text.length > maxChars ? `${text.slice(0, maxChars)}\n\n…（内容已截断）` : text);
    };
    reader.onerror = () => reject(reader.error || new Error('read failed'));
    reader.readAsText(file);
  });
}

export const useChatStore = defineStore('chat', () => {
  // --- State ---
  const conversations = ref({});
  const currentConversationId = ref(null);
  const currentModel = ref('GPT-4 Turbo');
  const uploadedFiles = ref({});
  const selectedFileId = ref(null);
  
  // --- Getters ---
  const currentConversation = computed(() => {
    return conversations.value[currentConversationId.value] || null;
  });

  const messages = computed(() => {
    return currentConversation.value ? currentConversation.value.messages : [];
  });

  const loading = computed(() => {
    return currentConversation.value ? currentConversation.value.loading : false;
  });

  const history = computed(() => {
    return Object.values(conversations.value).map(({ id, title, model, loading }) => ({ 
      id, 
      title, 
      model,
      loading 
    }));
  });

  const selectedFile = computed(() => {
    const id = selectedFileId.value;
    if (!id) return null;
    return uploadedFiles.value[id] || null;
  });

  // --- Actions ---

  /**
   * 初始化，创建第一个对话
   */
  function initialize() {
    if (Object.keys(conversations.value).length === 0) {
      createNewConversation();
    } else if (!currentConversationId.value) {
      currentConversationId.value = Object.keys(conversations.value)[0];
    }
  }

  /**
   * 发送消息
   * @param {string} content 
   */
  async function sendMessage(content) {
    const targetId = currentConversationId.value;
    if (!targetId || !conversations.value[targetId]) return;

    const convo = conversations.value[targetId];
    const normalizedContent = String(content || '');
    
    // 检查是否需要显示头像（如果是停止后的第一条或者新对话的第一条）
    const isFirstAfterStop = convo.wasInterrupted;
    convo.wasInterrupted = false;

    const userMessage = { 
      role: 'user', 
      type: 'text',
      content: normalizedContent,
      isFirstAfterStop: isFirstAfterStop || convo.messages.length === 0
    };
    
    convo.messages.push(userMessage);

    // 如果是第一条用户消息，使用它作为标题
    if (convo.messages.filter(m => m.role === 'user').length === 1) {
      convo.title = normalizedContent.substring(0, 20);
    }

    convo.loading = true;
    
    try {
      const detected = detectIntent(normalizedContent);

      if (detected?.intent === INTENTS.ORGANIZE_FILES) {
        const toolResult =
          detected.mode === 'execute'
            ? await executeOrganizeFiles(detected.params)
            : await previewOrganizeFiles(detected.params);

        const pathLabel =
          detected.params.pathKey === 'desktop'
            ? '桌面'
            : detected.params.pathKey === 'documents'
              ? '文档'
              : '下载';

        const actions =
          detected.mode === 'execute'
            ? []
            : [
                { label: '确认整理', command: `确认整理 ${pathLabel}` },
                { label: '直接整理', command: `直接整理 ${pathLabel}` },
              ];

        if (conversations.value[targetId] && conversations.value[targetId].loading) {
          conversations.value[targetId].messages.push({
            role: 'ai',
            type: 'tool_result',
            toolName: TOOL_NAMES.ORGANIZER,
            result: toolResult,
            actions,
            model: currentModel.value,
          });
          conversations.value[targetId].model = currentModel.value;
        }
        return;
      }

      if (normalizedContent.startsWith('确认整理') || normalizedContent.startsWith('直接整理') || normalizedContent.startsWith('执行整理')) {
        const pathKey = normalizedContent.includes('桌面') ? 'desktop' : normalizedContent.includes('文档') ? 'documents' : 'downloads';
        const toolResult = await executeOrganizeFiles({ pathKey });

        if (conversations.value[targetId] && conversations.value[targetId].loading) {
          conversations.value[targetId].messages.push({
            role: 'ai',
            type: 'tool_result',
            toolName: TOOL_NAMES.ORGANIZER,
            result: toolResult,
            actions: [],
            model: currentModel.value,
          });
          conversations.value[targetId].model = currentModel.value;
        }
        return;
      }

      const aiMessage = await mockApi.chat(normalizedContent);
      aiMessage.type = 'text';
      aiMessage.model = currentModel.value;

      if (conversations.value[targetId] && conversations.value[targetId].loading) {
        conversations.value[targetId].messages.push(aiMessage);
        conversations.value[targetId].model = currentModel.value;
      }
    } finally {
      if (conversations.value[targetId]) {
        conversations.value[targetId].loading = false;
      }
    }
  }

  /**
   * 停止生成
   */
  function stopGenerating() {
    if (currentConversationId.value && conversations.value[currentConversationId.value]) {
      conversations.value[currentConversationId.value].loading = false;
      conversations.value[currentConversationId.value].wasInterrupted = true;
    }
  }

  /**
   * 新建对话
   */
  function createNewConversation() {
    const id = generateUniqueId();
    conversations.value[id] = {
      id,
      title: '新的对话',
      messages: [],
      model: currentModel.value,
      loading: false,
      wasInterrupted: false
    };
    currentConversationId.value = id;
    
    // 添加欢迎语
    conversations.value[id].messages.push({
      role: 'ai',
      type: 'text',
      model: currentModel.value,
      content: '你好！我是 ModelHub AI。我们开始聊天吧！',
    });
  }

  /**
   * 切换对话
   * @param {string} id 
   */
  function switchConversation(id) {
    if (conversations.value[id]) {
      currentConversationId.value = id;
      currentModel.value = conversations.value[id].model;
    }
  }

  async function uploadFiles(files) {
    const targetId = currentConversationId.value;
    if (!targetId || !conversations.value[targetId]) return;

    const list = Array.from(files || []).filter(Boolean);
    if (!list.length) return;

    const convo = conversations.value[targetId];

    const fileEntries = [];
    for (const file of list) {
      const id = generateFileId();
      const kind = inferFileKind(file);
      const entry = {
        id,
        name: file.name,
        size: file.size,
        type: file.type,
        kind,
        uploadedAt: Date.now(),
        url: null,
        text: null,
        serverFileId: null,
      };

      if (kind === 'image') {
        entry.url = URL.createObjectURL(file);
      } else if (kind === 'text') {
        try {
          entry.text = await readFileAsText(file, 200000);
        } catch (e) {
          entry.text = '⚠️ 无法读取文本内容';
        }
      }

      uploadedFiles.value[id] = entry;
      fileEntries.push(entry);
    }

    const fileLines = list.map(f => `- ${f.name} (${formatFileSize(f.size)})`);
    convo.messages.push({
      role: 'user',
      type: 'text',
      content: `上传文件：\n${fileLines.join('\n')}`,
      isFirstAfterStop: convo.wasInterrupted || convo.messages.length === 0,
    });
    convo.wasInterrupted = false;

    const formData = new FormData();
    for (const file of list) {
      formData.append('files', file, file.name);
    }

    let resultText = '';

    try {
      const response = await fetch('/api/files/upload', {
        method: 'POST',
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();
      const items = data?.data?.files || data?.files || [];
      const uploadedLines = Array.isArray(items) && items.length
        ? items.map(item => `- ${item.originalName || item.name || 'unknown'}${item.fileId ? `（ID: ${item.fileId}）` : ''}`)
        : list.map(f => `- ${f.name}`);
      resultText = `✅ 上传成功\n${uploadedLines.join('\n')}`;

      if (Array.isArray(items) && items.length) {
        for (let i = 0; i < Math.min(items.length, fileEntries.length); i += 1) {
          const fileId = items[i]?.fileId;
          if (fileId) {
            uploadedFiles.value[fileEntries[i].id].serverFileId = fileId;
          }
        }
      }
    } catch (error) {
      resultText = `⚠️ 未能上传到服务器（后端未接入或接口不可用）\n已读取待上传文件：\n${fileLines.join('\n')}`;
    }

    convo.messages.push({
      role: 'ai',
      type: 'file_upload_result',
      toolName: '文档上传',
      result: resultText,
      files: fileEntries.map(f => ({
        id: f.id,
        name: f.name,
        size: f.size,
        kind: f.kind,
      })),
      actions: [],
      model: currentModel.value,
    });
    convo.model = currentModel.value;
  }

  function selectFile(fileId) {
    if (!fileId) return;
    if (!uploadedFiles.value[fileId]) return;
    selectedFileId.value = fileId;
  }

  function clearSelectedFile() {
    selectedFileId.value = null;
  }

  return {
    // State
    conversations,
    currentConversationId,
    currentModel,
    uploadedFiles,
    selectedFileId,
    // Getters
    currentConversation,
    messages,
    loading,
    history,
    selectedFile,
    // Actions
    initialize,
    sendMessage,
    stopGenerating,
    createNewConversation,
    switchConversation,
    uploadFiles,
    selectFile,
    clearSelectedFile,
  };
});

if (module.hot) {
  module.hot.accept(acceptHMRUpdate(useChatStore, module.hot));
}
