<template>
  <section>
    <h1 class="page-title">变量管理</h1>
    <div class="panel">
      <div class="toolbar">
        <el-select v-model="project" placeholder="项目" style="width: 180px" @change="loadEnvs">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="environment" placeholder="环境" clearable style="width: 180px">
          <el-option v-for="e in envs" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-button type="primary" @click="openCreate('project')">新增项目变量</el-button>
        <el-button type="success" :disabled="!environment" @click="openCreate('environment')">新增环境变量</el-button>
      </div>
      <h3>项目变量</h3>
      <el-table :data="projectVars">
        <el-table-column prop="key" label="Key" width="180" />
        <el-table-column prop="value" label="Value" />
        <el-table-column prop="description" label="说明" />
        <el-table-column prop="enabled" label="启用" width="80" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit('project', row)">编辑</el-button>
            <el-popconfirm title="确定要删除此变量吗？" @confirm="remove('project', row.id)">
              <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <h3>环境变量</h3>
      <el-table :data="environmentVars">
        <el-table-column prop="key" label="Key" width="180" />
        <el-table-column prop="value" label="Value" />
        <el-table-column prop="description" label="说明" />
        <el-table-column prop="enabled" label="启用" width="80" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit('environment', row)">编辑</el-button>
            <el-popconfirm title="确定要删除此变量吗？" @confirm="remove('environment', row.id)">
              <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>
    <el-dialog v-model="visible" title="变量" width="520px">
      <el-form label-width="80px">
        <el-form-item label="Key"><el-input v-model="form.key" /></el-form-item>
        <el-form-item label="Value"><el-input v-model="form.value" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="visible=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 变量管理页面，用于维护项目变量和环境变量，支持测试执行时的动态参数注入。
 * 2. 页面依赖项目、环境以及变量相关 API，和 RequestConfigEditor 中的变量引用能力形成前后呼应。
 * 3. 这里配置的变量会被接口用例、场景步骤、页面对象或 UI 运行过程引用，是跨模块共享配置的重要入口。
 */
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref, watch } from 'vue'
import { environmentApi, environmentVariableApi, projectApi, projectVariableApi } from '../api/resources'

const projects = ref([])
const envs = ref([])
const projectVars = ref([])
const environmentVars = ref([])
const project = ref(null)
const environment = ref(null)
const scope = ref('project')
const visible = ref(false)
const form = reactive({ id: null, key: '', value: '', description: '', enabled: true })

async function load() {
  const p = await projectApi.list()
  projects.value = p.results || p
  if (!project.value && projects.value.length) project.value = projects.value[0].id
  await loadEnvs()
  await loadVars()
}
async function loadEnvs() {
  if (!project.value) return
  const e = await environmentApi.list({ project: project.value })
  envs.value = e.results || e
  if (!environment.value && envs.value.length) environment.value = envs.value[0].id
}
async function loadVars() {
  const [pv, ev] = await Promise.all([
    project.value ? projectVariableApi.list({ project: project.value }) : [],
    environment.value ? environmentVariableApi.list({ environment: environment.value }) : []
  ])
  projectVars.value = pv.results || pv
  environmentVars.value = ev.results || ev
}
function openCreate(nextScope) {
  scope.value = nextScope
  Object.assign(form, { id: null, key: '', value: '', description: '', enabled: true })
  visible.value = true
}
function openEdit(nextScope, row) {
  scope.value = nextScope
  Object.assign(form, row)
  visible.value = true
}
async function save() {
  const payload = { ...form }
  if (scope.value === 'project') {
    payload.project = project.value
    form.id ? await projectVariableApi.update(form.id, payload) : await projectVariableApi.create(payload)
  } else {
    payload.environment = environment.value
    form.id ? await environmentVariableApi.update(form.id, payload) : await environmentVariableApi.create(payload)
  }
  ElMessage.success('已保存')
  visible.value = false
  await loadVars()
}
async function remove(scopeType, id) {
  if (scopeType === 'project') {
    await projectVariableApi.remove(id)
  } else {
    await environmentVariableApi.remove(id)
  }
  ElMessage.success('已删除')
  await loadVars()
}
watch([project, environment], loadVars)
onMounted(load)
</script>
