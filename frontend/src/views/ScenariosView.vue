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

    <el-drawer v-model="scenarioVisible" title="场景用例" size="640px">
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
    </el-drawer>

    <el-drawer v-model="stepsVisible" :title="activeScenario?.name || '步骤'" size="82%">
      <div class="toolbar">
        <el-button type="primary" @click="openStep()">新增步骤</el-button>
      </div>
      <el-table :data="steps">
        <el-table-column prop="sort_order" label="顺序" width="80" />
        <el-table-column prop="name" label="步骤" />
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
    </el-drawer>

    <el-drawer v-model="stepVisible" title="场景步骤" size="88%">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="名称"><el-input v-model="stepForm.name" /></el-form-item>
        <el-form-item label="接口">
          <el-select v-model="stepForm.api" filterable style="width:100%">
            <el-option v-for="api in apis" :key="api.id" :label="`${api.method} ${api.path}`" :value="api.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="顺序"><el-input-number v-model="stepForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="依赖步骤">
          <el-select v-model="stepForm.dependency_ids" multiple style="width:100%">
            <el-option v-for="s in steps.filter(item => item.id !== stepForm.id)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求配置">
          <RequestConfigEditor
            v-model:header="stepForm.header"
            v-model:payload="stepForm.payload"
            v-model:expect="stepForm.expect"
            v-model:extractors="stepForm.extractors"
          />
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="stepVisible=false">取消</el-button>
        <el-button type="primary" @click="saveStep">保存</el-button>
      </div>
    </el-drawer>
  </section>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiDefinitionApi, projectApi, scenarioApi, scenarioStepApi } from '../api/resources'
import RequestConfigEditor from '../components/editors/RequestConfigEditor.vue'

const projects = ref([])
const scenarios = ref([])
const apis = ref([])
const steps = ref([])
const activeScenario = ref(null)
const scenarioVisible = ref(false)
const stepsVisible = ref(false)
const stepVisible = ref(false)
const filters = reactive({ project: null, keyword: '' })
const scenarioForm = reactive({ id: null, project: null, name: '', description: '', level: 1, enabled: true })
const stepForm = reactive({
  id: null,
  scenario: null,
  api: null,
  name: '',
  sort_order: 0,
  dependency_ids: [],
  header: {},
  payload: {},
  expect: {},
  extractors: []
})
const scenarioRows = computed(() => scenarios.value.results || scenarios.value || [])

async function load() {
  const [projectData, scenarioData, apiData] = await Promise.all([
    projectApi.list(),
    scenarioApi.list(filters),
    apiDefinitionApi.list()
  ])
  projects.value = projectData.results || projectData
  if (!filters.project && projects.value.length) filters.project = projects.value[0].id
  scenarios.value = scenarioData
  apis.value = apiData.results || apiData
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
  await loadSteps(row.id)
  stepsVisible.value = true
}
async function loadSteps(scenario) {
  const data = await scenarioStepApi.list({ scenario })
  steps.value = data.results || data
}
function openStep(row = null) {
  Object.assign(stepForm, {
    ...(row || { id: null, scenario: activeScenario.value.id, api: apis.value[0]?.id, name: '', sort_order: steps.value.length + 1, dependency_ids: [] }),
    header: cloneJson(row?.header || {}),
    payload: cloneJson(row?.payload || {}),
    expect: cloneJson(row?.expect || {}),
    extractors: cloneJson(row?.extractors || [])
  })
  stepVisible.value = true
}
function cloneJson(value) {
  return JSON.parse(JSON.stringify(value))
}
async function saveStep() {
  const payload = { ...stepForm }
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
