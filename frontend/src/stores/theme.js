import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  // 主题模式: 'light' | 'dark'
  const theme = ref(localStorage.getItem('theme') || 'dark')
  
  // 侧边栏展开状态
  const sidebarExpanded = ref(localStorage.getItem('sidebarExpanded') !== 'false')

  // 主题颜色配置
  const themeColors = {
    light: {
      sidebarBg: '#f7f8fc',
      mainBg: '#ffffff',
      textPrimary: '#1a1a1a',
      textSecondary: '#666666',
      border: '#e5e5e5',
      inputBg: '#f5f5f5',
      sendBtn: '#615ced',
      sendBtnHover: '#5248d9'
    },
    dark: {
      sidebarBg: '#1d1d1f',
      mainBg: '#232326',
      textPrimary: '#e0e0e0',
      textSecondary: '#999999',
      border: '#3a3a3a',
      inputBg: '#2a2a2a',
      sendBtn: '#615ced',
      sendBtnHover: '#7571ff'
    }
  }

  // 获取当前主题颜色
  const colors = () => themeColors[theme.value]

  // 切换主题
  const toggleTheme = () => {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }

  // 设置主题
  const setTheme = (newTheme) => {
    theme.value = newTheme
  }

  // 切换侧边栏
  const toggleSidebar = () => {
    sidebarExpanded.value = !sidebarExpanded.value
  }

  // 监听变化并保存到localStorage
  watch(theme, (val) => {
    localStorage.setItem('theme', val)
    // 更新CSS变量
    updateCSSVariables()
  })

  watch(sidebarExpanded, (val) => {
    localStorage.setItem('sidebarExpanded', val)
  })

  // 更新CSS变量
  const updateCSSVariables = () => {
    const root = document.documentElement
    const currentColors = themeColors[theme.value]
    
    root.style.setProperty('--sidebar-bg', currentColors.sidebarBg)
    root.style.setProperty('--main-bg', currentColors.mainBg)
    root.style.setProperty('--text-primary', currentColors.textPrimary)
    root.style.setProperty('--text-secondary', currentColors.textSecondary)
    root.style.setProperty('--border-color', currentColors.border)
    root.style.setProperty('--input-bg', currentColors.inputBg)
    root.style.setProperty('--send-btn', currentColors.sendBtn)
    root.style.setProperty('--send-btn-hover', currentColors.sendBtnHover)
  }

  // 初始化CSS变量
  const initTheme = () => {
    updateCSSVariables()
  }

  return {
    theme,
    sidebarExpanded,
    colors,
    toggleTheme,
    setTheme,
    toggleSidebar,
    initTheme
  }
})
