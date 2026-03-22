import { acceptHMRUpdate, defineStore } from 'pinia';
import { computed, ref } from 'vue';

const STORAGE_KEY = 'edueval_theme';

function applyThemeClass(theme) {
  const root = document.documentElement;
  root.classList.toggle('theme-dark', theme === 'dark');
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref('light');

  const isDark = computed(() => theme.value === 'dark');

  function initialize() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'dark' || stored === 'light') {
      theme.value = stored;
    }
    applyThemeClass(theme.value);
  }

  function setTheme(next) {
    theme.value = next === 'dark' ? 'dark' : 'light';
    localStorage.setItem(STORAGE_KEY, theme.value);
    applyThemeClass(theme.value);
  }

  function toggle() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark');
  }

  return {
    theme,
    isDark,
    initialize,
    setTheme,
    toggle,
  };
});

if (module.hot) {
  module.hot.accept(acceptHMRUpdate(useThemeStore, module.hot));
}

