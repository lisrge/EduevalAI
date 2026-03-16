<template>
  <!-- 技能工具栏：与输入框对齐，移除背景色 -->
  <div class="bg-white overflow-x-auto no-scrollbar shrink-0 w-full" style="padding: 0px 32px; margin-top: 8px;">
    <div class="max-w-4xl mx-auto flex items-center gap-2 py-2">
      <!-- 遍历渲染每个技能按钮：加深颜色，选中时为淡蓝色，增加间距，移除选中蓝点 -->
      <button 
        v-for="skill in skills" 
        :key="skill.id"
        @click="toggleSkill(skill.id)"
        class="flex items-center whitespace-nowrap transition-all duration-300 group relative border-none"
        style="gap: 6px; height: 32px; padding: 0 12px; border-radius: 10px; margin-right: 8px;"
        :class="skill.active 
          ? 'bg-[#2563eb]/10 text-[#2563eb] font-bold' 
          : 'bg-gray-100/40 text-text-primary hover:bg-gray-100 hover:text-primary'"
      >
        <!-- 动态渲染图标 -->
        <component 
          :is="skill.icon" 
          :size="14" 
          class="transition-colors"
          :class="skill.active ? 'text-primary' : 'text-text-secondary group-hover:text-primary'"
        />
        <span class="text-[11px]">{{ skill.name }}</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { Search, Library, Calculator, Code, FileText } from 'lucide-vue-next';
import { ref, defineProps } from 'vue';

// 编译器宏
defineProps({});

/**
 * 技能列表：采用统一的色块设计
 */
const skills = ref([
  { id: 'search', name: '联网搜索', icon: Search, active: false },
  { id: 'kb', name: '知识库检索', icon: Library, active: true },
  { id: 'calc', name: '计算器', icon: Calculator, active: false },
  { id: 'code', name: '代码执行', icon: Code, active: false },
  { id: 'file', name: '文档分析', icon: FileText, active: false },
]);

/**
 * 切换技能状态
 */
const toggleSkill = (id) => {
  const skill = skills.value.find(s => s.id === id);
  if (skill) {
    skill.active = !skill.active;
  }
};
</script>

<style scoped>
/* 隐藏滚动条 */
.no-scrollbar::-webkit-scrollbar {
  display: none;
}
.no-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}
</style>
