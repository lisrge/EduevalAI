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
  const response = await fetch(`${getApiBase()}/applications`);
  return parseResponse(response);
}

export async function fetchApplicationDetail(applicationId) {
  const response = await fetch(`${getApiBase()}/applications/${applicationId}`);
  return parseResponse(response);
}

export async function uploadApplicationFile(file) {
  const formData = new FormData();
  formData.append('file', file);
  const response = await fetch(`${getApiBase()}/applications/upload`, {
    method: 'POST',
    body: formData,
  });
  return parseResponse(response);
}

export async function scoreApplication(applicationId) {
  const response = await fetch(`${getApiBase()}/applications/${applicationId}/score`, {
    method: 'POST',
  });
  return parseResponse(response);
}

export async function batchScoreApplications(applicationIds = []) {
  const response = await fetch(`${getApiBase()}/applications/score-batch`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ application_ids: applicationIds }),
  });
  return parseResponse(response);
}

export async function batchDeleteApplications(applicationIds = []) {
  const response = await fetch(`${getApiBase()}/applications/batch`, {
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

  const response = await fetch(`${getApiBase()}/auth/register`, {
    method: 'POST',
    body: formData,
  });
  return parseResponse(response);
}

export async function loginUser({ studentId, password, rememberMe }) {
  const response = await fetch(`${getApiBase()}/auth/login`, {
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
  const response = await fetch(`${getApiBase()}/auth/me`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function logout(token) {
  const response = await fetch(`${getApiBase()}/auth/logout`, {
    method: 'POST',
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function fetchUserProfile(token) {
  const response = await fetch(`${getApiBase()}/users/me/profile`, {
    headers: withAuthHeader(token),
  });
  return parseResponse(response);
}

export async function changeUserPassword(token, { oldPassword, newPassword }) {
  const response = await fetch(`${getApiBase()}/users/me/password`, {
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
  const response = await fetch(`${getApiBase()}/users/me/signature`, {
    headers: withAuthHeader(token),
  });
  return parseBlobResponse(response);
}
