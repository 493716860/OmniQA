<template>
  <section>
    <h1 class="page-title">UI 场景（编排）</h1>

    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.project" placeholder="项目" clearable style="width: 200px" @change="load">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索场景" clearable style="width: 240px" @keyup.enter="load" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" @click="openCreate">新增场景</el-button>
      </div>

      <el-table :data="rows" @row-click="openEdit">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="project_name" label="项目" width="140" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="name" label="场景名称" />
        <el-table-column prop="enabled" label="启用" width="90">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click.stop="removeScenario(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="rows.length === 0" description="暂无 UI 场景" />
    </div>

    <FullScreenDrawer v-model="visible" :title="form.id ? '编辑 UI 场景' : '新增 UI 场景'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="form.project" style="width: 100%" @change="loadModules">
            <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-select v-model="form.module" clearable style="width: 100%">
            <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>

      <div class="panel" style="margin-top: 16px;">
        <div class="toolbar">
          <strong>场景步骤（只编排页面方法）</strong>
          <el-button size="small" type="primary" @click="openStepCreate" :disabled="!form.id">新增步骤</el-button>
          <el-button size="small" @click="loadScenarioSteps" :disabled="!form.id">刷新</el-button>
        </div>
        <el-alert v-if="!form.id" type="warning" :closable="false" title="请先保存场景，再新增步骤" show-icon />
        <el-table :data="scenarioSteps" size="small">
          <el-table-column prop="sort_order" label="#" width="60" />
          <el-table-column prop="name" label="步骤名" width="200" />
          <el-table-column label="方法">
            <template #default="{ row }">
              <span>{{ row.page_name }} / {{ row.method_name }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="enabled" label="启用" width="90">
            <template #default="{ row }">
              <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-button size="small" @click="openStepEdit(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="removeScenarioStep(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="drawer-footer">
        <el-button @click="visible=false">关闭</el-button>
        <el-button type="primary" @click="saveScenario">保存场景</el-button>
      </div>
    </FullScreenDrawer>

    <FullScreenDrawer v-model="stepVisible" :title="stepForm.id ? '编辑步骤' : '新增步骤'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="步骤名"><el-input v-model="stepForm.name" placeholder="可选" /></el-form-item>
        <el-form-item label="页面方法">
          <el-select v-model="stepForm.method" filterable style="width: 100%">
            <el-option v-for="m in methods" :key="m.id" :label="`${m.page_name} / ${m.name}`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序"><el-input-number v-model="stepForm.sort_order" :min="0" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="stepForm.enabled" /></el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="stepVisible=false">取消</el-button>
        <el-button type="primary" @click="saveScenarioStep">保存</el-button>
      </div>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. UI 场景编排页面，用于把页面方法按顺序组织成可执行 UI 测试流程（资产维护/编排层）。
 * 2. 本页面只负责“维护 UI 场景与步骤”，不负责创建运行或查看执行记录；
 *    运行（创建 Run）与执行记录请统一到“任务管理”模块中处理（UiRunsView / UiTasksView）。
 * 3. 它强调“方法级复用”，步骤维护的是页面方法引用而非底层元素操作细节。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { moduleApi, projectApi, uiPageMethodApi, uiScenarioApi, uiScenarioStepApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'
const projects = ref([])
const modules = ref([])
const data = ref([])
const methods = ref([])
const scenarioSteps = ref([])


const filters = reactive({ project: null, keyword: '' })
const visible = ref(false)
const stepVisible = ref(false)

const form = reactive({ id: null, project: null, module: null, name: '', description: '', enabled: true })

const stepForm = reactive({ id: null, scenario: null, name: '', method: null, sort_order: 1, enabled: true })

const rows = computed(() => data.value.results || data.value || [])

const route = useRoute()

async function load() {
  const p = await projectApi.list()
  projects.value = p.results || p
  data.value = await uiScenarioApi.list({ project: filters.project || undefined, keyword: filters.keyword || undefined })
}

async function loadModules() {
  const m = await moduleApi.list({ project: form.project || filters.project || undefined })
  modules.value = m.results || m
}

async function loadMethods() {
  const methodRes = await uiPageMethodApi.list({})
  methods.value = methodRes?.results ?? methodRes ?? []
}

async function loadScenarioSteps() {
  if (!form.id) return
  const res = await uiScenarioStepApi.list({ scenario: form.id })
  scenarioSteps.value = res.results || res
}

function openCreate() {
  Object.assign(form, { id: null, project: filters.project || projects.value[0]?.id || null, module: null, name: '', description: '', enabled: true })
  scenarioSteps.value = []
  visible.value = true
  loadModules()
  loadMethods()
}

async function openEdit(row) {
  Object.assign(form, { id: row.id, project: row.project, module: row.module, name: row.name || '', description: row.description || '', enabled: row.enabled !== false })
  visible.value = true
  await loadModules()
  await loadMethods()
  await loadScenarioSteps()
}

async function saveScenario() {
  const payload = { ...form }
  if (form.id) await uiScenarioApi.update(form.id, payload)
  else {
    const created = await uiScenarioApi.create(payload)
    form.id = created.id
  }
  ElMessage.success('已保存')
  await load()
  await loadScenarioSteps()
}

async function removeScenario(row) {
  await ElMessageBox.confirm(`删除 UI 场景 ${row.name}?`)
  await uiScenarioApi.remove(row.id)
  await load()
}

function openStepCreate() {
  Object.assign(stepForm, { id: null, scenario: form.id, name: '', method: methods.value[0]?.id || null, sort_order: (scenarioSteps.value.length || 0) + 1, enabled: true })
  stepVisible.value = true
}
function openStepEdit(row) {
  Object.assign(stepForm, { id: row.id, scenario: form.id, name: row.name || '', method: row.method, sort_order: row.sort_order || 0, enabled: row.enabled !== false })
  stepVisible.value = true
}
async function saveScenarioStep() {
  const payload = { scenario: form.id, type: 'CALL_METHOD', name: stepForm.name, method: stepForm.method, sort_order: stepForm.sort_order, enabled: stepForm.enabled }
  if (stepForm.id) await uiScenarioStepApi.update(stepForm.id, payload)
  else await uiScenarioStepApi.create(payload)
  ElMessage.success('步骤已保存')
  stepVisible.value = false
  await loadScenarioSteps()
}
async function removeScenarioStep(row) {
  await ElMessageBox.confirm(`删除步骤 ${row.name || row.method_name}?`)
  await uiScenarioStepApi.remove(row.id)
  await loadScenarioSteps()
}

onMounted(load)

// 支持从任务中心“编辑计划”跳转过来：/ui-scenarios?id=<scenarioId>
onMounted(async () => {
  const id = route.query.id ? Number(route.query.id) : null
  if (!id) return
  await load()
  const row = (rows.value || []).find(r => Number(r.id) === id)
  if (row) await openEdit(row)
})
</script>

<style scoped>
.drawer-form {
  padding-right: 8px;
}
.drawer-footer {
  position: sticky;
  bottom: 0;
  z-index: 2;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  background: #fff;
  border-top: 1px solid #e5e7eb;
}
</style>
