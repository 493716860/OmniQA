<template>
  <section>
    <h1 v-if="!embedded" class="page-title">执行任务</h1>
    <div :class="embedded ? 'embedded-panel' : 'panel'">
      <div class="toolbar task-toolbar">
        <el-select v-model="filters.project" clearable placeholder="项目" style="width: 180px" @change="handleProjectChange">
          <el-option v-for="p in projectList" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.plan" clearable filterable placeholder="测试计划" style="width: 220px" @change="search">
          <el-option v-for="p in planList" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px" @change="search">
          <el-option label="待执行" value="PENDING" />
          <el-option label="执行中" value="RUNNING" />
          <el-option label="通过" value="PASSED" />
          <el-option label="失败" value="FAILED" />
          <el-option label="已取消" value="CANCELED" />
        </el-select>
        <el-input v-model="filters.keyword" clearable placeholder="计划名称" style="width: 220px" @keyup.enter="search" />
        <el-button @click="search">查询</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <el-button type="primary" @click="load">刷新</el-button>
      </div>
      <el-table :data="taskRows">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="plan_name" label="计划" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.progress" />
          </template>
        </el-table-column>
        <el-table-column prop="passed_count" label="通过" width="80" />
        <el-table-column prop="failed_count" label="失败" width="80" />
        <el-table-column prop="skipped_count" label="跳过" width="80" />
        <el-table-column label="当前用例">
          <template #default="{ row }">
            {{ row.current_case_code }} {{ row.current_case_title }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="$router.push(`/tasks/${row.id}`)">详情</el-button>
            <el-button
              v-if="hasReport(row)"
              size="small"
              type="success"
              @click="openReport(row)"
            >
              报告
            </el-button>
            <el-button
              v-if="['PENDING', 'RUNNING'].includes(row.status)"
              size="small"
              type="warning"
              @click="cancelTask(row)"
            >
              取消
            </el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="['RUNNING'].includes(row.status)"
              @click="removeTask(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-row" v-if="taskTotal > 0">
        <el-pagination
          v-model:current-page="filters.page"
          layout="total, prev, pager, next"
          :total="taskTotal"
          :page-size="20"
          @current-change="load"
        />
      </div>
      <el-empty v-if="taskRows.length === 0" description="暂无执行任务">
        <el-button type="primary" @click="$router.push('/plans')">去创建测试计划</el-button>
      </el-empty>
    </div>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 接口测试任务列表页，用于查询、筛选和管理测试计划执行后产生的任务记录。
 * 2. 页面依赖 taskApi、planApi 与 projectApi，承接 PlansView 和 SchedulesView 触发的执行结果，并提供报告入口。
 * 3. 该页面聚焦任务级概览；更细粒度的用例结果、事件日志与 Allure 报告需要进入 TaskDetailView 查看。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { planApi, projectApi, taskApi } from '../api/resources'

const { embedded = false } = defineProps({
  embedded: { type: Boolean, default: false }
})

const tasks = ref([])
const projectList = ref([])
const planList = ref([])
const filters = reactive({ project: null, plan: null, status: '', keyword: '', page: 1 })
const taskRows = computed(() => tasks.value.results || tasks.value || [])
const taskTotal = computed(() => tasks.value.count || taskRows.value.length)

async function load() {
  tasks.value = await taskApi.list({
    project: filters.project || undefined,
    plan: filters.plan || undefined,
    status: filters.status || undefined,
    keyword: filters.keyword || undefined,
    page: filters.page
  })
}

async function loadOptions() {
  const [projects, plans] = await Promise.all([
    projectApi.list(),
    planApi.list({ project: filters.project || undefined })
  ])
  projectList.value = projects.results || projects
  planList.value = plans.results || plans
}

async function search() {
  filters.page = 1
  await load()
}

async function handleProjectChange() {
  filters.plan = null
  await loadOptions()
  await search()
}

async function resetFilters() {
  Object.assign(filters, { project: null, plan: null, status: '', keyword: '', page: 1 })
  await loadOptions()
  await load()
}

function statusLabel(status) {
  const labels = {
    PENDING: '待执行',
    RUNNING: '执行中',
    PASSED: '通过',
    FAILED: '失败',
    CANCELED: '已取消'
  }
  return labels[status] || status
}

function statusType(status) {
  if (status === 'PASSED') return 'success'
  if (status === 'FAILED') return 'danger'
  if (status === 'CANCELED') return 'warning'
  return 'info'
}

function hasReport(row) {
  return ['PASSED', 'FAILED'].includes(row.status) && row.report_html_path
}

async function openReport(row) {
  const reportWindow = window.open('', '_blank')
  const info = await taskApi.allure(row.id)
  if (!info.url) {
    reportWindow?.close()
    ElMessage.warning('暂无报告')
    return
  }
  if (reportWindow) {
    reportWindow.location.href = info.url
  } else {
    window.location.href = info.url
  }
}

async function cancelTask(row) {
  await ElMessageBox.confirm(`确认取消任务 #${row.id}？`, '取消任务', { type: 'warning' })
  await taskApi.cancel(row.id)
  ElMessage.success('任务已取消')
  await load()
}

async function removeTask(row) {
  await ElMessageBox.confirm(`确认删除任务 #${row.id} 的执行记录？`, '删除任务', { type: 'warning' })
  try {
    await taskApi.remove(row.id)
    ElMessage.success('任务记录已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
    return
  }
  if (taskRows.value.length === 1 && filters.page > 1) {
    filters.page -= 1
  }
  await load()
}

onMounted(async () => {
  await loadOptions()
  await load()
})
</script>

<style scoped>
.embedded-panel {
  padding: 0;
  border: none;
  background: transparent;
  box-shadow: none;
}
</style>

<style scoped>
.task-toolbar {
  gap: 10px;
}
.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
