<template>
  <section>
    <h1 class="page-title">任务详情 #{{ id }}</h1>
    <div class="panel" v-if="task">
      <div class="toolbar">
        <el-tag>{{ task.status }}</el-tag>
        <el-progress :percentage="task.progress" style="width: 240px" />
        <el-button @click="load">刷新</el-button>
        <el-button type="danger" @click="cancel">取消</el-button>
        <el-button @click="loadAllure">Allure 报告</el-button>
      </div>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="计划">{{ task.plan_name }}</el-descriptions-item>
        <el-descriptions-item label="通过">{{ task.passed_count }}</el-descriptions-item>
        <el-descriptions-item label="失败">{{ task.failed_count }}</el-descriptions-item>
        <el-descriptions-item label="跳过">{{ task.skipped_count }}</el-descriptions-item>
        <el-descriptions-item label="当前用例">{{ task.current_case_code }} {{ task.current_case_title }}</el-descriptions-item>
        <el-descriptions-item label="当前步骤">{{ task.current_step_name || task.current_step_message }}</el-descriptions-item>
        <el-descriptions-item label="开始">{{ task.started_at }}</el-descriptions-item>
        <el-descriptions-item label="结束">{{ task.finished_at }}</el-descriptions-item>
        <el-descriptions-item label="失败原因">{{ task.failure_reason }}</el-descriptions-item>
      </el-descriptions>
      <el-input class="log-box" type="textarea" :rows="4" readonly :model-value="task.log" />
    </div>
    <div class="panel results">
      <div class="toolbar">
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px" @change="loadResults">
          <el-option label="失败" value="FAILED" />
          <el-option label="错误" value="ERROR" />
          <el-option label="跳过" value="SKIPPED" />
          <el-option label="通过" value="PASSED" />
        </el-select>
        <el-select v-model="filters.failure_category" clearable placeholder="失败分类" style="width: 180px" @change="loadResults">
          <el-option label="断言失败" value="ASSERTION_FAILED" />
          <el-option label="请求异常" value="REQUEST_ERROR" />
          <el-option label="依赖失败" value="DEPENDENCY_FAILED" />
          <el-option label="环境异常" value="ENVIRONMENT_ERROR" />
          <el-option label="脚本异常" value="SCRIPT_ERROR" />
          <el-option label="响应解析失败" value="RESPONSE_PARSE_ERROR" />
          <el-option label="超时" value="TIMEOUT" />
          <el-option label="网络异常" value="NETWORK_ERROR" />
        </el-select>
        <span class="duration">平均耗时 {{ duration.avg }} ms / 最慢 {{ duration.max }} ms</span>
      </div>
      <el-table :data="resultRows" @row-click="openResult">
        <el-table-column prop="case_code" label="用例ID" width="110" />
        <el-table-column prop="title" label="标题" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时(ms)" width="110" />
        <el-table-column prop="response_status" label="HTTP" width="90" />
        <el-table-column label="分类" width="130">
          <template #default="{ row }">{{ categoryLabel(row.failure_category) }}</template>
        </el-table-column>
        <el-table-column prop="assertion_error" label="错误" />
      </el-table>
      <el-empty v-if="resultRows.length === 0" description="暂无执行结果" />
    </div>
    <div class="panel results">
      <h3>场景步骤结果</h3>
      <el-table :data="stepResultRows" @row-click="openStepResult">
        <el-table-column prop="scenario_name" label="场景" />
        <el-table-column prop="step_name" label="步骤" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }"><el-tag :type="statusType(row.status)">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="duration_ms" label="耗时(ms)" width="110" />
        <el-table-column prop="response_status" label="HTTP" width="90" />
        <el-table-column label="分类" width="130">
          <template #default="{ row }">{{ categoryLabel(row.failure_category) }}</template>
        </el-table-column>
        <el-table-column prop="assertion_error" label="错误" />
      </el-table>
    </div>

    <div class="panel results">
      <div class="toolbar">
        <h3 style="margin:0;">执行事件</h3>
        <el-select v-model="eventFilters.level" clearable placeholder="级别" style="width: 140px" @change="loadEvents">
          <el-option label="信息" value="INFO" />
          <el-option label="警告" value="WARN" />
          <el-option label="错误" value="ERROR" />
        </el-select>
        <el-select v-model="eventFilters.category" clearable placeholder="类别" style="width: 160px" @change="loadEvents">
          <el-option label="任务" value="TASK" />
          <el-option label="请求" value="REQUEST" />
          <el-option label="断言" value="ASSERTION" />
          <el-option label="变量提取" value="EXTRACTOR" />
          <el-option label="依赖" value="DEPENDENCY" />
          <el-option label="报告" value="REPORT" />
          <el-option label="系统" value="SYSTEM" />
        </el-select>
        <el-button @click="loadEvents">刷新事件</el-button>
      </div>
      <el-table :data="eventRows" height="420">
        <el-table-column prop="id" label="#" width="80" />
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="level" label="级别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.level === 'ERROR' ? 'danger' : (row.level === 'WARN' ? 'warning' : 'info')">
              {{ row.level }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category" label="类别" width="120" />
        <el-table-column prop="object_type" label="对象" width="140" />
        <el-table-column prop="case_code" label="用例/场景" width="140" />
        <el-table-column prop="step_name" label="步骤" width="180" />
        <el-table-column prop="message" label="消息" min-width="240" show-overflow-tooltip />
      </el-table>
      <el-empty v-if="eventRows.length === 0" description="暂无事件" />
    </div>

    <FullScreenDrawer v-model="drawerVisible" title="执行结果详情">
      <template v-if="selectedResult">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="用例">{{ selectedResult.case_code }} {{ selectedResult.title }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ selectedResult.status }}</el-descriptions-item>
          <el-descriptions-item label="接口">{{ selectedResult.api_method }} {{ selectedResult.api_path }}</el-descriptions-item>
          <el-descriptions-item label="耗时">{{ selectedResult.duration_ms }} ms</el-descriptions-item>
        </el-descriptions>
        <h3>请求</h3>
        <el-button size="small" @click="copyCurl(selectedResult)">复制 curl</el-button>
        <pre>{{ pretty(selectedResult.request_data) }}</pre>
        <h3>响应</h3>
        <pre>{{ selectedResult.response_body }}</pre>
        <h3>错误</h3>
        <pre>{{ selectedResult.assertion_error }}</pre>
      </template>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 接口测试任务详情页，用于展示单次任务的总体状态、接口用例结果、场景步骤结果、执行事件与 Allure 报告入口。
 * 2. 页面依赖 taskApi 拉取任务明细，并通过定时刷新跟踪运行中任务，是 TasksView 的深入诊断页。
 * 3. 该页与 CasesView、ScenariosView、PlansView 形成闭环：前者定义资产，计划触发执行，本页负责落地展示执行证据与失败信息。
 */
import { ElMessage } from 'element-plus'
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { taskApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'

const id = useRoute().params.id
const task = ref(null)
const results = ref([])
const stepResults = ref([])
const events = ref([])
const selectedResult = ref(null)
const drawerVisible = ref(false)
const filters = reactive({ status: '', failure_category: '' })
const eventFilters = reactive({ level: '', category: '' })
let timer = null
const resultRows = computed(() => results.value.results || results.value || [])
const stepResultRows = computed(() => stepResults.value.results || stepResults.value || [])
const eventRows = computed(() => events.value.results || events.value || [])
const duration = computed(() => {
  const rows = [...resultRows.value, ...stepResultRows.value]
  if (!rows.length) return { avg: 0, max: 0 }
  const total = rows.reduce((sum, row) => sum + (row.duration_ms || 0), 0)
  const max = Math.max(...rows.map(row => row.duration_ms || 0))
  return { avg: Math.round(total / rows.length), max }
})

async function load() {
  task.value = await taskApi.detail(id)
  await loadResults()
  await loadEvents()
  if (['PASSED', 'FAILED', 'CANCELED'].includes(task.value.status) && timer) {
    clearInterval(timer)
    timer = null
  }
}
async function loadResults() {
  const params = {
    status: filters.status || undefined,
    failure_category: filters.failure_category || undefined
  }
  results.value = await taskApi.results(id, params)
  stepResults.value = await taskApi.stepResults(id, params)
}

async function loadEvents() {
  const params = {
    level: eventFilters.level || undefined,
    category: eventFilters.category || undefined
  }
  events.value = await taskApi.events(id, params)
}
async function cancel() {
  await taskApi.cancel(id)
  await load()
}
async function loadAllure() {
  const reportWindow = window.open('', '_blank')
  const info = await taskApi.allure(id)
  if (!info.url) {
    reportWindow?.close()
    ElMessage.warning('暂无 Allure 报告')
    return
  }
  if (reportWindow) {
    reportWindow.location.href = info.url
  } else {
    window.location.href = info.url
  }
}
function statusType(status) {
  if (status === 'PASSED') return 'success'
  if (status === 'SKIPPED') return 'warning'
  return 'danger'
}
function categoryLabel(category) {
  const labels = {
    ASSERTION_FAILED: '断言失败',
    REQUEST_ERROR: '请求异常',
    DEPENDENCY_FAILED: '依赖失败',
    ENVIRONMENT_ERROR: '环境异常',
    SCRIPT_ERROR: '脚本异常',
    RESPONSE_PARSE_ERROR: '响应解析失败',
    TIMEOUT: '超时',
    NETWORK_ERROR: '网络异常'
  }
  return labels[category] || '-'
}
function openResult(row) {
  selectedResult.value = row
  drawerVisible.value = true
}
function openStepResult(row) {
  selectedResult.value = row
  drawerVisible.value = true
}
function pretty(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value || '')
  }
}
function shellQuote(value) {
  return `'${String(value ?? '').replace(/'/g, "'\\''")}'`
}
async function copyCurl(row) {
  const request = row.request_data || {}
  const parts = ['curl', '-X', shellQuote(request.method || 'GET'), shellQuote(request.url || '')]
  Object.entries(request.headers || {}).forEach(([key, value]) => {
    parts.push('-H', shellQuote(`${key}: ${value}`))
  })
  if (request.payload !== undefined && request.payload !== null && request.payload !== '') {
    parts.push('--data', shellQuote(typeof request.payload === 'string' ? request.payload : JSON.stringify(request.payload)))
  }
  await navigator.clipboard.writeText(parts.join(' '))
  ElMessage.success('curl 已复制')
}
onMounted(async () => {
  await load()
  timer = setInterval(load, 2000)
})
onUnmounted(() => {
  if (timer) {
    clearInterval(timer)
  }
})
</script>

<style scoped>
.results,
.log-box {
  margin-top: 16px;
}
.duration {
  color: #64748b;
}
pre {
  padding: 12px;
  overflow: auto;
  background: #f5f7fb;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  white-space: pre-wrap;
}
</style>
