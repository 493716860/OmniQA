<template>
  <section>
    <h1 class="page-title">场景用例</h1>
    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" style="width:180px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索场景" clearable style="width: 220px" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" @click="openScenario()">新增场景</el-button>
      </div>
      <el-table :data="scenarioRows">
        <el-table-column prop="name" label="场景" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column prop="steps_count" label="步骤数" width="90" />
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button size="small" @click="openScenario(row)">编辑</el-button>
            <el-button size="small" type="success" @click="openSteps(row)">步骤</el-button>
            <el-button size="small" type="danger" @click="removeScenario(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="scenarioRows.length === 0" description="暂无场景用例" />
    </div>

    <FullScreenDrawer v-model="scenarioVisible" title="场景用例">
      <el-form class="drawer-form" label-width="80px">
        <el-form-item label="项目">
          <el-select v-model="scenarioForm.project" style="width:100%">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="scenarioForm.name" /></el-form-item>
        <el-form-item label="等级"><el-input-number v-model="scenarioForm.level" :min="1" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="scenarioForm.description" type="textarea" /></el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="scenarioVisible=false">取消</el-button>
        <el-button type="primary" @click="saveScenario">保存</el-button>
      </div>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="stepsVisible" :title="activeScenario?.name || '步骤'">
      <div class="toolbar">
        <el-button type="primary" @click="openStep()">新增步骤</el-button>
        <el-switch
          v-model="groupByCase"
          active-text="按用例分组"
          inactive-text="平铺列表"
          style="margin-left: 12px"
        />
      </div>

      <template v-if="!groupByCase">
        <el-table :data="steps">
          <el-table-column prop="sort_order" label="顺序" width="80" />
          <el-table-column prop="name" label="步骤" />
          <el-table-column label="来源" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.case_code" type="success" size="small">用例</el-tag>
              <el-tag v-else type="info" size="small">接口</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="case_code" label="引用用例" width="160" />
          <el-table-column prop="session_key" label="会话Key" width="120" />
          <el-table-column prop="api_method" label="方法" width="90" />
          <el-table-column prop="api_path" label="路径" />
          <el-table-column label="依赖" width="180">
            <template #default="{ row }">
              <el-tag v-for="name in row.dependency_names" :key="name" size="small">{{ name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="180">
            <template #default="{ row }">
              <el-button size="small" @click="openStep(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="removeStep(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else>
        <div v-for="group in groupedSteps" :key="group.key" class="step-group">
          <div class="step-group__title">
            <b>{{ group.label }}</b>
            <span v-if="group.subtitle" class="step-group__subtitle">{{ group.subtitle }}</span>
            <span class="step-group__count">{{ group.items.length }} 步</span>
          </div>
          <el-table :data="group.items" size="small">
            <el-table-column prop="sort_order" label="顺序" width="80" />
            <el-table-column prop="name" label="步骤" />
            <el-table-column prop="session_key" label="会话Key" width="120" />
            <el-table-column prop="api_method" label="方法" width="90" />
            <el-table-column prop="api_path" label="路径" />
            <el-table-column label="操作" width="160">
              <template #default="{ row }">
                <el-button size="small" @click="openStep(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="removeStep(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="stepVisible" title="场景步骤">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="名称"><el-input v-model="stepForm.name" /></el-form-item>
        <el-form-item label="来源">
          <el-radio-group v-model="stepForm.source">
            <el-radio-button label="case">引用用例</el-radio-button>
            <el-radio-button label="api">自定义接口</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="stepForm.source === 'case'" label="用例">
          <el-select v-model="stepForm.case_id" filterable style="width:100%" @change="onCaseChange">
            <el-option
              v-for="c in cases"
              :key="c.id"
              :label="`${c.case_code} ${c.subtitle || c.title}`"
              :value="c.id"
            />
          </el-select>
          <el-alert
            v-if="currentCase"
            type="success"
            :closable="false"
            style="margin-top: 8px"
            title="引用用例说明"
            :description="overrideEmpty ? '当前未填写任何覆盖项：执行时完全继承所选用例配置。' : '你已填写覆盖项：执行时会在用例配置基础上做覆盖（Header/Expect 浅合并，Payload/Extractors 覆盖）。'"
          />
        </el-form-item>
        <el-form-item label="会话Key">
          <el-input v-model="stepForm.session_key" placeholder="default / userA / userB" />
        </el-form-item>
        <el-form-item v-if="stepForm.source === 'api'" label="接口">
          <el-select v-model="stepForm.api" filterable style="width:100%">
            <el-option v-for="api in apis" :key="api.id" :label="`${api.method} ${api.path}`" :value="api.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-else label="接口">
          <el-input :model-value="currentCaseApiLabel" disabled />
        </el-form-item>
        <el-form-item label="顺序"><el-input-number v-model="stepForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="依赖步骤">
          <el-select v-model="stepForm.dependency_ids" multiple style="width:100%">
            <el-option v-for="s in steps.filter(item => item.id !== stepForm.id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求配置">
          <div v-if="stepForm.source === 'case'" class="override-toolbar">
            <el-button size="small" @click="fillOverridesFromCase" :disabled="!currentCase">复制用例到覆盖</el-button>
            <el-button size="small" @click="clearOverrides" :disabled="overrideEmpty">清空覆盖</el-button>
          </div>
          <RequestConfigEditor
            v-model:header="stepForm.header"
            v-model:payload="stepForm.payload"
            v-model:expect="stepForm.expect"
            v-model:extractors="stepForm.extractors"
          />
          <el-collapse v-if="stepForm.source === 'case' && currentCase" style="margin-top: 10px">
            <el-collapse-item title="继承用例配置预览（只读）" name="base">
              <pre class="json-preview">{{ baseCasePreviewText }}</pre>
            </el-collapse-item>
            <el-collapse-item title="合并后实际请求预览（只读）" name="merged">
              <pre class="json-preview">{{ mergedPreviewText }}</pre>
              <div style="font-size: 12px; color: #6b7280; margin-top: 6px">
                注：运行时还会叠加环境 Header 与接口默认 Header，这里只展示“用例 + 步骤覆盖”的合并结果。
              </div>
            </el-collapse-item>
          </el-collapse>
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="stepVisible=false">取消</el-button>
        <el-button type="primary" @click="saveStep">保存</el-button>
      </div>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 接口场景用例管理页面，用于把多个接口步骤串联成业务流程场景，并维护步骤依赖、执行顺序及局部请求配置。
 * 2. 页面依赖 scenarioApi、scenarioStepApi、apiDefinitionApi 与项目数据，是单接口用例到业务流程自动化之间的桥梁。
 * 3. 这里配置的场景可被 PlansView 纳入测试计划，也会在 TaskDetailView 中以场景步骤结果的形式展示执行明细。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiDefinitionApi, caseApi, projectApi, scenarioApi, scenarioStepApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'
import RequestConfigEditor from '../components/editors/RequestConfigEditor.vue'

const projects = ref([])
const scenarios = ref([])
const apis = ref([])
const cases = ref([])
const steps = ref([])
const activeScenario = ref(null)
const scenarioVisible = ref(false)
const stepsVisible = ref(false)
const stepVisible = ref(false)
const groupByCase = ref(false)
const filters = reactive({ project: null, keyword: '' })
const scenarioForm = reactive({ id: null, project: null, name: '', description: '', level: 1, enabled: true })
const stepForm = reactive({
  id: null,
  scenario: null,
  api: null,
  case_id: null,
  name: '',
  source: 'case',
  session_key: 'default',
  sort_order: 0,
  dependency_ids: [],
  header: {},
  payload: {},
  expect: {},
  extractors: []
})
const scenarioRows = computed(() => scenarios.value.results || scenarios.value || [])
const currentCaseApiLabel = computed(() => {
  const c = cases.value.find(item => item.id === stepForm.case_id)
  if (!c) return ''
  const api = apis.value.find(a => a.id === c.api)
  return api ? `${api.method} ${api.path}` : ''
})
const currentCase = computed(() => cases.value.find(item => item.id === stepForm.case_id))
const overrideEmpty = computed(() => {
  const headerEmpty = !stepForm.header || Object.keys(stepForm.header).length === 0
  const payloadEmpty = !stepForm.payload || Object.keys(stepForm.payload).length === 0
  const expectEmpty = !stepForm.expect || Object.keys(stepForm.expect).length === 0
  const extractorEmpty = !stepForm.extractors || stepForm.extractors.length === 0
  return headerEmpty && payloadEmpty && expectEmpty && extractorEmpty
})

function shallowMerge(base, override) {
  if (override == null) return base
  if (typeof override === 'string' && !override.trim()) return base
  if (Array.isArray(override) && override.length === 0) return base
  if (typeof override === 'object' && !Array.isArray(override) && Object.keys(override || {}).length === 0) return base
  if (typeof base === 'object' && typeof override === 'object' && !Array.isArray(base) && !Array.isArray(override)) {
    return { ...(base || {}), ...(override || {}) }
  }
  return override
}

const baseCasePreviewText = computed(() => {
  if (!currentCase.value) return ''
  const c = currentCase.value
  return JSON.stringify({
    case_code: c.case_code,
    subtitle: c.subtitle || c.title,
    session_key: c.session_key,
    header: c.header || {},
    payload: c.payload || {},
    expect: c.expect || {},
    extractors: c.extractors || []
  }, null, 2)
})

const mergedPreviewText = computed(() => {
  if (!currentCase.value) return ''
  const c = currentCase.value
  return JSON.stringify({
    session_key: stepForm.session_key || c.session_key || 'default',
    header: shallowMerge(c.header || {}, stepForm.header || {}),
    payload: shallowMerge(c.payload || {}, stepForm.payload || {}),
    expect: shallowMerge(c.expect || {}, stepForm.expect || {}),
    extractors: [...(c.extractors || []), ...(stepForm.extractors || [])]
  }, null, 2)
})

const groupedSteps = computed(() => {
  const groups = new Map()
  ;(steps.value || []).forEach(item => {
    const key = item.case_code || '自定义接口'
    if (!groups.has(key)) {
      groups.set(key, { key, label: key, subtitle: item.case_title || '', items: [] })
    }
    groups.get(key).items.push(item)
  })
  return Array.from(groups.values())
})

async function load() {
  const projectData = await projectApi.list()
  projects.value = projectData.results || projectData
  if (!filters.project && projects.value.length) filters.project = projects.value[0].id

  const [scenarioData, apiData, caseData] = await Promise.all([
    scenarioApi.list(filters),
    apiDefinitionApi.list({ project: filters.project }),
    caseApi.list({ project: filters.project })
  ])
  scenarios.value = scenarioData
  apis.value = apiData.results || apiData
  cases.value = caseData.results || caseData
}
function openScenario(row = null) {
  Object.assign(scenarioForm, row || { id: null, project: filters.project, name: '', description: '', level: 1, enabled: true })
  scenarioVisible.value = true
}
async function saveScenario() {
  scenarioForm.id ? await scenarioApi.update(scenarioForm.id, scenarioForm) : await scenarioApi.create(scenarioForm)
  ElMessage.success('已保存')
  scenarioVisible.value = false
  await load()
}
async function removeScenario(row) {
  await ElMessageBox.confirm(`删除场景 ${row.name}?`)
  await scenarioApi.remove(row.id)
  await load()
}
async function openSteps(row) {
  activeScenario.value = row
  await Promise.all([loadSteps(row.id), loadCases(row.project)])
  stepsVisible.value = true
}
async function loadSteps(scenario) {
  const data = await scenarioStepApi.list({ scenario })
  steps.value = data.results || data
}
async function loadCases(project) {
  if (!project) return
  const data = await caseApi.list({ project })
  cases.value = data.results || data
}

function onCaseChange() {
  const c = cases.value.find(item => item.id === stepForm.case_id)
  if (!c) return
  stepForm.api = c.api
  if (!stepForm.session_key || stepForm.session_key === 'default') {
    stepForm.session_key = (c.session_key || 'default').trim() || 'default'
  }
}

function clearOverrides() {
  stepForm.header = {}
  stepForm.payload = {}
  stepForm.expect = {}
  stepForm.extractors = []
}

function fillOverridesFromCase() {
  const c = currentCase.value
  if (!c) return
  stepForm.header = JSON.parse(JSON.stringify(c.header || {}))
  stepForm.payload = JSON.parse(JSON.stringify(c.payload || {}))
  stepForm.expect = JSON.parse(JSON.stringify(c.expect || {}))
  stepForm.extractors = JSON.parse(JSON.stringify(c.extractors || []))
  stepForm.session_key = (c.session_key || stepForm.session_key || 'default').trim() || 'default'
}
function openStep(row = null) {
  Object.assign(stepForm, {
    ...(row || { id: null, scenario: activeScenario.value.id, api: apis.value[0]?.id, case_id: null, name: '', sort_order: steps.value.length + 1, dependency_ids: [] }),
    header: cloneJson(row?.header || {}),
    payload: cloneJson(row?.payload || {}),
    expect: cloneJson(row?.expect || {}),
    extractors: cloneJson(row?.extractors || [])
  })
  stepForm.source = (stepForm.case_id || row?.case_id) ? 'case' : 'api'
  stepForm.case_id = row?.case_id || stepForm.case_id || null
  stepForm.session_key = (stepForm.session_key || 'default').trim() || 'default'
  if (stepForm.source === 'case' && stepForm.case_id) {
    onCaseChange()
  }
  stepVisible.value = true
}
function cloneJson(value) {
  return JSON.parse(JSON.stringify(value))
}
async function saveStep() {
  const payload = { ...stepForm }
  delete payload.source
  if (stepForm.source === 'api') {
    payload.case_id = null
  } else {
    onCaseChange()
  }
  stepForm.id ? await scenarioStepApi.update(stepForm.id, payload) : await scenarioStepApi.create(payload)
  ElMessage.success('已保存')
  stepVisible.value = false
  await loadSteps(activeScenario.value.id)
}
async function removeStep(row) {
  await ElMessageBox.confirm(`删除步骤 ${row.name}?`)
  await scenarioStepApi.remove(row.id)
  await loadSteps(activeScenario.value.id)
}
onMounted(load)
</script>

<style scoped>
.drawer-form {
  padding-right: 8px;
}
.override-toolbar {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 8px;
}
.json-preview {
  margin: 0;
  padding: 10px 12px;
  background: #0b1020;
  color: #e5e7eb;
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
.step-group {
  margin-top: 14px;
}
.step-group__title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin: 10px 0;
}
.step-group__subtitle {
  color: #6b7280;
  font-size: 12px;
}
.step-group__count {
  margin-left: auto;
  color: #6b7280;
  font-size: 12px;
}
.drawer-footer {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 0 0;
  background: #fff;
}
</style>
