<template>
  <div class="app-container" :class="theme">
    <!-- 侧边栏 - 仅在非认证页面显示 -->
    <aside v-if="!isAuthPage" class="sidebar" :class="{ collapsed: !sidebarExpanded }">
      <div class="sidebar-header">
        <button class="sidebar-toggle" @click="toggleSidebar" :title="sidebarExpanded ? '收起侧边栏' : '展开侧边栏'">
          <svg viewBox="0 0 1024 1024" class="toggle-icon" :class="{ flipped: !sidebarExpanded }">
            <path d="M768 102.4c54.186667 0 100.437333 19.2 138.752 57.514667C945.109333 198.229333 964.266667 244.48 964.266667 298.666667v426.666666c0 54.186667-19.2 100.437333-57.514667 138.794667C868.437333 902.4 822.186667 921.6 768 921.6H256c-54.186667 0-100.437333-19.2-138.752-57.514667C78.890667 825.813333 59.733333 779.52 59.733333 725.333333V298.666667c0-54.186667 19.2-100.437333 57.514667-138.752C155.562667 121.6 201.770667 102.4 256 102.4h512z m-512 85.333333c-73.941333 0-110.933333 36.992-110.933333 110.933334v426.666666c0 73.941333 36.949333 110.933333 110.933333 110.933334h85.333333V187.733333H256z m170.666667 648.533334h341.333333c73.941333 0 110.933333-36.992 110.933333-110.933334V298.666667c0-73.941333-36.992-110.933333-110.933333-110.933334h-341.333333v648.533334z"></path>
          </svg>
        </button>
      </div>
      
      <nav class="sidebar-nav" v-show="sidebarExpanded">
        <router-link to="/" class="nav-item" :class="{ active: isActive('/') }">
          <el-icon><ChatDotRound /></el-icon>
          <span>对话</span>
        </router-link>
        <router-link to="/api-test" class="nav-item" :class="{ active: isActive('/api-test') }">
          <el-icon><Document /></el-icon>
          <span>接口测试</span>
        </router-link>
        <router-link to="/tasks" class="nav-item" :class="{ active: isActive('/tasks') }">
          <el-icon><List /></el-icon>
          <span>任务管理</span>
        </router-link>
        <router-link to="/statistics" class="nav-item" :class="{ active: isActive('/statistics') }">
          <el-icon><DataAnalysis /></el-icon>
          <span>统计分析</span>
        </router-link>
        <router-link to="/help" class="nav-item" :class="{ active: isActive('/help') }">
          <el-icon><QuestionFilled /></el-icon>
          <span>使用帮助</span>
        </router-link>
      </nav>
      
      <div class="sidebar-footer" v-show="sidebarExpanded">
        <!-- 用户信息 -->
        <div v-if="isLoggedIn" class="user-info">
          <div class="user-avatar">{{ userInitial }}</div>
          <div class="user-details">
            <div class="user-name">{{ displayName }}</div>
          </div>
          <button class="logout-btn" @click="handleLogout" title="退出登录">
            <el-icon><SwitchButton /></el-icon>
          </button>
        </div>
        
        <button class="theme-toggle" @click="toggleTheme" :title="theme === 'dark' ? '切换到浅色模式' : '切换到深色模式'">
          <el-icon v-if="theme === 'dark'"><Sunny /></el-icon>
          <el-icon v-else><Moon /></el-icon>
          <span>{{ theme === 'dark' ? '浅色模式' : '深色模式' }}</span>
        </button>
      </div>
    </aside>
    
    <!-- 主内容区 -->
    <main class="main-content" :class="{ 'full-width': isAuthPage }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useThemeStore } from '@/stores/theme'
import { useUserStore } from '@/stores/user'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()
const userStore = useUserStore()

const { theme, sidebarExpanded } = storeToRefs(themeStore)
const { toggleTheme, toggleSidebar, initTheme } = themeStore

const { isLoggedIn, displayName } = storeToRefs(userStore)

// 判断是否是认证页面（登录/注册）
const isAuthPage = computed(() => {
  return route.path === '/login' || route.path === '/register'
})

// 用户名首字母
const userInitial = computed(() => {
  const name = displayName.value || ''
  return name.charAt(0).toUpperCase() || 'U'
})

const isActive = (path) => {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

const handleLogout = async () => {
  await userStore.logout()
  router.push('/login')
}

onMounted(() => {
  initTheme()
  // 初始化用户状态
  userStore.init()
})
</script>

<style scoped>
.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  overflow: hidden;
  transition: background-color 0.3s;
}

/* ==================== 侧边栏 ==================== */
.sidebar {
  width: 13%;
  min-width: 180px;
  max-width: 260px;
  height: 100%;
  background: var(--sidebar-bg);
  display: flex;
  flex-direction: column;
  transition: width 0.3s, min-width 0.3s, background-color 0.3s;
  flex-shrink: 0;
  border-right: 1px solid var(--border-color);
}

.sidebar.collapsed {
  width: 56px;
  min-width: 56px;
}

.sidebar-header {
  padding: 12px;
  display: flex;
  align-items: center;
}

.sidebar-toggle {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: background-color 0.2s;
}

.sidebar-toggle:hover {
  background: var(--border-color);
}

.toggle-icon {
  width: 20px;
  height: 20px;
  fill: var(--text-secondary);
  transition: transform 0.3s;
}

.toggle-icon.flipped {
  transform: scaleX(-1);
}

.sidebar-nav {
  flex: 1;
  padding: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  color: var(--text-secondary);
  text-decoration: none;
  border-radius: 8px;
  transition: all 0.2s;
  font-size: 14px;
}

.nav-item:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--border-color);
  color: var(--send-btn);
}

.nav-item .el-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.sidebar-footer {
  padding: 12px;
  border-top: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* ==================== 用户信息 ==================== */
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px;
  background: var(--border-color);
  border-radius: 8px;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--send-btn);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  flex-shrink: 0;
}

.user-details {
  flex: 1;
  min-width: 0;
}

.user-name {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.logout-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: all 0.2s;
}

.logout-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
}

.theme-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.theme-toggle:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.theme-toggle .el-icon {
  font-size: 18px;
}

/* ==================== 主内容区 ==================== */
.main-content {
  flex: 1;
  background: var(--main-bg);
  overflow: hidden;
  transition: background-color 0.3s;
}

.main-content.full-width {
  width: 100%;
}

/* ==================== 主题变量 ==================== */
.app-container.dark {
  --sidebar-bg: #1d1d1f;
  --main-bg: #232326;
  --text-primary: #e0e0e0;
  --text-secondary: #999999;
  --border-color: #3a3a3a;
  --input-bg: #2a2a2a;
  --send-btn: #615ced;
  --send-btn-hover: #7571ff;
}

.app-container.light {
  --sidebar-bg: #f7f8fc;
  --main-bg: #ffffff;
  --text-primary: #1a1a1a;
  --text-secondary: #666666;
  --border-color: #e5e5e5;
  --input-bg: #f5f5f5;
  --send-btn: #615ced;
  --send-btn-hover: #5248d9;
}
</style>
