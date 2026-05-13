<template>
  <section>
    <h1 class="page-title">页面对象（PO）</h1>

    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索页面" clearable style="width: 240px" @keyup.enter="load" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" @click="openCreate">新增页面</el-button>
      </div>

      <el-table :data="rows" @row-click="openEdit">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="name" label="页面名" width="200" />
        <el-table-column prop="url" label="URL" />
        <el-table-column prop="elements_count" label="元素" width="80" />
        <el-table-column prop="methods_count" label="方法" width="80" />
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click.stop="removePage(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="rows.length === 0" description="暂无页面对象" />
    </div>

    <FullScreenDrawer v-model="visible" :title="form.id ? '编辑页面' : '新增页面'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="form.project" style="width: 100%" @change="loadModules">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-select v-model="form.module" clearable style="width: 100%">
            <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="页面名"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="URL"><el-input v-model="form.url" placeholder="https://xxx/login" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>

      <el-tabs v-model="activeTab" style="margin-top:12px;">
        <el-tab-pane label="元素库" name="elements">
          <div class="toolbar">
            <el-button size="small" type="primary" @click="openElementCreate" :disabled="!form.id">新增元素</el-button>
          </div>
          <el-alert v-if="!form.id" type="warning" :closable="false" title="请先保存页面，再新增元素/方法" show-icon />
          <el-table :data="elements" size="small">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="元素名" width="200" />
            <el-table-column label="定位器">
              <template #default="{ row }">
                <code>{{ row.locator?.strategy }}:{{ row.locator?.value }}</code>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="描述" />
            <el-table-column label="操作" width="180">
              <template #default="{ row }">
                <el-button size="small" @click="openElementEdit(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="removeElement(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="页面方法" name="methods">
          <div class="toolbar">
            <el-button size="small" type="primary" @click="openMethodCreate" :disabled="!form.id">新增方法</el-button>
          </div>
          <el-table :data="methods" size="small">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="方法名" width="240" />
            <el-table-column prop="steps_count" label="步骤数" width="90" />
            <el-table-column prop="description" label="描述" />
            <el-table-column label="操作" width="240">
              <template #default="{ row }">
                <el-button size="small" @click="openMethodEdit(row)">编辑</el-button>
                <el-button size="small" @click="openMethodSteps(row)">步骤</el-button>
                <el-button size="small" type="danger" @click="removeMethod(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>

      <div class="drawer-footer">
        <el-button @click="visible=false">关闭</el-button>
        <el-button type="primary" @click="savePage">保存页面</el-button>
      </div>
    </FullScreenDrawer>

    <!-- 元素编辑 -->
    <FullScreenDrawer v-model="elementVisible" :title="elementForm.id ? '编辑元素' : '新增元素'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="元素名"><el-input v-model="elementForm.name" /></el-form-item>
        <el-form-item label="策略">
          <el-select v-model="elementForm.locator.strategy" style="width: 140px">
            <el-option label="CSS" value="css" />
            <el-option label="Text" value="text" />
            <el-option label="Role" value="role" />
            <el-option label="XPath" value="xpath" />
          </el-select>
          <el-input v-model="elementForm.locator.value" style="flex:1;margin-left:8px;" placeholder=".btn-login / 登录" />
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="elementForm.description" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="elementForm.enabled" /></el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="elementVisible=false">取消</el-button>
        <el-button type="primary" @click="saveElement">保存</el-button>
      </div>
    </FullScreenDrawer>

    <!-- 方法编辑 -->
    <FullScreenDrawer v-model="methodVisible" :title="methodForm.id ? '编辑方法' : '新增方法'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="方法名"><el-input v-model="methodForm.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="methodForm.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="methodForm.enabled" /></el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="methodVisible=false">取消</el-button>
        <el-button type="primary" @click="saveMethod">保存</el-button>
      </div>
    </FullScreenDrawer>

    <!-- 方法步骤编辑 -->
    <FullScreenDrawer v-model="stepVisible" :title="activeMethod ? `方法步骤：${activeMethod.name}` : '方法步骤'">
      <div class="toolbar">
        <el-button size="small" type="primary" @click="openStepCreate" :disabled="!activeMethod">新增步骤</el-button>
        <el-button size="small" @click="loadMethodSteps" :disabled="!activeMethod">刷新</el-button>
      </div>
      <el-table :data="methodSteps" size="small">
        <el-table-column prop="sort_order" label="#" width="60" />
        <el-table-column prop="name" label="步骤名" width="200" />
        <el-table-column prop="type" label="类型" width="110" />
        <el-table-column prop="element_name" label="元素" width="180" />
        <el-table-column label="参数/断言">
          <template #default="{ row }">
            <code>{{ row.params }}</code>
            <div v-if="row.type === 'ASSERT'"><code>{{ row.assertions }}</code></div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button size="small" @click="openStepEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="removeStep(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="drawer-footer">
        <el-button @click="stepVisible=false">关闭</el-button>
      </div>
    </FullScreenDrawer>

    <!-- 步骤弹窗 -->
    <FullScreenDrawer v-model="stepEditVisible" :title="stepForm.id ? '编辑步骤' : '新增步骤'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="名称"><el-input v-model="stepForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="stepForm.type" style="width: 100%">
            <el-option label="打开页面" value="GOTO" />
            <el-option label="点击" value="CLICK" />
            <el-option label="输入" value="FILL" />
            <el-option label="按键" value="PRESS" />
            <el-option label="等待" value="WAIT" />
            <el-option label="断言" value="ASSERT" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="['CLICK','FILL','WAIT','ASSERT'].includes(stepForm.type)" label="元素">
          <el-select v-model="stepForm.element" clearable filterable style="width: 100%">
            <el-option v-for="e in elements" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="params(JSON)">
          <el-input v-model="stepForm.paramsText" type="textarea" :rows="4" placeholder='例如：{"value":"${username}","timeout_ms":10000}' />
        </el-form-item>
        <el-form-item v-if="stepForm.type==='ASSERT'" label="assertions(JSON)">
          <el-input v-model="stepForm.assertionsText" type="textarea" :rows="3" placeholder='例如：{"kind":"text_contains","value":"欢迎"}' />
        </el-form-item>
        <el-form-item label="排序"><el-input-number v-model="stepForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="stepForm.enabled" /></el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="stepEditVisible=false">取消</el-button>
        <el-button type="primary" @click="saveMethodStep">保存</el-button>
      </div>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. UI 页面对象（PO）管理页面，用于维护页面、元素、页面方法及方法步骤，是 UI 自动化资产建模的核心入口。
 * 2. 页面依赖 uiPageApi、uiElementApi、uiPageMethodApi、uiMethodStepApi，以及项目/模块数据，为 UiScenariosView 提供可编排的方法资产。
 * 3. 它承担 UI 自动化中的“对象层”职责，把底层定位器和交互步骤沉淀为可复用能力，减少场景编排页面的重复配置。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { moduleApi, projectApi, uiElementApi, uiMethodStepApi, uiPageApi, uiPageMethodApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'

const projects = ref([])
const modules = ref([])
const data = ref([])

const visible = ref(false)
const activeTab = ref('elements')

const form = reactive({ id: null, project: null, module: null, name: '', url: '', description: '', enabled: true })
const filters = reactive({ project: null, keyword: '' })

const elements = ref([])
const methods = ref([])

const elementVisible = ref(false)
const elementForm = reactive({ id: null, page: null, name: '', locator: { strategy: 'css', value: '' }, description: '', enabled: true })

const methodVisible = ref(false)
const methodForm = reactive({ id: null, page: null, name: '', description: '', enabled: true })

const stepVisible = ref(false)
const stepEditVisible = ref(false)
const activeMethod = ref(null)
const methodSteps = ref([])
const stepForm = reactive({ id: null, method: null, name: '', type: 'CLICK', element: null, sort_order: 0, enabled: true, paramsText: '{}', assertionsText: '{}' })

const rows = computed(() => data.value.results || data.value || [])

function safeJson(text, fallback = {}) {
  try {
    return text ? JSON.parse(text) : fallback
  } catch (e) {
    throw new Error('JSON 格式错误')
  }
}

async function loadProjects() {
  const p = await projectApi.list()
  projects.value = p.results || p
}
async function loadModules() {
  const m = await moduleApi.list({ project: form.project || filters.project || undefined })
  modules.value = m.results || m
}

async function load() {
  await loadProjects()
  data.value = await uiPageApi.list({ project: filters.project || undefined, keyword: filters.keyword || undefined })
}

async function loadChildren() {
  if (!form.id) return
  const elementRes = await uiElementApi.list({ page_id: form.id })
  elements.value = elementRes?.results ?? elementRes ?? []
  const methodRes = await uiPageMethodApi.list({ page_id: form.id })
  methods.value = methodRes?.results ?? methodRes ?? []
}

function openCreate() {
  Object.assign(form, { id: null, project: filters.project || projects.value[0]?.id || null, module: null, name: '', url: '', description: '', enabled: true })
  elements.value = []
  methods.value = []
  visible.value = true
  loadModules()
}

async function openEdit(row) {
  Object.assign(form, { id: row.id, project: row.project, module: row.module, name: row.name || '', url: row.url || '', description: row.description || '', enabled: row.enabled !== false })
  visible.value = true
  await loadModules()
  await loadChildren()
}

async function savePage() {
  const payload = { ...form }
  if (form.id) await uiPageApi.update(form.id, payload)
  else {
    const created = await uiPageApi.create(payload)
    form.id = created.id
  }
  ElMessage.success('已保存')
  await load()
  await loadChildren()
}

async function removePage(row) {
  await ElMessageBox.confirm(`删除页面 ${row.name}?`)
  await uiPageApi.remove(row.id)
  await load()
}

async function openElementCreate() {
  Object.assign(elementForm, { id: null, page: form.id, name: '', locator: { strategy: 'css', value: '' }, description: '', enabled: true })
  elementVisible.value = true
}
function openElementEdit(row) {
  Object.assign(elementForm, JSON.parse(JSON.stringify(row)))
  elementForm.page = form.id
  elementForm.locator = elementForm.locator || { strategy: 'css', value: '' }
  elementVisible.value = true
}
async function saveElement() {
  const payload = { ...elementForm, page: form.id }
  if (elementForm.id) await uiElementApi.update(elementForm.id, payload)
  else await uiElementApi.create(payload)
  ElMessage.success('元素已保存')
  elementVisible.value = false
  await loadChildren()
}
async function removeElement(row) {
  await ElMessageBox.confirm(`删除元素 ${row.name}?`)
  await uiElementApi.remove(row.id)
  await loadChildren()
}

function openMethodCreate() {
  Object.assign(methodForm, { id: null, page: form.id, name: '', description: '', enabled: true })
  methodVisible.value = true
}
function openMethodEdit(row) {
  Object.assign(methodForm, JSON.parse(JSON.stringify(row)))
  methodForm.page = form.id
  methodVisible.value = true
}
async function saveMethod() {
  const payload = { ...methodForm, page: form.id }
  if (methodForm.id) await uiPageMethodApi.update(methodForm.id, payload)
  else await uiPageMethodApi.create(payload)
  ElMessage.success('方法已保存')
  methodVisible.value = false
  await loadChildren()
}
async function removeMethod(row) {
  await ElMessageBox.confirm(`删除方法 ${row.name}?`)
  await uiPageMethodApi.remove(row.id)
  await loadChildren()
}

async function openMethodSteps(method) {
  activeMethod.value = method
  stepVisible.value = true
  await loadMethodSteps()
}
async function loadMethodSteps() {
  if (!activeMethod.value) return
  const res = await uiMethodStepApi.list({ method: activeMethod.value.id })
  methodSteps.value = res.results || res
}

function openStepCreate() {
  Object.assign(stepForm, { id: null, method: activeMethod.value.id, name: '', type: 'CLICK', element: null, sort_order: (methodSteps.value.length || 0) + 1, enabled: true, paramsText: '{}', assertionsText: '{}' })
  stepEditVisible.value = true
}
function openStepEdit(row) {
  Object.assign(stepForm, { id: row.id, method: row.method, name: row.name, type: row.type, element: row.element || null, sort_order: row.sort_order || 0, enabled: row.enabled !== false, paramsText: JSON.stringify(row.params || {}, null, 2), assertionsText: JSON.stringify(row.assertions || {}, null, 2) })
  stepEditVisible.value = true
}
async function saveMethodStep() {
  let params = {}
  let assertions = {}
  try {
    params = safeJson(stepForm.paramsText, {})
    assertions = safeJson(stepForm.assertionsText, {})
  } catch (e) {
    ElMessage.error(String(e.message || e))
    return
  }
  const payload = { method: activeMethod.value.id, name: stepForm.name, type: stepForm.type, element: stepForm.element, sort_order: stepForm.sort_order, enabled: stepForm.enabled, params, assertions }
  if (stepForm.id) await uiMethodStepApi.update(stepForm.id, payload)
  else await uiMethodStepApi.create(payload)
  ElMessage.success('步骤已保存')
  stepEditVisible.value = false
  await loadMethodSteps()
  await loadChildren()
}
async function removeStep(row) {
  await ElMessageBox.confirm(`删除步骤 ${row.name}?`)
  await uiMethodStepApi.remove(row.id)
  await loadMethodSteps()
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
