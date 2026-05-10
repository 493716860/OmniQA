<template>
  <section>
    <h1 class="page-title">定时任务</h1>
    <div class="panel">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增定时任务</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
      <el-table :data="rows">
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="plan_name" label="测试计划" />
        <el-table-column prop="mode" label="模式" width="100" />
        <el-table-column prop="next_run_at" label="下次执行" width="190" />
        <el-table-column prop="enabled" label="启用" width="80" />
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" :type="row.enabled ? 'warning' : 'success'" @click="toggle(row)">{{ row.enabled ? '停用' : '启用' }}</el-button>
            <el-button size="small" type="primary" @click="runNow(row)">立即执行</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="定时任务" width="620px">
      <el-form label-width="100px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="测试计划">
          <el-select v-model="form.plan" style="width:100%">
            <el-option v-for="p in plans" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模式">
          <el-radio-group v-model="form.mode">
            <el-radio-button label="SIMPLE">简单周期</el-radio-button>
            <el-radio-button label="CRON">Cron</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <template v-if="form.mode === 'SIMPLE'">
          <el-form-item label="周期">
            <el-select v-model="form.simple_type" style="width:100%">
              <el-option label="每天" value="DAILY" />
              <el-option label="每周" value="WEEKLY" />
              <el-option label="每N小时" value="HOURLY" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="form.simple_type === 'HOURLY'" label="间隔小时">
            <el-input-number v-model="form.interval_hours" :min="1" />
          </el-form-item>
          <el-form-item v-else label="执行时间">
            <el-time-picker v-model="form.run_time" value-format="HH:mm:ss" />
          </el-form-item>
        </template>
        <el-form-item v-else label="Cron">
          <el-input v-model="form.cron" placeholder="*/30 * * * *" />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { planApi, scheduleApi } from '../api/resources'

const schedules = ref([])
const plans = ref([])
const visible = ref(false)
const form = reactive({ id: null, name: '', plan: null, mode: 'SIMPLE', simple_type: 'DAILY', interval_hours: 1, run_time: '09:00:00', cron: '', enabled: false })
const rows = computed(() => schedules.value.results || schedules.value || [])

async function load() {
  const [scheduleData, planData] = await Promise.all([scheduleApi.list(), planApi.list()])
  schedules.value = scheduleData
  plans.value = planData.results || planData
}
function openCreate() {
  Object.assign(form, { id: null, name: '', plan: plans.value[0]?.id, mode: 'SIMPLE', simple_type: 'DAILY', interval_hours: 1, run_time: '09:00:00', cron: '', enabled: false })
  visible.value = true
}
function openEdit(row) {
  Object.assign(form, row)
  visible.value = true
}
async function save() {
  form.id ? await scheduleApi.update(form.id, form) : await scheduleApi.create(form)
  ElMessage.success('已保存')
  visible.value = false
  await load()
}
async function toggle(row) {
  row.enabled ? await scheduleApi.disable(row.id) : await scheduleApi.enable(row.id)
  await load()
}
async function runNow(row) {
  const task = await scheduleApi.runNow(row.id)
  ElMessage.success(`已创建任务 #${task.id}`)
}
onMounted(load)
</script>
