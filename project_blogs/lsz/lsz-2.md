# 项目情况概述

- 前端核心
  - 统一头部 + 主题切换 + 头像菜单： ChatHeader.vue
  - 列表/上传/预览：
    - 列表组件（按钮定宽、列字段对齐、学生栏仅显示负责人名字）： ApplicationFileList.vue
    - 上传面板（新增“我的申请书”入口）： ApplicationUploadPanel.vue
    - 预览面板（iframe 自动带 theme 参数）： ApplicationPreviewPanel.vue
  - 登录/注册/个人空间（电子签名显示/修改密码）： LoginView.vue 、 RegisterView.vue 、 ProfileView.vue
  - “我的申请书/任务书”与编辑器（支持自动保存、导出、上传；成员电子签名图片预览/写入 DOCX）： MyDocumentsView.vue 、 DocumentEditorView.vue
  - 路由与 API 封装（带多终端 fallback + devServer 代理 /api ）： index.js 、 eduevalApi.js 、 vue.config.js
  - 主题与样式（全站变量、夜间反色、评分卡片、提醒样式）： main.css

# 工作内容

## 申报功能开发

申报功能分为三个模块：文件上传、AI评分以及管理操作
文件上传支持批量选择文件，在文件上传后可根据文件类型进行推断自动识别文件扩展名，并且自动显示大小。将上传任务加入队列，按顺序进行处理。在并发控制方面，控制最多两个并发上传，避免浏览器卡死。

### 批量选择文件：

遍历选择的文件列表，为每个文件生成唯一 ID，将文件信息加入队列，触发 pumpQueue 开始处理。使用队列模式，任务一个个处理或少量并发。状态设计：排队之后、上传中、已完成，每个状态对应不同的UI展示
- Date.now() 确保时间戳唯一
- Math.random().toString(36) 生成随机字符串
- 组合格式 app_时间戳_随机字符，既保证唯一又便于调试时识别
- 由此形成客户端唯一标识，不会与服务器ID冲突

```javascript
function generateUniqueId() {
  return Math.random().toString(36).substring(2, 9);
}

function generateLocalId() {
  return `app_${Date.now()}_${generateUniqueId()}`;
}
```

### 定义申报功能的所有状态

- items 存储所有本地和服务器的申报项目
- queue 存储待上传的文件ID列表
- activeWorkers 追踪当前正在上传的数量
- maxConcurrent = 2 限制最多2个并发上传

```javascript
export const useApplicationStore = defineStore('applications', () => {
  const items = ref([]);
  const selectedLocalId = ref(null);
  const queue = ref([]);
  const activeWorkers = ref(0);
  const detailLoadingLocalId = ref(null);
  const listLoading = ref(false);
  const maxConcurrent = ref(2);
});
```

### 加入队列

遍历所有选择的文件，为每个文件生成唯一的ID，并且初始化项目对象（状态为queued），然后将ID加入队列，自动触发pumpQueue开始处理

```javascript
function enqueueBatch({ files = [], autoscore = true } = {}) {
  const fileList = Array.from(files || []);
  const createdLocalIds = [];

  fileList.forEach((file) => {
    const localId = generateLocalId();
    createdLocalIds.push(localId);

    items.value.unshift({
      localId,
      file,
      fileName: file.name,
      fileSize: file.size,
      fileSizeLabel: formatFilesize(file.size),
      fileType: inferFileType(file),
      uploadStatus: 'queued',
      scoreStatus: autoScore ? 'queued' : 'idle',
      autoscore: Boolean(autoScore),
      applicationId: null,
      application: null,
      extraction: null,
      score: null,
      detail: null,
      error: null,
      createdAt: Date.now(),
    });

    queue.value.push(localId);
  });

  if (!selectedLocalId.value && createdLocalIds.length) {
    selectedLocalId.value = createdLocalIds[0];
  }

  pumpQueue();
}
```

### 评分面板
对申报项目进行AI评分

实现思路：
- 检查项目是否有 applicationId
- 检查是否已在评分中（防止重复点击）
- 更新状态为 scoring
- 调用评分 API
- 成功后更新评分结果
- 如果当前选中，重新加载详情（刷新显示）

```javascript
async function loadDetail(localId) {
  const item = getItem(localId);
  if (!item?.applicationId) return;
  if (detailLoadingLocalId.value === localId) return;

  detailLoadingLocalId.value = localId;

  try {
    const detail = await fetchApplicationDetail(item.applicationId);
    updateItem(localId, {
      detail,
      application: detail?.application || item.application,
      extraction: detail?.extraction || item.extraction,
      score: detail?.score || item.score,
    });
  } catch (error) {
    updateItem(localId, {
      error: error?.message || String(error)
    });
  }
}
```

在此基础上，进一步实现了一次对多个申报项目进行评分
用户可以在申报列表中勾选多个项目，点击“批量评分”进行使用

```javascript
async function batchScoreByLocalIds(localIds = []) {
  const targets = Array.from(new Set(localIds))
    .map(id => getItem(id))
    .filter(Boolean)
    .filter(item => Boolean(item.applicationId))
    .map(item => item.applicationId);

  if (!targets.length) return;

  try {
    const payload = await batchScoreApplications(targets);
    const results = payload?.results || [];

    results.forEach(r => {
      const applicationId = r?.application_id;
      if (!applicationId) return;

      const idx = items.value.findIndex(item => item.applicationId === applicationId);
      if (idx === -1) return;

      items.value[idx] = {
        ...items.value[idx],
        scoreStatus: r?.success ? 'scored' : 'failed',
        score: r?.score || items.value[idx].score,
        error: r?.success ? null : (r?.error || items.value[idx].error),
      };
    });
  } catch (error) {
    const msg = error?.message || String(error);
    localIds.forEach((id) => {
      const item = getItem(id);
      if (!item) return;
      updateItem(id, { error: msg });
    });
  }
}
```
首先先定义了一个异步函数，接收一个本地ID数组，如果没有有效项目，则直接返回，如果有，则发送评分请求到后端，最后遍历返回结果，更新每个项目的状态和评分。如果批量API调用失败，则给所有项目标记错误


## 聊天界面

## 初步实现了新建对话、切换对话的功能

为每个对话生成唯一 ID，存储在 conversations 对象中，切换时更新 currentConversationId。支持多对话管理，用户可创建多个聊天会话并随时切换

```javascript
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
    content: '你好!我是ModelHub AI。我们开始聊天吧!'
  });
}
```
同时支持多对话管理，用户可创建多个聊天会话并随时切换
用户发送消息后调用模拟 API 获取回复，loading 状态控制显示，stopGenerating 可随时中断


## 实现文件拖拽上传功能

- 用户可以拖拽上传文件至聊天窗口，并且会生成预览URL，可以立即预览
- 如何实现：监听 dragenter、dragover、drop 事件，拖拽结束时获取文件并调用上传

```javascript
onMounted(() => {
  chatstore.initialize();
  document.addEventListener('dragenter', onDragEnter, true);
  document.addEventListener('dragleave', onDragLeave, true);
  document.addEventListener('dragover', onDragover, true);
  document.addEventListener('drop', onDrop, true);
  document.addEventListener('dragend', onDragEnd, true);
});

onUnmounted(() => {
  document.removeEventListener('dragenter', onDragEnter, true);
  document.removeEventListener('dragleave', onDragLeave, true);
  document.removeEventListener('dragover', onDragover, true);
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
```
根据文件 kind 类型选择渲染方式：图片显示 img 标签，文本显示 pre 标签，其他显示提示，最终可实现右侧文件预览版面，显示选中文件中的内容。调用 detectIntent 分析用户消息，识别到"整理文件"等意图后执行对应函数，接着就可以识别意图，识别用户输入中的意图并执行相应操作