<template>
  <section>
    <h1 v-if="!embedded" class="page-title">测试计划</h1>
    <div :class="embedded ? 'embedded-panel' : 'panel'">
      <div class="toolbar plan-toolbar">
        <el-select v-model="planFilters.project" clearable placeholder="项目" style="width: 180px" @change="load">
          <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-input v-model="planFilters.keyword" clearable placeholder="计划名称" style="width: 220px" @keyup.enter="load" />
        <el-button @click="load">查询</el-button>
        <el-button @click="resetPlanFilters">重置</el-button>
        <el-button type="primary" @click="openCreate">新建计划</el-button>
      </div>
      <el-table :data="planRows">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="计划" />
        <el-table-column prop="project_name" label="项目" />
        <el-table-column prop="environment_name" label="环境" />
        <el-table-column prop="cases_count" label="用例数" width="100" />
        <el-table-column label="等级" width="120">
          <template #default="{ row }">
            {{ formatLevels(row.levels) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="320">
          <template #default="{ row }">
            <el-button size="small" @click="showCases(row)">用例明细</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="primary" @click="run(row.id)">执行</el-button>
            <el-button size="small" type="danger" @click="removePlan(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="planRows.length === 0" description="暂无测试计划">
        <el-button type="primary" @click="$router.push('/cases')">先查看用例</el-button>
      </el-empty>
    </div>

    <FullScreenDrawer v-model="createVisible" title="新建测试计划">
      <el-form label-width="88px">
        <el-form-item label="项目">
          <el-select v-model="form.project" placeholder="项目" style="width: 100%" @change="loadCreateEnvs">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="环境">
          <el-select v-model="form.environment" placeholder="环境" style="width: 100%">
            <el-option v-for="e in envList" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="计划名称" />
        </el-form-item>
        <el-form-item label="等级">
          <el-input v-model="levelText" placeholder="等级, 如 1,2" />
        </el-form-item>
        <el-form-item label="模块">
          <el-select
            v-model="form.module_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="createApiScopeDisabled"
            @change="clearCreateScenarios"
          >
            <el-option v-for="m in moduleList" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口">
          <el-select
            v-model="form.api_definition_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="createApiScopeDisabled"
            @change="clearCreateScenarios"
          >
            <el-option v-for="api in apiList" :key="api.id" :label="`${api.method} ${api.path}`" :value="api.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用例">
          <el-select
            v-model="form.case_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="createApiScopeDisabled"
            @change="clearCreateScenarios"
          >
            <el-option
              v-for="item in createCaseOptions"
              :key="item.id"
              :label="`${item.case_code} ${item.subtitle || item.title}`"
              :value="item.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="场景">
          <el-select
            v-model="form.scenario_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="createScenarioDisabled"
            @change="clearCreateApiScope"
          >
            <el-option v-for="s in scenarioList" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="tagText" placeholder="标签, 如 smoke,login" />
        </el-form-item>
        <el-form-item label="套件">
          <el-input v-model="suiteText" placeholder="套件, 如 冒烟,回归" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="previewCreate">预览范围</el-button>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" @click="createPlan">创建计划</el-button>
      </template>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="caseDrawerVisible" title="计划包含的用例">
      <h3>接口用例</h3>
      <el-table :data="planCases">
        <el-table-column type="index" label="顺序" width="70" />
        <el-table-column prop="case_code" label="用例ID" width="100" />
        <el-table-column prop="module_name" label="模块" width="130" />
        <el-table-column prop="title" label="接口" />
        <el-table-column prop="subtitle" label="用例" />
        <el-table-column prop="api_method" label="方法" width="90" />
        <el-table-column prop="api_path" label="路径" />
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column label="依赖" width="160">
          <template #default="{ row }">
            <el-tag v-for="code in row.dependency_codes" :key="code" size="small" style="margin-right: 4px">
              {{ code }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <h3>场景用例</h3>
      <el-table :data="planScenarios">
        <el-table-column prop="name" label="场景" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column prop="steps_count" label="步骤数" width="100" />
      </el-table>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="previewVisible" title="创建前执行预览">
      <div class="preview-summary">
        <span>接口用例 <b>{{ preview.cases_count }}</b></span>
        <span>场景用例 <b>{{ preview.scenarios_count }}</b></span>
        <span>预计耗时 <b>{{ formatDuration(preview.estimated_duration_ms) }}</b></span>
      </div>
      <h3>接口用例</h3>
      <el-table :data="preview.cases || []">
        <el-table-column prop="case_code" label="用例ID" width="110" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="title" label="接口" />
        <el-table-column prop="subtitle" label="用例" />
        <el-table-column prop="level" label="等级" width="80" />
      </el-table>
      <h3>场景用例</h3>
      <el-table :data="preview.scenarios || []">
        <el-table-column prop="name" label="场景" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="steps_count" label="步骤数" width="100" />
      </el-table>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="editVisible" title="编辑测试计划">
      <el-form label-width="80px">
        <el-form-item label="项目">
          <el-select v-model="editForm.project" placeholder="项目" style="width: 100%" @change="loadEditEnvs">
            <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="环境">
          <el-select v-model="editForm.environment" placeholder="环境" style="width: 100%">
            <el-option v-for="e in editEnvList" :key="e.id" :label="e.name" :value="e.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="editForm.name" placeholder="计划名称" />
        </el-form-item>
        <el-form-item label="等级">
          <el-input v-model="editLevelText" placeholder="等级, 如 1,2" />
        </el-form-item>
        <el-form-item label="模块">
          <el-select
            v-model="editForm.module_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="editApiScopeDisabled"
            @change="clearEditScenarios"
          >
            <el-option v-for="m in moduleList" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="接口">
          <el-select
            v-model="editForm.api_definition_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="editApiScopeDisabled"
            @change="clearEditScenarios"
          >
            <el-option v-for="api in apiList" :key="api.id" :label="`${api.method} ${api.path}`" :value="api.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用例">
          <el-select
            v-model="editForm.case_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="editApiScopeDisabled"
            @change="clearEditScenarios"
          >
            <el-option v-for="item in editCaseOptions" :key="item.id" :label="`${item.case_code} ${item.subtitle || item.title}`" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="场景">
          <el-select
            v-model="editForm.scenario_ids"
            multiple
            filterable
            style="width: 100%"
            :disabled="editScenarioDisabled"
            @change="clearEditApiScope"
          >
            <el-option v-for="s in scenarioList" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="editTagText" placeholder="标签, 如 smoke,login" />
        </el-form-item>
        <el-form-item label="套件">
          <el-input v-model="editSuiteText" placeholder="套件, 如 冒烟,回归" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="savePlan">保存</el-button>
      </template>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 测试计划管理页面，用于按项目、环境、模块、接口、用例或场景组合执行范围，并支持执行预览与计划编辑。
 * 2. 页面依赖计划、项目、环境、模块、接口、用例、场景与任务相关 API，是测试资产配置和实际任务执行之间的关键编排层。
 * 3. 创建或编辑的计划会被 SchedulesView 用作定时调度目标，也可直接在本页触发执行并跳转到 TasksView/TaskDetailView 查看结果。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { apiDefinitionApi, caseApi, environmentApi, moduleApi, planApi, projectApi, scenarioApi, taskApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'

const { embedded = false } = defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()
const plans = ref([])
const planCases = ref([])
const planScenarios = ref([])
const projectList = ref([])
const envList = ref([])
const editEnvList = ref([])
const scenarioList = ref([])
const moduleList = ref([])
const apiList = ref([])
const caseList = ref([])
const levelText = ref('')
const editLevelText = ref('')
const tagText = ref('')
const suiteText = ref('')
const editTagText = ref('')
const editSuiteText = ref('')
const createVisible = ref(false)
const editVisible = ref(false)
const caseDrawerVisible = ref(false)
const previewVisible = ref(false)
const saving = ref(false)
const planFilters = reactive({ project: null, keyword: '' })
const preview = ref({ cases_count: 0, scenarios_count: 0, estimated_duration_ms: 0, cases: [], scenarios: [] })
const form = reactive({ name: '', project: null, environment: null, module_ids: [], api_definition_ids: [], case_ids: [], scenario_ids: [] })
const editForm = reactive({
  id: null,
  name: '',
  project: null,
  environment: null,
  module_ids: [],
  api_definition_ids: [],
  case_ids: [],
  scenario_ids: []
})

const planRows = computed(() => plans.value.results || plans.value || [])
const createHasScenarioSelection = computed(() => form.scenario_ids.length > 0)
const createHasApiScopeSelection = computed(
  () => form.module_ids.length > 0 || form.api_definition_ids.length > 0 || form.case_ids.length > 0
)
const createApiScopeDisabled = computed(() => createHasScenarioSelection.value && !createHasApiScopeSelection.value)
const createScenarioDisabled = computed(() => createHasApiScopeSelection.value && !createHasScenarioSelection.value)
const editHasScenarioSelection = computed(() => editForm.scenario_ids.length > 0)
const editHasApiScopeSelection = computed(
  () => editForm.module_ids.length > 0 || editForm.api_definition_ids.length > 0 || editForm.case_ids.length > 0
)
const editApiScopeDisabled = computed(() => editHasScenarioSelection.value && !editHasApiScopeSelection.value)
const editScenarioDisabled = computed(() => editHasApiScopeSelection.value && !editHasScenarioSelection.value)

function filterCaseOptions(allCases, moduleIds, apiIds) {
  const list = allCases || []
  if (Array.isArray(apiIds) && apiIds.length) {
    const set = new Set(apiIds)
    return list.filter(item => set.has(item.api))
  }
  if (Array.isArray(moduleIds) && moduleIds.length) {
    const set = new Set(moduleIds)
    return list.filter(item => set.has(item.module))
  }
  return list
}

const createCaseOptions = computed(() => filterCaseOptions(caseList.value, form.module_ids, form.api_definition_ids))
const editCaseOptions = computed(() => filterCaseOptions(caseList.value, editForm.module_ids, editForm.api_definition_ids))

async function load() {
  plans.value = await planApi.list({
    project: planFilters.project || undefined,
    keyword: planFilters.keyword || undefined
  })
  const projects = await projectApi.list()
  const scenarios = await scenarioApi.list()
  projectList.value = projects.results || projects
  scenarioList.value = scenarios.results || scenarios
  if (!form.project && projectList.value.length) {
    form.project = projectList.value[0].id
    await loadCreateEnvs(form.project)
  }
}

function resetCreateForm() {
  Object.assign(form, {
    name: '',
    project: projectList.value[0]?.id || null,
    environment: null,
    module_ids: [],
    api_definition_ids: [],
    case_ids: [],
    scenario_ids: []
  })
  levelText.value = ''
  tagText.value = ''
  suiteText.value = ''
}

async function openCreate() {
  resetCreateForm()
  if (form.project) {
    await loadCreateEnvs(form.project)
  }
  createVisible.value = true
}

async function resetPlanFilters() {
  planFilters.project = null
  planFilters.keyword = ''
  await load()
}

async function loadCreateEnvs(project) {
  form.environment = null
  form.module_ids = []
  form.api_definition_ids = []
  form.case_ids = []
  form.scenario_ids = []
  const [envs] = await Promise.all([environmentApi.list({ project }), loadProjectAssets(project)])
  envList.value = envs.results || envs
  if (envList.value.length) {
    form.environment = envList.value[0].id
  }
}

async function loadEditEnvs(project, preferredEnvironment = null) {
  editForm.environment = null
  const [envs] = await Promise.all([environmentApi.list({ project }), loadProjectAssets(project)])
  editEnvList.value = envs.results || envs
  const preferred = editEnvList.value.find(env => env.id === preferredEnvironment)
  if (preferred) {
    editForm.environment = preferred.id
  } else if (editEnvList.value.length) {
    editForm.environment = editEnvList.value[0].id
  }
}

async function loadProjectAssets(project) {
  if (!project) return
  const [modules, apis, cases, scenarios] = await Promise.all([
    moduleApi.list({ project }),
    apiDefinitionApi.list({ project }),
    caseApi.list({ project }),
    scenarioApi.list({ project })
  ])
  moduleList.value = modules.results || modules
  apiList.value = apis.results || apis
  caseList.value = cases.results || cases
  scenarioList.value = scenarios.results || scenarios
}

function parseLevels(value) {
  return value ? value.split(',').map(v => Number(v.trim())).filter(Boolean) : []
}

function formatLevels(levels) {
  return Array.isArray(levels) && levels.length ? levels.join(',') : '-'
}

function parseTextList(value) {
  return value ? value.split(',').map(v => v.trim()).filter(Boolean) : []
}

function formatDuration(ms) {
  if (!ms) return '0 秒'
  const seconds = Math.ceil(ms / 1000)
  return seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`
}

function clearCreateApiScope() {
  if (!form.scenario_ids.length) return
  form.module_ids = []
  form.api_definition_ids = []
  form.case_ids = []
}

function clearCreateScenarios() {
  if (!createHasApiScopeSelection.value) return
  form.scenario_ids = []
}

function clearEditApiScope() {
  if (!editForm.scenario_ids.length) return
  editForm.module_ids = []
  editForm.api_definition_ids = []
  editForm.case_ids = []
}

function clearEditScenarios() {
  if (!editHasApiScopeSelection.value) return
  editForm.scenario_ids = []
}

function createPayload() {
  return {
    ...form,
    levels: parseLevels(levelText.value),
    tags: parseTextList(tagText.value),
    suites: parseTextList(suiteText.value)
  }
}

async function previewCreate() {
  if (!form.project) {
    ElMessage.warning('请选择项目')
    return
  }
  preview.value = await planApi.preview(createPayload())
  previewVisible.value = true
}

async function createPlan() {
  if (!form.project) {
    ElMessage.warning('请选择项目')
    return
  }
  if (!form.environment) {
    ElMessage.warning('请选择环境')
    return
  }
  if (!form.name.trim()) {
    ElMessage.warning('请输入计划名称')
    return
  }
  await planApi.create(createPayload())
  ElMessage.success('计划已创建')
  createVisible.value = false
  await load()
}

async function openEdit(row) {
  editForm.id = row.id
  editForm.name = row.name
  editForm.project = row.project
  editForm.module_ids = row.module_ids || []
  editForm.api_definition_ids = row.api_definition_ids || []
  editForm.case_ids = row.case_ids || []
  editForm.scenario_ids = row.scenario_ids || []
  editTagText.value = (row.tags || []).join(',')
  editSuiteText.value = (row.suites || []).join(',')
  editLevelText.value = formatLevels(row.levels) === '-' ? '' : formatLevels(row.levels)
  await loadEditEnvs(row.project, row.environment)
  editVisible.value = true
}

async function savePlan() {
  if (!editForm.project) {
    ElMessage.warning('请选择项目')
    return
  }
  if (!editForm.environment) {
    ElMessage.warning('请选择环境')
    return
  }
  if (!editForm.name.trim()) {
    ElMessage.warning('请输入计划名称')
    return
  }
  saving.value = true
  try {
    await planApi.update(editForm.id, {
      name: editForm.name,
      project: editForm.project,
      environment: editForm.environment,
      levels: parseLevels(editLevelText.value),
      module_ids: editForm.module_ids,
      api_definition_ids: editForm.api_definition_ids,
      case_ids: editForm.case_ids,
      scenario_ids: editForm.scenario_ids,
      tags: parseTextList(editTagText.value),
      suites: parseTextList(editSuiteText.value)
    })
    ElMessage.success('计划已更新')
    editVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function run(plan) {
  const task = await taskApi.create({ plan })
  router.push(`/tasks/${task.id}`)
}

async function removePlan(row) {
  await ElMessageBox.confirm(
    `确认删除测试计划「${row.name}」？\n删除后将同时删除该计划下的历史任务记录、用例结果、事件与定时任务（如有）。`,
    '删除测试计划',
    { type: 'warning' }
  )
  try {
    await planApi.remove(row.id)
    ElMessage.success('测试计划已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
    return
  }
  await load()
}

async function showCases(plan) {
  const data = await planApi.cases(plan.id)
  planCases.value = data.cases || data
  planScenarios.value = data.scenarios || []
  caseDrawerVisible.value = true
}

onMounted(load)
</script>

<style scoped>
.embedded-panel {
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
}
.plan-toolbar {
  flex-wrap: wrap;
  align-items: flex-start;
}
.preview-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.preview-summary span {
  padding: 14px;
  background: #f8fafc;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  color: #475569;
}
.preview-summary b {
  display: block;
  margin-top: 6px;
  color: #111827;
  font-size: 22px;
}
</style>
