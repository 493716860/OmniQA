<template>
  <div class="assertion-editor">
    <el-tabs v-model="mode">
      <el-tab-pane label="可视化规则" name="visual">
        <el-table :data="rules" size="small" border>
          <el-table-column label="断言类型" width="140">
            <template #default="{ row }">
              <el-select v-model="row.type" @change="emitRules">
                <el-option label="状态码" value="status_code" />
                <el-option label="字段断言" value="jsonpath" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="字段路径" min-width="180">
            <template #default="{ row }">
              <el-input v-model="row.path" :disabled="row.type === 'status_code'" placeholder="code / data.user.name / $.data.items[0].id" @input="emitRules" />
            </template>
          </el-table-column>
          <el-table-column label="比较符" width="130">
            <template #default="{ row }">
              <el-select v-model="row.operator" @change="emitRules">
                <el-option label="等于" value="equals" />
                <el-option label="存在" value="exists" />
                <el-option label="包含" value="contains" />
                <el-option label="非空" value="not_empty" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="期望值" min-width="180">
            <template #default="{ row }">
              <el-input
                v-model="row.value"
                :disabled="['exists', 'not_empty'].includes(row.operator)"
                placeholder='0 / success / {"id":1} / [1,2]'
                @input="emitRules"
              />
            </template>
          </el-table-column>
          <el-table-column width="72" align="center">
            <template #default="{ $index }">
              <el-button text type="danger" @click="removeRule($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div class="editor-actions">
          <el-button size="small" @click="addStatusCode">状态码等于 200</el-button>
          <el-button size="small" @click="addCodeOk">code 等于 0</el-button>
          <el-button size="small" @click="addFieldExists">字段存在</el-button>
          <el-button size="small" @click="addFieldNotEmpty">字段非空</el-button>
          <el-button size="small" @click="addObjectEquals">多层对象等于</el-button>
        </div>
      </el-tab-pane>
      <el-tab-pane label="高级 JSON" name="raw">
        <el-input v-model="rawText" type="textarea" :rows="10" spellcheck="false" @input="applyRaw" />
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <div class="editor-actions">
          <el-button size="small" @click="formatRaw">格式化</el-button>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'

const model = defineModel({ type: Object, default: () => ({}) })
const mode = ref('visual')
const rules = ref([])
const rawText = ref('{}')
const error = ref('')
let syncing = false

function normalizeRules(value) {
  if (Array.isArray(value?.__assertions)) {
    return value.__assertions.map(item => ({
      type: item.type || 'jsonpath',
      path: item.path || '',
      operator: item.operator || 'equals',
      value: stringifyValue(item.value)
    }))
  }
  const normalized = []
  if (value && Object.prototype.hasOwnProperty.call(value, 'status_code')) {
    normalized.push({ type: 'status_code', path: '', operator: 'equals', value: stringifyValue(value.status_code) })
  }
  Object.entries(value || {}).forEach(([key, val]) => {
    if (key !== 'status_code') {
      normalized.push({ type: 'jsonpath', path: denormalizePath(key), operator: 'equals', value: stringifyValue(val) })
    }
  })
  return normalized
}

function stringifyValue(value) {
  if (value == null) return ''
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function denormalizePath(path) {
  return String(path || '').replace(/^\$\./, '')
}

function parseValue(value) {
  if (value === 'true') return true
  if (value === 'false') return false
  if (value !== '' && !Number.isNaN(Number(value))) return Number(value)
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function buildExpect() {
  const active = rules.value.filter(row => row.type === 'status_code' || row.path.trim())
  return {
    __assertions: active.map(row => ({
      type: row.type,
      path: row.type === 'status_code' ? '' : denormalizePath(row.path.trim()),
      operator: row.operator,
      value: ['exists', 'not_empty'].includes(row.operator) ? true : parseValue(row.value)
    }))
  }
}

function refresh(value) {
  rules.value = normalizeRules(value)
  rawText.value = JSON.stringify(value || {}, null, 2)
  error.value = ''
}

function emitRules() {
  syncing = true
  model.value = buildExpect()
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
    rules.value = normalizeRules(next)
    nextTick(() => {
      syncing = false
    })
  } catch (err) {
    error.value = `JSON 格式错误：${err.message}`
  }
}

function formatRaw() {
  applyRaw()
  if (!error.value) rawText.value = JSON.stringify(model.value || {}, null, 2)
}

function addStatusCode() {
  rules.value.push({ type: 'status_code', path: '', operator: 'equals', value: '200' })
  emitRules()
}

function addCodeOk() {
  rules.value.push({ type: 'jsonpath', path: 'code', operator: 'equals', value: '0' })
  emitRules()
}

function addFieldExists() {
  rules.value.push({ type: 'jsonpath', path: 'data.token', operator: 'exists', value: '' })
  emitRules()
}

function addFieldNotEmpty() {
  rules.value.push({ type: 'jsonpath', path: 'data.list', operator: 'not_empty', value: '' })
  emitRules()
}

function addObjectEquals() {
  rules.value.push({ type: 'jsonpath', path: 'data.user', operator: 'equals', value: '{"id":1,"name":"demo"}' })
  emitRules()
}

function removeRule(index) {
  rules.value.splice(index, 1)
  emitRules()
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
.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
.assertion-editor :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
