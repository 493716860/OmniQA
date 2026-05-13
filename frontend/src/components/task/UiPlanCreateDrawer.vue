<template>
  <FullScreenDrawer v-model="visibleProxy" :title="title">
    <el-form label-width="100px" style="max-width: 980px;">
      <el-form-item label="项目">
        <el-select v-model="form.project" style="width: 100%" @change="emit('project-change')">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="计划名称">
        <el-input v-model="form.name" placeholder="如：UI 回归（登录+下单）" />
      </el-form-item>
      <el-form-item label="关联场景">
        <el-select v-model="form.scenario_ids" multiple filterable style="width: 100%" placeholder="选择已创建的 UI 场景">
          <el-option v-for="s in scenarios" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="默认数据集">
        <el-select v-model="form.default_dataset" clearable filterable style="width: 100%">
          <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="默认模式">
        <el-select v-model="form.default_mode" style="width: 200px">
          <el-option label="无头（HEADLESS）" value="HEADLESS" />
          <el-option label="有头（HEADED）" value="HEADED" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visibleProxy=false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="!canSubmit" @click="emit('submit')">保存</el-button>
    </template>
  </FullScreenDrawer>
</template>

<script setup>
import { computed } from 'vue'
import FullScreenDrawer from '../common/FullScreenDrawer.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: '新建 UI 测试计划' },
  projects: { type: Array, default: () => [] },
  scenarios: { type: Array, default: () => [] },
  datasets: { type: Array, default: () => [] },
  form: { type: Object, required: true },
  saving: { type: Boolean, default: false }
})

const emit = defineEmits(['update:visible', 'submit', 'project-change'])

const visibleProxy = computed({
  get: () => props.visible,
  set: v => emit('update:visible', v)
})

const canSubmit = computed(() => {
  if (!props.form.project) return false
  if (!String(props.form.name || '').trim()) return false
  return Array.isArray(props.form.scenario_ids) && props.form.scenario_ids.length > 0
})
</script>
