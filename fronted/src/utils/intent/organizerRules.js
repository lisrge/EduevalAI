import { INTENTS } from '../../constants/intents';

export const organizerRules = {
  intent: INTENTS.ORGANIZE_FILES,
  keywords: ['整理', '分类', '收拾', '归类', '太乱', '乱七八糟', '乱成'],
  previewKeywords: ['预览', '看看', '先看看', '都有什么', '查看'],
  executeKeywords: ['直接', '马上', '立刻', '现在', '执行', '确认'],
  extractParams(text) {
    const normalized = String(text || '');
    if (normalized.includes('下载')) return { pathKey: 'downloads' };
    if (normalized.includes('桌面')) return { pathKey: 'desktop' };
    if (normalized.includes('文档')) return { pathKey: 'documents' };
    return { pathKey: 'downloads' };
  },
  detectMode(text) {
    const normalized = String(text || '');
    if (this.previewKeywords.some(k => normalized.includes(k))) return 'preview';
    if (this.executeKeywords.some(k => normalized.includes(k))) return 'execute';
    return 'preview';
  },
  matches(text) {
    const normalized = String(text || '');
    const hasKeyword = this.keywords.some(k => normalized.includes(k));
    if (!hasKeyword) return false;
    const hasObject =
      normalized.includes('文件') ||
      normalized.includes('文件夹') ||
      normalized.includes('下载') ||
      normalized.includes('桌面') ||
      normalized.includes('文档');
    return hasObject;
  },
};
