import { acceptHMRUpdate, defineStore } from 'pinia'
import { computed, ref } from 'vue'

const STORAGE_KEY = 'edueval_theme'

function applyThemeClass(theme) {
  const root = document.documentElement
  if (theme === 'dark') {
    root.setAttribute('data-web-theme', 'dark')
    root.classList.add('theme-dark')
    root.classList.remove('theme-light')
  } else {
    root.setAttribute('data-web-theme', 'light')
    root.classList.add('theme-light')
    root.classList.remove('theme-dark')
  }
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref('light')

  const isDark = computed(() => theme.value === 'dark')

  function initialize() {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark' || stored === 'light') {
      theme.value = stored
    }
    applyThemeClass(theme.value)
  }

  function setTheme(next) {
    theme.value = next === 'dark' ? 'dark' : 'light'
    localStorage.setItem(STORAGE_KEY, theme.value)
    applyThemeClass(theme.value)
  }

  function toggle() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return {
    theme,
    isDark,
    initialize,
    setTheme,
    toggle
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useThemeStore, import.meta.hot))
}
