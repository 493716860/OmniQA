<template>
  <el-alert
    type="info"
    :closable="false"
    show-icon
    title="UI 定时任务暂未实现"
    description="当前后端 Schedule 仅绑定接口测试计划（TestPlan）。如果你希望 UI 测试也支持定时执行，需要后端增加 UiSchedule（绑定 UI 场景+数据集+模式）的模型与执行入口。"
  />
</template>

<script setup>
/**
 * frontend/src/views/task_center/UiScheduleView.vue
 *
 * 文件用途
 * -------
 * UI 定时任务占位页。
 *
 * 你提出的任务管理结构里“定时任务”需要同时支持接口与 UI。
 * 当前代码库后端 Schedule 只支持接口 TestPlan 的定时触发；
 * 因此先在任务中心里给 UI 保留明确入口，并提示下一步后端需要补齐的能力点。
 */
</script>

