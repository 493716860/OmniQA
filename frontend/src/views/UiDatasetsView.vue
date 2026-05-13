<template>
  <section>
    <h1 class="page-title">数据集（DDT）</h1>

    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索数据集" clearable style="width: 240px" @keyup.enter="load" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" @click="openCreate">新增数据集</el-button>
      </div>

      <el-table :data="rows" @row-click="openEdit">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="name" label="数据集名称" />
        <el-table-column prop="rows_count" label="行数" width="90" />
        <el-table-column label="敏感字段" width="220">
          <template #default="{ row }">
            <el-tag v-for="k in (row.schema?.sensitive_fields || [])" :key="k" size="small" style="margin-right:6px;">
              {{ k }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click.stop="removeDataset(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="rows.length === 0" description="暂无数据集" />
    </div>

    <FullScreenDrawer v-model="visible" :title="form.id ? '编辑数据集' : '新增数据集'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="form.project" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="敏感字段">
          <el-input v-model="sensitiveText" placeholder="password,token" />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>

      <div class="panel" style="margin-top:16px;">
        <div class="toolbar">
          <strong>数据行（JSON）</strong>
          <el-button size="small" type="primary" @click="openRowCreate" :disabled="!form.id">新增一行</el-button>
          <el-button size="small" @click="loadRows" :disabled="!form.id">刷新</el-button>
        </div>
        <el-alert v-if="!form.id" type="warning" :closable="false" title="请先保存数据集，再新增数据行" show-icon />
        <el-table :data="datasetRows" size="small">
          <el-table-column prop="id" label="ID" width="90" />
          <el-table-column prop="row_key" label="row_key" width="180" />
          <el-table-column label="数据预览">
            <template #default="{ row }">
              <code>{{ maskedPreview(row.data) }}</code>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="openRowEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="removeRow(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="drawer-footer">
        <el-button @click="visible=false">关闭</el-button>
        <el-button type="primary" @click="saveDataset">保存数据集</el-button>
      </div>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="rowVisible" :title="rowForm.id ? '编辑数据行' : '新增数据行'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="row_key"><el-input v-model="rowForm.row_key" placeholder="可选：手机号/用户ID" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="rowForm.enabled" /></el-form-item>
        <el-form-item label="data(JSON)">
          <el-input v-model="rowForm.dataText" type="textarea" :rows="10" placeholder='例如：{"username":"u1","password":"p1"}' />
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="rowVisible=false">取消</el-button>
        <el-button type="primary" @click="saveRow">保存</el-button>
      </div>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. UI 数据集管理页面，用于维护 DDT（数据驱动测试）所需的数据集及数据行，并支持敏感字段脱敏预览。
 * 2. 页面依赖 uiDatasetApi 与 uiDatasetRowApi，和 UiScenariosView 的运行配置直接关联，为 UI 场景提供批量执行输入数据。
 * 3. 该页面主要管理测试数据资产，不参与实际执行逻辑；真实运行时由 UI Run/UI Task 模块按数据行拆分子任务。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { projectApi, uiDatasetApi, uiDatasetRowApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'

const projects = ref([])
const data = ref([])
const datasetRows = ref([])

const filters = reactive({ project: null, keyword: '' })
const visible = ref(false)
const rowVisible = ref(false)

const form = reactive({ id: null, project: null, name: '', schema: {}, enabled: true })
const sensitiveText = ref('')

const rowForm = reactive({ id: null, dataset: null, row_key: '', enabled: true, dataText: '{}' })

const rows = computed(() => data.value.results || data.value || [])

function parseSensitive(text) {
  return text ? text.split(',').map(v => v.trim()).filter(Boolean) : []
}
function safeJson(text, fallback = {}) {
  try {
    return text ? JSON.parse(text) : fallback
  } catch (e) {
    throw new Error('JSON 格式错误')
  }
}

function maskedPreview(obj) {
  const sensitive = new Set(parseSensitive(sensitiveText.value))
  const out = {}
  Object.entries(obj || {}).forEach(([k, v]) => {
    out[k] = sensitive.has(k) ? '******' : v
  })
  const text = JSON.stringify(out)
  return text.length > 220 ? text.slice(0, 220) + '...' : text
}

async function load() {
  const p = await projectApi.list()
  projects.value = p.results || p
  data.value = await uiDatasetApi.list({ project: filters.project || undefined, keyword: filters.keyword || undefined })
}

async function loadRows() {
  if (!form.id) return
  const res = await uiDatasetRowApi.list({ dataset: form.id })
  datasetRows.value = res.results || res
}

function openCreate() {
  Object.assign(form, { id: null, project: filters.project || projects.value[0]?.id || null, name: '', schema: {}, enabled: true })
  sensitiveText.value = ''
  datasetRows.value = []
  visible.value = true
}

async function openEdit(row) {
  Object.assign(form, { id: row.id, project: row.project, name: row.name, schema: row.schema || {}, enabled: row.enabled !== false })
  sensitiveText.value = (row.schema?.sensitive_fields || []).join(',')
  visible.value = true
  await loadRows()
}

async function saveDataset() {
  const schema = { ...(form.schema || {}), sensitive_fields: parseSensitive(sensitiveText.value) }
  const payload = { project: form.project, name: form.name, enabled: form.enabled, schema }
  if (form.id) await uiDatasetApi.update(form.id, payload)
  else {
    const created = await uiDatasetApi.create(payload)
    form.id = created.id
  }
  ElMessage.success('已保存')
  await load()
  await loadRows()
}

async function removeDataset(row) {
  await ElMessageBox.confirm(`删除数据集 ${row.name}?`)
  await uiDatasetApi.remove(row.id)
  await load()
}

function openRowCreate() {
  Object.assign(rowForm, { id: null, dataset: form.id, row_key: '', enabled: true, dataText: '{}' })
  rowVisible.value = true
}
function openRowEdit(row) {
  Object.assign(rowForm, { id: row.id, dataset: form.id, row_key: row.row_key || '', enabled: row.enabled !== false, dataText: JSON.stringify(row.data || {}, null, 2) })
  rowVisible.value = true
}
async function saveRow() {
  let dataJson = {}
  try {
    dataJson = safeJson(rowForm.dataText, {})
  } catch (e) {
    ElMessage.error(String(e.message || e))
    return
  }
  const payload = { dataset: form.id, row_key: rowForm.row_key, enabled: rowForm.enabled, data: dataJson }
  if (rowForm.id) await uiDatasetRowApi.update(rowForm.id, payload)
  else await uiDatasetRowApi.create(payload)
  ElMessage.success('已保存')
  rowVisible.value = false
  await loadRows()
}
async function removeRow(row) {
  await ElMessageBox.confirm(`删除数据行 #${row.id}?`)
  await uiDatasetRowApi.remove(row.id)
  await loadRows()
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
  z-index: 2;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  background: #fff;
  border-top: 1px solid #e5e7eb;
}
</style>
