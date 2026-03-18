function delay(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function getPathLabel(pathKey) {
  if (pathKey === 'desktop') return '桌面';
  if (pathKey === 'documents') return '文档';
  return '下载';
}

function getMockFiles(pathKey) {
  if (pathKey === 'desktop') {
    return [
      '截图_2026-03-18.png',
      '需求文档_v3.docx',
      '会议记录.txt',
      'demo.zip',
      'invoice_2025.pdf',
      'photo_001.jpg',
      'video_clip.mp4',
    ];
  }
  if (pathKey === 'documents') {
    return [
      '论文草稿.docx',
      '简历.pdf',
      '项目方案.pptx',
      '预算表.xlsx',
      '合同扫描件.pdf',
      '读书笔记.md',
    ];
  }
  return [
    'setup.exe',
    'photo_2026_01.jpg',
    'report_final.docx',
    'dataset.csv',
    'movie_trailer.mp4',
    'archive.zip',
    'slides.pptx',
    'notes.txt',
    'invoice.pdf',
  ];
}

function categorize(files) {
  const categories = {
    图片: [],
    文档: [],
    压缩包: [],
    视频: [],
    安装包: [],
    其他: [],
  };

  for (const file of files) {
    const lower = String(file).toLowerCase();
    if (/\.(png|jpg|jpeg|gif|webp)$/.test(lower)) categories.图片.push(file);
    else if (/\.(doc|docx|pdf|ppt|pptx|xls|xlsx|md|txt|csv)$/.test(lower)) categories.文档.push(file);
    else if (/\.(zip|rar|7z|tar|gz)$/.test(lower)) categories.压缩包.push(file);
    else if (/\.(mp4|mov|mkv|avi)$/.test(lower)) categories.视频.push(file);
    else if (/\.(exe|msi|dmg)$/.test(lower)) categories.安装包.push(file);
    else categories.其他.push(file);
  }

  return categories;
}

function formatPreview({ pathLabel, categories }) {
  const lines = [`📋 预览：将整理 ${pathLabel} 文件夹`, ''];
  for (const [name, list] of Object.entries(categories)) {
    if (!list.length) continue;
    const samples = list.slice(0, 3).join('、');
    lines.push(`- ${name}: ${list.length} 个${samples ? `（例如：${samples}）` : ''}`);
  }
  return lines.join('\n');
}

function formatExecute({ pathLabel, categories }) {
  let total = 0;
  for (const list of Object.values(categories)) total += list.length;
  const operationId = Math.random().toString(36).slice(2, 10);
  return [`✅ 已完成整理：${pathLabel} 文件夹`, `- 处理文件: ${total} 个`, `- 操作编号: ${operationId}`].join('\n');
}

export async function previewOrganizeFiles({ pathKey }) {
  await delay(350);
  const pathLabel = getPathLabel(pathKey);
  const files = getMockFiles(pathKey);
  const categories = categorize(files);
  return formatPreview({ pathLabel, categories });
}

export async function executeOrganizeFiles({ pathKey }) {
  await delay(650);
  const pathLabel = getPathLabel(pathKey);
  const files = getMockFiles(pathKey);
  const categories = categorize(files);
  return formatExecute({ pathLabel, categories });
}
