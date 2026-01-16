import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api, { getToken, setToken, removeToken, getStoredUser, setStoredUser } from '@/api'

export const useUserStore = defineStore('user', () => {
  // 用户信息
  const user = ref(getStoredUser())
  
  // 加载状态
  const loading = ref(false)
  
  // 错误信息
  const error = ref(null)

  // 计算属性
  const isLoggedIn = computed(() => !!user.value && !!getToken())
  const username = computed(() => user.value?.username || '')
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')
  const isAdmin = computed(() => user.value?.role === 'admin')

  // 用户注册
  const register = async (userData) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.register(userData)
      return { success: true, user: response }
    } catch (err) {
      const message = err.response?.data?.detail || '注册失败，请稍后重试'
      error.value = message
      return { success: false, error: message }
    } finally {
      loading.value = false
    }
  }

  // 用户登录
  const login = async (credentials) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.login(credentials)
      
      // 保存 Token 和用户信息
      setToken(response.access_token)
      setStoredUser(response.user)
      user.value = response.user
      
      return { success: true, user: response.user }
    } catch (err) {
      const message = err.response?.data?.detail || '登录失败，请检查用户名和密码'
      error.value = message
      return { success: false, error: message }
    } finally {
      loading.value = false
    }
  }

  // 用户登出
  const logout = async () => {
    try {
      if (getToken()) {
        await api.logout()
      }
    } catch (err) {
      console.warn('登出请求失败:', err)
    } finally {
      // 无论请求是否成功，都清除本地状态
      removeToken()
      user.value = null
    }
  }

  // 获取当前用户信息
  const fetchCurrentUser = async () => {
    if (!getToken()) {
      return null
    }
    
    loading.value = true
    
    try {
      const response = await api.getCurrentUser()
      setStoredUser(response)
      user.value = response
      return response
    } catch (err) {
      // Token 无效，清除状态
      if (err.response?.status === 401) {
        removeToken()
        user.value = null
      }
      return null
    } finally {
      loading.value = false
    }
  }

  // 修改密码
  const changePassword = async (passwordData) => {
    loading.value = true
    error.value = null
    
    try {
      await api.changePassword(passwordData)
      // 修改密码成功后需要重新登录
      removeToken()
      user.value = null
      return { success: true }
    } catch (err) {
      const message = err.response?.data?.detail || '修改密码失败'
      error.value = message
      return { success: false, error: message }
    } finally {
      loading.value = false
    }
  }

  // 更新用户资料
  const updateProfile = async (profileData) => {
    loading.value = true
    error.value = null
    
    try {
      const response = await api.updateProfile(profileData)
      setStoredUser(response)
      user.value = response
      return { success: true, user: response }
    } catch (err) {
      const message = err.response?.data?.detail || '更新资料失败'
      error.value = message
      return { success: false, error: message }
    } finally {
      loading.value = false
    }
  }

  // 初始化 - 检查登录状态
  const init = async () => {
    const token = getToken()
    if (token) {
      await fetchCurrentUser()
    }
  }

  // 监听登出事件
  if (typeof window !== 'undefined') {
    window.addEventListener('auth:logout', (event) => {
      console.log('收到登出事件:', event.detail?.reason)
      user.value = null
    })
  }

  return {
    // 状态
    user,
    loading,
    error,
    
    // 计算属性
    isLoggedIn,
    username,
    displayName,
    isAdmin,
    
    // 方法
    register,
    login,
    logout,
    fetchCurrentUser,
    changePassword,
    updateProfile,
    init
  }
})
