<template>
  <div ref="containerRef" class="select-box-wrapper"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { MultiSelectBox, ConfirmSelectBox } from './index'

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (v) => ['multi', 'confirm'].includes(v)
  },
  config: {
    type: Object,
    required: true
  },
  modelValue: {
    type: [String, Array, Boolean],
    default: null
  }
})

const emit = defineEmits(['change', 'customInput', 'update:modelValue'])

const containerRef = ref(null)
let selectBox = null

onMounted(() => {
  if (!containerRef.value) return

  // 根据类型创建对应实例
  if (props.type === 'multi') {
    selectBox = new MultiSelectBox(props.config)
  } else if (props.type === 'confirm') {
    selectBox = new ConfirmSelectBox(props.config)
  }

  // 监听变化
  selectBox.onChange((selected) => {
    emit('change', selected)
    
    // 同步 v-model
    if (props.type === 'multi') {
      const values = selected.map(s => s.value)
      emit('update:modelValue', values)
    } else {
      emit('update:modelValue', selected?.value || null)
    }
  })

  // 监听自定义输入（仅 multi 类型）
  if (props.type === 'multi') {
    selectBox.onCustomInput((value) => {
      emit('customInput', value)
    })
  }

  // 渲染
  selectBox.render(containerRef.value)

  // 设置初始值
  if (props.modelValue) {
    selectBox.setSelected(props.modelValue)
  }
})

onUnmounted(() => {
  if (selectBox) {
    selectBox.destroy()
    selectBox = null
  }
})

// 响应外部 modelValue 变化
watch(() => props.modelValue, (newVal) => {
  if (selectBox && newVal) {
    selectBox.setSelected(newVal)
  }
})
</script>

<style scoped>
.select-box-wrapper {
  margin: 8px 0;
}

/* 适配聊天消息的样式 */
:deep(.select-box) {
  background: var(--input-bg, #f5f5f5);
  border-color: var(--border-color, #e5e5e5);
  margin: 0;
}

:deep(.select-box-title) {
  font-size: 14px;
}

:deep(.select-option) {
  padding: 10px 12px;
}
</style>
