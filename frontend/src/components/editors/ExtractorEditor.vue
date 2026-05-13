<template>
  <div>
    <el-table :data="rows" size="small" border>
      <el-table-column label="变量名" min-width="150">
        <template #default="{ row }">
          <el-input v-model="row.name" placeholder="token" @input="emitValue" />
        </template>
      </el-table-column>
      <el-table-column label="字段路径" min-width="220">
        <template #default="{ row }">
          <el-input v-model="row.path" placeholder="data.token / $.data.token" @input="emitValue" />
        </template>
      </el-table-column>
      <el-table-column label="必填" width="90" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.required" @change="emitValue" />
        </template>
      </el-table-column>
      <el-table-column label="示例值" min-width="160">
        <template #default="{ row }">
          <el-input v-model="row.example" placeholder="仅前端辅助说明" />
        </template>
      </el-table-column>
      <el-table-column width="72" align="center">
        <template #default="{ $index }">
          <el-button text type="danger" @click="removeRow($index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="editor-actions">
      <el-button size="small" @click="addRow">添加提取</el-button>
      <el-button size="small" @click="addToken">提取 token</el-button>
      <el-button size="small" @click="addUid">提取 uid_str</el-button>
    </div>
  </div>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 变量提取编辑器组件，用于定义从接口响应中抽取变量的规则列表，例如 token、uid 等后续依赖变量。
 * 2. 组件通过 defineModel 与父级请求配置表单双向同步，常由 RequestConfigEditor 统一承载，再被用例和场景步骤页面复用。
 * 3. 它只负责前端配置结构的录入与整理，真正的变量提取与上下文传递在后端执行引擎中完成。
 */
import { nextTick, ref, watch } from 'vue'

const model = defineModel({ type: Array, default: () => [] })
const rows = ref([])
let syncing = false

function normalize(items) {
  return (items || []).map(item => ({
    name: item.name || '',
    path: item.path || '',
    required: Boolean(item.required),
    example: item.example || ''
  }))
}

function emitValue() {
  syncing = true
  model.value = rows.value
    .filter(row => row.name.trim() && row.path.trim())
    .map(row => ({ name: row.name.trim(), path: row.path.trim(), required: Boolean(row.required) }))
  nextTick(() => {
    syncing = false
  })
}

function addRow() {
  rows.value.push({ name: '', path: '', required: false, example: '' })
}

function addToken() {
  rows.value.push({ name: 'token', path: 'data.token', required: true, example: '' })
  emitValue()
}

function addUid() {
  rows.value.push({ name: 'uid_str', path: 'data.uid_str', required: false, example: '' })
  emitValue()
}

function removeRow(index) {
  rows.value.splice(index, 1)
  emitValue()
}

watch(
  model,
  value => {
    if (!syncing) rows.value = normalize(value)
  },
  { immediate: true, deep: true }
)
</script>

<style scoped>
.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
</style>
