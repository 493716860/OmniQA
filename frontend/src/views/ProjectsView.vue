<template>
  <section>
    <h1 class="page-title">项目环境</h1>
    <div class="panel">
      <div class="toolbar">
        <el-input v-model="projectForm.name" placeholder="项目名称" style="width: 240px" />
        <el-button type="primary" @click="createProject">新增项目</el-button>
      </div>
      <el-table :data="projects.results || projects">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="项目" />
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" type="primary" plain @click="selectedProject = row; loadEnvs(row.id); loadModules(row.id)">配置</el-button>
            <el-button size="small" @click="openEditProject(row)">编辑</el-button>
            <el-popconfirm title="确定要删除此项目吗？" @confirm="removeProject(row.id)">
              <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="panel env-panel" v-if="selectedProject">
      <h2>{{ selectedProject.name }} / 环境</h2>
      <div class="toolbar">
        <el-input v-model="envForm.name" placeholder="环境名称" style="width: 180px" />
        <el-input v-model="envForm.base_url" placeholder="Base URL" style="width: 320px" />
        <el-button type="primary" @click="createEnv">新增环境</el-button>
      </div>
      <el-table :data="envs.results || envs">
        <el-table-column prop="name" label="环境" />
        <el-table-column prop="base_url" label="Base URL" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openEditEnv(row)">编辑</el-button>
            <el-popconfirm title="确定要删除此环境吗？" @confirm="removeEnv(row.id)">
              <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="panel env-panel" v-if="selectedProject">
      <h2>{{ selectedProject.name }} / 模块</h2>
      <div class="toolbar">
        <el-input v-model="moduleForm.name" placeholder="模块名称（如：订单、支付、登录）" style="width: 260px" />
        <el-button type="primary" @click="createModule">新增模块</el-button>
      </div>
      <el-table :data="modules.results || modules">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="模块" />
        <el-table-column prop="sort_order" label="排序" width="100" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button size="small" @click="openEditModule(row)">编辑</el-button>
            <el-popconfirm title="确定要删除此模块吗？（若模块下有接口/用例将删除失败）" @confirm="removeModule(row.id)">
              <template #reference><el-button size="small" type="danger" plain>删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="projectDialogVisible" title="编辑项目" width="400px">
      <el-form label-width="80px">
        <el-form-item label="名称"><el-input v-model="editingProject.name" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="projectDialogVisible=false">取消</el-button><el-button type="primary" @click="saveProject">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="envDialogVisible" title="编辑环境" width="500px">
      <el-form label-width="100px">
        <el-form-item label="环境名称"><el-input v-model="editingEnv.name" /></el-form-item>
        <el-form-item label="Base URL"><el-input v-model="editingEnv.base_url" /></el-form-item>
        <el-form-item label="超时(秒)"><el-input-number v-model="editingEnv.timeout_seconds" :min="1" :max="120" /></el-form-item>
        <el-form-item label="校验SSL"><el-switch v-model="editingEnv.verify_ssl" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="envDialogVisible=false">取消</el-button><el-button type="primary" @click="saveEnv">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="moduleDialogVisible" title="编辑模块" width="420px">
      <el-form label-width="90px">
        <el-form-item label="模块名称"><el-input v-model="editingModule.name" /></el-form-item>
        <el-form-item label="排序"><el-input-number v-model="editingModule.sort_order" :min="0" :max="9999" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="moduleDialogVisible=false">取消</el-button>
        <el-button type="primary" @click="saveModule">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 项目与环境管理页面，负责维护测试项目清单及其下属环境（如 dev、test、prod）的基础配置。
 * 2. 页面依赖 projectApi 与 environmentApi 完成增删改查，为变量管理、Cookie 管理、测试计划执行等模块提供环境基础数据。
 * 3. 该页面属于平台配置层，修改结果会影响接口测试与 UI 测试中的环境选择和请求基础地址解析。
 */
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { environmentApi, moduleApi, projectApi } from '../api/resources'

const projects = ref([])
const envs = ref([])
const modules = ref([])
const selectedProject = ref(null)

const projectForm = reactive({ name: '' })
const envForm = reactive({ name: '', base_url: '' })
const moduleForm = reactive({ name: '' })

// 编辑状态控制
const projectDialogVisible = ref(false)
const envDialogVisible = ref(false)
const moduleDialogVisible = ref(false)
const editingProject = reactive({ id: null, name: '' })
const editingEnv = reactive({ id: null, name: '', base_url: '', timeout_seconds: 10, verify_ssl: false })
const editingModule = reactive({ id: null, name: '', sort_order: 0 })

async function loadProjects() {
  projects.value = await projectApi.list()
}
async function createProject() {
  if (!projectForm.name.trim()) return ElMessage.warning('项目名称不能为空')
  await projectApi.create(projectForm)
  projectForm.name = ''
  ElMessage.success('已新增项目')
  await loadProjects()
}
async function removeProject(id) {
  try {
    await projectApi.remove(id)
    ElMessage.success('已删除')
    if (selectedProject.value && selectedProject.value.id === id) {
      selectedProject.value = null
      envs.value = []
      modules.value = []
    }
    await loadProjects()
  } catch (e) {
    ElMessage.error('删除失败，可能存在关联数据')
  }
}
function openEditProject(row) {
  Object.assign(editingProject, row)
  projectDialogVisible.value = true
}
async function saveProject() {
  await projectApi.update(editingProject.id, { name: editingProject.name })
  ElMessage.success('已保存')
  projectDialogVisible.value = false
  await loadProjects()
}

async function loadEnvs(project) {
  envs.value = await environmentApi.list({ project })
}

async function loadModules(project) {
  modules.value = await moduleApi.list({ project })
}

async function createModule() {
  if (!moduleForm.name.trim()) return ElMessage.warning('模块名称不能为空')
  await moduleApi.create({ name: moduleForm.name.trim(), project: selectedProject.value.id, sort_order: 0 })
  moduleForm.name = ''
  ElMessage.success('已新增模块')
  await loadModules(selectedProject.value.id)
}

async function removeModule(id) {
  try {
    await moduleApi.remove(id)
    ElMessage.success('已删除')
    await loadModules(selectedProject.value.id)
  } catch (e) {
    ElMessage.error('删除失败，可能模块下存在接口/用例')
  }
}

function openEditModule(row) {
  Object.assign(editingModule, row)
  moduleDialogVisible.value = true
}

async function saveModule() {
  const { id, ...data } = editingModule
  await moduleApi.update(id, data)
  ElMessage.success('已保存')
  moduleDialogVisible.value = false
  await loadModules(selectedProject.value.id)
}
async function createEnv() {
  if (!envForm.name.trim()) return ElMessage.warning('环境名称不能为空')
  await environmentApi.create({ ...envForm, project: selectedProject.value.id })
  envForm.name = ''
  envForm.base_url = ''
  ElMessage.success('已新增环境')
  await loadEnvs(selectedProject.value.id)
}
async function removeEnv(id) {
  try {
    await environmentApi.remove(id)
    ElMessage.success('已删除')
    await loadEnvs(selectedProject.value.id)
  } catch (e) {
    ElMessage.error('删除失败，可能存在关联数据')
  }
}
function openEditEnv(row) {
  Object.assign(editingEnv, row)
  envDialogVisible.value = true
}
async function saveEnv() {
  const { id, ...data } = editingEnv
  await environmentApi.update(id, data)
  ElMessage.success('已保存')
  envDialogVisible.value = false
  await loadEnvs(selectedProject.value.id)
}

onMounted(loadProjects)
</script>

<style scoped>
.env-panel {
  margin-top: 16px;
}
h2 {
  margin: 0 0 16px;
  font-size: 18px;
}
</style>
