import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

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

export const useChatStore = defineStore('chat', () => {
  // --- State ---
  const conversations = ref({});
  const currentConversationId = ref(null);
  const currentModel = ref('GPT-4 Turbo');
  
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
    
    // 检查是否需要显示头像（如果是停止后的第一条或者新对话的第一条）
    const isFirstAfterStop = convo.wasInterrupted;
    convo.wasInterrupted = false;

    const userMessage = { 
      role: 'user', 
      content,
      isFirstAfterStop: isFirstAfterStop || convo.messages.length === 0
    };
    
    convo.messages.push(userMessage);

    // 如果是第一条用户消息，使用它作为标题
    if (convo.messages.filter(m => m.role === 'user').length === 1) {
      convo.title = content.substring(0, 20);
    }

    convo.loading = true;
    
    try {
      const aiMessage = await mockApi.chat(content);
      // 确保消息仍然发送到正确的会话中
      if (conversations.value[targetId] && conversations.value[targetId].loading) {
        aiMessage.model = currentModel.value;
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

  return {
    // State
    conversations,
    currentConversationId,
    currentModel,
    // Getters
    currentConversation,
    messages,
    loading,
    history,
    // Actions
    initialize,
    sendMessage,
    stopGenerating,
    createNewConversation,
    switchConversation,
  };
});
