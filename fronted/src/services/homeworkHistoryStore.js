const STORAGE_KEY = 'edueval_homework_upload_history_v1';

export const HOMEWORK_TYPES = [
  { key: 'source', label: '项目代码压缩包', accept: '.zip,.7z,.rar,.tar,.gz,.bz2,.xz' },
  { key: 'ppt', label: 'PPT', accept: '.ppt,.pptx,.pdf' },
  { key: 'video', label: '演示视频', accept: '.mp4,.mov,.avi,.mkv,.webm' },
  { key: 'summary', label: '工作概述', accept: '.pdf,.doc,.docx,.txt,.md' },
];

function readRaw() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch (e) {
    return {};
  }
}

function writeRaw(value) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(value || {}));
}

export function getHistoryByType(typeKey) {
  const all = readRaw();
  const list = Array.isArray(all[typeKey]) ? all[typeKey] : [];
  return list.sort((a, b) => String(b.uploadedAt || '').localeCompare(String(a.uploadedAt || '')));
}

export function addHistoryItem(typeKey, file) {
  const all = readRaw();
  const list = Array.isArray(all[typeKey]) ? all[typeKey] : [];
  list.push({
    id: `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    name: file?.name || 'unknown',
    size: Number(file?.size || 0),
    uploadedAt: new Date().toISOString(),
  });
  all[typeKey] = list;
  writeRaw(all);
}

export function removeHistoryItem(typeKey, itemId) {
  const all = readRaw();
  const list = Array.isArray(all[typeKey]) ? all[typeKey] : [];
  all[typeKey] = list.filter((item) => item?.id !== itemId);
  writeRaw(all);
}
