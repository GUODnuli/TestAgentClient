/**
 * 选框组件使用示例
 * 展示 MultiSelectBox 和 ConfirmSelectBox 的基本用法
 */

import { MultiSelectBox, ConfirmSelectBox } from './index'

// ==================== 示例 1: 多选项组件 ====================

function demoMultiSelectBox() {
  // 创建组件实例
  const multiBox = new MultiSelectBox({
    id: 'demo-multi-select',
    title: '选择你感兴趣的技术栈（可多选）',
    description: '最多支持5个选项，最后一个可自定义输入',
    options: [
      { 
        label: 'Vue.js', 
        value: 'vue',
        description: '渐进式 JavaScript 框架'
      },
      { 
        label: 'React', 
        value: 'react',
        description: '用于构建用户界面的库'
      },
      { 
        label: 'TypeScript', 
        value: 'ts',
        description: 'JavaScript 的超集'
      },
      { 
        label: 'Node.js', 
        value: 'node',
        description: '服务端 JavaScript 运行时'
      }
    ],
    allowCustomInput: true,
    customInputLabel: '其他技术',
    customInputPlaceholder: '请输入其他技术名称...'
  })

  // 监听选择变化
  multiBox.onChange((selected) => {
    console.log('[MultiSelectBox] 当前选中:', selected)
    
    // 可以在这里处理选中的值
    const values = selected.map(s => s.value)
    console.log('[MultiSelectBox] 选中的值:', values)
  })

  // 监听自定义输入
  multiBox.onCustomInput((value) => {
    console.log('[MultiSelectBox] 自定义输入:', value)
  })

  // 渲染到页面
  const container = document.createElement('div')
  container.id = 'multi-select-container'
  document.body.appendChild(container)
  
  multiBox.render(container)

  // 程序化操作示例
  setTimeout(() => {
    // 设置选中项
    multiBox.setSelected(['vue', 'ts'])
    
    // 设置自定义值
    multiBox.setCustomValue('Rust')
  }, 2000)

  return multiBox
}


// ==================== 示例 2: 确认选框组件 ====================

function demoConfirmSelectBox() {
  // 创建组件实例
  const confirmBox = new ConfirmSelectBox({
    id: 'demo-confirm',
    title: '是否执行批量操作？',
    description: '请选择操作方式',
    yesLabel: '是，执行一次',
    yesAutoLabel: '是，并授权后续自动执行',
    yesAutoDescription: '后续相同操作将自动执行，不再询问',
    noLabel: '否，取消操作',
    defaultValue: 'no'
  })

  // 监听选择变化
  confirmBox.onChange((selected) => {
    console.log('[ConfirmSelectBox] 当前选中:', selected)

    // 判断选中状态
    if (confirmBox.isYes()) {
      console.log('[ConfirmSelectBox] 用户选择了"是"')
      
      if (confirmBox.isYesAuto()) {
        console.log('[ConfirmSelectBox] ⚡ 用户授权了自动执行！')
        // 保存自动执行授权到本地存储
        localStorage.setItem('autoExecuteAuthorized', 'true')
      }
    } else if (confirmBox.isNo()) {
      console.log('[ConfirmSelectBox] 用户选择了"否"')
    }
  })

  // 渲染到页面
  const container = document.createElement('div')
  container.id = 'confirm-select-container'
  document.body.appendChild(container)
  
  confirmBox.render(container)

  // 程序化操作示例
  setTimeout(() => {
    // 选择"是+自动执行"
    confirmBox.selectYesAuto()
    
    // 检查是否授权
    console.log('[ConfirmSelectBox] 是否授权自动执行:', confirmBox.hasAutoExecute())
  }, 3000)

  return confirmBox
}


// ==================== 示例 3: 组合使用 ====================

function demoCombinedUsage() {
  // 场景：删除确认 + 删除范围选择
  
  const deleteConfirmBox = new ConfirmSelectBox({
    id: 'delete-confirm',
    title: '确认删除选中的项目？',
    yesLabel: '是，删除所选',
    yesAutoLabel: '是，并授权自动删除',
    yesAutoDescription: '后续删除操作将自动执行',
    noLabel: '否，取消',
    defaultValue: 'no'
  })

  const deleteScopeBox = new MultiSelectBox({
    id: 'delete-scope',
    title: '选择删除范围',
    options: [
      { label: '仅删除文件', value: 'files' },
      { label: '删除文件和目录', value: 'files-and-dirs' },
      { label: '清空回收站', value: 'empty-trash' }
    ],
    allowCustomInput: true,
    customInputLabel: '自定义删除规则',
    customInputPlaceholder: '输入自定义规则...'
  })

  // 监听确认选择
  deleteConfirmBox.onChange((selected) => {
    if (deleteConfirmBox.isYes()) {
      const scope = deleteScopeBox.getSelected()
      console.log('[Combined] 执行删除，范围:', scope)
      
      if (deleteConfirmBox.hasAutoExecute()) {
        console.log('[Combined] 已授权自动删除，后续不再询问')
      }
    }
  })

  // 渲染
  const container1 = document.createElement('div')
  const container2 = document.createElement('div')
  document.body.appendChild(container1)
  document.body.appendChild(container2)
  
  deleteConfirmBox.render(container1)
  deleteScopeBox.render(container2)

  return { deleteConfirmBox, deleteScopeBox }
}


// ==================== 示例 4: 带样式的使用 ====================

function demoWithStyles() {
  // 添加自定义样式
  const style = document.createElement('style')
  style.textContent = `
    .select-box {
      background: var(--bg-primary, #fff);
      border: 1px solid var(--border-color, #e5e5e5);
      border-radius: 8px;
      padding: 16px;
      margin: 16px 0;
      max-width: 400px;
    }
    
    .select-box-title {
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary, #1a1a1a);
      margin-bottom: 4px;
    }
    
    .select-box-description {
      font-size: 13px;
      color: var(--text-secondary, #666);
      margin-bottom: 12px;
    }
    
    .select-option {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      padding: 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: background 0.2s;
    }
    
    .select-option:hover {
      background: var(--bg-hover, #f5f5f5);
    }
    
    .select-option.selected {
      background: rgba(97, 92, 237, 0.08);
    }
    
    .option-checkbox {
      width: 18px;
      height: 18px;
      border: 2px solid var(--border-color, #d9d9d9);
      border-radius: 4px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }
    
    .select-option.selected .option-checkbox {
      background: var(--send-btn, #615ced);
      border-color: var(--send-btn, #615ced);
    }
    
    .check-mark {
      color: white;
      font-size: 12px;
      display: none;
    }
    
    .select-option.selected .check-mark {
      display: block;
    }
    
    .option-radio {
      width: 18px;
      height: 18px;
      border: 2px solid var(--border-color, #d9d9d9);
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 2px;
    }
    
    .select-option.selected .option-radio {
      border-color: var(--send-btn, #615ced);
    }
    
    .radio-dot {
      width: 8px;
      height: 8px;
      background: var(--send-btn, #615ced);
      border-radius: 50%;
      display: none;
    }
    
    .select-option.selected .radio-dot {
      display: block;
    }
    
    .option-label {
      font-size: 14px;
      font-weight: 500;
      color: var(--text-primary, #1a1a1a);
    }
    
    .option-description {
      font-size: 12px;
      color: var(--text-secondary, #666);
      margin-top: 2px;
    }
    
    .auto-badge {
      display: inline-block;
      font-size: 10px;
      font-weight: 600;
      color: var(--send-btn, #615ced);
      background: rgba(97, 92, 237, 0.1);
      padding: 2px 6px;
      border-radius: 4px;
      margin-left: 8px;
    }
    
    .custom-input {
      width: 100%;
      padding: 8px 12px;
      border: 1px solid var(--border-color, #d9d9d9);
      border-radius: 6px;
      font-size: 13px;
      margin-top: 8px;
      background: var(--bg-primary, #fff);
      color: var(--text-primary, #1a1a1a);
    }
    
    .custom-input:focus {
      outline: none;
      border-color: var(--send-btn, #615ced);
    }
    
    .custom-label {
      font-size: 13px;
      color: var(--text-secondary, #666);
    }
  `
  document.head.appendChild(style)

  // 创建示例组件
  const box1 = new MultiSelectBox({
    id: 'styled-multi',
    title: '带样式的多选项',
    options: [
      { label: '选项 A', value: 'a' },
      { label: '选项 B', value: 'b' },
      { label: '选项 C', value: 'c' }
    ],
    allowCustomInput: true
  })

  const box2 = new ConfirmSelectBox({
    id: 'styled-confirm',
    title: '带样式的确认选框',
    yesAutoLabel: '是，自动执行'
  })

  const container1 = document.createElement('div')
  const container2 = document.createElement('div')
  document.body.appendChild(container1)
  document.body.appendChild(container2)

  box1.render(container1)
  box2.render(container2)

  return { box1, box2 }
}


// 导出所有演示函数
export {
  demoMultiSelectBox,
  demoConfirmSelectBox,
  demoCombinedUsage,
  demoWithStyles
}

// 如果在浏览器环境中，自动运行演示
if (typeof window !== 'undefined') {
  console.log('[Selector Demo] 可用的演示函数：')
  console.log('  - demoMultiSelectBox()')
  console.log('  - demoConfirmSelectBox()')
  console.log('  - demoCombinedUsage()')
  console.log('  - demoWithStyles()')
}
