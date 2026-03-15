/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: "#2563eb",
        'primary-hover': "#1d4ed8",
        // 全局底层背景
        'app-bg': "#dee5ed",
        // 统一的边栏、导航栏、底部栏背景：极浅冰蓝色
        'surface-bg': "#f0f4f9",
        // 中间对话区背景：纯白
        'chat-bg': "#ffffff",
        // AI 消息气泡背景
        'ai-bubble': "#f8fafc",
        // 文字颜色
        'text-primary': "#0f172a",
        'text-secondary': "#475569",
        'text-tertiary': "#94a3b8",
        'user-gradient-start': "#2563eb",
        'user-gradient-end': "#3b82f6",
      },
      borderRadius: {
        'btn': '8px',
        'bubble': '22px',
        'input': '24px',
        'panel': '24px',
      },
      boxShadow: {
        'card-hover': '0 4px 12px rgba(0,0,0,0.08)',
        'dropdown': '0 12px 24px rgba(0,0,0,0.12)',
        'btn-hover': '0 2px 8px rgba(37,99,235,0.3)',
        'nav': '0 2px 8px rgba(0,0,0,0.04)',
      }
    },
  },
  plugins: [],
}
