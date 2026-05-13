<template>
  <section>
    <h1 v-if="!embedded" class="page-title">UI 执行记录</h1>
    <div :class="embedded ? 'embedded-panel' : 'panel'">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="handleProjectChange">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.plan" placeholder="UI 测试计划" clearable filterable style="width: 260px" @change="load">
          <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="filters.status" placeholder="状态" clearable style="width: 160px" @change="load">
          <el-option label="待执行" value="PENDING" />
          <el-option label="执行中" value="RUNNING" />
          <el-option label="通过" value="PASSED" />
          <el-option label="失败" value="FAILED" />
          <el-option label="已取消" value="CANCELED" />
        </el-select>
        <el-button type="primary" @click="goPlans">去测试计划</el-button>
        <el-button @click="resetFilters">重置</el-button>
        <el-button @click="load">刷新</el-button>
      </div>

      <el-alert
        v-if="focusedId"
        type="success"
        show-icon
        :closable="false"
        :title="`已创建执行记录 #${focusedId}`"
        style="margin-bottom: 12px;"
      />

      <el-table :data="rows" @row-click="openTasks">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="plan_name" label="计划" />
        <el-table-column prop="dataset_name" label="数据集" width="180" />
        <el-table-column prop="mode" label="模式" width="110" />
        <el-table-column prop="status" label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="160">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" />
          </template>
        </el-table-column>
        <el-table-column prop="passed" label="通过" width="80" />
        <el-table-column prop="failed" label="失败" width="80" />
        <el-table-column prop="canceled" label="取消" width="80" />
        <el-table-column prop="total" label="总数" width="80" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click.stop="openTasks(row)">查看任务</el-button>
            <el-button
              v-if="['PENDING', 'RUNNING'].includes(row.status)"
              size="small"
              type="warning"
              @click.stop="cancelExecTask(row)"
            >
              取消
            </el-button>
            <el-button
              size="small"
              type="danger"
              :disabled="['PENDING', 'RUNNING'].includes(row.status)"
              @click.stop="removeExecTask(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-row" v-if="total > 0">
        <el-pagination
          v-model:current-page="filters.page"
          layout="total, prev, pager, next"
          :total="total"
          :page-size="20"
          @current-change="load"
        />
      </div>

      <el-empty v-if="rows.length === 0" description="暂无 UI 执行记录" />
    </div>
  </section>
</template>

<script setup>
/**
 * frontend/src/views/task_center/UiExecRecordsView.vue
 *
 * 文件用途
 * -------
 * 任务中心 - UI 执行记录页：
 * - 展示 UiExecTask（一次 UI 测试计划的运行）
 * - 点击进入该执行记录下的场景任务明细（UiTask 列表，按 exec_task 过滤）
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { projectApi, uiExecTaskApi, uiPlanApi } from '../../api/resources'

const { embedded = false } = defineProps({
  embedded: { type: Boolean, default: false }
})

const router = useRouter()
const route = useRoute()

const projects = ref([])
const plans = ref([])
const data = ref([])

const filters = reactive({ project: null, plan: null, status: null, page: 1 })
const rows = computed(() => data.value.results || data.value || [])
const total = computed(() => data.value.count || rows.value.length)

const focusedId = computed(() => (route.query.exec_task ? Number(route.query.exec_task) : null))

async function loadPlans() {
  const res = await uiPlanApi.list({ project: filters.project || undefined })
  plans.value = res.results || res
}

async function load() {
  const p = await projectApi.list()
  projects.value = p.results || p
  await loadPlans()

  // 如果从“运行”跳过来带 exec_task，则直接展示该条记录
  if (focusedId.value) {
    const detail = await uiExecTaskApi.detail(focusedId.value)
    data.value = [detail]
    return
  }

  data.value = await uiExecTaskApi.list({
    project: filters.project || undefined,
    plan: filters.plan || undefined,
    status: filters.status || undefined,
    page: filters.page
  })
}

async function handleProjectChange() {
  filters.plan = null
  filters.page = 1
  await load()
}

async function resetFilters() {
  filters.project = null
  filters.plan = null
  filters.status = null
  filters.page = 1
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

function openTasks(row) {
  router.push({ path: '/ui-tasks', query: { exec_task: row.id } })
}

async function cancelExecTask(row) {
  await ElMessageBox.confirm(`确认取消执行记录 #${row.id}？将取消其下尚未结束的 UI 任务。`, '取消执行记录', { type: 'warning' })
  await uiExecTaskApi.cancel(row.id)
  ElMessage.success('已取消')
  await load()
}

async function removeExecTask(row) {
  await ElMessageBox.confirm(
    `确认删除执行记录 #${row.id}？\n删除后将同时删除其下所有 UI 任务、步骤结果、事件与工件。`,
    '删除执行记录',
    { type: 'warning' }
  )
  try {
    await uiExecTaskApi.remove(row.id)
    ElMessage.success('已删除')
  } catch (err) {
    ElMessage.error(err?.response?.data?.detail || '删除失败')
    return
  }
  if (rows.value.length === 1 && filters.page > 1) {
    filters.page -= 1
  }
  await load()
}

function goPlans() {
  router.push({ path: '/task-center', query: { tab: 'plans', type: 'ui' } })
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
.pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
