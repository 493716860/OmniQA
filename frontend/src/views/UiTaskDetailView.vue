<template>
  <section>
    <h1 class="page-title">UI 任务详情 #{{ id }}</h1>
    <div class="panel" v-if="task">
      <div class="toolbar">
        <el-tag>{{ task.status }}</el-tag>
        <el-progress :percentage="task.progress" style="width: 240px" />
        <el-button @click="load">刷新</el-button>
        <el-button type="danger" @click="cancel" :disabled="!['PENDING','RUNNING'].includes(task.status)">取消</el-button>
      </div>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="项目">{{ task.project_name }}</el-descriptions-item>
        <el-descriptions-item label="场景">{{ task.scenario_name }}</el-descriptions-item>
        <el-descriptions-item label="模式">{{ task.mode }}</el-descriptions-item>
        <el-descriptions-item label="通过">{{ task.passed_steps }}</el-descriptions-item>
        <el-descriptions-item label="失败">{{ task.failed_steps }}</el-descriptions-item>
        <el-descriptions-item label="跳过">{{ task.skipped_steps }}</el-descriptions-item>
        <el-descriptions-item label="开始">{{ task.started_at }}</el-descriptions-item>
        <el-descriptions-item label="结束">{{ task.finished_at }}</el-descriptions-item>
        <el-descriptions-item label="失败原因">{{ task.failure_reason }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <div class="panel results">
      <div class="toolbar">
        <strong>步骤结果</strong>
        <el-select v-model="filters.status" clearable placeholder="状态" style="width: 140px" @change="loadResults">
          <el-option label="失败" value="FAILED" />
          <el-option label="错误" value="ERROR" />
          <el-option label="跳过" value="SKIPPED" />
          <el-option label="通过" value="PASSED" />
        </el-select>
      </div>
      <el-table :data="resultRows">
        <el-table-column prop="id" label="#" width="80" />
        <el-table-column prop="step_name" label="步骤" width="220" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="duration_ms" label="耗时(ms)" width="120" />
        <el-table-column prop="failure_category" label="分类" width="160" />
        <el-table-column prop="error_message" label="错误" />
      </el-table>
    </div>

    <div class="panel results">
      <div class="toolbar">
        <strong>工件</strong>
        <el-button size="small" @click="loadArtifacts">刷新工件</el-button>
      </div>
      <el-table :data="artifactRows">
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column prop="name" label="名称" width="220" />
        <el-table-column prop="url" label="链接">
          <template #default="{ row }">
            <a v-if="row.url" :href="row.url" target="_blank" rel="noreferrer">{{ row.url }}</a>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="panel results">
      <div class="toolbar">
        <strong>事件</strong>
        <el-select v-model="eventFilters.level" clearable placeholder="级别" style="width: 140px" @change="loadEvents">
          <el-option label="信息" value="INFO" />
          <el-option label="警告" value="WARN" />
          <el-option label="错误" value="ERROR" />
        </el-select>
        <el-button size="small" @click="loadEvents">刷新事件</el-button>
      </div>
      <el-table :data="eventRows" height="420">
        <el-table-column prop="id" label="#" width="80" />
        <el-table-column prop="created_at" label="时间" width="180" />
        <el-table-column prop="level" label="级别" width="100" />
        <el-table-column prop="category" label="类别" width="120" />
        <el-table-column prop="step_name" label="步骤" width="200" />
        <el-table-column prop="message" label="消息" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. UI 任务详情页，用于查看单个 UI 子任务的执行状态、步骤结果、工件链接与事件日志。
 * 2. 页面依赖 uiTaskApi，是 UiTasksView 的下钻详情页，也是排查 UI 自动化失败原因、查看 trace 或截图工件的主要入口。
 * 3. 它与 UiPagesView、UiScenariosView、UiDatasetsView 共同构成 UI 自动化闭环：资产建模、场景编排、数据驱动执行、结果回溯。
 */
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { uiTaskApi } from '../api/resources'

const id = useRoute().params.id
const task = ref(null)
const results = ref([])
const artifacts = ref([])
const events = ref([])
const filters = reactive({ status: '' })
const eventFilters = reactive({ level: '' })

const resultRows = computed(() => results.value.results || results.value || [])
const artifactRows = computed(() => artifacts.value.results || artifacts.value || [])
const eventRows = computed(() => events.value.results || events.value || [])

async function load() {
  task.value = await uiTaskApi.detail(id)
  await Promise.all([loadResults(), loadArtifacts(), loadEvents()])
}

async function loadResults() {
  results.value = await uiTaskApi.results(id, { status: filters.status || undefined })
}

async function loadArtifacts() {
  artifacts.value = await uiTaskApi.artifacts(id)
}

async function loadEvents() {
  events.value = await uiTaskApi.events(id, { level: eventFilters.level || undefined })
}

async function cancel() {
  await uiTaskApi.cancel(id)
  ElMessage.success('已取消')
  await load()
}

onMounted(load)
</script>

<style scoped>
.results {
  margin-top: 16px;
}
</style>
