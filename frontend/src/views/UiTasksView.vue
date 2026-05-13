<template>
  <section>
    <h1 v-if="!embedded" class="page-title">UI 任务</h1>
    <div :class="embedded ? 'embedded-panel' : 'panel'">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.scenario" placeholder="UI 场景" clearable style="width: 240px" @change="load">
          <el-option v-for="s in scenarios" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-input v-model="filters.exec_task" placeholder="执行记录ID(可选)" clearable style="width: 170px" @clear="load" />
        <el-button type="primary" @click="goRun">去测试计划</el-button>
        <el-button @click="load">刷新</el-button>
      </div>

      <el-table :data="rows" @row-click="openDetail">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="scenario_name" label="场景" />
        <el-table-column prop="mode" label="模式" width="100" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="progress" label="进度" width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button size="small" @click.stop="openDetail(row)">详情</el-button>
            <el-button size="small" @click.stop="openReport(row)" :disabled="!canReport(row)">报告</el-button>
            <el-button size="small" type="danger" @click.stop="cancel(row)" :disabled="!['PENDING','RUNNING'].includes(row.status)">取消</el-button>
            <el-button size="small" type="danger" plain @click.stop="remove(row)" :disabled="['PENDING','RUNNING'].includes(row.status)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="rows.length === 0" description="暂无 UI 任务" />
    </div>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. UI 任务列表页，用于查看 UI 场景运行后拆分出的子任务，支持按项目、场景和 Run 维度筛选。
 * 2. 页面依赖 uiTaskApi、uiScenarioApi 与 projectApi，承接 UiScenariosView/UiRunsView 的执行结果，并提供报告、取消、删除等操作入口。
 * 3. 它是 UI 自动化执行链路中的任务概览层，具体步骤结果、工件与事件需要进入 UiTaskDetailView 查看。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { projectApi, uiScenarioApi, uiTaskApi } from '../api/resources'

const { embedded = false } = defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()
const route = useRoute()
const projects = ref([])
const scenarios = ref([])
const data = ref([])

const filters = reactive({ project: null, scenario: null, exec_task: '' })

const rows = computed(() => data.value.results || data.value || [])

async function load() {
  if (route.query.exec_task && !filters.exec_task) filters.exec_task = String(route.query.exec_task)
  const p = await projectApi.list()
  projects.value = p.results || p
  const s = await uiScenarioApi.list({ project: filters.project || undefined })
  scenarios.value = s.results || s
  data.value = await uiTaskApi.list({
    project: filters.project || undefined,
    scenario: filters.scenario || undefined,
    exec_task: filters.exec_task || undefined,
  })
}

function goRun() {
  router.push({ path: '/task-center', query: { tab: 'plans', type: 'ui' } })
}

function openDetail(row) {
  router.push(`/ui-tasks/${row.id}`)
}

function canReport(row) {
  return ['PASSED', 'FAILED', 'CANCELED'].includes(row.status)
}

async function openReport(row) {
  const reportWindow = window.open('', '_blank')
  const info = await uiTaskApi.report(row.id)
  if (!info.url) {
    reportWindow?.close()
    ElMessage.warning('暂无报告（trace）')
    return
  }
  if (reportWindow) reportWindow.location.href = info.url
  else window.location.href = info.url
}

async function cancel(row) {
  await uiTaskApi.cancel(row.id)
  ElMessage.success('已取消')
  await load()
}

async function remove(row) {
  await ElMessageBox.confirm(`确认删除 UI 任务 #${row.id} 的执行记录？`, '删除任务', { type: 'warning' })
  await uiTaskApi.remove(row.id)
  ElMessage.success('任务记录已删除')
  await load()
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
</style>
