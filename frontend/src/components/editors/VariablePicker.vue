<template>
  <div class="variable-picker">
    <span class="hint">变量引用</span>
    <el-button v-for="item in options" :key="item" size="small" @click="$emit('insert', item)">
      {{ item }}
    </el-button>
  </div>
</template>

<script setup>
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
