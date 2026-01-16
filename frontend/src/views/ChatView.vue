<template>
  <div class="chat-page" :class="{ 'has-messages': hasMessages }">
    <!-- 无对话时的居中布局 -->
    <div v-if="!hasMessages" class="empty-state">
      <h1 class="welcome-title">我现在能怎么帮您？</h1>
      
      <!-- 输入框容器 -->
      <div class="prompt-input-container">
        <div class="prompt-input-file-list" v-if="attachedFiles.length > 0">
          <div 
            v-for="(file, index) in attachedFiles" 
            :key="index" 
            class="file-item"
          >
            <span class="file-name">{{ file.name }}</span>
            <button class="file-remove" @click="removeFile(index)">×</button>
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
          <button class="action-btn add-btn" @click="handleAddClick" title="添加附件">
            <el-icon><Plus /></el-icon>
          </button>
          <div class="spacer"></div>
          <button 
            class="action-btn send-btn" 
            @click="sendMessage" 
            :disabled="!inputMessage.trim() || loading"
            title="发送消息"
          >
            <el-icon><Top /></el-icon>
          </button>
        </div>
      </div>
    </div>

    <!-- 有对话时的布局 -->
    <template v-else>
      <!-- 对话消息区域 -->
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
              <template v-if="msg.content">{{ msg.content }}</template>
              <span v-if="loading && msg.role === 'assistant' && index === messages.length - 1" class="typing-cursor"></span>
            </div>
          </div>
        </div>
        
        <!-- 加载中指示器（仅当最后一条助手消息为空时显示） -->
        <div v-if="loading && messages.length > 0 && messages[messages.length - 1].role === 'assistant' && !messages[messages.length - 1].content" class="message assistant">
          <div class="message-content">
            <div class="message-avatar">A</div>
            <div class="message-text loading-dots">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部输入框容器 -->
      <div class="bottom-input-wrapper">
        <div class="prompt-input-container">
          <div class="prompt-input-file-list" v-if="attachedFiles.length > 0">
            <div 
              v-for="(file, index) in attachedFiles" 
              :key="index" 
              class="file-item"
            >
              <span class="file-name">{{ file.name }}</span>
              <button class="file-remove" @click="removeFile(index)">×</button>
            </div>
          </div>

          <div class="prompt-input-input-area">
            <textarea
              ref="inputTextareaBottom"
              v-model="inputMessage"
              placeholder="有什么我能帮您的吗？"
              @input="adjustTextareaHeight"
              @keydown="handleKeydown"
              rows="1"
            ></textarea>
          </div>

          <div class="prompt-input-action-bar">
            <button class="action-btn add-btn" @click="handleAddClick" title="添加附件">
              <el-icon><Plus /></el-icon>
            </button>
            <div class="spacer"></div>
            <button 
              class="action-btn send-btn" 
              @click="sendMessage" 
              :disabled="!inputMessage.trim() || loading"
              title="发送消息"
            >
              <el-icon><Top /></el-icon>
            </button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/api'

// 消息列表
const messages = ref([])

// 输入消息
const inputMessage = ref('')

// 加载状态
const loading = ref(false)

// 附件文件列表（预留功能）
const attachedFiles = ref([])

// DOM引用
const inputTextarea = ref(null)
const inputTextareaBottom = ref(null)
const messagesContainer = ref(null)

// 会话ID
const conversationId = ref(null)

// 是否有消息
const hasMessages = computed(() => messages.value.length > 0)

// 调整textarea高度
const adjustTextareaHeight = () => {
  const textarea = inputTextarea.value || inputTextareaBottom.value
  if (!textarea) return
  
  // 重置高度以获取正确的scrollHeight
  textarea.style.height = 'auto'
  
  // 计算新高度，限制最大高度
  const minHeight = 24  // 单行最小高度
  const maxHeight = 160 // 最大高度
  const newHeight = Math.min(Math.max(textarea.scrollHeight, minHeight), maxHeight)
  
  textarea.style.height = `${newHeight}px`
}

// 处理键盘事件
const handleKeydown = (event) => {
  // Enter发送，Shift+Enter换行
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    sendMessage()
  }
}

// 发送消息（使用 SSE 流式响应）
const sendMessage = async () => {
  const message = inputMessage.value.trim()
  if (!message || loading.value) return

  console.log('[ChatView] 发送消息:', message)

  // 添加用户消息到列表
  messages.value.push({
    role: 'user',
    content: message
  })

  // 清空输入框
  inputMessage.value = ''
  nextTick(() => {
    adjustTextareaHeight()
    scrollToBottom()
  })

  // 添加助手消息占位（用于流式更新）
  const assistantMessageIndex = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: ''
  })

  // 发送请求
  loading.value = true
  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        message: message,
        conversation_id: conversationId.value
      })
    })

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      
      if (done) {
        console.log('[ChatView] SSE 流结束')
        break
      }

      buffer += decoder.decode(value, { stream: true })
      
      // 解析 SSE 事件
      const lines = buffer.split('\n')
      buffer = lines.pop() || '' // 保留最后一个不完整的行
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const dataStr = line.slice(6)
          try {
            const data = JSON.parse(dataStr)
            console.log('[ChatView] SSE 事件:', data.type, data)
            
            if (data.type === 'start') {
              // 更新会话ID
              if (data.conversation_id) {
                conversationId.value = data.conversation_id
              }
            } else if (data.type === 'chunk') {
              // 追加文本块
              messages.value[assistantMessageIndex].content += data.content
              nextTick(scrollToBottom)
            } else if (data.type === 'done') {
              // 完成
              console.log('[ChatView] 流式响应完成')
            } else if (data.type === 'error') {
              ElMessage.error(data.message || '生成失败')
            }
          } catch (e) {
            console.warn('[ChatView] 解析 SSE 数据失败:', dataStr)
          }
        }
      }
    }

    // 检查是否有内容
    if (!messages.value[assistantMessageIndex].content) {
      messages.value[assistantMessageIndex].content = '抱歉，无法生成回复。'
    }

  } catch (error) {
    console.error('[ChatView] 发送消息失败:', error)
    ElMessage.error('发送消息失败: ' + (error.message || '网络错误'))
    // 更新错误消息
    messages.value[assistantMessageIndex].content = '抱歉，发生错误：' + (error.message || '网络错误')
  } finally {
    loading.value = false
    nextTick(scrollToBottom)
  }
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

// 添加按钮点击（功能置空）
const handleAddClick = () => {
  console.log('[ChatView] 添加按钮点击 - 功能待实现')
  ElMessage.info('附件功能开发中...')
}

// 移除附件
const removeFile = (index) => {
  attachedFiles.value.splice(index, 1)
}

// 监听消息变化，自动滚动
watch(messages, () => {
  nextTick(scrollToBottom)
}, { deep: true })

// 组件挂载
onMounted(() => {
  // 聚焦输入框
  if (inputTextarea.value) {
    inputTextarea.value.focus()
  }
})
</script>

<style scoped>
.chat-page {
  width: 100%;
  height: 100%;
  background: var(--main-bg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: background-color 0.3s;
}

/* ==================== 无对话时的居中布局 ==================== */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 20px;
  overflow: hidden;
}

.welcome-title {
  color: var(--text-primary);
  font-size: 28px;
  font-weight: 500;
  margin-bottom: 32px;
  text-align: center;
  transition: color 0.3s;
}

/* ==================== 有对话时的布局 ==================== */
.chat-page.has-messages {
  justify-content: flex-start;
}

/* 消息区域 */
.chat-messages {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
}

.message {
  display: flex;
}

.message-content {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  max-width: 100%;
}

.message-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 13px;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: var(--send-btn);
  color: white;
}

.message.assistant .message-avatar {
  background: var(--input-bg);
  color: var(--send-btn);
  transition: background-color 0.3s;
}

.message-text {
  flex: 1;
  padding: 0;
  line-height: 1.7;
  word-break: break-word;
  white-space: pre-wrap;
  color: var(--text-primary);
  font-size: 15px;
  transition: color 0.3s;
}

/* 加载动画 */
.loading-dots {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background: var(--send-btn);
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }
.loading-dots span:nth-child(3) { animation-delay: 0s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

/* 打字光标 */
.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 1.2em;
  background: var(--send-btn);
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 底部输入框包装器 */
.bottom-input-wrapper {
  padding: 20px;
  display: flex;
  justify-content: center;
  background: var(--main-bg);
  flex-shrink: 0;
  transition: background-color 0.3s;
}

/* ==================== 输入框容器（共用样式） ==================== */
.prompt-input-container {
  width: 100%;
  max-width: 800px;
  background: var(--input-bg);
  border-radius: 24px;
  border: 1px solid var(--border-color);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: border-color 0.2s, box-shadow 0.2s, background-color 0.3s;
}

.prompt-input-container:focus-within {
  border-color: var(--send-btn);
  box-shadow: 0 0 0 2px rgba(97, 92, 237, 0.15);
}

/* 文件列表区域 */
.prompt-input-file-list {
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: var(--border-color);
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 12px;
  color: var(--text-primary);
}

.file-name {
  max-width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-remove {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 0;
  font-size: 16px;
  line-height: 1;
}

.file-remove:hover {
  color: #ff4d4f;
}

/* 输入区域 */
.prompt-input-input-area {
  padding: 16px 20px 8px;
}

.prompt-input-input-area textarea {
  width: 100%;
  min-height: 24px;
  max-height: 160px;
  background: transparent;
  border: none;
  outline: none;
  color: var(--text-primary);
  font-size: 16px;
  line-height: 1.5;
  resize: none;
  font-family: inherit;
  transition: color 0.3s;
}

.prompt-input-input-area textarea::placeholder {
  color: var(--text-secondary);
}

/* 操作栏 */
.prompt-input-action-bar {
  display: flex;
  align-items: center;
  padding: 8px 12px 12px;
  gap: 8px;
}

.spacer {
  flex: 1;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
}

.add-btn {
  background: transparent;
  color: var(--text-secondary);
}

.add-btn:hover {
  background: var(--border-color);
  color: var(--text-primary);
}

.send-btn {
  background: var(--send-btn);
  color: white;
}

.send-btn:hover:not(:disabled) {
  background: var(--send-btn-hover);
}

.send-btn:disabled {
  background: var(--border-color);
  color: var(--text-secondary);
  cursor: not-allowed;
}

/* 滚动条样式 */
.chat-messages::-webkit-scrollbar {
  width: 6px;
}

.chat-messages::-webkit-scrollbar-track {
  background: transparent;
}

.chat-messages::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 3px;
}

.chat-messages::-webkit-scrollbar-thumb:hover {
  background: var(--text-secondary);
}
</style>
