<template>
  <div class="json-body-editor">
    <el-radio-group v-model="mode" size="small">
      <el-radio-button label="form">JSON 表单</el-radio-button>
      <el-radio-button label="raw">Raw JSON</el-radio-button>
    </el-radio-group>

    <div v-if="mode === 'form'" class="body-table">
      <el-table :data="rows" size="small" border>
        <el-table-column label="Key" min-width="180">
          <template #default="{ row }">
            <el-input v-model="row.key" placeholder="字段名，支持 data.name" @input="emitFormValue" />
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-select v-model="row.type" @change="emitFormValue">
              <el-option label="String" value="string" />
              <el-option label="Number" value="number" />
              <el-option label="Boolean" value="boolean" />
              <el-option label="JSON" value="json" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="Value" min-width="240">
          <template #default="{ row }">
            <el-input v-model="row.value" placeholder="Value，支持 ${token}" @input="emitFormValue" />
          </template>
        </el-table-column>
        <el-table-column width="72" align="center">
          <template #default="{ $index }">
            <el-button text type="danger" @click="removeRow($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="editor-actions">
        <el-button size="small" @click="addRow">添加字段</el-button>
        <el-button size="small" @click="insertVariable('${token}')">插入 ${token}</el-button>
      </div>
    </div>

    <div v-else class="raw-box">
      <el-input v-model="rawText" type="textarea" :rows="10" spellcheck="false" @input="applyRaw" />
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <div class="editor-actions">
        <el-button size="small" @click="formatRaw">格式化</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 请求体编辑器组件，负责维护接口请求 payload，支持“表单化键值录入”和“Raw JSON”两种编辑方式。
 * 2. 该组件被 RequestConfigEditor 聚合后供用例、场景步骤等页面复用，帮助业务页面避免重复实现 JSON 录入逻辑。
 * 3. 内部主要处理对象拍平、路径回填、类型推断与 JSON 文本互转，确保前端编辑体验与后端数据结构保持一致。
 */
import { nextTick, ref, watch } from 'vue'

const model = defineModel({ default: () => ({}) })
const mode = ref('form')
const rows = ref([])
const rawText = ref('{}')
const error = ref('')
let syncing = false

function setByPath(target, path, value) {
  const parts = path.split('.').filter(Boolean)
  let cursor = target
  parts.forEach((part, index) => {
    if (index === parts.length - 1) {
      cursor[part] = value
      return
    }
    cursor[part] = cursor[part] && typeof cursor[part] === 'object' && !Array.isArray(cursor[part]) ? cursor[part] : {}
    cursor = cursor[part]
  })
}

function flatten(value, prefix = '') {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return []
  }
  return Object.entries(value).flatMap(([key, item]) => {
    const path = prefix ? `${prefix}.${key}` : key
    if (item && typeof item === 'object' && !Array.isArray(item)) {
      return flatten(item, path)
    }
    return [{ key: path, type: inferType(item), value: stringifyValue(item) }]
  })
}

function inferType(value) {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  if (value && typeof value === 'object') return 'json'
  return 'string'
}

function stringifyValue(value) {
  if (value == null) return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function parseValue(row) {
  if (row.type === 'number') {
    const number = Number(row.value)
    return Number.isNaN(number) ? row.value : number
  }
  if (row.type === 'boolean') return row.value === true || row.value === 'true'
  if (row.type === 'json') {
    try {
      return JSON.parse(row.value || 'null')
    } catch {
      return row.value
    }
  }
  return row.value
}

function rowsToObject() {
  const target = {}
  rows.value.forEach(row => {
    if (row.key.trim()) {
      setByPath(target, row.key.trim(), parseValue(row))
    }
  })
  return target
}

function refresh(value) {
  rows.value = flatten(value)
  rawText.value = JSON.stringify(value ?? {}, null, 2)
  error.value = ''
}

function emitFormValue() {
  syncing = true
  model.value = rowsToObject()
  rawText.value = JSON.stringify(model.value, null, 2)
  nextTick(() => {
    syncing = false
  })
}

function applyRaw() {
  try {
    const next = JSON.parse(rawText.value || '{}')
    error.value = ''
    syncing = true
    model.value = next
    rows.value = flatten(next)
    nextTick(() => {
      syncing = false
    })
  } catch (err) {
    error.value = `JSON 格式错误：${err.message}`
  }
}

function formatRaw() {
  applyRaw()
  if (!error.value) rawText.value = JSON.stringify(model.value ?? {}, null, 2)
}

function addRow() {
  rows.value.push({ key: '', type: 'string', value: '' })
}

function removeRow(index) {
  rows.value.splice(index, 1)
  emitFormValue()
}

function insertVariable(token) {
  rows.value.push({ key: 'token', type: 'string', value: token })
  emitFormValue()
}

watch(
  model,
  value => {
    if (!syncing) refresh(value)
  },
  { immediate: true, deep: true }
)
</script>

<style scoped>
.body-table,
.raw-box {
  margin-top: 10px;
}
.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.raw-box :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
