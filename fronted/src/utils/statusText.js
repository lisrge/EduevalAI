const EXACT_MESSAGE_MAP = {
  'Request failed': '请求失败',
  'Internal Server Error': '服务器内部错误',
  'Failed to fetch': '无法连接服务器，请检查后端是否已启动',
  'Load failed': '加载失败',
  'Not Found': '未找到对应资源',
  'Forbidden': '无权访问该资源',
  'Unauthorized': '登录已失效，请重新登录',
  'invalid credentials': '账号或密码错误',
  'admin required': '需要管理员权限',
  'teacher required': '需要教师权限',
  'teacher or admin required': '需要教师或管理员权限',
  'students only': '仅学生可执行此操作',
  'forbidden': '无权访问该资源',
  'assignment not found': '未找到对应作业',
  'submission not found': '未找到对应提交记录',
  'submission member not found': '未找到对应成员',
  'submission not assigned to current teacher': '当前教师未被分配到该提交，不能评分',
  'repo binding not found': '未找到仓库绑定信息',
  'user not found': '未找到对应用户',
  'student not found': '未找到对应学生',
  'group not found': '未找到对应小组',
  'leader user not found': '未找到组长账号',
  'request not found': '未找到对应申请',
  'asset not found': '未找到对应文件',
  'stored file not found': '服务器中未找到文件',
  'stored source file not found': '服务器中未找到源文件',
  'upload asset placeholder not found': '未找到上传占位记录',
  'chunk session lost': '分片上传会话已丢失，请重新上传',
  'upload_id required': '缺少上传会话编号',
  'md5 mismatch': '文件校验失败，MD5 不一致',
  'invalid md5': 'MD5 参数不合法',
  'invalid file_size': '文件大小参数不合法',
  'file too large': '文件过大',
  'invalid asset_type': '材料类型不合法',
  'unsupported format': '不支持该导出格式',
  'no group assignment found': '当前用户尚未分组',
  'repo_url is required': '请先填写仓库地址',
  'only gitee repositories are supported': '目前仅支持 Gitee 仓库地址',
  'invalid gitee repository url': 'Gitee 仓库地址格式不正确',
  'playwright is not available': '未安装 Playwright 依赖',
  'signature not found': '未找到签名图片',
  'signature file missing': '缺少签名图片文件',
  'signature must be an image': '签名必须是图片文件',
  'signature file is empty': '签名文件为空',
  'signature is required': '请上传签名',
  'signature request already pending': '签名修改申请正在审核中',
  'signature already exists; please submit an update request': '已有签名图片，如需修改请先提交申请',
  'no signature on file; please upload your first signature directly': '当前还没有签名图片，请先直接上传首张签名',
  'cannot modify your own role': '不能修改自己的权限',
  'invalid role': '权限类型不合法',
  'initial admin role cannot be modified': '初始管理员权限不可修改',
  'score must be between 0 and 100': '分数必须在 0 到 100 之间',
  'group_number must be positive': '组号必须为正整数',
  'group already exists': '该小组已存在',
  'user_ids is required': '请选择要操作的用户',
  'invalid status': '状态值不合法',
  'request already reviewed': '该申请已经审核过',
  'blog_ids is required': '请选择要操作的博客',
  'blog not found': '未找到对应博客',
  'screenshot not found': '未找到博客截图记录',
  'screenshot file not found': '未找到博客截图文件',
  'html not found': '未找到博客网页记录',
  'html file not found': '未找到博客网页文件',
  'invalid review_status': '审核状态不合法',
  'duplicate application': '该申请书已上传，请勿重复提交',
  'Application not found': '未找到对应申请书',
  'Stored file not found': '服务器中未找到文件',
  'application already uploaded; request admin approval before reupload': '申请书已上传，如需重传请先申请管理员审批',
  'application_ids is required': '请选择要操作的申请书',
  'no application uploaded yet': '当前还没有上传申请书',
  'reupload already approved': '重传申请已经通过',
  'reupload request already pending': '重传申请正在审核中',
  'some teachers not found or role invalid': '部分教师不存在，或其账号权限不是教师',
};

const SUBMISSION_STATUS_MAP = {
  draft: '草稿',
  submitted: '已提交',
};

const COMPLETENESS_STATUS_MAP = {
  complete: '完整',
  incomplete: '不完整',
};

const UPLOAD_STATUS_MAP = {
  uploaded: '已上传',
  uploading: '上传中',
  hashing: '计算校验中',
  resuming: '断点续传中',
  merging: '服务端合并中',
  failed: '上传失败',
  normal: '正常',
};

const REPO_SYNC_STATUS_MAP = {
  synced: '已同步',
  failed: '同步失败',
  never_bound: '未绑定仓库',
  never_synced: '未同步',
  group_repo_only: '仅填写了组仓库',
  queued: '排队中',
  refreshing: '刷新中',
  ready: '已就绪',
  missing: '待生成',
  idle: '空闲',
  unknown: '未知',
};

const CONTRIBUTION_SOURCE_MAP = {
  git: '仅 Git',
  mixed: 'Git + 非 Git',
  non_git: '非 Git',
};

const RISK_LEVEL_MAP = {
  high: '高风险',
  medium: '中风险',
  low: '低风险',
  unknown: '未知',
};

const PROGRESS_STATUS_MAP = {
  active: '进展活跃',
  steady: '稳定推进',
  limited: '进展较少',
};

const RISK_FLAG_MAP = {
  user_without_group: '用户尚未分组',
  analysis_pending: '仓库分析尚未生成',
  no_repo_bound: '未绑定仓库',
  non_git_members_present: '存在非 Git 成员',
  empty_repository: '仓库内容为空',
  no_detected_source_files: '未检测到源代码文件',
  very_small_codebase: '代码规模过小',
  low_source_file_ratio: '源代码占比偏低',
  members_without_gitee_profile: '有成员未绑定 Gitee 昵称',
  no_mapped_member_workload: '尚未匹配到成员工作量',
  unmapped_git_authors_present: '存在未映射的 Git 作者',
  git_activity_without_student_mapping: '存在未关联到学生的 Git 活动',
  teacher_reviews_not_started: '教师评分尚未开始',
  teacher_reviews_incomplete: '教师评分未完成',
  teacher_average_score_low: '教师评分偏低',
  bundled_assets_present: '压缩包内包含大量打包产物',
  invalid_zip_archive: '压缩包已损坏',
  archive_format_not_supported_for_scan: '当前压缩包格式暂不支持扫描',
  empty_archive: '压缩包为空',
};

function normalizeKey(value) {
  return String(value || '').trim();
}

function titleCaseToChineseFallback(value) {
  return String(value || '')
    .replace(/_/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function translateApiMessage(input) {
  const raw = normalizeKey(input);
  if (!raw) return '请求失败';
  if (EXACT_MESSAGE_MAP[raw]) return EXACT_MESSAGE_MAP[raw];

  if (/^Internal Server Error$/i.test(raw)) return '服务器内部错误';
  if (/^Request failed$/i.test(raw)) return '请求失败';
  if (/^Failed to fetch$/i.test(raw)) return '无法连接服务器，请检查后端是否已启动';
  if (/^gitee sync failed:/i.test(raw)) return `Gitee 同步失败：${raw.replace(/^gitee sync failed:\s*/i, '')}`;
  if (/^gitee graph browser fetch failed:/i.test(raw)) return `Gitee 图谱抓取失败：${raw.replace(/^gitee graph browser fetch failed:\s*/i, '')}`;
  return raw;
}

export function translateSubmissionStatus(value) {
  const key = normalizeKey(value).toLowerCase();
  return SUBMISSION_STATUS_MAP[key] || (value ? String(value) : '未创建');
}

export function translateCompletenessStatus(value) {
  const key = normalizeKey(value).toLowerCase();
  return COMPLETENESS_STATUS_MAP[key] || (value ? String(value) : '-');
}

export function translateUploadStatus(value) {
  const key = normalizeKey(value).toLowerCase();
  return UPLOAD_STATUS_MAP[key] || (value ? String(value) : '未知');
}

export function translateRepoSyncStatus(value) {
  const key = normalizeKey(value).toLowerCase();
  return REPO_SYNC_STATUS_MAP[key] || (value ? String(value) : '未知');
}

export function translateContributionSource(value) {
  const key = normalizeKey(value).toLowerCase();
  return CONTRIBUTION_SOURCE_MAP[key] || (value ? String(value) : '未设置');
}

export function translateRiskLevel(value) {
  const key = normalizeKey(value).toLowerCase();
  return RISK_LEVEL_MAP[key] || (value ? String(value) : '未知');
}

export function translateProgressStatus(value) {
  const key = normalizeKey(value).toLowerCase();
  return PROGRESS_STATUS_MAP[key] || (value ? String(value) : '待判断');
}

export function translateRiskFlag(value) {
  const raw = normalizeKey(value);
  if (!raw) return '';
  if (RISK_FLAG_MAP[raw]) return RISK_FLAG_MAP[raw];
  if (raw.startsWith('member_without_git_activity:')) {
    return `成员缺少 Git 活动：${raw.split(':').slice(1).join(':')}`;
  }
  if (raw.startsWith('blog_missing:')) {
    return `缺少博客：${raw.split(':').slice(1).join(':')}`;
  }
  if (raw.startsWith('blog_code_dump:')) {
    return `博客疑似代码堆砌：${raw.split(':').slice(1).join(':')}`;
  }
  if (raw.startsWith('missing:')) {
    return `缺少材料：${raw.split(':').slice(1).join(':')}`;
  }
  if (raw.startsWith('submission_without_repo:')) {
    return `提交未绑定仓库：${raw.split(':').slice(1).join(':')}`;
  }
  return titleCaseToChineseFallback(raw);
}
