/**
 * 选框组件库入口
 * 
 * 使用示例：
 * 
 * ```typescript
 * import { MultiSelectBox, ConfirmSelectBox } from '@/components/selector'
 * 
 * // 多选项组件
 * const multiBox = new MultiSelectBox({
 *   id: 'my-multi-select',
 *   title: '选择你喜欢的颜色',
 *   options: [
 *     { label: '红色', value: 'red' },
 *     { label: '绿色', value: 'green' },
 *     { label: '蓝色', value: 'blue' }
 *   ]
 * })
 * 
 * multiBox.onChange((selected) => {
 *   console.log('选中:', selected)
 * })
 * 
 * multiBox.render(document.getElementById('container'))
 * 
 * // 确认选框组件
 * const confirmBox = new ConfirmSelectBox({
 *   id: 'my-confirm',
 *   title: '是否确认删除？',
 *   yesAutoLabel: '是，并授权后续自动删除'
 * })
 * 
 * confirmBox.onChange((selected) => {
 *   if (confirmBox.isYesAuto()) {
 *     console.log('用户授权了自动执行')
 *   }
 * })
 * 
 * confirmBox.render(document.getElementById('container'))
 * ```
 */

// 基类和类型
export { 
  SelectBoxBase,
  type SelectOption,
  type SelectBoxConfig,
  type SelectChangeHandler,
  type CustomInputHandler
} from './base/SelectBoxBase'

// 多选项组件
export {
  MultiSelectBox,
  type MultiSelectBoxConfig
} from './impl/MultiSelectBox'

// 确认选框组件
export {
  ConfirmSelectBox,
  type ConfirmSelectBoxConfig,
  type ConfirmValue,
  type ConfirmOption
} from './impl/ConfirmSelectBox'

// Vue 包装组件（用于集成到聊天区域）
export { default as SelectBoxWrapper } from './SelectBoxWrapper.vue'
