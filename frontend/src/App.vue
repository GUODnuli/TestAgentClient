<template>
  <el-container class="app-container">
    <el-header class="app-header">
      <div class="header-content">
        <h1>🤖 MCP 接口测试智能体</h1>
        <el-menu mode="horizontal" :default-active="activeMenu" router>
          <el-menu-item index="/">首页</el-menu-item>
          <el-menu-item index="/tasks">任务管理</el-menu-item>
          <el-menu-item index="/statistics">统计分析</el-menu-item>
          <el-menu-item index="/help">使用帮助</el-menu-item>
        </el-menu>
      </div>
    </el-header>
    
    <el-main class="app-main">
      <router-view />
    </el-main>
    
    <el-footer class="app-footer">
      <p>MCP 接口测试智能体 v1.0.0 | Powered by AgentScope & Dify</p>
    </el-footer>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.app-header {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 20px;
}

.header-content h1 {
  margin: 0;
  font-size: 24px;
}

.app-main {
  background: #f5f7fa;
  padding: 20px;
}

.app-footer {
  text-align: center;
  background: #fff;
  border-top: 1px solid #e4e7ed;
}

:deep(.el-menu--horizontal) {
  border-bottom: none;
  background: transparent;
}

:deep(.el-menu--horizontal .el-menu-item) {
  color: white;
  border-bottom: 2px solid transparent;
}

:deep(.el-menu--horizontal .el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.1);
}

:deep(.el-menu--horizontal .el-menu-item.is-active) {
  border-bottom-color: white;
  background: rgba(255, 255, 255, 0.2);
}
</style>
