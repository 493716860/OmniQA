<template>
  <section>
    <h1 class="page-title">任务管理</h1>
    <div class="panel task-center-panel">
      <el-tabs v-model="activeTop" type="card" class="task-center-tabs">
        <el-tab-pane name="plans" label="测试计划">
          <el-tabs v-model="activeType" class="inner-tabs task-center-inner-tabs">
            <el-tab-pane name="api" label="接口测试">
              <PlansView :embedded="true" />
            </el-tab-pane>
            <el-tab-pane name="ui" label="UI 测试">
              <UiPlanView />
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane name="schedules" label="定时任务">
          <el-tabs v-model="activeType" class="inner-tabs task-center-inner-tabs">
            <el-tab-pane name="api" label="接口测试">
              <SchedulesView :embedded="true" />
            </el-tab-pane>
            <el-tab-pane name="ui" label="UI 测试">
              <UiScheduleView />
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>

        <el-tab-pane name="records" label="执行记录">
          <el-tabs v-model="activeType" class="inner-tabs task-center-inner-tabs">
            <el-tab-pane name="api" label="接口测试">
              <TasksView :embedded="true" />
            </el-tab-pane>
            <el-tab-pane name="ui" label="UI 测试">
              <UiExecRecordsView :embedded="true" />
            </el-tab-pane>
          </el-tabs>
        </el-tab-pane>
      </el-tabs>
    </div>
  </section>
</template>

<script setup>
/**
 * frontend/src/views/TaskCenterView.vue
 *
 * 文件用途
 * -------
 * 任务管理“总控台”页面（聚合页）。
 *
 * 需求背景：
 * - 原先接口测试下挂“计划与定时”，UI 测试下挂“运行记录”，导致用户心智分散、入口绕。
 * - 本页把“创建/执行任务 + 查看执行记录”统一收敛到任务管理模块中：
 *   1) 测试计划（接口计划 / UI 计划）
 *   2) 定时任务（接口定时 / UI 定时）
 *   3) 执行记录（接口任务 / UI 任务）
 *
 * 设计原则：
 * - 接口测试/UI 测试模块只负责资产与用例/场景维护
 * - 任务管理模块负责“执行”与“记录”
 */
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import PlansView from './PlansView.vue'
import SchedulesView from './SchedulesView.vue'
import TasksView from './TasksView.vue'
import UiTasksView from './UiTasksView.vue'
import UiPlanView from './task_center/UiPlanView.vue'
import UiExecRecordsView from './task_center/UiExecRecordsView.vue'
import UiScheduleView from './task_center/UiScheduleView.vue'

const route = useRoute()
const activeTop = ref('plans')
const activeType = ref('api')

function syncFromQuery() {
  const tab = String(route.query.tab || '')
  const type = String(route.query.type || '')
  if (['plans', 'schedules', 'records'].includes(tab)) activeTop.value = tab
  if (['api', 'ui'].includes(type)) activeType.value = type
}

onMounted(syncFromQuery)
watch(() => route.query, syncFromQuery)
</script>

<style scoped>
.inner-tabs {
  margin-top: 8px;
}

/* Element Plus Tabs 默认 content 区域没有 padding，嵌套页面会显得“贴边/拥挤”。 */
.task-center-panel :deep(.el-tabs__content) {
  padding-top: 12px;
}

/* card tabs 的头部背景更浅一些，贴合 .panel 视觉 */
.task-center-tabs :deep(.el-tabs__header) {
  margin: 0;
}
</style>
