<!--
  CoordinatorPlanCard 组件演示
  
  此文件展示了 CoordinatorPlanCard 组件的各种状态和用法。
  可以在开发环境中引入此组件进行预览测试。
-->
<template>
  <div class="demo-container" :class="theme">
    <h2>Coordinator Plan Card 组件演示</h2>
    
    <!-- 主题切换 -->
    <div class="theme-toggle">
      <button @click="theme = 'light'" :class="{ active: theme === 'light' }">☀️ 白天</button>
      <button @click="theme = 'dark'" :class="{ active: theme === 'dark' }">🌙 黑夜</button>
    </div>

    <!-- 状态控制 -->
    <div class="controls">
      <h3>状态控制</h3>
      <button @click="simulatePlanCreated">🚀 创建计划</button>
      <button @click="simulatePhaseStart(1)">▶️ 开始 Phase 1</button>
      <button @click="simulatePhaseComplete(1)">✓ 完成 Phase 1</button>
      <button @click="simulatePhaseStart(2)">▶️ 开始 Phase 2</button>
      <button @click="reset">🔄 重置</button>
    </div>

    <!-- 演示区域 -->
    <div class="demo-area">
      <CoordinatorPlanCard
        :plan="coordinatorPlan"
        :activePhase="activeCoordinatorPhase"
        :completedPhases="completedCoordinatorPhases"
        :phaseOutputs="coordinatorPhaseOutputs"
      />
    </div>

    <!-- 数据结构展示 -->
    <div class="data-preview">
      <h3>当前数据状态</h3>
      <pre>{{ JSON.stringify({
        plan: coordinatorPlan,
        activePhase: activeCoordinatorPhase,
        completedPhases: completedCoordinatorPhases,
        phaseOutputs: coordinatorPhaseOutputs
      }, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import CoordinatorPlanCard from './CoordinatorPlanCard.vue'

const theme = ref('light')

// Coordinator 计划相关状态
const coordinatorPlan = ref(null)
const activeCoordinatorPhase = ref(null)
const completedCoordinatorPhases = ref([])
const coordinatorPhaseOutputs = ref({})

// 模拟计划数据
const mockPlan = {
  task_id: "task-123456",
  objective: "测试 Spring Boot 用户管理接口",
  context: {},
  phases: [
    {
      phase: 1,
      name: "需求分析",
      workers: [
        { worker: "analyzer", task: "分析用户接口需求", input: {}, depends_on: [] }
      ],
      parallel: false,
      depends_on: []
    },
    {
      phase: 2,
      name: "测试计划制定",
      workers: [
        { worker: "planner", task: "制定测试策略", input: {}, depends_on: [] }
      ],
      parallel: false,
      depends_on: ["phase_1"]
    },
    {
      phase: 3,
      name: "测试用例生成",
      workers: [
        { worker: "executor", task: "生成 API 测试用例", input: {}, depends_on: [] }
      ],
      parallel: false,
      depends_on: ["phase_2"]
    },
    {
      phase: 4,
      name: "测试执行",
      workers: [
        { worker: "executor", task: "执行测试用例", input: {}, depends_on: [] }
      ],
      parallel: true,
      depends_on: ["phase_3"]
    },
    {
      phase: 5,
      name: "结果验证与报告",
      workers: [
        { worker: "validator", task: "验证测试结果", input: {}, depends_on: [] },
        { worker: "reporter", task: "生成测试报告", input: {}, depends_on: [] }
      ],
      parallel: true,
      depends_on: ["phase_4"]
    }
  ],
  completion_criteria: "所有测试用例执行完成并生成报告"
}

// 模拟创建计划
function simulatePlanCreated() {
  coordinatorPlan.value = mockPlan
  activeCoordinatorPhase.value = null
  completedCoordinatorPhases.value = []
  coordinatorPhaseOutputs.value = {}
}

// 模拟开始 phase
function simulatePhaseStart(phaseNum) {
  activeCoordinatorPhase.value = phaseNum
}

// 模拟完成 phase
function simulatePhaseComplete(phaseNum) {
  if (!completedCoordinatorPhases.value.includes(phaseNum)) {
    completedCoordinatorPhases.value.push(phaseNum)
  }
  coordinatorPhaseOutputs.value[phaseNum] = `Phase ${phaseNum} 执行完成，输出结果...`
  if (activeCoordinatorPhase.value === phaseNum) {
    activeCoordinatorPhase.value = null
  }
}

// 重置
function reset() {
  coordinatorPlan.value = null
  activeCoordinatorPhase.value = null
  completedCoordinatorPhases.value = []
  coordinatorPhaseOutputs.value = {}
}
</script>

<style scoped>
.demo-container {
  padding: 40px;
  min-height: 100vh;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
}

.demo-container.light {
  background: #ffffff;
  color: #1a1a1a;
  --sidebar-bg: #f7f8fc;
  --main-bg: #ffffff;
  --text-primary: #1a1a1a;
  --text-secondary: #666666;
  --border-color: #e5e5e5;
  --input-bg: #f5f5f5;
  --send-btn: #615ced;
  --send-btn-hover: #5248d9;
}

.demo-container.dark {
  background: #232326;
  color: #e0e0e0;
  --sidebar-bg: #1d1d1f;
  --main-bg: #232326;
  --text-primary: #e0e0e0;
  --text-secondary: #999999;
  --border-color: #3a3a3a;
  --input-bg: #2a2a2a;
  --send-btn: #615ced;
  --send-btn-hover: #7571ff;
}

h2 {
  margin-bottom: 24px;
}

h3 {
  margin: 24px 0 12px;
  font-size: 16px;
  color: var(--text-secondary);
}

/* 主题切换 */
.theme-toggle {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.theme-toggle button {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  color: var(--text-primary);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.theme-toggle button.active {
  background: var(--send-btn);
  color: white;
  border-color: var(--send-btn);
}

/* 控制按钮 */
.controls {
  margin-bottom: 24px;
}

.controls button {
  padding: 10px 16px;
  margin: 4px;
  border: 1px solid var(--border-color);
  background: var(--input-bg);
  color: var(--text-primary);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.controls button:hover {
  background: var(--border-color);
}

/* 演示区域 */
.demo-area {
  position: relative;
  min-height: 400px;
  background: var(--main-bg);
  border: 1px solid var(--border-color);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 24px;
}

/* 覆盖组件样式以便在演示中正常显示 */
.demo-area :deep(.coordinator-plan-card) {
  position: relative;
  top: auto;
  right: auto;
  width: 320px;
}

/* 数据预览 */
.data-preview {
  background: var(--input-bg);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 16px;
}

.data-preview pre {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  overflow-x: auto;
  color: var(--text-secondary);
}
</style>
