/**
 * 多选项选框组件
 * 支持最多5个预定义选项 + 1个用户自定义输入选项
 * 可多选，不做任何校验
 */

import { SelectBoxBase, SelectOption, SelectBoxConfig } from '../base/SelectBoxBase'

export interface MultiSelectBoxConfig extends SelectBoxConfig {
  options: SelectOption[]  // 最多5个选项
  maxSelection?: number     // 最大可选数量，默认不限制
  allowCustomInput?: boolean  // 是否允许自定义输入，默认true
  customInputPlaceholder?: string  // 自定义输入框占位符
  customInputLabel?: string   // 自定义输入选项的标签
}

export class MultiSelectBox extends SelectBoxBase {
  protected config: MultiSelectBoxConfig
  private customValue: string = ''
  private customInputElement: HTMLInputElement | null = null
  private customOptionId = '__custom__'

  constructor(config: MultiSelectBoxConfig) {
    super(config)
    
    // 限制最多5个选项
    this.config.options = config.options.slice(0, 5)
    this.config.allowCustomInput = config.allowCustomInput !== false
    this.config.customInputPlaceholder = config.customInputPlaceholder || '请输入自定义选项...'
    this.config.customInputLabel = config.customInputLabel || '其他（自定义）'
  }

  /**
   * 获取当前选中的选项列表
   */
  getSelected(): SelectOption[] {
    const selected: SelectOption[] = []
    
    // 添加预定义选项中选中的
    this.config.options.forEach(option => {
      if (this.isSelected(option.value)) {
        selected.push(option)
      }
    })
    
    // 添加自定义选项（如果有输入值且被选中）
    if (this.config.allowCustomInput && this.isSelected(this.customOptionId) && this.customValue) {
      selected.push({
        label: this.customValue,
        value: this.customValue,
        isCustom: true
      })
    }
    
    return selected
  }

  /**
   * 设置选中的选项
   * @param values 选项值数组，自定义选项用 '__custom__' 标识
   */
  setSelected(values: (string | number | boolean)[]): void {
    this.selectedValues.clear()
    
    values.forEach(value => {
      if (value === this.customOptionId) {
        this.selectedValues.add(this.customOptionId)
      } else {
        // 检查是否是预定义选项
        const exists = this.config.options.some(opt => opt.value === value)
        if (exists) {
          this.selectedValues.add(value)
        }
      }
    })
    
    this.notifyChange()
    this.updateUI()
  }

  /**
   * 设置自定义输入值
   */
  setCustomValue(value: string): void {
    this.customValue = value
    if (value && !this.isSelected(this.customOptionId)) {
      this.selectedValues.add(this.customOptionId)
    }
    this.notifyChange()
    this.updateUI()
  }

  /**
   * 获取自定义输入值
   */
  getCustomValue(): string {
    return this.customValue
  }

  /**
   * 创建内容区域
   */
  protected createContent(): HTMLElement {
    const content = document.createElement('div')
    content.className = 'select-box-content multi-select-box'

    // 创建选项列表
    const optionsList = document.createElement('div')
    optionsList.className = 'options-list'

    // 添加预定义选项（最多5个）
    this.config.options.forEach((option, index) => {
      const optionEl = this.createOptionElement(option, index)
      optionsList.appendChild(optionEl)
    })

    // 添加自定义输入选项
    if (this.config.allowCustomInput) {
      const customEl = this.createCustomInputElement()
      optionsList.appendChild(customEl)
    }

    content.appendChild(optionsList)
    return content
  }

  /**
   * 创建单个选项元素
   */
  private createOptionElement(option: SelectOption, index: number): HTMLElement {
    const optionEl = document.createElement('div')
    optionEl.className = 'select-option'
    optionEl.dataset.value = String(option.value)
    optionEl.dataset.index = String(index)
    
    if (option.disabled) {
      optionEl.classList.add('disabled')
    }

    // 复选框
    const checkbox = document.createElement('div')
    checkbox.className = 'option-checkbox'
    checkbox.innerHTML = '<span class="check-mark">✓</span>'
    optionEl.appendChild(checkbox)

    // 选项内容
    const content = document.createElement('div')
    content.className = 'option-content'

    const label = document.createElement('div')
    label.className = 'option-label'
    label.textContent = option.label
    content.appendChild(label)

    if (option.description) {
      const desc = document.createElement('div')
      desc.className = 'option-description'
      desc.textContent = option.description
      content.appendChild(desc)
    }

    optionEl.appendChild(content)

    // 点击事件
    if (!option.disabled) {
      optionEl.addEventListener('click', () => {
        this.toggleValue(option.value)
      })
    }

    return optionEl
  }

  /**
   * 创建自定义输入选项
   */
  private createCustomInputElement(): HTMLElement {
    const wrapper = document.createElement('div')
    wrapper.className = 'select-option custom-option'
    wrapper.dataset.value = this.customOptionId

    // 复选框
    const checkbox = document.createElement('div')
    checkbox.className = 'option-checkbox'
    checkbox.innerHTML = '<span class="check-mark">✓</span>'
    wrapper.appendChild(checkbox)

    // 输入区域
    const inputArea = document.createElement('div')
    inputArea.className = 'custom-input-area'

    const label = document.createElement('div')
    label.className = 'custom-label'
    label.textContent = this.config.customInputLabel
    inputArea.appendChild(label)

    // 输入框
    const input = document.createElement('input')
    input.type = 'text'
    input.className = 'custom-input'
    input.placeholder = this.config.customInputPlaceholder!
    input.value = this.customValue
    
    // 输入事件 - 不做任何校验
    input.addEventListener('input', (e) => {
      const target = e.target as HTMLInputElement
      this.customValue = target.value
      
      // 只要有输入就自动选中自定义选项
      if (this.customValue && !this.isSelected(this.customOptionId)) {
        this.selectedValues.add(this.customOptionId)
        this.updateUI()
      }
      
      // 通知自定义输入
      this.notifyCustomInput(this.customValue)
    })

    // 聚焦时自动选中
    input.addEventListener('focus', () => {
      if (!this.isSelected(this.customOptionId)) {
        this.selectedValues.add(this.customOptionId)
        this.updateUI()
        this.notifyChange()
      }
    })

    inputArea.appendChild(input)
    this.customInputElement = input

    wrapper.appendChild(inputArea)

    // 点击复选框区域切换选中
    checkbox.addEventListener('click', (e) => {
      e.stopPropagation()
      this.toggleValue(this.customOptionId)
    })

    return wrapper
  }

  /**
   * 更新 UI 状态
   */
  protected updateUI(): void {
    if (!this.container) return

    // 更新所有预定义选项的选中状态
    this.config.options.forEach((option, index) => {
      const optionEl = this.container!.querySelector(`[data-index="${index}"]`)
      if (optionEl) {
        optionEl.classList.toggle('selected', this.isSelected(option.value))
      }
    })

    // 更新自定义选项的选中状态
    const customEl = this.container!.querySelector(`[data-value="${this.customOptionId}"]`)
    if (customEl) {
      customEl.classList.toggle('selected', this.isSelected(this.customOptionId))
    }
  }
}

export default MultiSelectBox
