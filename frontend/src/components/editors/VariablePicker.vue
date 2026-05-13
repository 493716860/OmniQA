<template>
  <div class="variable-picker">
    <span class="hint">变量引用</span>
    <el-button v-for="item in options" :key="item" size="small" @click="$emit('insert', item)">
      {{ item }}
    </el-button>
  </div>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 变量选择器组件，以快捷按钮形式展示常用变量引用模板，便于在请求头、请求体、断言或提取规则中快速插入变量。
 * 2. 它通常作为 RequestConfigEditor 的辅助组件出现，为接口用例和场景步骤编辑流程提供更高效的输入体验。
 * 3. 组件本身不维护业务状态，只负责把用户点击的变量值通过 insert 事件回传给父组件。
 */
defineEmits(['insert'])
defineProps({
  options: {
    type: Array,
    default: () => ['${token}', '${uid}', '${uid_str}', '${LOGIN_001.data.token}']
  }
})
</script>

<style scoped>
.variable-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 8px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.hint {
  color: #64748b;
  font-size: 13px;
}
</style>
