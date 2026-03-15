<template>
  <!-- 顶部导航栏：边框改为更明确但依然极浅的灰色 #e2e8f0 -->
  <header class="h-24 flex items-center justify-between px-12 bg-[#f0f4f9] shrink-0 relative z-10 border-b border-[#f1f5f9] shadow-sm pt-6 pb-2">
    <!-- 左侧：项目 Logo 与 名称 -->
    <div class="flex items-center" style="gap: 24px;">
      <img src="../assets/ModelHub.png" style="margin-left: 24px;" alt="Logo" class="logo-image rounded-2xl object-cover shadow-sm" />
      <div class="flex items-center" style="gap: 16px;">
        <h1 class="font-kavo text-3xl text-text-primary tracking-normal">ModelHub</h1>
        <!-- BETA 标签：紫色渐变或纯色 -->
        <span class="px-3 py-1 text-[9px] bg-purple-100 text-purple-600 rounded-full font-black uppercase tracking-widest shadow-sm inline-flex items-center justify-center">Beta</span>
      </div>
    </div>

    <!-- 右侧：功能按钮 -->
    <div class="flex items-center" style="gap: 40px; margin-right: 24px;">
      <div class="flex items-center" style="gap: 16px;">
        <button class="p-3 text-text-secondary bg-white hover:text-primary rounded-xl shadow-sm hover:shadow-md transition-all duration-300 border-none active:scale-95" title="切换主题">
          <Sun :size="20" />
        </button>
        <button class="p-3 text-text-secondary bg-white hover:text-red-500 rounded-xl shadow-sm hover:shadow-md transition-all duration-300 border-none active:scale-95" title="清空对话">
          <Trash2 :size="20" />
        </button>
      </div>

      <!-- 用户资料区域：优化布局并强制锁定头像尺寸 -->
      <div class="flex items-center group cursor-pointer bg-white/80 rounded-full shadow-sm hover:shadow-md transition-all duration-300" style="padding: 4px 12px; gap: 8px;">
        <div class="flex flex-col items-end hidden md:flex">
          <span class="text-[11px] font-black text-text-primary leading-none">用户名</span>
          <span class="text-[9px] text-text-tertiary mt-0.5 font-bold uppercase tracking-tighter">Standard User</span>
        </div>
        <!-- 用户头像：强制使用 inline style 锁定极小尺寸 (32px) -->
        <div 
          class="rounded-full border border-gray-100 overflow-hidden shadow-sm shrink-0" 
          style="width: 32px !important; height: 32px !important; min-width: 32px !important; min-height: 32px !important;"
        >
          <img src="https://ui-avatars.com/api/?name=User&background=2563eb&color=fff" alt="Avatar" style="width: 100%; height: 100%; object-cover: cover;" />
        </div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { Sun, Trash2 } from 'lucide-vue-next';
import { defineProps } from 'vue';

// 编译器宏
defineProps({});
</script>

<style scoped>
/* 显式定义 Logo 尺寸 */
.logo-image {
  width: 48px !important;
  height: 48px !important;
  min-width: 36px;
  min-height: 36px;
}
</style>
