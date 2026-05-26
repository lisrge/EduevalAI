import { acceptHMRUpdate, defineStore } from 'pinia';
import { computed, ref } from 'vue';
import { fetchMe, loginUser, logout as apiLogout, registerUser } from '../services/eduevalApi';

const TOKEN_STORAGE_KEY = 'edueval_auth_token';
const REMEMBER_STORAGE_KEY = 'edueval_auth_remember';

function readStoredToken() {
  const remembered = localStorage.getItem(REMEMBER_STORAGE_KEY) === '1';
  const token = remembered ? localStorage.getItem(TOKEN_STORAGE_KEY) : sessionStorage.getItem(TOKEN_STORAGE_KEY);
  return { token: token || null, remembered };
}

function storeToken(token, remember) {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  sessionStorage.removeItem(TOKEN_STORAGE_KEY);

  localStorage.setItem(REMEMBER_STORAGE_KEY, remember ? '1' : '0');
  if (remember) {
    localStorage.setItem(TOKEN_STORAGE_KEY, token);
  } else {
    sessionStorage.setItem(TOKEN_STORAGE_KEY, token);
  }
}

function clearStoredToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
  sessionStorage.removeItem(TOKEN_STORAGE_KEY);
  localStorage.removeItem(REMEMBER_STORAGE_KEY);
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(null);
  const user = ref(null);
  const rememberMe = ref(false);
  const initialized = ref(false);
  const loading = ref(false);
  const error = ref(null);

  const isAuthenticated = computed(() => Boolean(token.value) && Boolean(user.value));
  const isAdmin = computed(() => String(user.value?.role || '').toLowerCase() === 'admin');
  const isTeacher = computed(() => String(user.value?.role || '').toLowerCase() === 'teacher');
  const isStaff = computed(() => isAdmin.value || isTeacher.value);

  async function ensureInitialized() {
    if (initialized.value) return;
    initialized.value = true;

    const stored = readStoredToken();
    if (!stored.token) return;

    token.value = stored.token;
    rememberMe.value = stored.remembered;

    try {
      const me = await fetchMe(token.value);
      user.value = me?.user || null;
    } catch (e) {
      token.value = null;
      user.value = null;
      rememberMe.value = false;
      clearStoredToken();
    }
  }

  async function login({ studentId, password, remember }) {
    loading.value = true;
    error.value = null;
    try {
      const result = await loginUser({ studentId, password, rememberMe: remember });
      token.value = result?.token || null;
      user.value = result?.user || null;
      rememberMe.value = Boolean(remember);
      if (token.value) storeToken(token.value, rememberMe.value);
      return result;
    } catch (e) {
      error.value = e?.message || String(e);
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function register({ studentId, realName, password, signatureFile }) {
    loading.value = true;
    error.value = null;
    try {
      const result = await registerUser({ studentId, realName, password, signatureFile });
      return result;
    } catch (e) {
      error.value = e?.message || String(e);
      throw e;
    } finally {
      loading.value = false;
    }
  }

  async function logout() {
    const currentToken = token.value;
    token.value = null;
    user.value = null;
    rememberMe.value = false;
    clearStoredToken();
    if (!currentToken) return;
    try {
      await apiLogout(currentToken);
    } catch (e) {
      return;
    }
  }

  return {
    token,
    user,
    rememberMe,
    initialized,
    loading,
    error,
    isAuthenticated,
    isAdmin,
    isTeacher,
    isStaff,
    ensureInitialized,
    login,
    register,
    logout,
  };
});

if (module.hot) {
  module.hot.accept(acceptHMRUpdate(useAuthStore, module.hot));
}
