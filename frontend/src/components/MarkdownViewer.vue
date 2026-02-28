<template>
  <div class="markdown-viewer">
    <MarkdownRender 
      :content="content"
      :custom-components="customComponents"
    />
  </div>
</template>

<script setup>
import { MarkdownRender, setCustomComponents } from 'markstream-vue'
import 'markstream-vue/index.css'

const props = defineProps({
  content: {
    type: String,
    default: ''
  },
  // 支持传入自定义组件映射，用于扩展特殊格式渲染
  customComponents: {
    type: Object,
    default: () => ({})
  }
})

// 暴露 setCustomComponents 方法供外部注册全局自定义组件
defineExpose({
  setCustomComponents
})
</script>

<style scoped>
.markdown-viewer {
  max-width: 100%;
  overflow-x: auto;
}
</style>

<style>
/* 暗色模式下覆盖 markstream-vue 的白色背景和浅色文字 */
.dark .markdown-viewer,
.dark .markdown-viewer * {
  background-color: transparent !important;
  color: var(--text-primary, #e0e0e0);
}

/* 代码块 */
.dark .markdown-viewer pre,
.dark .markdown-viewer code {
  background-color: #1e1e2e !important;
  color: #cdd6f4 !important;
  border-color: #3a3a4a !important;
}

/* 内联代码 */
.dark .markdown-viewer :not(pre) > code {
  background-color: rgba(255, 255, 255, 0.1) !important;
  color: #cba6f7 !important;
}

/* 表格 */
.dark .markdown-viewer table {
  border-color: #3a3a3a !important;
}
.dark .markdown-viewer th {
  background-color: #2a2a2a !important;
  color: #e0e0e0 !important;
  border-color: #3a3a3a !important;
}
.dark .markdown-viewer td {
  border-color: #3a3a3a !important;
}
.dark .markdown-viewer tr:nth-child(even) {
  background-color: rgba(255, 255, 255, 0.03) !important;
}

/* 引用块 */
.dark .markdown-viewer blockquote {
  border-left-color: #615ced !important;
  background-color: rgba(97, 92, 237, 0.08) !important;
  color: #b0b0b0 !important;
}

/* 水平线 */
.dark .markdown-viewer hr {
  border-color: #3a3a3a !important;
}

/* 链接 */
.dark .markdown-viewer a {
  color: #89b4fa !important;
}

/* 标题 */
.dark .markdown-viewer h1,
.dark .markdown-viewer h2,
.dark .markdown-viewer h3,
.dark .markdown-viewer h4,
.dark .markdown-viewer h5,
.dark .markdown-viewer h6 {
  color: #e0e0e0 !important;
  border-bottom-color: #3a3a3a !important;
}
</style>
