<template>
  <section>
    <h1 class="page-title">用例列表</h1>
    <div class="panel">
      <div class="toolbar">
        <el-input v-model="filters.keyword" placeholder="搜索用例/接口" clearable style="width: 260px" />
        <el-input v-model="filters.level" placeholder="等级" clearable style="width: 120px" />
        <el-button type="primary" @click="search">查询</el-button>
        <el-button type="success" @click="openCreate">新增用例</el-button>
      </div>
      <el-table v-loading="loading" :data="caseRows">
        <el-table-column prop="case_code" label="ID" width="110" />
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="title" label="接口" />
        <el-table-column prop="subtitle" label="用例" />
        <el-table-column prop="api_method" label="方法" width="90" />
        <el-table-column prop="api_path" label="路径" />
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column prop="suite" label="套件" width="100" />
        <el-table-column label="标签" width="180">
          <template #default="{ row }">
            <el-tag v-for="tag in row.tags || []" :key="tag" size="small" style="margin-right: 4px">{{ tag }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_setup ? 'warning' : 'success'">{{ row.is_setup ? 'Setup' : 'Case' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="依赖" width="160">
          <template #default="{ row }">
            <el-tag v-for="code in row.dependency_codes" :key="code" size="small" style="margin-right: 4px">
              {{ code }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" @click="copyCase(row)">复制</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!loading && caseRows.length === 0" description="暂无用例，请先导入 Excel">
        <el-button type="primary" @click="$router.push('/import')">去导入 Excel</el-button>
      </el-empty>
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          background
          layout="total, prev, pager, next, jumper"
          @current-change="load"
        />
      </div>
    </div>
    <FullScreenDrawer v-model="visible" :title="form.id ? '编辑用例' : '新增用例'">
      <el-form class="drawer-form" label-width="90px">
        <el-form-item label="接口">
          <el-select v-model="form.api" filterable style="width:100%">
            <el-option v-for="api in apis" :key="api.id" :label="`${api.method} ${api.path}`" :value="api.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="用例ID"><el-input v-model="form.case_code" /></el-form-item>
        <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="子标题"><el-input v-model="form.subtitle" /></el-form-item>
        <el-form-item label="会话Key">
          <el-input v-model="form.session_key" placeholder="default / userA / userB" />
        </el-form-item>
        <el-form-item label="等级"><el-input-number v-model="form.level" :min="1" /></el-form-item>
        <el-form-item label="套件"><el-input v-model="form.suite" placeholder="冒烟 / 回归 / 主流程" /></el-form-item>
        <el-form-item label="标签"><el-input v-model="tagText" placeholder="多个标签用英文逗号分隔，如 smoke,login" /></el-form-item>
        <el-form-item label="预计耗时"><el-input-number v-model="form.estimated_duration_ms" :min="100" :step="100" /> ms</el-form-item>
        <el-form-item label="依赖">
          <el-select v-model="form.dependency_ids" multiple filterable style="width:100%">
            <el-option v-for="item in dependencyOptions" :key="item.id" :label="`${item.case_code} ${item.subtitle || item.title}`" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="请求配置">
          <RequestConfigEditor
            v-model:header="form.header"
            v-model:payload="form.payload"
            v-model:expect="form.expect"
            v-model:extractors="form.extractors"
          />
        </el-form-item>
        <el-form-item label="启用"><el-switch v-model="form.enabled" /></el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="visible=false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
    </FullScreenDrawer>
  </section>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 接口用例管理页面，在接口定义基础上维护可执行测试用例，包括请求配置、断言、变量提取、标签和依赖关系。
 * 2. 页面通过 RequestConfigEditor 组合多个编辑器子组件完成复杂配置录入，并依赖 caseApi、apiDefinitionApi 进行数据读写。
 * 3. 它是测试计划、任务执行与质量看板的重要数据来源，属于接口自动化链路中的核心资产维护页面。
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiDefinitionApi, caseApi } from '../api/resources'
import FullScreenDrawer from '../components/common/FullScreenDrawer.vue'
import RequestConfigEditor from '../components/editors/RequestConfigEditor.vue'

const cases = ref([])
const apis = ref([])
const filters = reactive({ keyword: '', level: '' })
const loading = ref(false)
const visible = ref(false)
const tagText = ref('')
const form = reactive({
  id: null,
  api: null,
  case_code: '',
  title: '',
  subtitle: '',
  session_key: 'default',
  header: {},
  payload: {},
  expect: {},
  extractors: [],
  tags: [],
  suite: '',
  estimated_duration_ms: 1000,
  dependency_ids: [],
  level: 1,
  enabled: true,
  is_setup: false
})
const pagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0
})

const caseRows = computed(() => cases.value.results || cases.value)
const dependencyOptions = computed(() => caseRows.value.filter(item => item.id !== form.id))

async function load() {
  loading.value = true
  try {
    const [data, apiData] = await Promise.all([caseApi.list({
      ...filters,
      page: pagination.page
    }), apiDefinitionApi.list()])
    cases.value = data
    apis.value = apiData.results || apiData
    pagination.total = data.count ?? data.length ?? 0
  } finally {
    loading.value = false
  }
}

function search() {
  pagination.page = 1
  load()
}
function assignForm(row) {
  Object.assign(form, {
    ...row,
    header: { ...(row.header || {}) },
    payload: cloneJson(row.payload || {}),
    expect: cloneJson(row.expect || {}),
    extractors: cloneJson(row.extractors || [])
  })
  form.session_key = (form.session_key || 'default').trim() || 'default'
  form.dependency_ids = row.dependency_ids || row.dependencies || []
  tagText.value = (row.tags || []).join(',')
}
function openCreate() {
  assignForm({ id: null, api: apis.value[0]?.id, case_code: '', title: '', subtitle: '', session_key: 'default', header: {}, payload: {}, expect: {}, extractors: [], tags: [], suite: '', estimated_duration_ms: 1000, dependency_ids: [], level: 1, enabled: true, is_setup: false })
  visible.value = true
}
function openEdit(row) {
  assignForm(row)
  visible.value = true
}
function copyCase(row) {
  assignForm({ ...row, id: null, case_code: `${row.case_code}_copy_${Date.now().toString().slice(-5)}`, subtitle: `${row.subtitle || row.title} copy` })
  visible.value = true
}
function parseTags(value) {
  return value ? value.split(',').map(v => v.trim()).filter(Boolean) : []
}
function cloneJson(value) {
  return JSON.parse(JSON.stringify(value))
}
async function save() {
  try {
    const payload = {
      ...form,
      tags: parseTags(tagText.value)
    }
    form.id ? await caseApi.update(form.id, payload) : await caseApi.create(payload)
    ElMessage.success('已保存')
    visible.value = false
    await load()
  } catch {
    ElMessage.error('保存失败，请检查配置')
  }
}
async function remove(row) {
  await ElMessageBox.confirm(`删除用例 ${row.case_code}?`)
  await caseApi.remove(row.id)
  await load()
}
onMounted(load)
</script>

<style scoped>
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
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
  padding: 14px 0 0;
  background: #fff;
}
</style>
