const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']);
const WORD_EXTENSIONS = new Set(['doc', 'docx']);
const EXCEL_EXTENSIONS = new Set(['xls', 'xlsx', 'csv']);
const VIDEO_EXTENSIONS = new Set(['mp4', 'webm', 'ogg', 'mov', 'm4v']);
const ARCHIVE_EXTENSIONS = new Set(['zip', 'rar', '7z', 'tar', 'gz']);
const PRESENTATION_EXTENSIONS = new Set(['ppt', 'pptx', 'pps', 'ppsx']);

export function getFileExtension(fileName = '') {
  const text = String(fileName || '').trim();
  const parts = text.split('.');
  return parts.length > 1 ? String(parts.pop() || '').toLowerCase() : '';
}

export function detectSubmissionAssetPreview(asset = {}) {
  const fileName = String(asset?.file_name || '');
  const mimeType = String(asset?.mime_type || '').toLowerCase();
  const extension = getFileExtension(fileName);

  if (mimeType.includes('pdf') || extension === 'pdf') {
    return { type: 'pdf', label: 'PDF 在线预览', canPreview: true };
  }
  if (mimeType.startsWith('image/') || IMAGE_EXTENSIONS.has(extension)) {
    return { type: 'image', label: '图片预览', canPreview: true };
  }
  if (
    mimeType.includes('word') ||
    mimeType.includes('officedocument.wordprocessingml') ||
    WORD_EXTENSIONS.has(extension)
  ) {
    return { type: 'word', label: 'Word 预览', canPreview: true };
  }
  if (
    mimeType.includes('excel') ||
    mimeType.includes('spreadsheetml') ||
    mimeType.includes('csv') ||
    EXCEL_EXTENSIONS.has(extension)
  ) {
    return { type: 'excel', label: 'Excel 预览', canPreview: true };
  }
  if (
    mimeType.includes('presentation') ||
    mimeType.includes('powerpoint') ||
    PRESENTATION_EXTENSIONS.has(extension)
  ) {
    return { type: 'presentation', label: 'PPT 预览', canPreview: true };
  }
  if (mimeType.startsWith('video/') || VIDEO_EXTENSIONS.has(extension)) {
    return { type: 'video', label: '视频预览', canPreview: true };
  }
  if (
    mimeType.includes('zip') ||
    mimeType.includes('rar') ||
    mimeType.includes('7z') ||
    mimeType.includes('compressed') ||
    ARCHIVE_EXTENSIONS.has(extension)
  ) {
    return { type: 'archive', label: '压缩包下载', canPreview: false };
  }
  return { type: 'generic', label: '下载文件', canPreview: false };
}

export function formatFileSize(value) {
  const size = Number(value || 0);
  if (!Number.isFinite(size) || size <= 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let current = size;
  let index = 0;
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }
  const digits = current >= 100 || index === 0 ? 0 : current >= 10 ? 1 : 2;
  return `${current.toFixed(digits)} ${units[index]}`;
}

export function downloadBlob(blob, fileName = 'download') {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = fileName;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function needsServerSidePreview(asset = {}) {
  const extension = getFileExtension(asset?.file_name || '');
  return ['doc', 'xls', 'ppt', 'pptx', 'pps', 'ppsx'].includes(extension);
}
