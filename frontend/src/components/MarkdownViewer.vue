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
