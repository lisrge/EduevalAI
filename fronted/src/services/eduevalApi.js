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

function withAuthHeader(token, headers = {}) {
  if (!token) return headers;
  return {
    ...headers,
    Authorization: `Bearer ${token}`,
  };
}

export async function fetchApplications() {
  const response = await fetchWithFallback(`${getApiBase()}/applications`);
  return parseResponse(response);
}

export async function fetchApplicationDetail(applicationId) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/${applicationId}`);
  return parseResponse(response);
}

export async function uploadApplicationFile(file, meta = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (meta && typeof meta === 'object') {
    if (meta.student_name) formData.append('student_name', String(meta.student_name));
    if (meta.student_id) formData.append('student_id', String(meta.student_id));
    if (meta.project_title) formData.append('project_title', String(meta.project_title));
  }
  const response = await fetchWithFallback(`${getApiBase()}/applications/upload`, {
    method: 'POST',
    body: formData,
  });
  return parseResponse(response);
}

export async function scoreApplication(applicationId) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/${applicationId}/score`, {
    method: 'POST',
  });
  return parseResponse(response);
}

export async function batchScoreApplications(applicationIds = []) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/score-batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ application_ids: applicationIds }),
  });
  return parseResponse(response);
}

export async function batchDeleteApplications(applicationIds = []) {
  const response = await fetchWithFallback(`${getApiBase()}/applications/batch`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ application_ids: applicationIds }),
  });
  return parseResponse(response);
}

export function buildExportUrl(format = 'csv') {
  return `${getApiBase()}/exports/scores?format=${format}`;
}

export async function registerUser({ studentId, password, signatureFile }) {
  const formData = new FormData();
  formData.append('student_id', studentId);
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
