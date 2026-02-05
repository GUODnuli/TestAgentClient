/**
 * 选框组件基类
 * 提供通用的状态管理、事件处理和渲染接口
 */

export interface SelectOption {
  label: string
  value: string | number | boolean
  description?: string
  icon?: string
  disabled?: boolean
  [key: string]: any
}

export interface SelectBoxConfig {
  id: string
  title?: string
  description?: string
  allowEmpty?: boolean  // 是否允许不选
  className?: string
}

export type SelectChangeHandler = (selected: SelectOption | SelectOption[] | null) => void
export type CustomInputHandler = (value: string) => void

export abstract class SelectBoxBase {
  protected config: SelectBoxConfig
  protected options: SelectOption[] = []
  protected selectedValues: Set<string | number | boolean> = new Set()
  protected container: HTMLElement | null = null
  protected changeHandlers: SelectChangeHandler[] = []
  protected customInputHandlers: CustomInputHandler[] = []
  protected isRendered = false

  constructor(config: SelectBoxConfig) {
    this.config = {
      allowEmpty: false,
      ...config
    }
  }

  /**
   * 获取组件唯一标识
   */
  get id(): string {
    return this.config.id
  }

  /**
   * 获取当前选中的选项
   */
  abstract getSelected(): SelectOption | SelectOption[] | null

  /**
   * 设置选中项
   */
  abstract setSelected(value: string | number | boolean | (string | number | boolean)[]): void

  /**
   * 清空选择
   */
  clear(): void {
    this.selectedValues.clear()
    this.notifyChange()
    this.updateUI()
  }

  /**
   * 注册变化回调
   */
  onChange(handler: SelectChangeHandler): void {
    this.changeHandlers.push(handler)
  }

  /**
   * 移除变化回调
   */
  offChange(handler: SelectChangeHandler): void {
    const index = this.changeHandlers.indexOf(handler)
    if (index > -1) {
      this.changeHandlers.splice(index, 1)
    }
  }

  /**
   * 注册自定义输入回调（用于支持自定义输入的组件）
   */
  onCustomInput(handler: CustomInputHandler): void {
    this.customInputHandlers.push(handler)
  }

  /**
   * 通知所有监听器选择变化
   */
  protected notifyChange(): void {
    const selected = this.getSelected()
    this.changeHandlers.forEach(handler => {
      try {
        handler(selected)
      } catch (e) {
        console.error(`[SelectBox ${this.config.id}] Change handler error:`, e)
      }
    })
  }

  /**
   * 通知自定义输入
   */
  protected notifyCustomInput(value: string): void {
    this.customInputHandlers.forEach(handler => {
      try {
        handler(value)
      } catch (e) {
        console.error(`[SelectBox ${this.config.id}] Custom input handler error:`, e)
      }
    })
  }

  /**
   * 渲染组件到指定容器
   */
  render(container: HTMLElement): void {
    this.container = container
    this.container.innerHTML = ''
    
    const wrapper = this.createWrapper()
    wrapper.appendChild(this.createHeader())
    wrapper.appendChild(this.createContent())
    
    this.container.appendChild(wrapper)
    this.isRendered = true
    this.updateUI()
  }

  /**
   * 销毁组件
   */
  destroy(): void {
    this.changeHandlers = []
    this.customInputHandlers = []
    if (this.container) {
      this.container.innerHTML = ''
    }
    this.container = null
    this.isRendered = false
  }

  /**
   * 创建外层容器
   */
  protected createWrapper(): HTMLElement {
    const wrapper = document.createElement('div')
    wrapper.className = `select-box ${this.config.className || ''}`.trim()
    wrapper.dataset.selectBoxId = this.config.id
    return wrapper
  }

  /**
   * 创建头部（标题和描述）
   */
  protected createHeader(): HTMLElement {
    const header = document.createElement('div')
    header.className = 'select-box-header'

    if (this.config.title) {
      const title = document.createElement('div')
      title.className = 'select-box-title'
      title.textContent = this.config.title
      header.appendChild(title)
    }

    if (this.config.description) {
      const desc = document.createElement('div')
      desc.className = 'select-box-description'
      desc.textContent = this.config.description
      header.appendChild(desc)
    }

    return header
  }

  /**
   * 创建内容区域 - 子类必须实现
   */
  protected abstract createContent(): HTMLElement

  /**
   * 更新 UI 状态 - 子类应该重写
   */
  protected abstract updateUI(): void

  /**
   * 切换选项选中状态
   */
  protected toggleValue(value: string | number | boolean): void {
    if (this.selectedValues.has(value)) {
      this.selectedValues.delete(value)
    } else {
      this.selectedValues.add(value)
    }
    this.notifyChange()
    this.updateUI()
  }

  /**
   * 设置单个值（单选模式）
   */
  protected setSingleValue(value: string | number | boolean): void {
    this.selectedValues.clear()
    this.selectedValues.add(value)
    this.notifyChange()
    this.updateUI()
  }

  /**
   * 检查值是否被选中
   */
  protected isSelected(value: string | number | boolean): boolean {
    return this.selectedValues.has(value)
  }
}

export default SelectBoxBase
