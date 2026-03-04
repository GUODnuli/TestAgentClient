<template>
  <div class="chat-container-root">
    <!-- 右侧聊天区域 -->
    <main class="chat-main">
      <div class="chat-container" :class="{ 'has-messages': hasMessages }">
        <!-- 无对话时的居中布局 -->
        <div v-if="!hasMessages" class="empty-state">
          <h1 class="welcome-title">我现在能怎么帮您？</h1>
          
          <div class="prompt-input-container">
            <!-- 文件预览区 -->
            <div v-if="selectedFiles.length > 0" class="file-preview-list">
              <div
                v-for="(file, idx) in selectedFiles"
                :key="idx"
                class="file-preview-tab"
              >
                <div class="file-info">
                  <el-icon><Document /></el-icon>
                  <span class="file-name">{{ file.name }}</span>
                </div>
                <button class="cancel-file-btn" @click="cancelFile(idx)">
                  <el-icon><Close /></el-icon>
                </button>
              </div>
            </div>

            <div class="prompt-input-input-area">
              <textarea
                ref="inputTextarea"
                v-model="inputMessage"
                placeholder="有什么我能帮您的吗？"
                @input="adjustTextareaHeight"
                @keydown="handleKeydown"
                rows="1"
              ></textarea>
            </div>

            <div class="prompt-input-action-bar">
              <button 
                class="action-btn upload-btn" 
                @click="triggerFileInput"
                title="上传文件"
              >
                <el-icon><Paperclip /></el-icon>
              </button>
              <div class="spacer"></div>
              <button
                class="action-btn send-btn"
                @click="sendMessage"
                :disabled="(!inputMessage.trim() && !selectedFiles.length) || loading"
                title="发送消息"
              >
                <el-icon><Top /></el-icon>
              </button>
            </div>
          </div>
        </div>

        <!-- 有对话时的布局 -->
        <template v-else>
          <div class="chat-messages" ref="messagesContainer">
            <div 
              v-for="(msg, index) in messages" 
              :key="index" 
              :class="['message', msg.role]"
            >
              <div class="message-content">
                <div class="message-avatar">
                  {{ msg.role === 'user' ? 'U' : 'A' }}
                </div>
                <div class="message-text">
                  <template v-if="msg.role === 'user'">{{ msg.content }}</template>
                  <template v-else-if="msg.role === 'assistant'">
                    <!-- 思考过程展示（灰色小号字体） -->
                    <div v-if="msg.thinking" class="thinking-block">
                      <div class="thinking-label">思考过程</div>
                      <div class="thinking-content">{{ msg.thinking }}</div>
                    </div>

                    <!-- 事件驱动渲染（新模型） -->
                    <template v-if="msg.events && msg.events.length > 0">
                      <template v-for="(event, eIdx) in msg.events">
                        <MarkdownViewer
                          v-if="event.type === 'text'"
                          :key="'text-' + eIdx"
                          :content="event.content"
                        />
                        <ToolCallCard
                          v-else-if="event.type === 'tool_call'"
                          :key="'tool-' + eIdx"
                          :tool="event"
                          :result="findToolResult(msg.events, event.id)"
                        />
                        <!-- tool_result events are rendered inside ToolCallCard -->
                      </template>
                    </template>
                    <!-- 兼容旧消息格式（无 events 字段） -->
                    <template v-else>
                      <MarkdownViewer
                        v-if="msg.content"
                        :content="msg.content"
                      />
                    </template>

                    <!-- 测试用例展示 -->
                    <div v-if="msg.testcases && msg.testcases.length > 0" class="testcases-block">
                      <div class="testcases-header">
                        <el-icon><DocumentChecked /></el-icon>
                        <span>测试用例（共 {{ msg.testcases.length }} 个）</span>
                      </div>
                      <el-collapse class="testcases-list">
                        <el-collapse-item
                          v-for="(testcase, idx) in msg.testcases"
                          :key="testcase.id || idx"
                          :name="idx"
                        >
                          <template #title>
                            <div class="testcase-title">
                              <el-tag :type="testcase.tags?.includes('security') ? 'danger' : testcase.tags?.includes('negative') ? 'warning' : 'success'" size="small">
                                {{ testcase.tags?.[0] || 'test' }}
                              </el-tag>
                              <span>{{ testcase.interface_name || testcase.description || `测试用例 #${idx + 1}` }}</span>
                            </div>
                          </template>
                          <div class="testcase-details">
                            <div class="detail-row">
                              <strong>接口路径:</strong> {{ testcase.interface_path || testcase.request?.url }}
                            </div>
                            <div class="detail-row">
                              <strong>请求方法:</strong> {{ testcase.request?.method || 'POST' }}
                            </div>
                            <div v-if="testcase.request?.body" class="detail-row">
                              <strong>请求参数:</strong>
                              <pre>{{ JSON.stringify(testcase.request.body, null, 2) }}</pre>
                            </div>
                            <div v-if="testcase.assertions?.length" class="detail-row">
                              <strong>断言:</strong>
                              <ul>
                                <li v-for="(assertion, aIdx) in testcase.assertions" :key="aIdx">
                                  {{ assertion.description || `${assertion.type}: ${assertion.expected}` }}
                                </li>
                              </ul>
                            </div>
                            <div v-if="testcase.description" class="detail-row">
                              <strong>说明:</strong> {{ testcase.description }}
                            </div>
                          </div>
                        </el-collapse-item>
                      </el-collapse>
                    </div>
                    <div v-else-if="loading && index === messages.length - 1 && !msg.events?.length && !msg.content" class="loading-dots">
                      <span></span><span></span><span></span>
                    </div>
                  </template>
                  <span v-if="loading && msg.role === 'assistant' && index === messages.length - 1 && (msg.content || msg.events?.length)" class="typing-cursor"></span>
                </div>
              </div>
            </div>
          </div>

          <!-- 计划步骤展示组件 -->
          <PlanStepBar :planData="currentPlanData" />
          
          <!-- 任务树/执行计划面板 (浮动在右侧，支持旧 phase 模式和新任务树模式) -->
          <TaskTreePanel ref="taskTreePanel" :conversation-id="currentConversationId" />

          <div class="bottom-input-wrapper">
            <div class="bottom-input-container">
              <!-- 文件预览区 -->
              <div v-if="selectedFiles.length > 0" class="file-preview-list">
                <div
                  v-for="(file, idx) in selectedFiles"
                  :key="idx"
                  class="file-preview-tab"
                >
                  <div class="file-info">
                    <el-icon><Document /></el-icon>
                    <span class="file-name">{{ file.name }}</span>
                  </div>
                  <button class="cancel-file-btn" @click="cancelFile(idx)">
                    <el-icon><Close /></el-icon>
                  </button>
                </div>
              </div>

              <div class="prompt-input-input-area">
                <textarea
                  ref="bottomInputTextarea"
                  v-model="inputMessage"
                  placeholder="输入消息..."
                  @input="adjustBottomTextareaHeight"
                  @keydown="handleKeydown"
                  rows="1"
                ></textarea>
              </div>

              <div class="prompt-input-action-bar">
                <button 
                  class="action-btn upload-btn" 
                  @click="triggerFileInput"
                  title="上传文件"
                >
                  <el-icon><Paperclip /></el-icon>
                </button>
                <div class="spacer"></div>
                <!-- 发送/终止按钮 -->
                <button
                  v-if="!loading || !currentReplyId"
                  class="action-btn send-btn"
                  @click="sendMessage"
                  :disabled="(!inputMessage.trim() && !selectedFiles.length) || loading"
                  title="发送消息"
                >
                  <el-icon><Top /></el-icon>
                </button>
                <button 
                  v-else
                  class="action-btn stop-btn" 
                  @click="stopAgent" 
                  title="终止生成"
                >
                  <el-icon><Close /></el-icon>
                </button>
              </div>
            </div>
          </div>
        </template>
      </div>
    </main>

    <!-- 隐藏的文件上传 input -->
    <input
      type="file"
      ref="fileInput"
      style="display: none"
      multiple
      @change="onFileSelected"
    />
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import api from '@/api'
import { useChatStore } from '@/stores/chat'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import PlanStepBar from '@/components/PlanStepBar.vue'
import TaskTreePanel from '@/components/TaskTreePanel.vue'
import ToolCallCard from '@/components/ToolCallCard.vue'
import { SSEParser } from '@/utils/sse-parser.js'

const chatStore = useChatStore()
const { 
  conversations, 
  currentConversationId, 
  messages, 
  loading 
} = storeToRefs(chatStore)
const { loadConversations, startNewChat } = chatStore

const inputMessage = ref('')

// 当前正在执行的 reply_id，用于终止
const currentReplyId = ref(null)

const selectedFiles = ref([])
const fileInput = ref(null)

const inputTextarea = ref(null)
const bottomInputTextarea = ref(null)
const messagesContainer = ref(null)

const currentPlanData = ref(null)

// TaskTreePanel 组件引用（替代旧的独立状态变量）
const taskTreePanel = ref(null)

const hasMessages = computed(() => messages.value.length > 0)

// 标志位，防止发送消息时触发的 ID 变化导致重复加载
const isSending = ref(false)

// 监听当前对话变化，加载消息和计划
watch(currentConversationId, async (newId) => {
  if (isSending.value) return // 如果正在发送中，不触发自动加载，避免覆盖本地正在生成的流

  // 重置 TaskTreePanel 状态
  taskTreePanel.value?.reset()

  if (newId) {
    try {
      // 并行加载消息和计划
      const [messagesData, planData] = await Promise.all([
        api.listMessages(newId, { limit: 1000 }),
        api.getConversationPlan(newId).catch(() => null) // 计划可能不存在
      ])

      // 加载消息（从 metadata 恢复 events）
      messages.value = messagesData.map(msg => {
        const baseMsg = {
          role: msg.role,
          content: msg.content
        }
        // 如果是 assistant 消息且有 metadata.events，恢复 events
        if (msg.role === 'assistant' && msg.metadata?.events) {
          baseMsg.events = msg.metadata.events
        }
        return baseMsg
      })

      // 恢复任务树状态：从消息历史中重播 coordinator_event 事件
      for (const msg of messages.value) {
        if (msg.role === 'assistant' && msg.events) {
          for (const event of msg.events) {
            if (event.type === 'coordinator_event') {
              taskTreePanel.value?.handleCoordinatorEvent(event.event_type, event.data)
            }
          }
        }
      }

      // 加载计划（如果存在，恢复到旧 phase 模式）
      if (planData) {
        taskTreePanel.value?.handleCoordinatorEvent('plan_created', { plan: planData.plan })
        if (planData.activePhase) {
          taskTreePanel.value?.handleCoordinatorEvent('phase_started', { phase: planData.activePhase })
        }
        for (const p of planData.completedPhases || []) {
          taskTreePanel.value?.handleCoordinatorEvent('phase_completed', { phase: p })
        }
      }

      await nextTick()
      scrollToBottom(true)
    } catch (error) {
      console.error('加载对话消息失败:', error)
    }
  } else {
    messages.value = []
  }
}, { immediate: true })

/**
 * Find tool_result event matching a tool_call by id.
 * Used in template for ToolCallCard rendering.
 */
const findToolResult = (events, toolId) => {
  if (!events || !toolId) return null
  return events.find(e => e.type === 'tool_result' && e.id === toolId) || null
}

/**
 * Merge adjacent text events in the events array to reduce DOM nodes.
 * Modifies the array in-place for performance during streaming.
 */
const mergeAdjacentTextEvents = (events) => {
  if (events.length < 2) return
  const last = events[events.length - 1]
  const secondLast = events[events.length - 2]
  if (last.type === 'text' && secondLast.type === 'text') {
    events.splice(events.length - 2, 2, {
      type: 'text',
      content: secondLast.content + last.content,
    })
  }
}

/**
 * Handle Coordinator events — delegates to TaskTreePanel component.
 * Supports both legacy phase events and new task_tree_* events.
 */
const handleCoordinatorEvent = (eventType, data) => {
  if (!eventType || !data) return
  taskTreePanel.value?.handleCoordinatorEvent(eventType, data)
}

// 发送消息
const sendMessage = async () => {
  if ((!inputMessage.value.trim() && !selectedFiles.value.length) || loading.value) return

  isSending.value = true
  let userMessage = inputMessage.value.trim()
  const currentFiles = [...selectedFiles.value]

  inputMessage.value = ''
  selectedFiles.value = []
  resetTextareaHeight()

  try {
    // 处理文件上传
    let fileInfoString = ''
    if (currentFiles.length > 0) {
      // 如果没有会话ID，先创建一个，否则上传会失败
      if (!currentConversationId.value) {
        try {
          const newConv = await api.createConversation({
            title: userMessage.substring(0, 50) || currentFiles[0].name
          })
          currentConversationId.value = newConv.conversation_id
          await loadConversations()
        } catch (err) {
          console.error('创建会话失败:', err)
          throw new Error('无法开始新对话并上传文件')
        }
      }

      const uploadedNames = []
      const failedNames = []
      for (const file of currentFiles) {
        try {
          const uploadRes = await api.uploadChatFile(currentConversationId.value, file)
          if (uploadRes.success) {
            uploadedNames.push(file.name)
          } else {
            failedNames.push(file.name)
          }
        } catch (err) {
          console.error(`文件上传失败: ${file.name}`, err)
          failedNames.push(file.name)
        }
      }
      if (uploadedNames.length > 0) {
        fileInfoString += `\n\n[文件已上传: ${uploadedNames.join(', ')}]`
      }
      if (failedNames.length > 0) {
        fileInfoString += `\n\n[文件上传失败: ${failedNames.join(', ')}]`
      }
    }

    const finalMessage = userMessage + fileInfoString

    // 添加用户消息
    messages.value.push({
      role: 'user',
      content: finalMessage
    })

    await nextTick()
    scrollToBottom(true)

    loading.value = true

    // 添加空的助手消息占位（使用 events 数组模型）
    const assistantMsgIndex = messages.value.length
    messages.value.push({
      role: 'assistant',
      content: '',
      thinking: '',
      events: [],
    })

    // 调用聊天接口(SSE流式)
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      },
      body: JSON.stringify({
        message: finalMessage,
        conversation_id: currentConversationId.value || undefined
      })
    })

    if (!response.ok) {
      throw new Error('请求失败')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let thinkingResponse = ''

    // 使用缓冲式 SSE 解析器，修复 chunk 边界切断问题
    const parser = new SSEParser(({ data: parsed }) => {
      try {
        if (typeof parsed !== 'object' || parsed === null) return
        const msg = messages.value[assistantMsgIndex]

        if (parsed.type === 'start') {
          if (!currentConversationId.value) {
            currentConversationId.value = parsed.conversation_id
            loadConversations()
          }
          if (parsed.reply_id) {
            currentReplyId.value = parsed.reply_id
          }
        } else if (parsed.type === 'plan_update' && parsed.data) {
          currentPlanData.value = parsed.data
        } else if (parsed.type === 'testcases' && parsed.data) {
          const testcasesData = parsed.data
          if (!msg.testcases) {
            msg.testcases = []
          }
          msg.testcases.push(...testcasesData.testcases)
        } else if (parsed.type === 'thinking' && parsed.content) {
          thinkingResponse += parsed.content
          msg.thinking = thinkingResponse
        } else if (parsed.type === 'chunk' && parsed.content) {
          // Text chunk — add as text event
          msg.events.push({ type: 'text', content: parsed.content })
          mergeAdjacentTextEvents(msg.events)
          // Also maintain flat content for DB compatibility
          msg.content = (msg.content || '') + parsed.content
        } else if (parsed.type === 'tool_call') {
          // 按 ID 去重，防止流式累积消息导致同一工具调用多次渲染
          if (!parsed.id || !msg.events.some(e => e.type === 'tool_call' && e.id === parsed.id)) {
            msg.events.push({
              type: 'tool_call',
              id: parsed.id,
              name: parsed.name,
              input: parsed.input,
            })
          }
        } else if (parsed.type === 'tool_result') {
          // 按 ID 去重
          if (!parsed.id || !msg.events.some(e => e.type === 'tool_result' && e.id === parsed.id)) {
            msg.events.push({
              type: 'tool_result',
              id: parsed.id,
              name: parsed.name,
              output: parsed.output,
              success: parsed.success,
            })
          }
        } else if (parsed.type === 'title_generated') {
          chatStore.updateConversationTitle(parsed.conversation_id, parsed.title)
        } else if (parsed.type === 'coordinator_event' && parsed.data) {
          // 处理 Coordinator 事件
          handleCoordinatorEvent(parsed.event_type, parsed.data)
        } else if (parsed.type === 'error') {
          throw new Error(parsed.message || '流式输出错误')
        }
        // done, heartbeat, cancelled — no action needed for rendering
      } catch (e) {
        console.warn('处理SSE事件失败:', e)
      }
    })

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = decoder.decode(value, { stream: true })
      parser.feed(chunk)

      await nextTick()
      scrollToBottom()
    }

    // Flush any remaining buffered data
    parser.flush()
    await nextTick()
    scrollToBottom()

  } catch (error) {
    console.error('发送消息失败:', error)
    if (messages.value.length > 0) {
      const lastMsg = messages.value[messages.value.length - 1]
      if (lastMsg.role === 'assistant') {
        lastMsg.content = `抱歉,发送消息时出现错误: ${error.message}`
        // Clear events so it falls back to content rendering
        lastMsg.events = []
      }
    }
  } finally {
    loading.value = false
    isSending.value = false
    currentReplyId.value = null
  }
}

// 终止 Agent
const stopAgent = async () => {
  if (!currentReplyId.value) return

  try {
    const response = await fetch('/api/chat/interrupt', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      },
      body: JSON.stringify({
        reply_id: currentReplyId.value
      })
    })

    const result = await response.json()
    if (result.success) {
      console.log('Agent 已终止')
      // 添加终止提示
      if (messages.value.length > 0) {
        const lastMsg = messages.value[messages.value.length - 1]
        if (lastMsg.role === 'assistant') {
          lastMsg.content += '\n\n[用户终止了请求]'
        }
      }
    } else {
      console.error('终止失败:', result.message)
    }
  } catch (error) {
    console.error('终止 Agent 失败:', error)
  } finally {
    loading.value = false
    currentReplyId.value = null
  }
}

// 文本框高度调整
const adjustTextareaHeight = () => {
  const textarea = inputTextarea.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = textarea.scrollHeight + 'px'
}

const adjustBottomTextareaHeight = () => {
  const textarea = bottomInputTextarea.value
  if (!textarea) return
  textarea.style.height = 'auto'
  textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
}

const resetTextareaHeight = () => {
  if (inputTextarea.value) {
    inputTextarea.value.style.height = 'auto'
  }
  if (bottomInputTextarea.value) {
    bottomInputTextarea.value.style.height = 'auto'
  }
}

// 文件处理逻辑
const triggerFileInput = () => {
  if (fileInput.value) {
    fileInput.value.click()
  }
}

const onFileSelected = (e) => {
  const files = Array.from(e.target.files)
  const timestamp = new Date().toISOString().replace(/[-:]/g, '').split('.')[0].replace('T', '_')
  const renamed = files.map(file => {
    const namePart = file.name.substring(0, file.name.lastIndexOf('.')) || file.name
    const extension = file.name.includes('.') ? file.name.substring(file.name.lastIndexOf('.')) : ''
    const newFileName = `${namePart}_${timestamp}${extension}`
    return new File([file], newFileName, { type: file.type })
  })
  // 追加到已选文件列表（去重：同名文件以新选的为准）
  const existing = selectedFiles.value.filter(f => !renamed.some(r => r.name === f.name))
  selectedFiles.value = [...existing, ...renamed]
  // 清空 input 使得同一个文件可以重复触发 change
  e.target.value = ''
}

const cancelFile = (idx) => {
  selectedFiles.value = selectedFiles.value.filter((_, i) => i !== idx)
}

// 键盘事件处理
const handleKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    sendMessage()
  }
}

// 滚动到底部（智能模式：用户上滚查看历史时不强制拉回）
const scrollToBottom = (force = false) => {
  if (!messagesContainer.value) return
  if (force) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    return
  }
  const el = messagesContainer.value
  const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  if (distanceFromBottom <= 80) {
    el.scrollTop = el.scrollHeight
  }
}

// 初始化
onMounted(() => {
  loadConversations()
})
</script>

<style scoped>
.chat-container-root {
  width: 100%;
  height: 100%;
  display: flex;
  background: var(--main-bg);
  overflow: hidden;
}

/* ==================== 右侧聊天区域 ==================== */
.chat-main {
  flex: 1;
  height: 100%;
  overflow: hidden;
  width: 100%;
}

.chat-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: var(--main-bg);
  overflow: hidden;
}

.chat-container.has-messages {
  justify-content: flex-start;
}

/* 空状态 */
.empty-state {
  width: 100%;
  max-width: 800px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  padding: 0 24px;
}

.welcome-title {
  font-size: 32px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
  text-align: center;
}

/* 输入框样式 */
.prompt-input-container,
.bottom-input-container {
  width: 100%;
  max-width: 760px;
  background: var(--input-bg);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.prompt-input-input-area {
  width: 100%;
}

.prompt-input-input-area textarea {
  width: 100%;
  min-height: 24px;
  max-height: 200px;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.6;
  resize: none;
  outline: none;
  font-family: inherit;
}

.prompt-input-input-area textarea::placeholder {
  color: var(--text-secondary);
}

.prompt-input-action-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.spacer {
  flex: 1;
}

.action-btn {
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: var(--border-color);
}

.send-btn {
  background: var(--send-btn);
  color: white;
}

.send-btn:hover:not(:disabled) {
  background: var(--send-btn-hover);
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 消息列表 */
.chat-messages {
  flex: 1;
  width: 100%;
  max-width: 800px;
  overflow-y: auto;
  padding: 24px;
  margin: 0 auto;
}

/* 大屏幕优化：2K/2.5K/4K 屏幕增大内容区宽度 */
@media (min-width: 1920px) {
  .chat-messages {
    max-width: 1000px;
  }
}

@media (min-width: 2560px) {
  .chat-messages {
    max-width: 1200px;
  }
}

@media (min-width: 3440px) {
  .chat-messages {
    max-width: 1400px;
  }
}

.message {
  margin-bottom: 24px;
}

.message-content {
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.message-avatar {
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

.message.user .message-avatar {
  background: var(--border-color);
  color: var(--text-primary);
}

.message-text {
  flex: 1;
  min-width: 0;
  overflow-x: hidden;
  color: var(--text-primary);
  font-size: 15px;
  line-height: 1.6;
  word-break: break-word;
  overflow-wrap: anywhere;  /* 增强换行支持 */
}

.message.user .message-text {
  white-space: pre-wrap;
}

/* 思考过程样式 - 灰色小号字体，黑白主题下均为灰色 */
.thinking-block {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(128, 128, 128, 0.1);
  border-radius: 6px;
  border-left: 3px solid #888;
}

.thinking-label {
  font-size: 12px;
  color: #888;
  margin-bottom: 4px;
  font-weight: 500;
}

.thinking-content {
  font-size: 13px;
  color: #888;
  line-height: 1.5;
  white-space: pre-wrap;
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  background: var(--text-primary);
  margin-left: 2px;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.loading-dots {
  display: flex;
  gap: 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--text-secondary);
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) {
  animation-delay: -0.32s;
}

.loading-dots span:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 底部输入框 */
.bottom-input-wrapper {
  width: 100%;
  padding: 16px 24px;
  background: var(--main-bg);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: center;
}

.bottom-input-container {
  max-width: 800px;
}

/* 大屏幕优化 */
@media (min-width: 1920px) {
  .bottom-input-container,
  .prompt-input-container {
    max-width: 1000px;
  }
}

@media (min-width: 2560px) {
  .bottom-input-container,
  .prompt-input-container {
    max-width: 1200px;
  }
}

@media (min-width: 3440px) {
  .bottom-input-container,
  .prompt-input-container {
    max-width: 1400px;
  }
}

/* 文件预览区：多文件换行布局 */
.file-preview-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

/* 文件预览 Tab 样式：自适应宽度，超长文件名截断 */
.file-preview-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--main-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 4px 8px 4px 10px;
  max-width: 240px;
  min-width: 0;
}

.file-info {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
  font-size: 13px;
  flex: 1;
  min-width: 0;
}

.file-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}

.cancel-file-btn {
  background: transparent;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  flex-shrink: 0;
  transition: background 0.2s;
}

.cancel-file-btn:hover {
  background: var(--border-color);
  color: #f56c6c;
}

.upload-btn {
  margin-right: auto;
}

.upload-btn:hover:not(:disabled) {
  background: var(--border-color);
  color: var(--send-btn);
}

/* 测试用例展示样式 */
.testcases-block {
  margin-top: 16px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.testcases-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.testcases-list {
  border: none;
}

.testcase-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  flex: 1;
}

.testcase-details {
  padding: 12px;
  background: var(--bg-primary);
  border-radius: 4px;
  font-size: 13px;
}

.detail-row {
  margin-bottom: 12px;
}

.detail-row:last-child {
  margin-bottom: 0;
}

.detail-row strong {
  color: var(--text-primary);
  margin-right: 8px;
}

.detail-row pre {
  margin-top: 4px;
  padding: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  overflow-x: auto;
  font-size: 12px;
  color: var(--text-secondary);
}

.detail-row ul {
  margin-top: 4px;
  padding-left: 20px;
}

.detail-row li {
  margin-bottom: 4px;
  color: var(--text-secondary);
}

/* 终止按钮样式 */
.stop-btn {
  background: #f56c6c !important;
  color: white !important;
  transition: all 0.2s;
}

.stop-btn:hover:not(:disabled) {
  background: #f78989 !important;
  transform: scale(1.05);
}

.stop-btn:active {
  transform: scale(0.95);
}

/* ==================== Coordinator 侧边栏布局适配 ==================== */
/* 
 * 注意：侧边栏使用 fixed 定位浮动在右侧，不挤压主内容区
 * 主内容区(chat-messages)保持原有宽度和位置不变
 * 用户可以通过收起侧边栏来查看右侧内容
 */
</style>
