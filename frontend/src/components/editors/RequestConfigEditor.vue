<template>
  <div class="request-config-editor">
    <div class="editor-main">
      <VariablePicker :options="variableOptions" @insert="insertVariable" />
      <el-tabs v-model="activeForm">
        <el-tab-pane label="Headers" name="headers">
          <KeyValueEditor v-model="header" />
        </el-tab-pane>
        <el-tab-pane label="Payload" name="payload">
          <JsonBodyEditor v-model="payload" />
        </el-tab-pane>
        <el-tab-pane label="Expect" name="expect">
          <AssertionEditor v-model="expect" />
        </el-tab-pane>
        <el-tab-pane label="提取变量" name="extractors">
          <ExtractorEditor v-model="extractors" />
        </el-tab-pane>
      </el-tabs>
    </div>
    <div class="json-panel">
      <div class="json-title">
        <span>高级 JSON</span>
        <el-select v-model="activeJson" size="small" style="width: 130px" @change="refreshJson">
          <el-option label="Header" value="header" />
          <el-option label="Payload" value="payload" />
          <el-option label="Expect" value="expect" />
          <el-option label="Extractors" value="extractors" />
        </el-select>
      </div>
      <el-input v-model="jsonText" type="textarea" :rows="18" spellcheck="false" @input="applyJson" />
      <el-alert v-if="jsonError" :title="jsonError" type="error" :closable="false" show-icon />
      <div class="editor-actions">
        <el-button size="small" @click="formatJson">格式化</el-button>
        <el-button size="small" @click="copyJson">复制</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { nextTick, ref, watch } from 'vue'
import AssertionEditor from './AssertionEditor.vue'
import ExtractorEditor from './ExtractorEditor.vue'
import JsonBodyEditor from './JsonBodyEditor.vue'
import KeyValueEditor from './KeyValueEditor.vue'
import VariablePicker from './VariablePicker.vue'

const header = defineModel('header', { type: Object, default: () => ({}) })
const payload = defineModel('payload', { default: () => ({}) })
const expect = defineModel('expect', { type: Object, default: () => ({}) })
const extractors = defineModel('extractors', { type: Array, default: () => [] })

defineProps({
  variableOptions: {
    type: Array,
    default: () => ['${token}', '${uid}', '${uid_str}', '${LOGIN_001.data.token}']
  }
})

const activeForm = ref('headers')
const activeJson = ref('header')
const jsonText = ref('{}')
const jsonError = ref('')
let syncingJson = false

function activeModel() {
  return {
    header,
    payload,
    expect,
    extractors
  }[activeJson.value]
}

function refreshJson() {
  jsonText.value = JSON.stringify(activeModel().value ?? (activeJson.value === 'extractors' ? [] : {}), null, 2)
  jsonError.value = ''
}

function applyJson() {
  try {
    const next = JSON.parse(jsonText.value || (activeJson.value === 'extractors' ? '[]' : '{}'))
    jsonError.value = ''
    syncingJson = true
    activeModel().value = next
    nextTick(() => {
      syncingJson = false
    })
  } catch (error) {
    jsonError.value = `JSON 格式错误：${error.message}`
  }
}

function formatJson() {
  applyJson()
  if (!jsonError.value) refreshJson()
}

async function copyJson() {
  await navigator.clipboard.writeText(jsonText.value)
  ElMessage.success('JSON 已复制')
}

function insertVariable(token) {
  if (activeForm.value === 'headers') {
    header.value = { ...(header.value || {}), Authorization: `Bearer ${token}` }
  } else if (activeForm.value === 'payload') {
    payload.value = { ...(payload.value || {}), value: token }
  } else if (activeForm.value === 'expect') {
    expect.value = {
      __assertions: [
        ...((expect.value || {}).__assertions || []),
        { type: 'jsonpath', path: 'data.token', operator: 'equals', value: token }
      ]
    }
  } else {
    extractors.value = [...(extractors.value || []), { name: token.replace(/[${}]/g, ''), path: 'data.token', required: false }]
  }
}

watch([header, payload, expect, extractors], () => {
  if (!syncingJson) refreshJson()
}, { deep: true })

watch(activeJson, refreshJson, { immediate: true })
</script>

<style scoped>
.request-config-editor {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 16px;
  align-items: start;
}
.editor-main,
.json-panel {
  min-width: 0;
}
.json-panel {
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.json-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
  font-weight: 700;
}
.json-panel :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 10px;
}
@media (max-width: 980px) {
  .request-config-editor {
    grid-template-columns: 1fr;
  }
}
</style>
