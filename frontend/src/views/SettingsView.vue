<template>
  <div class="settings-page">
    <div class="settings-container">
      <!-- 返回按钮 -->
      <button class="back-button" @click="goBack">
        <svg viewBox="0 0 1024 1024" class="back-icon">
          <path d="M597.248 187.8016l283.4432 297.6256a38.144 38.144 0 0 1 0 53.6576l-283.4432 297.6256a38.144 38.144 0 1 1-55.2448-52.6336l222.6176-233.6768H170.9056a38.144 38.144 0 1 1 0-76.288h593.7152l-222.6176-233.6768a38.144 38.144 0 1 1 55.296-52.6336z"></path>
        </svg>
      </button>

      <!-- 设置内容 -->
      <div class="settings-content">
        <!-- 左侧导航 -->
        <aside class="settings-sidebar">
          <h2 class="settings-title">设置</h2>
          <nav class="settings-nav">
            <button
              class="nav-item"
              :class="{ active: activeSection === 'general' }"
              @click="activeSection = 'general'"
            >
              <svg viewBox="0 0 1024 1024" class="nav-icon">
                <path d="M512 85.333333c235.648 0 426.666667 191.018667 426.666667 426.666667s-191.018667 426.666667-426.666667 426.666667S85.333333 747.648 85.333333 512 276.352 85.333333 512 85.333333z m0 85.333334C323.477333 170.666667 170.666667 323.477333 170.666667 512s152.810667 341.333333 341.333333 341.333333 341.333333-152.810667 341.333333-341.333333S700.522667 170.666667 512 170.666667z m0 128a42.666667 42.666667 0 0 1 42.666667 42.666666v128h128a42.666667 42.666667 0 0 1 0 85.333334h-128v128a42.666667 42.666667 0 0 1-85.333334 0v-128h-128a42.666667 42.666667 0 0 1 0-85.333334h128v-128A42.666667 42.666667 0 0 1 512 298.666667z"></path>
              </svg>
              <span>通用</span>
            </button>
            <button
              class="nav-item"
              :class="{ active: activeSection === 'account' }"
              @click="activeSection = 'account'"
            >
              <svg viewBox="0 0 1024 1024" class="nav-icon">
                <path d="M512 85.333333c235.648 0 426.666667 191.018667 426.666667 426.666667s-191.018667 426.666667-426.666667 426.666667S85.333333 747.648 85.333333 512 276.352 85.333333 512 85.333333z m0 85.333334C323.477333 170.666667 170.666667 323.477333 170.666667 512c0 84.010667 30.378667 160.981333 80.768 220.522667C304.469333 672.768 397.482667 640 512 640s207.530667 32.768 260.565333 92.522667c50.389333-59.541333 80.768-136.512 80.768-220.522667 0-188.522667-152.810667-341.333333-341.333333-341.333333z m0 128c70.692267 0 128 57.307733 128 128s-57.307733 128-128 128-128-57.307733-128-128 57.307733-128 128-128z"></path>
              </svg>
              <span>账号</span>
            </button>
          </nav>
        </aside>

        <!-- 右侧内容 -->
        <main class="settings-main">
          <!-- 通用设置 -->
          <div v-if="activeSection === 'general'" class="settings-section">
            <h3 class="section-title">通用设置</h3>
            
            <div class="setting-item">
              <div class="setting-label">
                <span class="label-text">主题</span>
                <span class="label-desc">选择界面主题模式</span>
              </div>
              <div class="setting-control">
                <button
                  class="theme-option"
                  :class="{ active: theme === 'light' }"
                  @click="setTheme('light')"
                >
                  <el-icon><Sunny /></el-icon>
                  <span>浅色</span>
                </button>
                <button
                  class="theme-option"
                  :class="{ active: theme === 'dark' }"
                  @click="setTheme('dark')"
                >
                  <el-icon><Moon /></el-icon>
                  <span>深色</span>
                </button>
              </div>
            </div>

            <div class="setting-item">
              <div class="setting-label">
                <span class="label-text">语言</span>
                <span class="label-desc">选择界面显示语言</span>
              </div>
              <div class="setting-control">
                <select class="language-select" disabled>
                  <option value="zh-CN">Chinese（简体中文）</option>
                </select>
              </div>
            </div>
          </div>

          <!-- 账号设置 -->
          <div v-if="activeSection === 'account'" class="settings-section">
            <h3 class="section-title">账号设置</h3>
            
            <div class="setting-item">
              <div class="setting-label">
                <span class="label-text">密码管理</span>
                <span class="label-desc">更改您的账户密码</span>
              </div>
              <div class="setting-control">
                <button class="action-btn" @click="showChangePassword = true">更改密码</button>
              </div>
            </div>

            <div class="setting-item danger">
              <div class="setting-label">
                <span class="label-text">账户管理</span>
                <span class="label-desc">永久删除您的账户及所有数据</span>
              </div>
              <div class="setting-control">
                <button class="action-btn danger" @click="showDeleteAccount = true">删除账号</button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>

    <!-- 修改密码对话框 -->
    <transition name="dialog-fade">
      <div v-if="showChangePassword" class="dialog-overlay" @click="showChangePassword = false">
        <div class="dialog-content" @click.stop>
          <h3 class="dialog-title">修改密码</h3>
          <form @submit.prevent="handleChangePassword">
            <div class="form-group">
              <label>旧密码</label>
              <input
                v-model="passwordForm.oldPassword"
                type="password"
                placeholder="请输入旧密码"
                required
              />
            </div>
            <div class="form-group">
              <label>新密码</label>
              <input
                v-model="passwordForm.newPassword"
                type="password"
                placeholder="请输入新密码（至少8位）"
                required
                minlength="8"
              />
            </div>
            <div v-if="passwordError" class="error-message">{{ passwordError }}</div>
            <div class="dialog-actions">
              <button type="button" class="btn-cancel" @click="showChangePassword = false">取消</button>
              <button type="submit" class="btn-confirm" :disabled="passwordLoading">
                {{ passwordLoading ? '修改中...' : '确认' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <!-- 删除账号对话框 -->
    <transition name="dialog-fade">
      <div v-if="showDeleteAccount" class="dialog-overlay" @click="showDeleteAccount = false">
        <div class="dialog-content danger" @click.stop>
          <h3 class="dialog-title">删除账号</h3>
          <p class="danger-warning">
            此操作将永久删除您的账号及所有相关数据，且无法恢复。请谨慎操作。
          </p>
          <div class="dialog-actions">
            <button type="button" class="btn-cancel" @click="showDeleteAccount = false">取消</button>
            <button type="button" class="btn-danger" @click="handleDeleteAccount">
              确认删除
            </button>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useThemeStore } from '@/stores/theme'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const themeStore = useThemeStore()
const userStore = useUserStore()

const { theme } = storeToRefs(themeStore)
const { setTheme } = themeStore

const activeSection = ref('general')

// 修改密码
const showChangePassword = ref(false)
const passwordForm = ref({
  oldPassword: '',
  newPassword: ''
})
const passwordError = ref('')
const passwordLoading = ref(false)

// 删除账号
const showDeleteAccount = ref(false)

const goBack = () => {
  router.push('/')
}

const handleChangePassword = async () => {
  passwordError.value = ''
  passwordLoading.value = true

  const result = await userStore.changePassword(passwordForm.value)

  passwordLoading.value = false

  if (result.success) {
    showChangePassword.value = false
    passwordForm.value = { oldPassword: '', newPassword: '' }
    alert('密码修改成功，请重新登录')
    router.push('/login')
  } else {
    passwordError.value = result.error
  }
}

const handleDeleteAccount = () => {
  alert('删除账号功能暂未实现')
  showDeleteAccount.value = false
}
</script>

<style scoped>
.settings-page {
  width: 100%;
  height: 100vh;
  background: var(--main-bg);
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 20px;
}

.settings-container {
  width: 100%;
  max-width: 1000px;
  height: 100%;
  max-height: 700px;
  background: var(--sidebar-bg);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* 返回按钮 */
.back-button {
  position: absolute;
  top: 20px;
  left: 20px;
  width: 36px;
  height: 36px;
  border: none;
  background: var(--border-color);
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
  z-index: 10;
}

.back-button:hover {
  background: var(--send-btn);
}

.back-button:hover .back-icon {
  fill: white;
}

.back-icon {
  width: 20px;
  height: 20px;
  fill: var(--text-secondary);
  transform: rotate(180deg);
  transition: fill 0.2s;
}

/* 设置内容 */
.settings-content {
  display: flex;
  height: 100%;
  margin-top: 60px;
}

/* 左侧导航 */
.settings-sidebar {
  width: 240px;
  border-right: 1px solid var(--border-color);
  padding: 20px;
  flex-shrink: 0;
}

.settings-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 24px 0;
}

.settings-nav {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  text-align: left;
  cursor: pointer;
  border-radius: 8px;
  font-size: 14px;
  transition: all 0.2s;
}

.nav-item:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.nav-item.active {
  background: var(--border-color);
  color: var(--send-btn);
}

.nav-icon {
  width: 18px;
  height: 18px;
  fill: currentColor;
  flex-shrink: 0;
}

/* 右侧内容 */
.settings-main {
  flex: 1;
  padding: 32px;
  overflow-y: auto;
}

.settings-section {
  max-width: 600px;
}

.section-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 24px 0;
}

.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 0;
  border-bottom: 1px solid var(--border-color);
}

.setting-item.danger {
  border-bottom-color: rgba(239, 68, 68, 0.2);
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label-text {
  font-size: 15px;
  font-weight: 500;
  color: var(--text-primary);
}

.setting-item.danger .label-text {
  color: #ef4444;
}

.label-desc {
  font-size: 13px;
  color: var(--text-secondary);
}

.setting-control {
  display: flex;
  gap: 8px;
}

/* 主题选择 */
.theme-option {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.theme-option:hover {
  border-color: var(--send-btn);
  color: var(--text-primary);
}

.theme-option.active {
  border-color: var(--send-btn);
  background: var(--send-btn);
  color: white;
}

/* 语言选择 */
.language-select {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  color: var(--text-primary);
  border-radius: 8px;
  font-size: 14px;
  cursor: not-allowed;
  opacity: 0.6;
}

/* 操作按钮 */
.action-btn {
  padding: 8px 20px;
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  color: var(--text-primary);
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}

.action-btn:hover {
  border-color: var(--send-btn);
  background: var(--send-btn);
  color: white;
}

.action-btn.danger {
  border-color: rgba(239, 68, 68, 0.3);
  color: #ef4444;
}

.action-btn.danger:hover {
  border-color: #ef4444;
  background: #ef4444;
  color: white;
}

/* 对话框 */
.dialog-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.dialog-content {
  width: 90%;
  max-width: 400px;
  background: var(--sidebar-bg);
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.dialog-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 20px 0;
}

.form-group {
  margin-bottom: 16px;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.form-group input {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  color: var(--text-primary);
  border-radius: 8px;
  font-size: 14px;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: var(--send-btn);
}

.error-message {
  padding: 10px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #ef4444;
  font-size: 13px;
  margin-bottom: 16px;
}

.danger-warning {
  padding: 12px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #ef4444;
  font-size: 14px;
  line-height: 1.6;
  margin-bottom: 20px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel,
.btn-confirm,
.btn-danger {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-cancel {
  background: var(--border-color);
  color: var(--text-primary);
}

.btn-cancel:hover {
  background: var(--input-bg);
}

.btn-confirm {
  background: var(--send-btn);
  color: white;
}

.btn-confirm:hover:not(:disabled) {
  background: var(--send-btn-hover);
}

.btn-confirm:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

/* 对话框动画 */
.dialog-fade-enter-active,
.dialog-fade-leave-active {
  transition: opacity 0.2s;
}

.dialog-fade-enter-from,
.dialog-fade-leave-to {
  opacity: 0;
}

.dialog-fade-enter-active .dialog-content,
.dialog-fade-leave-active .dialog-content {
  transition: transform 0.2s;
}

.dialog-fade-enter-from .dialog-content {
  transform: scale(0.95);
}

.dialog-fade-leave-to .dialog-content {
  transform: scale(0.95);
}
</style>
