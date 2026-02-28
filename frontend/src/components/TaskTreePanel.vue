<template>
  <div
    class="task-tree-panel"
    :class="{
      'is-expanded': isExpanded,
      'is-collapsed': !isExpanded
    }"
  >
    <!-- ══════════ 展开状态 ══════════ -->
    <div v-if="isExpanded" class="panel-content">
      <!-- 头部 -->
      <div class="panel-header">
        <div class="header-title">
          <el-icon class="header-icon"><Connection /></el-icon>
          <div class="title-text">
            <span class="panel-name">{{ truncatedObjective }}</span>
            <span class="panel-progress">{{ completedCount }}/{{ totalCount }} 完成</span>
          </div>
        </div>
        <button class="collapse-btn" @click="isExpanded = false" title="收起">
          <el-icon><ArrowRight /></el-icon>
        </button>
      </div>

      <!-- 标签栏 -->
      <div class="tab-bar">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'tasks' }"
          @click="switchToTasks()"
        >任务</button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'downloads' }"
          @click="switchToDownloads"
        >下载</button>
      </div>

      <!-- ─── 任务树模式 ─── -->
      <div v-if="activeTab === 'tasks' && displayMode === 'tree'" class="scroll-area">
        <div class="tree-container">
          <TaskNodeItem
            v-for="nodeId in rootTaskIds"
            :key="nodeId"
            :node="taskNodes[nodeId]"
            :task-nodes="taskNodes"
          />
        </div>

        <!-- 完成横幅 -->
        <div v-if="isAllCompleted" class="completion-banner">
          <el-icon class="completion-icon"><CircleCheckFilled /></el-icon>
          <span>执行完成</span>
        </div>
      </div>

      <!-- ─── 旧 Phase 模式（向后兼容）─── -->
      <div v-else-if="activeTab === 'tasks' && displayMode === 'legacy' && legacyPlan" class="scroll-area">
        <div class="phases-container">
          <div
            v-for="(phase, index) in legacyPlan.phases"
            :key="phase.phase || index"
            class="phase-item"
            :class="[
              getLegacyPhaseStatusClass(phase),
              { 'is-active': isLegacyPhaseActive(phase) }
            ]"
          >
            <div class="phase-timeline">
              <div class="status-icon-wrapper">
                <span v-if="isLegacyPhaseCompleted(phase)" class="status-icon completed">✓</span>
                <span v-else-if="isLegacyPhaseActive(phase)" class="status-icon active">
                  <span class="pulse-ring"></span>
                </span>
                <span v-else class="status-icon pending">○</span>
              </div>
              <div v-if="index < legacyPlan.phases.length - 1" class="timeline-line"></div>
            </div>
            <div class="phase-content">
              <div class="phase-header-row">
                <span class="phase-badge">P{{ phase.phase }}</span>
                <span class="phase-name" :class="{ 'is-strikethrough': isLegacyPhaseCompleted(phase) }">
                  {{ phase.name }}
                </span>
              </div>
              <div v-if="phase.workers && phase.workers.length > 0" class="workers-list">
                <div
                  v-for="(worker, wIdx) in phase.workers"
                  :key="wIdx"
                  class="worker-item"
                >
                  <el-icon class="worker-icon"><UserFilled /></el-icon>
                  <span class="worker-name">{{ worker.worker }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="isAllCompleted" class="completion-banner">
          <el-icon class="completion-icon"><CircleCheckFilled /></el-icon>
          <span>执行完成</span>
        </div>
      </div>

      <!-- ─── 任务空状态 ─── -->
      <div v-else-if="activeTab === 'tasks'" class="scroll-area">
        <div class="tasks-empty">本次会话暂无任务记录</div>
      </div>

      <!-- ─── 下载标签页 ─── -->
      <div v-if="activeTab === 'downloads'" class="scroll-area">
        <div v-if="loadingFiles" class="download-loading">加载中...</div>
        <div v-else-if="outputFiles.length === 0" class="download-empty">暂无可下载文件</div>
        <div v-else class="download-list">
          <!-- 全选 -->
          <label class="select-all-label">
            <input type="checkbox" @change="toggleAll" :checked="allSelected" />
            <span>全选 ({{ outputFiles.length }} 个文件)</span>
          </label>
          <!-- 文件条目 -->
          <div
            v-for="f in outputFiles"
            :key="f.name"
            class="file-item"
          >
            <input
              type="checkbox"
              :value="f.name"
              :checked="selectedFiles.has(f.name)"
              @change="toggleFile(f.name)"
            />
            <span class="file-item-name" :title="f.name">{{ f.name }}</span>
            <span class="file-item-size">{{ formatSize(f.size) }}</span>
          </div>
          <!-- 下载按钮 -->
          <button
            class="download-btn"
            @click="downloadSelected"
            :disabled="selectedFiles.size === 0"
          >
            下载选中 ({{ selectedFiles.size }})
          </button>
        </div>
      </div>
    </div>

    <!-- ══════════ 收起状态 ══════════ -->
    <div v-else class="panel-collapsed" @click="isExpanded = true">
      <div class="collapsed-content">
        <el-icon class="collapsed-icon"><Connection /></el-icon>
        <!-- 有任务时显示进度环 -->
        <div v-if="totalCount > 0" class="collapsed-progress">
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
        <!-- 无任务时显示下载文件数角标 -->
        <div v-else class="collapsed-downloads">
          <span class="collapsed-dl-count">{{ outputFiles.length }}</span>
          <span class="collapsed-label">文件</span>
        </div>
        <el-icon class="expand-arrow"><ArrowLeft /></el-icon>
      </div>
    </div>
  </div>
</template>

<script setup>
import { h, ref, computed, watch, defineExpose, defineProps } from 'vue'
import {
  Connection,
  ArrowRight,
  ArrowLeft,
  UserFilled,
  CircleCheckFilled,
} from '@element-plus/icons-vue'
import { api } from '@/api'

// ─── TaskNodeItem (递归子组件) ─────────────────────────────────────────────────
// 使用 render 函数代替 template 字符串，避免 Vue 3 runtime-only 构建缺少模板编译器
// 导致组件渲染为空注释节点 (<!---->) 的问题。
const TaskNodeItem = {
  name: 'TaskNodeItem',
  props: {
    node: { type: Object, required: true },
    taskNodes: { type: Object, required: true },
  },
  computed: {
    childIds() {
      return Object.values(this.taskNodes)
        .filter(n => n.parent_id === this.node.task_id)
        .map(n => n.task_id)
    }
  },
  render() {
    const { node, taskNodes, childIds } = this

    // 状态图标
    let statusIcon
    if (node.status === 'completed') {
      statusIcon = h('span', { class: 'icon-completed' }, '✓')
    } else if (node.status === 'running') {
      statusIcon = h('span', { class: 'icon-running' }, [
        h('span', { class: 'pulse-ring' })
      ])
    } else if (node.status === 'failed') {
      statusIcon = h('span', { class: 'icon-failed' }, '✗')
    } else {
      statusIcon = h('span', { class: 'icon-pending' }, '○')
    }

    // 节点主体内容
    const bodyChildren = [
      h('div', { class: 'node-desc' }, node.description),
      h('div', { class: 'node-meta' }, [
        h('span', { class: 'node-worker-badge' }, node.worker_name),
        h('span', { class: 'node-id' }, node.task_id),
      ]),
    ]

    if (node.status === 'completed' && node.result) {
      bodyChildren.push(h('div', { class: 'node-result' }, node.result))
    }
    if (node.status === 'failed' && node.error) {
      bodyChildren.push(h('div', { class: 'node-error' }, node.error))
    }

    // 节点行
    const nodeRow = h('div', { class: 'node-row' }, [
      h('div', { class: 'node-status-icon' }, [statusIcon]),
      h('div', { class: 'node-body' }, bodyChildren),
    ])

    // 子节点递归
    const children = [nodeRow]
    if (childIds.length > 0) {
      children.push(
        h('div', { class: 'node-children' },
          childIds.map(childId =>
            h(TaskNodeItem, {
              key: childId,
              node: taskNodes[childId],
              taskNodes,
            })
          )
        )
      )
    }

    return h('div', { class: ['task-node', 'node-' + node.status] }, children)
  },
}

const props = defineProps({
  conversationId: {
    type: String,
    default: '',
  },
})

// ─── State ───────────────────────────────────────────────────────────────────

const isExpanded = ref(true)

// Display mode: 'none' | 'legacy' | 'tree'
const displayMode = ref('none')

// ── Tab state ──
const activeTab = ref('tasks')

// ── Downloads state ──
const outputFiles = ref([])
const selectedFiles = ref(new Set())
const loadingFiles = ref(false)
const loadingTaskTree = ref(false)

// ── Legacy phase mode (backward compat) ──
const legacyPlan = ref(null)
const legacyActivePhase = ref(null)
const legacyCompletedPhases = ref([])

// ── Task tree mode ──
const taskNodes = ref({})        // task_id → TaskNode
const rootTaskIds = ref([])      // top-level task IDs (no parent)

// ─── Visibility ──────────────────────────────────────────────────────────────

const isVisible = computed(() => {
  if (displayMode.value === 'tree') return Object.keys(taskNodes.value).length > 0
  if (displayMode.value === 'legacy') return legacyPlan.value !== null
  return false
})

// ─── Progress computation ─────────────────────────────────────────────────────

const totalCount = computed(() => {
  if (displayMode.value === 'tree') return Object.keys(taskNodes.value).length
  if (displayMode.value === 'legacy') return legacyPlan.value?.phases?.length || 0
  return 0
})

const completedCount = computed(() => {
  if (displayMode.value === 'tree') {
    return Object.values(taskNodes.value).filter(n => n.status === 'completed').length
  }
  if (displayMode.value === 'legacy') return legacyCompletedPhases.value.length
  return 0
})

const progressPercent = computed(() => {
  if (totalCount.value === 0) return 0
  return Math.round((completedCount.value / totalCount.value) * 100)
})

const isAllCompleted = computed(() => {
  if (totalCount.value === 0) return false
  return completedCount.value === totalCount.value
})

const truncatedObjective = computed(() => {
  if (displayMode.value === 'tree') return '任务树'
  const obj = legacyPlan.value?.objective || '执行计划'
  return obj.length <= 20 ? obj : obj.substring(0, 18) + '...'
})

// ─── Public event handler (called by ChatView) ───────────────────────────────

function handleCoordinatorEvent(eventType, data) {
  if (!eventType || !data) return

  switch (eventType) {
    // ── Legacy phase events ──
    case 'plan_created':
      displayMode.value = 'legacy'
      legacyPlan.value = data.plan || null
      legacyActivePhase.value = null
      legacyCompletedPhases.value = []
      break

    case 'phase_started':
      if (data.phase) legacyActivePhase.value = data.phase
      break

    case 'phase_completed':
      if (data.phase) {
        legacyCompletedPhases.value.push(data.phase)
        if (legacyActivePhase.value === data.phase) legacyActivePhase.value = null
      }
      break

    case 'coordinator_initialized':
      reset()
      break

    // ── New task tree events ──
    case 'task_tree_snapshot':
      displayMode.value = 'tree'
      rebuildFromSnapshot(data.nodes || [])
      break

    case 'task_tree_node_created':
      displayMode.value = 'tree'
      taskNodes.value[data.task_id] = {
        task_id: data.task_id,
        description: data.description,
        worker_name: data.worker_name,
        status: data.status || 'pending',
        result: null,
        error: null,
        parent_id: data.parent_id || null,
        depth: data.depth || 0,
      }
      if (!data.parent_id) {
        if (!rootTaskIds.value.includes(data.task_id)) {
          rootTaskIds.value.push(data.task_id)
        }
      }
      break

    case 'task_tree_node_started':
      if (taskNodes.value[data.task_id]) {
        taskNodes.value[data.task_id] = {
          ...taskNodes.value[data.task_id],
          status: 'running',
        }
      }
      break

    case 'task_tree_node_completed':
      if (taskNodes.value[data.task_id]) {
        taskNodes.value[data.task_id] = {
          ...taskNodes.value[data.task_id],
          status: 'completed',
          result: data.result_summary || null,
        }
      }
      break

    case 'task_tree_node_failed':
      if (taskNodes.value[data.task_id]) {
        taskNodes.value[data.task_id] = {
          ...taskNodes.value[data.task_id],
          status: 'failed',
          error: data.error || null,
        }
      }
      break

    default:
      break
  }
}

function rebuildFromSnapshot(nodes) {
  const newNodes = {}
  const newRoots = []
  for (const n of nodes) {
    newNodes[n.task_id] = n
    if (!n.parent_id) newRoots.push(n.task_id)
  }
  taskNodes.value = newNodes
  rootTaskIds.value = newRoots
}

function reset() {
  displayMode.value = 'none'
  legacyPlan.value = null
  legacyActivePhase.value = null
  legacyCompletedPhases.value = []
  taskNodes.value = {}
  rootTaskIds.value = []
  activeTab.value = 'tasks'
  outputFiles.value = []
  selectedFiles.value = new Set()
}

// ─── Downloads helpers ────────────────────────────────────────────────────────

const allSelected = computed(() => {
  return outputFiles.value.length > 0 && selectedFiles.value.size === outputFiles.value.length
})

function toggleFile(name) {
  const next = new Set(selectedFiles.value)
  if (next.has(name)) {
    next.delete(name)
  } else {
    next.add(name)
  }
  selectedFiles.value = next
}

function toggleAll(event) {
  if (event.target.checked) {
    selectedFiles.value = new Set(outputFiles.value.map(f => f.name))
  } else {
    selectedFiles.value = new Set()
  }
}

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadOutputFiles() {
  if (!props.conversationId) return
  loadingFiles.value = true
  try {
    const res = await api.get(`/conversations/${props.conversationId}/outputs`)
    outputFiles.value = res.data ?? []
  } catch (e) {
    console.warn('加载输出文件失败:', e)
    outputFiles.value = []
  } finally {
    loadingFiles.value = false
  }
}

function switchToDownloads() {
  activeTab.value = 'downloads'
  loadOutputFiles()
}

async function loadTaskTree() {
  if (!props.conversationId) return
  loadingTaskTree.value = true
  try {
    const res = await api.get(`/conversations/${props.conversationId}/task-tree`)
    const nodes = res.data?.nodes ?? []
    if (nodes.length > 0) {
      displayMode.value = 'tree'
      rebuildFromSnapshot(nodes)
    }
  } catch (e) {
    console.warn('加载任务树失败:', e)
  } finally {
    loadingTaskTree.value = false
  }
}

function switchToTasks() {
  activeTab.value = 'tasks'
  loadTaskTree()
}

async function downloadSelected() {
  if (!props.conversationId) return
  for (const name of selectedFiles.value) {
    try {
      const url = `/conversations/${props.conversationId}/outputs/${encodeURIComponent(name)}`
      const resp = await api.get(url, { responseType: 'blob' })
      const blob = resp instanceof Blob ? resp : new Blob([resp])
      const objectUrl = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = objectUrl
      link.download = name
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(objectUrl)
    } catch (e) {
      console.warn(`下载 ${name} 失败:`, e)
    }
  }
}

// ─── Legacy phase helpers ────────────────────────────────────────────────────

function isLegacyPhaseCompleted(phase) {
  const num = phase.phase || phase.id
  return legacyCompletedPhases.value.includes(num)
}

function isLegacyPhaseActive(phase) {
  const num = phase.phase || phase.id
  return legacyActivePhase.value === num && !isLegacyPhaseCompleted(phase)
}

function getLegacyPhaseStatusClass(phase) {
  if (isLegacyPhaseCompleted(phase)) return 'status-completed'
  if (isLegacyPhaseActive(phase)) return 'status-active'
  return 'status-pending'
}

// ─── Watch for completion ─────────────────────────────────────────────────────

watch(isAllCompleted, (val) => {
  if (val) isExpanded.value = true
})

// ─── Auto-load downloads when conversation changes ────────────────────────────

watch(() => props.conversationId, (newId) => {
  if (newId) {
    loadOutputFiles()
    loadTaskTree()
  }
}, { immediate: true })

// ─── Expose ──────────────────────────────────────────────────────────────────

defineExpose({
  handleCoordinatorEvent,
  reset,
  isExpanded: computed(() => isExpanded.value),
})
</script>

<style scoped>
/* ══════════ Container ══════════ */
.task-tree-panel {
  position: fixed;
  top: 0;
  right: 0;
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

.task-tree-panel.is-expanded { width: 360px; }
.task-tree-panel.is-collapsed { width: 56px; }

/* ══════════ Expanded content ══════════ */
.panel-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
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

.panel-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #1a1a1a);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.panel-progress {
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

/* ══════════ Tab bar ══════════ */
.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--border-color, #e5e5e5);
  background: var(--main-bg, #ffffff);
  flex-shrink: 0;
}

.tab-btn {
  flex: 1;
  padding: 8px 0;
  border: none;
  background: transparent;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary, #666);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn.active {
  color: var(--send-btn, #615ced);
  border-bottom-color: var(--send-btn, #615ced);
}

.tab-btn:hover:not(.active) {
  color: var(--text-primary, #1a1a1a);
  background: rgba(0, 0, 0, 0.03);
}

/* ══════════ Downloads panel ══════════ */
.download-loading,
.download-empty {
  text-align: center;
  padding: 32px 16px;
  font-size: 13px;
  color: var(--text-secondary, #999);
}

.download-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.select-all-label {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--main-bg, #fff);
  border: 1px solid var(--border-color, #e5e5e5);
  font-size: 12px;
  color: var(--text-secondary, #666);
  cursor: pointer;
}

.select-all-label input[type="checkbox"] {
  cursor: pointer;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--main-bg, #fff);
  border: 1px solid var(--border-color, #e5e5e5);
}

.file-item input[type="checkbox"] {
  flex-shrink: 0;
  cursor: pointer;
}

.file-item-name {
  flex: 1;
  font-size: 12px;
  color: var(--text-primary, #1a1a1a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: monospace;
}

.file-item-size {
  font-size: 11px;
  color: var(--text-secondary, #999);
  flex-shrink: 0;
}

.download-btn {
  margin-top: 4px;
  padding: 8px 16px;
  border: none;
  border-radius: 8px;
  background: var(--send-btn, #615ced);
  color: white;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s, opacity 0.2s;
}

.download-btn:hover:not(:disabled) {
  background: var(--send-btn-hover, #4f4bcc);
}

.download-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ══════════ Scroll area ══════════ */
.scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
}

.scroll-area::-webkit-scrollbar { width: 4px; }
.scroll-area::-webkit-scrollbar-track { background: transparent; }
.scroll-area::-webkit-scrollbar-thumb {
  background: var(--border-color, #e5e5e5);
  border-radius: 2px;
}

/* ══════════ Task tree nodes ══════════ */
.tree-container {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

/* Individual node */
.task-node {
  border-radius: 8px;
  overflow: hidden;
}

:deep(.node-row) {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--main-bg, #ffffff);
  border: 1px solid var(--border-color, #e5e5e5);
  transition: background 0.15s;
}

.node-pending :deep(.node-row) { border-left: 3px solid var(--border-color, #e5e5e5); }
.node-running :deep(.node-row) { border-left: 3px solid #409eff; background: rgba(64, 158, 255, 0.04); }
.node-completed :deep(.node-row) { border-left: 3px solid #67c23a; }
.node-failed :deep(.node-row) { border-left: 3px solid #f56c6c; background: rgba(245, 108, 108, 0.04); }

:deep(.node-status-icon) {
  display: flex;
  align-items: flex-start;
  padding-top: 2px;
  flex-shrink: 0;
  width: 18px;
}

:deep(.icon-completed) { color: #67c23a; font-weight: 700; font-size: 13px; }
:deep(.icon-failed)    { color: #f56c6c; font-weight: 700; font-size: 13px; }
:deep(.icon-pending)   { color: var(--text-secondary, #aaa); font-size: 13px; }

:deep(.icon-running) {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Pulse for running */
:deep(.pulse-ring) {
  display: inline-block;
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { transform: scale(1); opacity: 1; }
  50% { transform: scale(1.4); opacity: 0.5; }
}

:deep(.node-body) { flex: 1; min-width: 0; }

:deep(.node-desc) {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-primary, #1a1a1a);
  line-height: 1.5;
  word-break: break-word;
}

:deep(.node-meta) {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 4px;
}

:deep(.node-worker-badge) {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 10px;
  background: rgba(97, 92, 237, 0.1);
  color: var(--send-btn, #615ced);
  font-weight: 600;
}

:deep(.node-id) {
  font-size: 10px;
  color: var(--text-secondary, #aaa);
  font-family: monospace;
}

:deep(.node-result) {
  font-size: 11px;
  color: var(--text-secondary, #666);
  margin-top: 4px;
  line-height: 1.4;
  max-height: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

:deep(.node-error) {
  font-size: 11px;
  color: #f56c6c;
  margin-top: 4px;
  line-height: 1.4;
}

/* Children indentation */
:deep(.node-children) {
  margin-left: 18px;
  margin-top: 4px;
  padding-left: 10px;
  border-left: 2px solid var(--border-color, #e5e5e5);
  display: flex;
  flex-direction: column;
  gap: 4px;
}

/* ══════════ Empty state ══════════ */
.tasks-empty {
  text-align: center;
  padding: 40px 16px;
  font-size: 13px;
  color: var(--text-secondary, #999);
}

/* ══════════ Collapsed downloads badge ══════════ */
.collapsed-downloads {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.collapsed-dl-count {
  font-size: 16px;
  font-weight: 700;
  color: var(--send-btn, #615ced);
  line-height: 1;
}

/* ══════════ Legacy phase styles (reused from CoordinatorPlanCard) ══════════ */
.phases-container { display: flex; flex-direction: column; gap: 0; }

.phase-item {
  display: flex;
  gap: 12px;
  padding: 12px 0;
}

.phase-item.status-active {
  background: rgba(64, 158, 255, 0.06);
  margin: 0 -16px;
  padding: 12px 16px;
  border-radius: 8px;
}

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

.status-icon.pending { color: var(--text-secondary, #999); font-size: 16px; }
.status-icon.active  { color: #409eff; position: relative; }
.status-icon.completed { color: #67c23a; font-size: 16px; }

.timeline-line {
  width: 2px;
  flex: 1;
  min-height: 20px;
  background: var(--border-color, #e5e5e5);
  margin: 4px 0;
}

.phase-content { flex: 1; min-width: 0; padding-bottom: 8px; }

.phase-header-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.phase-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary, #666);
  background: var(--main-bg, #fff);
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

.is-strikethrough { text-decoration: line-through; color: var(--text-secondary, #999); }

.workers-list { display: flex; flex-direction: column; gap: 4px; margin-top: 4px; }

.worker-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-secondary, #666);
}

.worker-icon { font-size: 12px; color: var(--send-btn, #615ced); }
.worker-name { font-weight: 500; }

/* ══════════ Completion banner ══════════ */
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

.completion-icon { font-size: 18px; }

/* ══════════ Collapsed state ══════════ */
.panel-collapsed {
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

.panel-collapsed:hover { background: var(--border-color, #e5e5e5); }

.collapsed-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.collapsed-icon { font-size: 20px; color: var(--send-btn, #615ced); }

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

.collapsed-label { font-size: 10px; color: var(--text-secondary, #666); }

.expand-arrow {
  font-size: 14px;
  color: var(--text-secondary, #666);
  animation: bounce-left 1.5s infinite;
}

@keyframes bounce-left {
  0%, 100% { transform: translateX(0); }
  50% { transform: translateX(-3px); }
}

/* ══════════ Dark mode ══════════ */
:global(.dark) .task-tree-panel {
  background: #1d1d1f;
  border-left-color: #3a3a3a;
}

:global(.dark) .panel-header {
  background: #232326;
  border-bottom-color: #3a3a3a;
}

:global(.dark) .node-row {
  background: #2a2a2c;
  border-color: #3a3a3a;
}

:global(.dark) .panel-collapsed:hover { background: #3a3a3a; }

/* ══════════ Responsive ══════════ */
@media (max-width: 768px) {
  .task-tree-panel.is-expanded {
    width: 100%;
    height: 50vh;
    top: auto;
    bottom: 80px;
    border-left: none;
    border-top: 1px solid var(--border-color, #e5e5e5);
    box-shadow: 0 -2px 8px rgba(0, 0, 0, 0.08);
  }

  .task-tree-panel.is-collapsed {
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
