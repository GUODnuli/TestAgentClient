/**
 * 确认选框组件
 * 支持三种选项：
 * 1. yes - 是
 * 2. yes-auto - 是和固定操作授权自动执行
 * 3. no - 否
 */

import { SelectBoxBase, SelectOption, SelectBoxConfig } from '../base/SelectBoxBase'

export type ConfirmValue = 'yes' | 'yes-auto' | 'no'

export interface ConfirmSelectBoxConfig extends SelectBoxConfig {
  yesLabel?: string           // "是" 选项的标签
  yesAutoLabel?: string       // "是+自动执行" 选项的标签
  noLabel?: string            // "否" 选项的标签
  yesDescription?: string     // "是" 选项的描述
  yesAutoDescription?: string // "是+自动执行" 选项的描述
  noDescription?: string      // "否" 选项的描述
  defaultValue?: ConfirmValue // 默认值
}

export interface ConfirmOption extends SelectOption {
  value: ConfirmValue
  autoExecute?: boolean  // 是否包含自动执行授权
}

export class ConfirmSelectBox extends SelectBoxBase {
  protected config: ConfirmSelectBoxConfig
  private options: ConfirmOption[] = []

  constructor(config: ConfirmSelectBoxConfig) {
    super(config)
    
    this.config.yesLabel = config.yesLabel || '是'
    this.config.yesAutoLabel = config.yesAutoLabel || '是，并授权自动执行'
    this.config.noLabel = config.noLabel || '否'

    // 初始化三个固定选项
    this.options = [
      {
        label: this.config.yesLabel,
        value: 'yes',
        description: config.yesDescription,
        autoExecute: false
      },
      {
        label: this.config.yesAutoLabel,
        value: 'yes-auto',
        description: config.yesAutoDescription || '选择后将自动执行固定操作，无需再次确认',
        autoExecute: true
      },
      {
        label: this.config.noLabel,
        value: 'no',
        description: config.noDescription,
        autoExecute: false
      }
    ]

    // 设置默认值
    if (config.defaultValue) {
      this.selectedValues.add(config.defaultValue)
    }
  }

  /**
   * 获取当前选中的选项
   */
  getSelected(): ConfirmOption | null {
    const selectedValue = Array.from(this.selectedValues)[0]
    if (!selectedValue) return null
    
    return this.options.find(opt => opt.value === selectedValue) || null
  }

  /**
   * 获取选中的值
   */
  getValue(): ConfirmValue | null {
    const selected = this.getSelected()
    return selected ? selected.value : null
  }

  /**
   * 是否选择了"是"
   */
  isYes(): boolean {
    const value = this.getValue()
    return value === 'yes' || value === 'yes-auto'
  }

  /**
   * 是否选择了"是+自动执行"
   */
  isYesAuto(): boolean {
    return this.getValue() === 'yes-auto'
  }

  /**
   * 是否选择了"否"
   */
  isNo(): boolean {
    return this.getValue() === 'no'
  }

  /**
   * 是否授权了自动执行
   */
  hasAutoExecute(): boolean {
    const selected = this.getSelected()
    return selected ? selected.autoExecute || false : false
  }

  /**
   * 设置选中的选项
   */
  setSelected(value: ConfirmValue): void {
    this.setSingleValue(value)
  }

  /**
   * 选择"是"
   */
  selectYes(): void {
    this.setSelected('yes')
  }

  /**
   * 选择"是+自动执行"
   */
  selectYesAuto(): void {
    this.setSelected('yes-auto')
  }

  /**
   * 选择"否"
   */
  selectNo(): void {
    this.setSelected('no')
  }

  /**
   * 创建内容区域
   */
  protected createContent(): HTMLElement {
    const content = document.createElement('div')
    content.className = 'select-box-content confirm-select-box'

    // 创建选项列表
    const optionsList = document.createElement('div')
    optionsList.className = 'options-list confirm-options'

    this.options.forEach(option => {
      const optionEl = this.createOptionElement(option)
      optionsList.appendChild(optionEl)
    })

    content.appendChild(optionsList)
    return content
  }

  /**
   * 创建单个选项元素
   */
  private createOptionElement(option: ConfirmOption): HTMLElement {
    const optionEl = document.createElement('div')
    optionEl.className = 'select-option confirm-option'
    optionEl.dataset.value = option.value

    // 单选按钮
    const radio = document.createElement('div')
    radio.className = 'option-radio'
    radio.innerHTML = '<span class="radio-dot"></span>'
    optionEl.appendChild(radio)

    // 选项内容
    const content = document.createElement('div')
    content.className = 'option-content'

    const labelRow = document.createElement('div')
    labelRow.className = 'option-label-row'

    const label = document.createElement('span')
    label.className = 'option-label'
    label.textContent = option.label
    labelRow.appendChild(label)

    // 自动执行标识
    if (option.autoExecute) {
      const autoBadge = document.createElement('span')
      autoBadge.className = 'auto-badge'
      autoBadge.textContent = '自动'
      labelRow.appendChild(autoBadge)
    }

    content.appendChild(labelRow)

    if (option.description) {
      const desc = document.createElement('div')
      desc.className = 'option-description'
      desc.textContent = option.description
      content.appendChild(desc)
    }

    optionEl.appendChild(content)

    // 点击事件 - 单选模式
    optionEl.addEventListener('click', () => {
      this.setSingleValue(option.value)
    })

    return optionEl
  }

  /**
   * 更新 UI 状态
   */
  protected updateUI(): void {
    if (!this.container) return

    this.options.forEach(option => {
      const optionEl = this.container!.querySelector(`[data-value="${option.value}"]`)
      if (optionEl) {
        const isSelected = this.isSelected(option.value)
        optionEl.classList.toggle('selected', isSelected)
        
        // 更新 radio 状态
        const radio = optionEl.querySelector('.option-radio')
        if (radio) {
          radio.classList.toggle('checked', isSelected)
        }
      }
    })
  }
}

export default ConfirmSelectBox
