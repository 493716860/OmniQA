<template>
  <div>
    <div class="toolbar">
      <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="load">
        <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
      </el-select>
      <el-input v-model="filters.keyword" clearable placeholder="计划名称" style="width: 220px" @keyup.enter="load" />
      <el-button type="primary" @click="openCreatePlan">新建计划</el-button>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-table :data="rows">
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="project_name" label="项目" width="160" />
      <el-table-column prop="name" label="UI 测试计划" />
      <el-table-column prop="scenarios_count" label="场景数" width="100" />
      <el-table-column prop="default_dataset_name" label="默认数据集" width="180" />
      <el-table-column prop="default_mode" label="默认模式" width="120" />
      <el-table-column prop="enabled" label="启用" width="90">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="260">
        <template #default="{ row }">
          <el-button size="small" @click="editPlan(row)">编辑</el-button>
          <el-button size="small" type="primary" @click="openRun(row)">运行</el-button>
          <el-button size="small" type="danger" @click="removePlan(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-empty v-if="rows.length === 0" description="暂无 UI 测试计划">
      <el-button type="primary" @click="openCreatePlan">新建计划</el-button>
    </el-empty>

    <UiTaskRunDrawer
      v-model:visible="runVisible"
      title="运行 UI 计划"
      submit-text="运行"
      :projects="projects"
      :datasets="datasets"
      :form="runForm"
      :creating="running"
      @submit="runNow"
    />

    <UiPlanCreateDrawer
      v-model:visible="createVisible"
      :title="createForm.id ? '编辑 UI 测试计划' : '新建 UI 测试计划'"
      :projects="projects"
      :scenarios="allScenarios"
      :datasets="datasets"
      :form="createForm"
      :saving="saving"
      @project-change="handlePlanProjectChange"
      @submit="createPlan"
    />
  </div>
</template>

<script setup>
/**
 * frontend/src/views/task_center/UiPlanView.vue
 *
 * 文件用途
 * -------
 * UI 测试计划页（任务管理内）。
 *
 * 目标（交互对齐接口任务）：
 * - UI “计划”直接使用 UiScenario（场景）作为可运行对象
 * - 点击运行后直接创建一个 UiTask（一次运行=一个任务）
 * - DDT 在该 UiTask 内部循环执行（后端 runner 处理），不再暴露 UiRun 概念
 *
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { projectApi, uiDatasetApi, uiScenarioApi, uiPlanApi } from '../../api/resources'
import UiTaskRunDrawer from '../../components/task/UiTaskRunDrawer.vue'
import UiPlanCreateDrawer from '../../components/task/UiPlanCreateDrawer.vue'

const router = useRouter()

const projects = ref([])
const datasets = ref([])
const data = ref([])
const allScenarios = ref([])

const filters = reactive({ project: null, keyword: '' })
const rows = computed(() => data.value.results || data.value || [])

// 运行（创建 UiExecTask + 多个 UiTask）
const runVisible = ref(false)
const running = ref(false)
const runForm = reactive({ project: null, plan: null, dataset: null, mode: 'HEADLESS' })

// 新建计划（创建 UiPlan：只关联已存在的 UI 场景）
const createVisible = ref(false)
const saving = ref(false)
const createForm = reactive({ id: null, project: null, name: '', scenario_ids: [], default_dataset: null, default_mode: 'HEADLESS', enabled: true })

async function load() {
  const p = await projectApi.list()
  projects.value = p.results || p
  data.value = await uiPlanApi.list({ project: filters.project || undefined, keyword: filters.keyword || undefined })
  // 计划创建需要选择场景：从 UI 场景库读取（任务中心只关联，不创建）
  const projectId = filters.project || undefined
  const s = await uiScenarioApi.list({ project: projectId })
  allScenarios.value = s.results || s
}

async function loadDatasets(projectId) {
  const d = await uiDatasetApi.list({ project: projectId || undefined })
  datasets.value = d.results || d
}

function openCreatePlan() {
  createForm.id = null
  createForm.project = filters.project || projects.value[0]?.id || null
  createForm.name = ''
  createForm.scenario_ids = []
  createForm.default_dataset = null
  createForm.default_mode = 'HEADLESS'
  createForm.enabled = true
  createVisible.value = true
  loadDatasets(createForm.project)
}

async function createPlan() {
  saving.value = true
  try {
    if (createForm.id) {
      await uiPlanApi.update(createForm.id, { ...createForm })
      ElMessage.success('计划已保存')
    } else {
      await uiPlanApi.create({ ...createForm })
      ElMessage.success('计划已创建')
    }
    createVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function editPlan(row) {
  // 计划编辑仍在任务中心完成（本页复用创建抽屉即可）
  Object.assign(createForm, {
    id: row.id,
    project: row.project,
    name: row.name,
    scenario_ids: (row.scenario_ids || []),
    default_dataset: row.default_dataset || null,
    default_mode: row.default_mode || 'HEADLESS',
    enabled: row.enabled !== false
  })
  createVisible.value = true
  loadDatasets(createForm.project)
}

async function handlePlanProjectChange() {
  // 切换项目时，联动场景与数据集候选项
  await loadDatasets(createForm.project)
  const s = await uiScenarioApi.list({ project: createForm.project || undefined })
  allScenarios.value = s.results || s
  // 清空不属于新项目的选择
  createForm.scenario_ids = []
  createForm.default_dataset = null
}

async function openRun(row) {
  runForm.project = row?.project || filters.project || projects.value[0]?.id || null
  runForm.plan = row?.id || null
  // 如果计划已配置默认数据集/模式，则点击“运行”直接执行（不再弹抽屉）
  runForm.dataset = row?.default_dataset || null
  runForm.mode = row?.default_mode || 'HEADLESS'

  if (runForm.dataset) {
    await runNow()
    return
  }

  // 未配置默认数据集：仍需用户选择一次（保持“模式+数据集必须可选”的约束）
  runVisible.value = true
  await loadDatasets(runForm.project)
}

async function runNow() {
  running.value = true
  try {
    const created = await uiPlanApi.run(runForm.plan, { dataset: runForm.dataset, mode: runForm.mode })
    ElMessage.success(`已开始执行（执行记录 #${created.id}）`)
    runVisible.value = false
    // 跳到执行记录（UI tab），并按 exec_task 过滤
    router.push({ path: '/task-center', query: { tab: 'records', type: 'ui', exec_task: created.id } })
  } finally {
    running.value = false
  }
}

async function removePlan(row) {
  await ElMessageBox.confirm(`确认删除 UI 测试计划「${row.name}」？`, '删除计划', { type: 'warning' })
  await uiPlanApi.remove(row.id)
  ElMessage.success('计划已删除')
  await load()
}

onMounted(load)
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}
</style>
