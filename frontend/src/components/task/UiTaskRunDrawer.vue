<template>
  <FullScreenDrawer v-model="visibleProxy" :title="title">
    <el-form label-width="90px" style="max-width: 920px;">
      <el-form-item label="项目">
        <el-select v-model="form.project" style="width: 100%" @change="emit('project-change')">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="UI 场景">
        <el-select v-model="form.scenario" filterable style="width: 100%" placeholder="请选择要运行的 UI 场景">
          <el-option v-for="s in scenarios" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="数据集">
        <el-select v-model="form.dataset" filterable style="width: 100%" placeholder="DDT：将按数据行在同一任务内循环执行">
          <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="模式">
        <el-select v-model="form.mode" style="width: 180px">
          <el-option label="无头（HEADLESS）" value="HEADLESS" />
          <el-option label="有头（HEADED）" value="HEADED" />
        </el-select>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visibleProxy = false">取消</el-button>
      <el-button type="primary" :loading="creating" :disabled="!form.scenario || !form.dataset" @click="emit('submit')">
        {{ submitText }}
      </el-button>
    </template>
  </FullScreenDrawer>
</template>

<script setup>
/**
 * frontend/src/components/task/UiTaskRunDrawer.vue
 *
 * 文件用途
 * -------
 * UI 任务“创建并运行”的抽屉组件（任务管理内复用）。
 *
 * 设计动机：
 * - 任务中心里的列表区域高度会随数据量变化，若使用 el-dialog 且不 append-to-body，
 *   弹窗可能被父容器裁剪，导致需要滚动页面才能看全。
 * - 抽屉（Drawer）更符合本项目“创建型操作统一抽屉交互”的习惯（与 PlansView 一致）。
 *
 * 组件职责：
 * - 只负责 UI 与表单交互
 * - 数据加载（项目/场景/数据集列表）与提交动作由父组件控制
 */
import { computed } from 'vue'
import FullScreenDrawer from '../common/FullScreenDrawer.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '运行 UI 计划' },
  submitText: { type: String, default: '运行' },
  projects: { type: Array, default: () => [] },
  scenarios: { type: Array, default: () => [] },
  datasets: { type: Array, default: () => [] },
  form: { type: Object, required: true },
  creating: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'submit', 'project-change'])

const visibleProxy = computed({
  get: () => props.visible,
  set: v => emit('update:visible', v)
})
</script>

<style scoped></style>
