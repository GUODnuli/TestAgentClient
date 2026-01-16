<template>
  <div class="register-page">
    <div class="register-container">
      <div class="register-header">
        <h1 class="register-title">MCP 接口测试智能体</h1>
        <p class="register-subtitle">创建新账户</p>
      </div>

      <form class="register-form" @submit.prevent="handleRegister">
        <div class="form-group">
          <label for="username">用户名</label>
          <input
            id="username"
            v-model="form.username"
            type="text"
            placeholder="4-32位，字母开头，可含字母数字下划线"
            autocomplete="username"
            :disabled="loading"
          />
          <span v-if="errors.username" class="field-error">{{ errors.username }}</span>
        </div>

        <div class="form-group">
          <label for="email">邮箱 <span class="optional">(可选)</span></label>
          <input
            id="email"
            v-model="form.email"
            type="email"
            placeholder="请输入邮箱"
            autocomplete="email"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label for="display_name">显示名称 <span class="optional">(可选)</span></label>
          <input
            id="display_name"
            v-model="form.display_name"
            type="text"
            placeholder="用于展示的名称"
            :disabled="loading"
          />
        </div>

        <div class="form-group">
          <label for="password">密码</label>
          <input
            id="password"
            v-model="form.password"
            type="password"
            placeholder="至少8位"
            autocomplete="new-password"
            :disabled="loading"
          />
          <span v-if="errors.password" class="field-error">{{ errors.password }}</span>
        </div>

        <div class="form-group">
          <label for="confirmPassword">确认密码</label>
          <input
            id="confirmPassword"
            v-model="form.confirmPassword"
            type="password"
            placeholder="再次输入密码"
            autocomplete="new-password"
            :disabled="loading"
          />
          <span v-if="errors.confirmPassword" class="field-error">{{ errors.confirmPassword }}</span>
        </div>

        <div v-if="errorMessage" class="error-message">
          {{ errorMessage }}
        </div>

        <div v-if="successMessage" class="success-message">
          {{ successMessage }}
        </div>

        <button type="submit" class="register-btn" :disabled="loading || !isFormValid">
          <span v-if="loading">注册中...</span>
          <span v-else>注册</span>
        </button>

        <div class="register-footer">
          <span>已有账户？</span>
          <router-link to="/login" class="login-link">立即登录</router-link>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const userStore = useUserStore()

const form = ref({
  username: '',
  email: '',
  display_name: '',
  password: '',
  confirmPassword: ''
})

const errors = ref({
  username: '',
  password: '',
  confirmPassword: ''
})

const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

// 验证用户名格式
const validateUsername = (username) => {
  if (!username) return '请输入用户名'
  if (username.length < 4) return '用户名至少4位'
  if (username.length > 32) return '用户名最多32位'
  if (!/^[a-zA-Z]/.test(username)) return '用户名必须以字母开头'
  if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(username)) return '用户名只能包含字母、数字和下划线'
  return ''
}

// 验证密码
const validatePassword = (password) => {
  if (!password) return '请输入密码'
  if (password.length < 8) return '密码至少8位'
  return ''
}

// 监听输入变化进行实时验证
watch(() => form.value.username, (val) => {
  errors.value.username = val ? validateUsername(val) : ''
})

watch(() => form.value.password, (val) => {
  errors.value.password = val ? validatePassword(val) : ''
  if (form.value.confirmPassword) {
    errors.value.confirmPassword = val !== form.value.confirmPassword ? '两次输入的密码不一致' : ''
  }
})

watch(() => form.value.confirmPassword, (val) => {
  errors.value.confirmPassword = val && val !== form.value.password ? '两次输入的密码不一致' : ''
})

const isFormValid = computed(() => {
  return form.value.username.trim() 
    && form.value.password 
    && form.value.confirmPassword
    && form.value.password === form.value.confirmPassword
    && !errors.value.username
    && !errors.value.password
    && !errors.value.confirmPassword
})

const handleRegister = async () => {
  if (!isFormValid.value || loading.value) return

  // 最终验证
  errors.value.username = validateUsername(form.value.username)
  errors.value.password = validatePassword(form.value.password)
  errors.value.confirmPassword = form.value.password !== form.value.confirmPassword ? '两次输入的密码不一致' : ''

  if (errors.value.username || errors.value.password || errors.value.confirmPassword) {
    return
  }

  loading.value = true
  errorMessage.value = ''
  successMessage.value = ''

  const result = await userStore.register({
    username: form.value.username,
    password: form.value.password,
    email: form.value.email || undefined,
    display_name: form.value.display_name || undefined
  })

  loading.value = false

  if (result.success) {
    successMessage.value = '注册成功！即将跳转到登录页面...'
    setTimeout(() => {
      router.push('/login')
    }, 1500)
  } else {
    errorMessage.value = result.error
  }
}
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--main-bg, #232326);
  padding: 20px;
}

.register-container {
  width: 100%;
  max-width: 420px;
  background-color: var(--sidebar-bg, #1d1d1f);
  border-radius: 16px;
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.register-header {
  text-align: center;
  margin-bottom: 32px;
}

.register-title {
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary, #e0e0e0);
  margin: 0 0 8px 0;
}

.register-subtitle {
  font-size: 14px;
  color: var(--text-secondary, #999999);
  margin: 0;
}

.register-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary, #e0e0e0);
}

.optional {
  font-weight: 400;
  color: var(--text-secondary, #999999);
  font-size: 12px;
}

.form-group input {
  padding: 12px 16px;
  font-size: 14px;
  border: 1px solid var(--border-color, #3a3a3a);
  border-radius: 8px;
  background-color: var(--input-bg, #2a2a2a);
  color: var(--text-primary, #e0e0e0);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: var(--send-btn, #615ced);
  box-shadow: 0 0 0 3px rgba(97, 92, 237, 0.2);
}

.form-group input::placeholder {
  color: var(--text-secondary, #999999);
  font-size: 13px;
}

.form-group input:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.field-error {
  font-size: 12px;
  color: #ef4444;
}

.error-message {
  padding: 12px;
  background-color: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 8px;
  color: #ef4444;
  font-size: 14px;
  text-align: center;
}

.success-message {
  padding: 12px;
  background-color: rgba(34, 197, 94, 0.1);
  border: 1px solid rgba(34, 197, 94, 0.3);
  border-radius: 8px;
  color: #22c55e;
  font-size: 14px;
  text-align: center;
}

.register-btn {
  padding: 14px;
  font-size: 16px;
  font-weight: 600;
  color: white;
  background-color: var(--send-btn, #615ced);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s, transform 0.1s;
  margin-top: 4px;
}

.register-btn:hover:not(:disabled) {
  background-color: var(--send-btn-hover, #7571ff);
}

.register-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.register-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.register-footer {
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary, #999999);
  margin-top: 4px;
}

.login-link {
  color: var(--send-btn, #615ced);
  text-decoration: none;
  font-weight: 500;
  margin-left: 4px;
}

.login-link:hover {
  text-decoration: underline;
}
</style>
