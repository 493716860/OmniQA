<template>
  <section>
    <h1 class="page-title">接口管理</h1>
    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.module" placeholder="模块" clearable style="width: 180px">
          <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索接口" clearable style="width: 240px" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" @click="openCreate">新增接口</el-button>
        <el-button type="success" plain @click="openCurlImport">导入 cURL</el-button>
      </div>
      <el-table :data="rows">
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="name" label="接口名称" />
        <el-table-column prop="method" label="方法" width="100" />
        <el-table-column prop="path" label="路径" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <FullScreenDrawer v-model="visible" :title="form.id ? '编辑接口' : '新增接口'">
      <el-form class="drawer-form" label-width="100px">
        <el-form-item label="模块">
          <el-select v-model="form.module" style="width: 100%">
            <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="方法">
          <el-select v-model="form.method" style="width: 100%">
            <el-option v-for="m in methods" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="路径"><el-input v-model="form.path" placeholder="支持 ${环境变量} 格式，如 ${host_account}/api/v1/login" /></el-form-item>
        <el-form-item label="默认Header">
          <KeyValueEditor v-model="form.default_headers" />
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button type="success" plain @click="openDebug" style="margin-right: auto;">调试 (Debug)</el-button>
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
    </FullScreenDrawer>

    <!-- 新增接口调试弹窗：之前只有 openDebug/sendDebug 逻辑但没有 UI，导致“点了没反应” -->
    <el-dialog v-model="debugVisible" title="接口调试" width="880px">
      <el-form label-width="90px">
        <el-form-item label="运行环境">
          <el-select v-model="debugForm.environment_id" style="width: 100%">
            <el-option v-for="e in envs" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="临时Body">
          <el-input
            v-model="debugForm.payload"
            type="textarea"
            :rows="4"
            placeholder="（可选）输入 JSON 格式的临时请求体用于测试；GET 请求可直接填 query 的 JSON 对象"
          />
        </el-form-item>
      </el-form>

      <div v-if="debugResult" class="debug-result">
        <div class="status-bar">
          <el-tag :type="debugResult.status >= 200 && debugResult.status < 300 ? 'success' : 'danger'">
            {{ debugResult.status || 'ERROR' }}
          </el-tag>
          <span class="time">{{ debugResult.duration_ms || 0 }} ms</span>
          <span class="url" :title="debugResult.url">{{ debugResult.url }}</span>
        </div>
        <pre class="response-body">{{ debugResult.body || debugResult.error || '无响应内容' }}</pre>
      </div>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="debugVisible = false">关闭</el-button>
          <el-button type="success" plain :loading="debugLoading" @click="sendDebug">发送调试</el-button>
        </span>
      </template>
    </el-dialog>

    <FullScreenDrawer v-model="curlVisible" title="导入 cURL">
      <el-form class="drawer-form" label-width="110px">
        <el-form-item label="目标模块">
          <el-select v-model="curlForm.module" style="width: 100%" @change="resetCurlPreview">
            <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口名称">
          <el-input v-model="curlForm.name" placeholder="可选，留空时自动生成" @input="resetCurlPreview" />
        </el-form-item>
        <el-form-item label="默认用例标题">
          <el-input v-model="curlForm.case_title" placeholder="可选，留空时与接口名称一致" @input="resetCurlPreview" />
        </el-form-item>
        <el-form-item label="cURL">
          <el-input
            v-model="curlForm.curl_text"
            type="textarea"
            :rows="8"
            placeholder="请粘贴浏览器 F12 复制的 curl 命令"
            spellcheck="false"
            @input="resetCurlPreview"
          />
        </el-form-item>
      </el-form>

      <div v-if="curlPreview" class="curl-preview">
        <div class="preview-header">
          <strong>解析预览</strong>
          <el-tag size="small" :type="curlPreview.action.api_definition === 'created' ? 'success' : 'warning'">
            {{ apiActionText(curlPreview.action.api_definition) }}
          </el-tag>
          <el-tag size="small" :type="curlPreview.action.api_case === 'created' ? 'success' : 'warning'">
            {{ caseActionText(curlPreview.action.api_case) }}
          </el-tag>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="方法">{{ curlPreview.parsed.method }}</el-descriptions-item>
          <el-descriptions-item label="Path">{{ curlPreview.parsed.path }}</el-descriptions-item>
          <el-descriptions-item label="完整 URL" :span="2">{{ curlPreview.parsed.url }}</el-descriptions-item>
          <el-descriptions-item label="Header 数量">{{ Object.keys(curlPreview.parsed.headers || {}).length }}</el-descriptions-item>
          <el-descriptions-item label="Content-Type">{{ curlPreview.parsed.content_type || '-' }}</el-descriptions-item>
          <el-descriptions-item label="Body 摘要" :span="2">{{ summarizePayload(curlPreview.api_case.payload) }}</el-descriptions-item>
        </el-descriptions>

        <div class="curl-debug-section">
          <div class="section-header">
            <strong>在线调试</strong>
          </div>
          <el-form label-width="90px">
            <el-form-item label="运行环境">
              <el-select v-model="curlDebugForm.environment_id" style="width: 100%">
                <el-option v-for="e in envs" :key="e.id" :label="e.name" :value="e.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="临时Body">
              <el-input
                v-model="curlDebugForm.payload"
                type="textarea"
                :rows="4"
                placeholder="（可选）输入 JSON 格式的临时请求体用于测试"
              />
            </el-form-item>
          </el-form>
          <div v-if="curlDebugResult" class="debug-result">
            <div class="status-bar">
              <el-tag :type="curlDebugResult.status >= 200 && curlDebugResult.status < 300 ? 'success' : 'danger'">
                {{ curlDebugResult.status || 'ERROR' }}
              </el-tag>
              <span class="time">{{ curlDebugResult.duration_ms || 0 }} ms</span>
              <span class="url" :title="curlDebugResult.url">{{ curlDebugResult.url }}</span>
            </div>
            <pre class="response-body">{{ curlDebugResult.body || curlDebugResult.error || '无响应内容' }}</pre>
          </div>
        </div>
      </div>

      <div class="drawer-footer">
        <el-button type="success" plain :disabled="!curlPreview" :loading="curlDebugLoading" @click="sendCurlDebug">调试</el-button>
        <el-button @click="curlVisible = false">取消</el-button>
        <el-button @click="previewCurl" :loading="curlPreviewLoading">解析</el-button>
        <el-button type="primary" :disabled="!curlPreview" @click="submitCurlImport">导入并生成默认用例</el-button>
      </div>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 接口定义管理页面，负责维护接口基础信息、默认请求头，并支持基于 cURL 的快速导入和在线调试。
 * 2. 页面依赖 apiDefinitionApi、moduleApi、environmentApi 与 importApi，是接口资产层的核心入口，其结果会被用例、场景和计划模块引用。
 * 3. 这里维护的是“接口模板”而非具体执行实例，CasesView 会在其基础上扩展出带断言、提取和依赖关系的测试用例。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiDefinitionApi, importApi, moduleApi, environmentApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'
import KeyValueEditor from '../components/editors/KeyValueEditor.vue'

const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const data = ref([])
const modules = ref([])
const envs = ref([])
const visible = ref(false)
const curlVisible = ref(false)
const debugVisible = ref(false)
const debugLoading = ref(false)
const curlDebugLoading = ref(false)
const curlPreviewLoading = ref(false)

const filters = reactive({ module: null, keyword: '' })
const form = reactive({ id: null, module: null, name: '', method: 'POST', path: '', default_headers: {} })
const curlForm = reactive({ module: null, name: '', case_title: '', curl_text: '' })
const debugForm = reactive({ environment_id: null, payload: '' })
const curlDebugForm = reactive({ environment_id: null, payload: '' })
const curlPreview = ref(null)
const debugResult = ref(null)
const curlDebugResult = ref(null)

const rows = computed(() => data.value.results || data.value || [])

async function load() {
  data.value = await apiDefinitionApi.list(filters)
  const moduleData = await moduleApi.list()
  modules.value = moduleData.results || moduleData
}

function openCreate() {
  Object.assign(form, { id: null, module: modules.value[0]?.id || null, name: '', method: 'POST', path: '', default_headers: {} })
  visible.value = true
}

// ---- 新增调试逻辑 ----
async function openDebug() {
  if (!form.path) {
    ElMessage.warning('请先填写接口路径')
    return
  }
  debugVisible.value = true
  debugResult.value = null
  const eData = await environmentApi.list()
  envs.value = eData.results || eData
  if (envs.value.length > 0 && !debugForm.environment_id) {
    debugForm.environment_id = envs.value[0].id
  }
}

async function sendDebug() {
  debugLoading.value = true
  debugResult.value = null
  try {
    let parsedPayload = null
    if (debugForm.payload) {
      try { parsedPayload = JSON.parse(debugForm.payload) }
      catch { parsedPayload = debugForm.payload }
    }
    const res = await apiDefinitionApi.debug({
      method: form.method,
      path: form.path,
      headers: form.default_headers,
      environment_id: debugForm.environment_id,
      payload: parsedPayload
    })
    debugResult.value = res
  } catch (e) {
    debugResult.value = e.response?.data || { error: e.message }
  } finally {
    debugLoading.value = false
  }
}
// ----------------------

async function openCurlImport() {
  Object.assign(curlForm, { module: filters.module || modules.value[0]?.id || null, name: '', case_title: '', curl_text: '' })
  Object.assign(curlDebugForm, { environment_id: null, payload: '' })
  curlPreview.value = null
  curlDebugResult.value = null
  curlVisible.value = true
  const eData = await environmentApi.list()
  envs.value = eData.results || eData
  if (envs.value.length > 0 && !curlDebugForm.environment_id) {
    curlDebugForm.environment_id = envs.value[0].id
  }
}

function openEdit(row) {
  Object.assign(form, { ...row, default_headers: { ...(row.default_headers || {}) } })
  visible.value = true
}

function resetCurlPreview() {
  curlPreview.value = null
}

async function save() {
  const payload = { ...form, default_headers: form.default_headers || {} }
  if (form.id) await apiDefinitionApi.update(form.id, payload)
  else await apiDefinitionApi.create(payload)
  ElMessage.success('已保存')
  visible.value = false
  await load()
}

async function previewCurl() {
  if (!curlForm.module) return ElMessage.warning('请选择目标模块')
  if (!curlForm.curl_text.trim()) return ElMessage.warning('请先粘贴 cURL 内容')
  curlPreviewLoading.value = true
  try {
    curlPreview.value = await importApi.curl({ ...curlForm, dry_run: true })
    curlDebugResult.value = null
  } finally {
    curlPreviewLoading.value = false
  }
}

async function sendCurlDebug() {
  if (!curlPreview.value) return ElMessage.warning('请先解析 cURL')
  curlDebugLoading.value = true
  curlDebugResult.value = null
  try {
    const parsed = curlPreview.value.parsed
    let parsedBody = null
    if (curlDebugForm.payload) {
      try { parsedBody = JSON.parse(curlDebugForm.payload) }
      catch { parsedBody = curlDebugForm.payload }
    } else if (parsed.payload && Object.keys(parsed.payload).length > 0) {
      parsedBody = parsed.payload
    }

    // 把 cURL 的 base_url/query/body 组合成后端可识别的“用例格式”
    // 这样 GET 请求也能带上 query params（否则很多接口会“调试不通”）
    const payload = {
      __base_url: parsed.base_url,
      __query: parsed.query || {},
      __body: parsedBody
    }

    const res = await apiDefinitionApi.debug({
      method: parsed.method,
      // 只传 path，让后端用 payload.__base_url 或 environment.base_url 拼接；避免 query 丢失/重复
      path: parsed.path,
      headers: parsed.headers,
      environment_id: curlDebugForm.environment_id,
      payload
    })
    curlDebugResult.value = res
  } catch (e) {
    curlDebugResult.value = e.response?.data || { error: e.message }
  } finally {
    curlDebugLoading.value = false
  }
}

async function submitCurlImport() {
  if (!curlPreview.value) return ElMessage.warning('请先解析 cURL')
  const result = await importApi.curl(curlForm)
  curlVisible.value = false
  ElMessage.success(`已${apiActionText(result.action.api_definition)}接口，并${caseActionText(result.action.api_case)}默认用例`)
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`删除接口 ${row.name}?`)
  await apiDefinitionApi.remove(row.id)
  await load()
}

function apiActionText(action) {
  return {
    created: '新建',
    updated: '更新',
    reused: '复用'
  }[action] || '处理'
}

function caseActionText(action) {
  return {
    created: '生成',
    updated: '更新',
    reused: '复用'
  }[action] || '处理'
}

function summarizePayload(payload) {
  if (payload == null || payload === '') return '无请求体'
  if (typeof payload === 'string') return payload.length > 140 ? `${payload.slice(0, 140)}...` : payload
  try {
    const text = JSON.stringify(payload)
    return text.length > 140 ? `${text.slice(0, 140)}...` : text
  } catch {
    return String(payload)
  }
}

onMounted(load)
</script>

<style scoped>
.drawer-form {
  padding-right: 8px;
}
.drawer-footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
  padding: 14px 0 0;
  background: #fff;
  z-index: 10;
  border-top: 1px solid #e2e8f0;
}
.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
/* 调试面板样式 */
.debug-result {
  margin-top: 16px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  overflow: hidden;
}
.status-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  background: #f8fafc;
  border-bottom: 1px solid #e2e8f0;
  font-size: 13px;
}
.status-bar .time {
  color: #64748b;
  font-weight: 500;
}
.status-bar .url {
  color: #94a3b8;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.response-body {
  margin: 0;
  padding: 14px;
  max-height: 300px;
  overflow: auto;
  background: #1e293b;
  color: #f8fafc;
  font-family: monospace;
  font-size: 13px;
}
/* cURL 预览和调试样式 */
.curl-preview {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}
.preview-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}
.curl-debug-section {
  margin-top: 16px;
  padding: 16px;
  background: #fafafa;
  border-radius: 6px;
}
.section-header {
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #e2e8f0;
}
</style>
