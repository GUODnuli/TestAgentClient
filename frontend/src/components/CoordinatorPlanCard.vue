<template>
  <div 
    v-if="plan" 
    class="coordinator-plan-sidebar"
    :class="{ 
      'is-expanded': isExpanded,
      'is-collapsed': !isExpanded 
    }"
  >
    <!-- 展开状态下的内容 -->
    <div v-if="isExpanded" class="sidebar-content">
      <!-- 头部 -->
      <div class="sidebar-header">
        <div class="header-title">
          <el-icon class="header-icon"><Connection /></el-icon>
          <div class="title-text">
            <span class="plan-name">{{ truncatedObjective }}</span>
            <span class="plan-progress">{{ completedCount }}/{{ totalCount }} 完成</span>
          </div>
        </div>
        <button class="collapse-btn" @click="isExpanded = false" title="收起">
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>

      <!-- Phase 列表区域 -->
      <div class="phases-scroll-area">
        <div class="phases-container">
          <div
            v-for="(phase, index) in plan.phases"
            :key="phase.phase || index"
            class="phase-item"
            :class="[
              getPhaseStatusClass(phase),
              { 'is-active': isPhaseActive(phase) }
            ]"
          >
            <!-- 状态图标和时间线 -->
            <div class="phase-timeline">
              <div class="status-icon-wrapper">
                <span v-if="isPhaseCompleted(phase)" class="status-icon completed">✓</span>
                <span v-else-if="isPhaseActive(phase)" class="status-icon active">
                  <span class="pulse-ring"></span>
                </span>
                <span v-else class="status-icon pending">○</span>
              </div>
              <div v-if="index < plan.phases.length - 1" class="timeline-line"></div>
            </div>

            <!-- Phase 内容 -->
            <div class="phase-content">
              <div class="phase-header-row">
                <span class="phase-badge">P{{ phase.phase }}</span>
                <span class="phase-name" :class="{ 'is-strikethrough': isPhaseCompleted(phase) }">
                  {{ phase.name }}
                </span>
              </div>

              <!-- Workers -->
              <div v-if="phase.workers && phase.workers.length > 0" class="workers-list">
                <div
                  v-for="(worker, wIdx) in phase.workers"
                  :key="wIdx"
                  class="worker-item"
                  :class="{ 'is-strikethrough': isPhaseCompleted(phase) }"
                >
                  <el-icon class="worker-icon"><UserFilled /></el-icon>
                  <span class="worker-name">{{ worker.worker }}</span>
                </div>
              </div>

              <!-- 依赖提示 -->
              <div v-if="phase.depends_on && phase.depends_on.length > 0" class="phase-deps">
                <el-icon><Link /></el-icon>
                <span>{{ formatDeps(phase.depends_on) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 完成状态 -->
        <div v-if="isPlanCompleted" class="completion-banner">
          <el-icon class="completion-icon"><CircleCheckFilled /></el-icon>
          <span>执行完成</span>
        </div>
      </div>
    </div>

    <!-- 收起状态下的标签 -->
    <div v-else class="sidebar-collapsed" @click="isExpanded = true">
      <div class="collapsed-content">
        <el-icon class="collapsed-icon"><Connection /></el-icon>
        <div class="collapsed-progress">
          <div class="progress-ring">
            <svg viewBox="0 0 36 36">
              <path
                class="progress-ring-bg"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
              <path
                class="progress-ring-fill"
                :stroke-dasharray="`${progressPercent}, 100`"
                d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
              />
            </svg>
            <span class="progress-text">{{ completedCount }}</span>
          </div>
          <span class="collapsed-label">/{{ totalCount }}</span>
        </div>
        <el-icon class="expand-arrow"><ArrowLeft /></el-icon>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, defineExpose } from 'vue'
import {
  Connection,
  ArrowRight,
  ArrowLeft,
  UserFilled,
  Link,
  CircleCheckFilled
} from '@element-plus/icons-vue'

const props = defineProps({
  plan: {
    type: Object,
    default: null
  },
  activePhase: {
    type: Number,
    default: null
  },
  completedPhases: {
    type: Array,
    default: () => []
  },
  phaseOutputs: {
    type: Object,
    default: () => ({})
  }
})

const isExpanded = ref(true)

// 计算总任务数
const totalCount = computed(() => props.plan?.phases?.length || 0)

// 计算已完成数
const completedCount = computed(() => props.completedPhases?.length || 0)

// 计算进度百分比
const progressPercent = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((completedCount.value / totalCount.value) * 100)
})

// 检查计划是否全部完成
const isPlanCompleted = computed(() => {
  return totalCount.value > 0 && completedCount.value === totalCount.value
})

// 截断目标文本
const truncatedObjective = computed(() => {
  const objective = props.plan?.objective || '执行计划'
  if (objective.length <= 20) return objective
  return objective.substring(0, 18) + '...'
})

// 判断 phase 是否已完成
function isPhaseCompleted(phase) {
  const phaseNum = phase.phase || phase.id
  return props.completedPhases.includes(phaseNum)
}

// 判断 phase 是否正在进行
function isPhaseActive(phase) {
  const phaseNum = phase.phase || phase.id
  return props.activePhase === phaseNum && !isPhaseCompleted(phase)
}

// 获取 phase 状态类名
function getPhaseStatusClass(phase) {
  if (isPhaseCompleted(phase)) return 'status-completed'
  if (isPhaseActive(phase)) return 'status-active'
  return 'status-pending'
}

// 格式化依赖显示
function formatDeps(deps) {
  if (!deps || deps.length === 0) return ''
  return '依赖: ' + deps.map(d => d.replace('phase_', 'P')).join(', ')
}

// 监听完成状态，完成后保持展开但显示完成标记
watch(isPlanCompleted, (completed) => {
  if (completed) {
    // 完成后保持展开，让用户看到完成状态
    isExpanded.value = true
  }
})

// 暴露 isExpanded 状态给父组件
defineExpose({
  isExpanded: computed(() => isExpanded.value)
})
</script>

<style scoped>
/* ==================== 侧边栏容器 ==================== */
.coordinator-plan-sidebar {
  position: fixed;
  top: 0;
  right: 0;
  /* 高度计算：视口高度 - 底部输入区高度(约100px) - 安全间距(40px) */
  height: calc(100vh - 140px) !important;
  max-height: calc(100vh - 140px) !important;
  background: var(--sidebar-bg, #f7f8fc);
  border-left: 1px solid var(--border-color, #e5e5e5);
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.08);
  z-index: 100;
  display: flex;
  flex-direction: column;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;
}

/* 展开状态 */
.coordinator-plan-sidebar.is-expanded {
  width: 320px;
}

/* 收起状态 */
.coordinator-plan-sidebar.is-collapsed {
  width: 56px;
}

/* ==================== 展开状态内容 ==================== */
.sidebar-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* 头部 */
.sidebar-header {
  padding: 16px;
  background: var(--main-bg, #ffffff);
  border-bottom: 1px solid var(--border-color, #e5e5e5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  overflow: hidden;
}

.header-icon {
  font-size: 20px;
  color: var(--send-btn, #615ced);
  flex-shrink: 0;
}

.title-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}

.plan-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.plan-progress {
  font-size: 12px;
  color: var(--text-secondary, #666666);
}

.collapse-btn {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #666666);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: all 0.2s;
  flex-shrink: 0;
}

.collapse-btn:hover {
  background: var(--border-color, #e5e5e5);
  color: var(--text-primary, #1a1a1a);
}

/* Phase 滚动区域 */
.phases-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.phases-scroll-area::-webkit-scrollbar {
  width: 4px;
}

.phases-scroll-area::-webkit-scrollbar-track {
  background: transparent;
}

.phases-scroll-area::-webkit-scrollbar-thumb {
  background: var(--border-color, #e5e5e5);
  border-radius: 2px;
}

/* Phase 容器 */
.phases-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Phase 项 */
.phase-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
  position: relative;
}

.phase-item.status-active {
  background: rgba(64, 158, 255, 0.06);
  margin: 0 -16px;
  padding: 12px 16px;
  border-radius: 8px;
}

/* 时间线 */
.phase-timeline {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
}

.status-icon-wrapper {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-icon {
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
}

.status-icon.pending {
  color: var(--text-secondary, #999999);
  font-size: 16px;
}

.status-icon.active {
  color: #409eff;
  position: relative;
}

.status-icon.completed {
  color: #67c23a;
  font-size: 16px;
}

/* 脉冲动画 */
.pulse-ring {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { 
    transform: scale(1); 
    opacity: 1; 
  }
  50% { 
    transform: scale(1.4); 
    opacity: 0.5; 
  }
}

/* 时间线连接线 */
.timeline-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: var(--border-color, #e5e5e5);
  margin: 4px 0;
}

/* Phase 内容 */
.phase-content {
  flex: 1;
  min-width: 0;
  padding-bottom: 8px;
}

.phase-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.phase-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary, #666666);
  background: var(--main-bg, #ffffff);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid var(--border-color, #e5e5e5);
  flex-shrink: 0;
}

.phase-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
  line-height: 1.4;
}

.phase-name.is-strikethrough,
.is-strikethrough {
  text-decoration: line-through;
  color: var(--text-secondary, #999999);
}

/* Workers */
.workers-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.worker-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #666666);
}

.worker-icon {
  font-size: 12px;
  color: var(--send-btn, #615ced);
}

.worker-name {
  font-weight: 500;
}

/* 依赖信息 */
.phase-deps {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: var(--text-secondary, #999999);
  margin-top: 6px;
  padding-left: 18px;
}

.phase-deps .el-icon {
  font-size: 12px;
}

/* 完成横幅 */
.completion-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-top: 16px;
  padding: 12px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: 8px;
  color: #67c23a;
  font-size: 13px;
  font-weight: 500;
}

.completion-icon {
  font-size: 18px;
}

/* ==================== 收起状态 ==================== */
.sidebar-collapsed {
  width: 56px;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px 0;
  cursor: pointer;
  background: var(--sidebar-bg, #f7f8fc);
  transition: background 0.2s;
}

.sidebar-collapsed:hover {
  background: var(--border-color, #e5e5e5);
}

.collapsed-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.collapsed-icon {
  font-size: 20px;
  color: var(--send-btn, #615ced);
}

.collapsed-progress {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.progress-ring {
  position: relative;
  width: 36px;
  height: 36px;
}

.progress-ring svg {
  width: 100%;
  height: 100%;
  transform: rotate(-90deg);
}

.progress-ring-bg {
  fill: none;
  stroke: var(--border-color, #e5e5e5);
  stroke-width: 3;
}

.progress-ring-fill {
  fill: none;
  stroke: var(--send-btn, #615ced);
  stroke-width: 3;
  stroke-linecap: round;
  transition: stroke-dasharray 0.3s ease;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
}

.collapsed-label {
  font-size: 10px;
  color: var(--text-secondary, #666666);
}

.expand-arrow {
  font-size: 14px;
  color: var(--text-secondary, #666666);
  animation: bounce-left 1.5s infinite;
}

@keyframes bounce-left {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(-3px); }
}

/* ==================== 暗黑模式适配 ==================== */
:global(.dark) .coordinator-plan-sidebar {
  background: #1d1d1f;
  border-left-color: #3a3a3a;
}

:global(.dark) .sidebar-header {
  background: #232326;
  border-bottom-color: #3a3a3a;
}

:global(.dark) .phase-badge {
  background: #2a2a2a;
  border-color: #3a3a3a;
}

:global(.dark) .phase-item.status-active {
  background: rgba(64, 158, 255, 0.1);
}

:global(.dark) .sidebar-collapsed:hover {
  background: #3a3a3a;
}

/* ==================== 响应式 ==================== */
@media (max-width: 768px) {
  .coordinator-plan-sidebar.is-expanded {
    width: 100%;
    height: 50vh;
    top: auto;
    bottom: 80px;
    border-left: none;
    border-top: 1px solid var(--border-color, #e5e5e5);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);
  }
  
  .coordinator-plan-sidebar.is-collapsed {
    width: 48px;
    height: 48px;
    top: auto;
    bottom: 100px;
    right: 16px;
    border-radius: 50%;
    border: 1px solid var(--border-color, #e5e5e5);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  }
}
</style>
