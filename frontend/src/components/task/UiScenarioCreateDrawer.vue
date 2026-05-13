<template>
  <FullScreenDrawer v-model="visibleProxy" title="新建 UI 计划（场景）">
    <el-form label-width="90px" style="max-width: 920px;">
      <el-form-item label="项目">
        <el-select v-model="form.project" style="width: 100%" @change="emit('project-change')">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="模块">
        <el-select v-model="form.module" clearable style="width: 100%" placeholder="可选">
          <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="名称">
        <el-input v-model="form.name" placeholder="如：登录场景（UI）" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visibleProxy=false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!form.project || !String(form.name||'').trim()" @click="emit('submit')">
        保存
      </el-button>
    </template>
  </FullScreenDrawer>
</template>

<script setup>
/**
 * frontend/src/components/task/UiScenarioCreateDrawer.vue
 *
 * 文件用途
 * -------
 * 在“任务中心 → 测试计划 → UI 测试”中创建 UI 计划（本质是 UiScenario）。
 *
 * 说明：
 * - UI 场景的“步骤编排”依然在 UI 场景页面完成
 * - 这里提供快速创建入口，交互与接口“新建计划”一致：先创建，再独立运行
 */
import { computed } from 'vue'
import FullScreenDrawer from '../common/FullScreenDrawer.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  projects: { type: Array, default: () => [] },
  modules: { type: Array, default: () => [] },
  form: { type: Object, required: true },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'project-change', 'submit'])

const visibleProxy = computed({
  get: () => props.visible,
  set: v => emit('update:visible', v)
})
</script>

<style scoped></style>

