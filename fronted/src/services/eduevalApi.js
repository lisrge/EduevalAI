const DEFAULT_API_BASE = (() => {
  try {
    const protocol = window.location.protocol || 'http:';
    const host = window.location.hostname || 'localhost';
    return `${protocol}//${host}:8001/api`;
  } catch (e) {
    return 'http://localhost:8001/api';
  }
})();

function getApiBase() {
  return process.env.VUE_APP_EDUEVAL_API_BASE || DEFAULT_API_BASE;
}

export function getServerBase() {
  const apiBase = getApiBase();
  return String(apiBase).replace(/\/api\/?$/, '');
}

function getOriginApiBase() {
  try {
    return `${window.location.origin}/api`;
  } catch (e) {
    return '/api';
  }
}

function getLocalFallbackApiBase() {
  try {
    const protocol = window.location.protocol || 'http:';
    return `${protocol}//localhost:8001/api`;
  } catch (e) {
    return 'http://localhost:8001/api';
  }
}

async function fetchWithFallback(url, init) {
  const currentBase = getApiBase();
  const originBase = getOriginApiBase();
  const candidates = [
    currentBase,
    originBase,
    getLocalFallbackApiBase(),
  ].filter((v, idx, arr) => Boolean(v) && arr.indexOf(v) === idx);

  try {
    return await fetch(url, init);
  } catch (e) {
    const message = e?.message || String(e);
    if (!message.includes('Failed to fetch') && !message.includes('NetworkError')) throw e;

    for (const base of candidates) {
      if (!currentBase || base === currentBase) continue;
      const nextUrl = String(url).replace(String(currentBase), String(base));
      try {
        const resp = await fetch(nextUrl, init);
        if (resp.ok) return resp;
        if (resp.status === 404 && base === originBase) continue;
        return resp;
      } catch (inner) {
        continue;
      }
    }

    throw e;
  }
}

async function parseResponse(response) {
  if (!response.ok) {
    let message = 'Request failed';
    try {
      const payload = await response.json();
      message = payload?.detail || payload?.message || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.json();
}

async function parseBlobResponse(response) {
  if (!response.ok) {
    let message = 'Request failed';
    try {
      const payload = await response.json();
      message = payload?.detail || payload?.message || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.blob();
}

async function parseTextResponse(response) {
  if (!response.ok) {
    let message = 'Request failed';
    try {
      const payload = await response.json();
      message = payload?.detail || payload?.message || message;
    } catch (error) {
      message = response.statusText || message;
    }
    throw new Error(message);
  }
  return response.text();
}

function withAuthHeader(token, headers = {}) {
  if (!token) return headers;
  return {
    ...headers,
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchApplications(token) {
  const response = await fetchWithFallback(`${getApiBase()}/applications`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchMyApplicationStatus(token) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/me/status`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchMyRequests(token) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/me/requests`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function requestApplicationReupload(token, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/me/reupload-request`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function requestSignatureUpdate(token, signatureFile, requestNote = '') {
  const formData = new FormData();
  formData.append('signature', signatureFile);
  formData.append('request_note', requestNote || '');
  const response = await fetchWithFallback(`${getApiBase()}/applications/me/signature-request`, {
    method: 'POST',
    headers: withAuthHeader(token),
    body: formData,
  });
  return parseResponse(response);
}

export async function fetchApplicationDetail(token, applicationId) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/${applicationId}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function uploadApplicationFile(token, file, meta = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (meta && typeof meta === 'object') {
    if (meta.student_name) formData.append('student_name', String(meta.student_name));
    if (meta.student_id) formData.append('student_id', String(meta.student_id));
    if (meta.project_title) formData.append('project_title', String(meta.project_title));
  }
  const response = await fetchWithFallback(`${getApiBase()}/applications/upload`, {
    method: 'POST',
    headers: withAuthHeader(token),
    body: formData,
  });
  return parseResponse(response);
}

export async function scoreApplication(token, applicationId) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/${applicationId}/score`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function batchScoreApplications(token, applicationIds = []) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/score-batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ application_ids: applicationIds }),
  });
  return parseResponse(response);
}

export async function batchDeleteApplications(token, applicationIds = []) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/batch`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ application_ids: applicationIds }),
  });
  return parseResponse(response);
}

export function buildExportUrl(format = 'csv') {
  return `${getApiBase()}/exports/scores?format=${format}`;
}

export async function registerUser({ studentId, realName, password, signatureFile }) {
  const formData = new FormData();
  formData.append('student_id', studentId);
  formData.append('real_name', realName);
  formData.append('password', password);
  formData.append('signature', signatureFile);

  const response = await fetchWithFallback(`${getApiBase()}/auth/register`, {
    method: 'POST',
    body: formData,
  });
  return parseResponse(response);
}

export async function loginUser({ studentId, password, rememberMe }) {
  const response = await fetchWithFallback(`${getApiBase()}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      student_id: studentId,
      password,
      remember_me: Boolean(rememberMe),
    }),
  });
  return parseResponse(response);
}

export async function fetchMe(token) {
  const response = await fetchWithFallback(`${getApiBase()}/auth/me`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function logout(token) {
  const response = await fetchWithFallback(`${getApiBase()}/auth/logout`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchUserProfile(token) {
  const response = await fetchWithFallback(`${getApiBase()}/users/me/profile`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function changeUserPassword(token, { oldPassword, newPassword }) {
  const response = await fetchWithFallback(`${getApiBase()}/users/me/password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({
      old_password: oldPassword,
      new_password: newPassword,
    }),
  });
  return parseResponse(response);
}

export async function fetchUserSignature(token) {
  const response = await fetchWithFallback(`${getApiBase()}/users/me/signature`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function adminListUsers(token) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminUpdateUserRole(token, userId, role) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/role`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ role }),
  });
  return parseResponse(response);
}

export async function adminUpdateUserBasicProfile(token, userId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/basic-profile`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function adminListGroups(token) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/groups`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminCreateGroup(token, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/groups`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function adminUpdateGroup(token, groupId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/groups/${groupId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function adminDeleteGroup(token, groupId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/groups/${groupId}`, {
    method: 'DELETE',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminBootstrapGroups(token, totalGroups = 86) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/groups/bootstrap`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ total_groups: totalGroups }),
  });
  return parseResponse(response);
}

export async function adminAssignUserGroup(token, userId, groupId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/group`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ group_id: groupId }),
  });
  return parseResponse(response);
}

export async function adminListUserRequests(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/requests`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminListAllRequests(token, status = 'pending') {
  const qs = status ? `?status=${encodeURIComponent(status)}` : '';
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/requests${qs}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminReviewUserRequest(token, userId, requestId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/requests/${requestId}/review`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function adminListUserApplicationDrafts(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/drafts/applications`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminListUserTaskDrafts(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/drafts/tasks`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminExportApplicationDraftDocx(token, userId, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/drafts/applications/${draftId}/docx`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function adminExportTaskDraftDocx(token, userId, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/drafts/tasks/${draftId}/docx`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function adminFetchApplicationDraftMarkdown(token, userId, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/drafts/applications/${draftId}/md`, {
    headers: withAuthHeader(token),
  });
  return parseTextResponse(response);
}

export async function adminFetchTaskDraftMarkdown(token, userId, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/drafts/tasks/${draftId}/md`, {
    headers: withAuthHeader(token),
  });
  return parseTextResponse(response);
}

export async function adminListUserBlogs(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminGetUserBlogProfile(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blog-profile`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminUpdateUserBlogProfile(token, userId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blog-profile`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function adminTriggerUserBlogCrawl(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/crawl`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminTriggerBatchBlogCrawl(token, userIds = []) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/blogs/crawl-batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ user_ids: userIds }),
  });
  return parseResponse(response);
}

export async function adminListUserBlogCrawlRuns(token, userId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/crawl-runs`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminListAllBlogCrawlRuns(token) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/blogs/crawl-runs`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminFetchUserBlogDetail(token, userId, blogId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/${blogId}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminFetchUserBlogMarkdown(token, userId, blogId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/${blogId}/md`, {
    headers: withAuthHeader(token),
  });
  return parseTextResponse(response);
}

export async function adminFetchUserBlogScreenshot(token, userId, blogId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/${blogId}/screenshot`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function adminFetchUserBlogHtml(token, userId, blogId) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/${blogId}/html`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function adminReviewUserBlog(token, userId, blogId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/users/admin/users/${userId}/blogs/${blogId}/review`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function listApplicationDrafts(token) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/applications`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function createApplicationDraft(token, { title, content } = {}) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/applications`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ title, content }),
  });
  return parseResponse(response);
}

export async function fetchApplicationDraft(token, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/applications/${draftId}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function updateApplicationDraft(token, draftId, { title, status, content } = {}) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/applications/${draftId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ title, status, content }),
  });
  return parseResponse(response);
}

export async function deleteApplicationDraft(token, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/applications/${draftId}`, {
    method: 'DELETE',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function exportApplicationDraftDocx(token, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/applications/${draftId}/docx`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function listTaskDrafts(token) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/tasks`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function createTaskDraft(token, { title, content } = {}) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/tasks`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ title, content }),
  });
  return parseResponse(response);
}

export async function fetchTaskDraft(token, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/tasks/${draftId}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function updateTaskDraft(token, draftId, { title, status, content } = {}) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/tasks/${draftId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ title, status, content }),
  });
  return parseResponse(response);
}

export async function deleteTaskDraft(token, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/tasks/${draftId}`, {
    method: 'DELETE',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function exportTaskDraftDocx(token, draftId) {
  const response = await fetchWithFallback(`${getApiBase()}/drafts/tasks/${draftId}/docx`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function fetchAssignments(token) {
  const response = await fetchWithFallback(`${getApiBase()}/assignments`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchMyAssignmentSubmission(token, assignmentId) {
  const response = await fetchWithFallback(`${getApiBase()}/assignments/${encodeURIComponent(String(assignmentId))}/submissions/me`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function upsertAssignmentSubmission(token, assignmentId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/assignments/${encodeURIComponent(String(assignmentId))}/submissions`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function uploadSubmissionAsset(token, submissionId, assetType, file) {
  const formData = new FormData();
  formData.append('asset_type', String(assetType || ''));
  formData.append('file', file);
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/assets`, {
    method: 'POST',
    headers: withAuthHeader(token),
    body: formData,
  });
  return parseResponse(response);
}

export async function finalizeSubmission(token, submissionId) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/finalize`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function adminListSubmissionSummaries(token, assignmentId = null) {
  const qs = assignmentId ? `?assignment_id=${encodeURIComponent(String(assignmentId))}` : '';
  const response = await fetchWithFallback(`${getApiBase()}${`/admin/submissions${qs}`}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchSubmissionDetail(token, submissionId) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function exportTeacherScores(token, { format = 'xlsx', assignmentId = null } = {}) {
  const qs = new URLSearchParams();
  qs.set('format', String(format || 'xlsx'));
  if (assignmentId) qs.set('assignment_id', String(assignmentId));
  const response = await fetchWithFallback(`${getApiBase()}/exports/teacher-scores?${qs.toString()}`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}

export async function fetchSubmissionRepoBinding(token, submissionId) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/repo-binding`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function upsertSubmissionRepoBinding(token, submissionId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/repo-binding`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function syncRepoBinding(token, bindingId) {
  const response = await fetchWithFallback(`${getApiBase()}/repo-bindings/${encodeURIComponent(String(bindingId))}/sync`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function updateRepoBindingAutoSync(token, bindingId, autoSyncEnabled) {
  const response = await fetchWithFallback(`${getApiBase()}/repo-bindings/${encodeURIComponent(String(bindingId))}/auto-sync`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify({ auto_sync_enabled: Boolean(autoSyncEnabled) }),
  });
  return parseResponse(response);
}

export async function fetchRepoSchedulerStatus(token) {
  const response = await fetchWithFallback(`${getApiBase()}/repo-sync/scheduler-status`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function runRepoSchedulerNow(token) {
  const response = await fetchWithFallback(`${getApiBase()}/repo-sync/run-now`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchRepoCommits(token, bindingId) {
  const response = await fetchWithFallback(`${getApiBase()}/repo-bindings/${encodeURIComponent(String(bindingId))}/commits`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchRepoWeeklyStats(token, bindingId) {
  const response = await fetchWithFallback(`${getApiBase()}/repo-bindings/${encodeURIComponent(String(bindingId))}/weekly-stats`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchSubmissionRepoContributions(token, submissionId) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/repo-contributions`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function updateSubmissionRepoMemberMappings(token, submissionId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/repo-member-mappings`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function fetchSubmissionWorkloadSummary(token, submissionId) {
  const response = await fetchWithFallback(`${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/workload`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchStudentWorkloadSummary(token, submissionId, studentId) {
  const response = await fetchWithFallback(
    `${getApiBase()}/submissions/${encodeURIComponent(String(submissionId))}/workload/${encodeURIComponent(String(studentId))}`,
    {
      headers: withAuthHeader(token),
    },
  );
  return parseResponse(response);
}

export async function fetchTeacherReviewQueue(token, assignmentId = null, reviewed = null) {
  const qs = new URLSearchParams();
  if (assignmentId) qs.set('assignment_id', String(assignmentId));
  if (reviewed !== null && reviewed !== undefined && reviewed !== '') qs.set('reviewed', String(reviewed));
  const response = await fetchWithFallback(`${getApiBase()}/teacher/submissions${qs.toString() ? `?${qs.toString()}` : ''}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchTeacherSubmissionReview(token, submissionId) {
  const response = await fetchWithFallback(`${getApiBase()}/teacher/submissions/${encodeURIComponent(String(submissionId))}`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function saveTeacherSubmissionScore(token, submissionId, payload) {
  const response = await fetchWithFallback(`${getApiBase()}/teacher/submissions/${encodeURIComponent(String(submissionId))}/score`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...withAuthHeader(token),
    },
    body: JSON.stringify(payload || {}),
  });
  return parseResponse(response);
}

export async function fetchTeacherAssignmentState(token, submissionId) {
  const response = await fetchWithFallback(
    `${getApiBase()}/teacher/admin/submissions/${encodeURIComponent(String(submissionId))}/teacher-assignments`,
    {
      headers: withAuthHeader(token),
    },
  );
  return parseResponse(response);
}

export async function updateTeacherAssignments(token, submissionId, teacherUserIds = []) {
  const response = await fetchWithFallback(
    `${getApiBase()}/teacher/admin/submissions/${encodeURIComponent(String(submissionId))}/teacher-assignments`,
    {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...withAuthHeader(token),
      },
      body: JSON.stringify({ teacher_user_ids: Array.isArray(teacherUserIds) ? teacherUserIds : [] }),
    },
  );
  return parseResponse(response);
}

export async function fetchBlogOverview(token) {
  const response = await fetchWithFallback(`${getApiBase()}/blogs/admin/overview`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function crawlAllBlogSources(token) {
  const response = await fetchWithFallback(`${getApiBase()}/blogs/admin/crawl-all`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}
