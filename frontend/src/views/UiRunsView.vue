<template>
  <section>
    <h1 class="page-title">（已废弃）UI 运行批次（Run）</h1>
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      title="该页面已整合到【任务管理 → 任务中心】"
      description="请前往【任务管理 → 任务中心 → 测试计划 → UI 测试】创建并运行；创建后会直接进入任务详情。执行记录在【任务中心 → 执行记录 → UI 测试】查看。"
      style="margin-bottom: 12px;"
    />
    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-button type="primary" @click="openCreate">创建运行</el-button>
        <el-button @click="load">刷新</el-button>
      </div>

      <el-table :data="rows">
        <el-table-column prop="id" label="Run ID" width="110" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="scenario_name" label="场景" />
        <el-table-column prop="dataset_name" label="数据集" width="200" />
        <el-table-column prop="mode" label="模式" width="100" />
        <el-table-column prop="total" label="总数" width="90" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openTasks(row)">查看子任务</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="rows.length === 0" description="暂无运行记录" />
    </div>

    <el-dialog v-model="createVisible" title="创建 UI 运行（Run）" width="760px">
      <el-form label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="createForm.project" style="width: 100%" @change="loadScenarioAndDatasets">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="场景">
          <el-select v-model="createForm.scenario" filterable style="width: 100%" placeholder="请选择要运行的 UI 场景">
            <el-option v-for="s in scenarios" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据集">
          <el-select v-model="createForm.dataset" filterable style="width: 100%" placeholder="DDT：每行数据会生成一个子任务">
            <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模式">
          <el-select v-model="createForm.mode" style="width: 180px">
            <el-option label="无头（HEADLESS）" value="HEADLESS" />
            <el-option label="有头（HEADED）" value="HEADED" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="createVisible=false">取消</el-button>
          <el-button type="primary" :loading="creating" :disabled="!createForm.scenario || !createForm.dataset" @click="createRun">
            创建并查看子任务
          </el-button>
        </span>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. UI 任务的“运行批次（Run）”页面：负责创建 Run（选择场景+数据集+模式）并查看历史 Run 记录。
 * 2. 该页面属于“任务管理”模块：强调运行/执行/记录，不承担 UI 资产维护职责。
 * 3. Run 是批次概念：每次创建 Run，会按数据集行拆分出多个 UiTask；单个任务明细在 UiTaskDetailView 查看。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { projectApi, uiDatasetApi, uiRunApi, uiScenarioApi } from '../api/resources'

const router = useRouter()
const projects = ref([])
const data = ref([])
const scenarios = ref([])
const datasets = ref([])
const filters = reactive({ project: null })

const rows = computed(() => data.value.results || data.value || [])

const createVisible = ref(false)
const creating = ref(false)
const createForm = reactive({ project: null, scenario: null, dataset: null, mode: 'HEADLESS' })

async function load() {
  const p = await projectApi.list()
  projects.value = p.results || p
  data.value = await uiRunApi.list({ project: filters.project || undefined })
}

async function loadScenarioAndDatasets() {
  const project = createForm.project
  const s = await uiScenarioApi.list({ project: project || undefined })
  scenarios.value = s.results || s
  const d = await uiDatasetApi.list({ project: project || undefined })
  datasets.value = d.results || d
}

function openCreate() {
  createForm.project = filters.project || projects.value[0]?.id || null
  createForm.scenario = null
  createForm.dataset = null
  createForm.mode = 'HEADLESS'
  createVisible.value = true
  loadScenarioAndDatasets()
}

async function createRun() {
  creating.value = true
  try {
    const created = await uiRunApi.create({
      scenario: createForm.scenario,
      dataset: createForm.dataset,
      mode: createForm.mode
    })
    ElMessage.success(`已创建 Run #${created.id}，正在生成子任务`)
    createVisible.value = false
    await load()
    router.push({ path: '/ui-tasks', query: { run: created.id } })
  } finally {
    creating.value = false
  }
}

function openTasks(row) {
  router.push({ path: '/ui-tasks', query: { run: row.id } })
}

onMounted(load)
</script>
