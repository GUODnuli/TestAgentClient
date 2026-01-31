<template>
  <div class="tool-call-card" :class="statusClass">
    <div class="tool-header" @click="toggleExpanded">
      <div class="tool-icon">
        <span v-if="status === 'running'" class="icon-spin">&#9881;</span>
        <span v-else-if="status === 'success'" class="icon-success">&#10003;</span>
        <span v-else-if="status === 'error'" class="icon-error">&#10007;</span>
        <span v-else class="icon-pending">&#9881;</span>
      </div>
      <span class="tool-name">{{ tool.name }}</span>
      <span class="tool-status-label">{{ statusLabel }}</span>
      <span class="expand-arrow" :class="{ rotated: expanded }">&#9654;</span>
    </div>

    <div v-if="expanded" class="tool-body">
      <div class="tool-section">
        <div class="section-label">输入参数</div>
        <pre class="section-content">{{ formattedInput }}</pre>
      </div>

      <div v-if="result" class="tool-section">
        <div class="section-label">执行结果</div>
        <pre class="section-content result-content">{{ truncatedOutput }}</pre>
        <button
          v-if="isOutputTruncated"
          class="show-more-btn"
          @click.stop="showFullOutput = !showFullOutput"
        >
          {{ showFullOutput ? '收起' : '展开全部' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  tool: {
    type: Object,
    required: true,
  },
  result: {
    type: Object,
    default: null,
  },
})

const expanded = ref(false)
const showFullOutput = ref(false)

const OUTPUT_TRUNCATE_LENGTH = 500

const status = computed(() => {
  if (!props.result) return 'running'
  return props.result.success ? 'success' : 'error'
})

const statusClass = computed(() => `status-${status.value}`)

const statusLabel = computed(() => {
  switch (status.value) {
    case 'running': return '运行中'
    case 'success': return '完成'
    case 'error': return '失败'
    default: return ''
  }
})

const formattedInput = computed(() => {
  const input = props.tool.input
  if (typeof input === 'string') return input
  try {
    return JSON.stringify(input, null, 2)
  } catch {
    return String(input)
  }
})

const isOutputTruncated = computed(() => {
  if (!props.result) return false
  return (props.result.output?.length ?? 0) > OUTPUT_TRUNCATE_LENGTH
})

const truncatedOutput = computed(() => {
  if (!props.result) return ''
  const output = props.result.output ?? ''
  if (showFullOutput.value || output.length <= OUTPUT_TRUNCATE_LENGTH) {
    return output
  }
  return output.slice(0, OUTPUT_TRUNCATE_LENGTH) + '...'
})

const toggleExpanded = () => {
  expanded.value = !expanded.value
}
</script>

<style scoped>
.tool-call-card {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  margin: 8px 0;
  overflow: hidden;
  background: var(--input-bg);
  font-size: 13px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
}

.tool-header:hover {
  background: rgba(128, 128, 128, 0.1);
}

.tool-icon {
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
}

.icon-spin {
  animation: spin 1.5s linear infinite;
  color: #409eff;
}

.icon-success {
  color: #67c23a;
  font-weight: bold;
}

.icon-error {
  color: #f56c6c;
  font-weight: bold;
}

.icon-pending {
  color: #909399;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.tool-name {
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
}

.tool-status-label {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 500;
}

.status-running .tool-status-label {
  background: rgba(64, 158, 255, 0.15);
  color: #409eff;
}

.status-success .tool-status-label {
  background: rgba(103, 194, 58, 0.15);
  color: #67c23a;
}

.status-error .tool-status-label {
  background: rgba(245, 108, 108, 0.15);
  color: #f56c6c;
}

.expand-arrow {
  font-size: 10px;
  color: var(--text-secondary);
  transition: transform 0.2s;
}

.expand-arrow.rotated {
  transform: rotate(90deg);
}

.tool-body {
  border-top: 1px solid var(--border-color);
  padding: 8px 12px;
}

.tool-section {
  margin-bottom: 8px;
}

.tool-section:last-child {
  margin-bottom: 0;
}

.section-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 4px;
  font-weight: 500;
}

.section-content {
  margin: 0;
  padding: 8px;
  background: var(--main-bg);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 12px;
  line-height: 1.5;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-all;
  color: var(--text-primary);
  font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
}

.show-more-btn {
  margin-top: 4px;
  padding: 2px 8px;
  font-size: 11px;
  border: none;
  background: transparent;
  color: #409eff;
  cursor: pointer;
  border-radius: 4px;
}

.show-more-btn:hover {
  background: rgba(64, 158, 255, 0.1);
}
</style>
