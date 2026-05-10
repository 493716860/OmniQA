<template>
  <div class="kv-editor">
    <el-table :data="rows" size="small" border>
      <el-table-column label="启用" width="70" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="emitValue" />
        </template>
      </el-table-column>
      <el-table-column label="Key" min-width="180">
        <template #default="{ row }">
          <el-input v-model="row.key" placeholder="Header Key" @input="emitValue" />
        </template>
      </el-table-column>
      <el-table-column label="Value" min-width="220">
        <template #default="{ row }">
          <el-input v-model="row.value" placeholder="Value，支持 ${token}" @input="emitValue" />
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="160">
        <template #default="{ row }">
          <el-input v-model="row.description" placeholder="仅前端辅助说明" />
        </template>
      </el-table-column>
      <el-table-column width="72" align="center">
        <template #default="{ $index }">
          <el-button text type="danger" @click="removeRow($index)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="editor-actions">
      <el-button size="small" @click="addRow">添加一行</el-button>
      <el-button size="small" @click="insertBearer">Bearer Token</el-button>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const model = defineModel({ type: Object, default: () => ({}) })
const rows = ref([])
let syncing = false

function fromObject(value) {
  return Object.entries(value || {}).map(([key, item]) => ({
    enabled: true,
    key,
    value: item == null ? '' : String(item),
    description: ''
  }))
}

function toObject() {
  return rows.value.reduce((target, row) => {
    if (row.enabled && row.key.trim()) {
      target[row.key.trim()] = row.value
    }
    return target
  }, {})
}

function emitValue() {
  syncing = true
  model.value = toObject()
  nextTick(() => {
    syncing = false
  })
}

function addRow() {
  rows.value.push({ enabled: true, key: '', value: '', description: '' })
}

function removeRow(index) {
  rows.value.splice(index, 1)
  emitValue()
}

function insertBearer() {
  rows.value.push({ enabled: true, key: 'Authorization', value: 'Bearer ${token}', description: '登录 token' })
  emitValue()
}

watch(
  model,
  value => {
    if (!syncing) {
      rows.value = fromObject(value)
    }
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
.kv-editor {
  width: 100%;
}
</style>
