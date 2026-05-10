<template>
  <section>
    <h1 class="page-title">接口管理</h1>
    <div class="panel">
      <div class="toolbar">
        <el-select v-model="filters.module" placeholder="模块" clearable style="width: 180px">
          <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
        <el-input v-model="filters.keyword" placeholder="搜索接口" clearable style="width: 240px" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" @click="openCreate">新增接口</el-button>
      </div>
      <el-table :data="rows">
        <el-table-column prop="module_name" label="模块" width="140" />
        <el-table-column prop="name" label="接口名称" />
        <el-table-column prop="method" label="方法" width="100" />
        <el-table-column prop="path" label="路径" />
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-drawer v-model="visible" :title="form.id ? '编辑接口' : '新增接口'" size="720px">
      <el-form class="drawer-form" label-width="100px">
        <el-form-item label="模块">
          <el-select v-model="form.module" style="width: 100%">
            <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="方法">
          <el-select v-model="form.method" style="width: 100%">
            <el-option v-for="m in methods" :key="m" :label="m" :value="m" />
          </el-select>
        </el-form-item>
        <el-form-item label="路径"><el-input v-model="form.path" /></el-form-item>
        <el-form-item label="默认Header">
          <KeyValueEditor v-model="form.default_headers" />
        </el-form-item>
      </el-form>
      <div class="drawer-footer">
        <el-button @click="visible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </div>
    </el-drawer>
  </section>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { apiDefinitionApi, moduleApi } from '../api/resources'
import KeyValueEditor from '../components/editors/KeyValueEditor.vue'

const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
const data = ref([])
const modules = ref([])
const visible = ref(false)
const filters = reactive({ module: null, keyword: '' })
const form = reactive({ id: null, module: null, name: '', method: 'POST', path: '', default_headers: {} })
const rows = computed(() => data.value.results || data.value || [])

async function load() {
  data.value = await apiDefinitionApi.list(filters)
  const moduleData = await moduleApi.list()
  modules.value = moduleData.results || moduleData
}
function openCreate() {
  Object.assign(form, { id: null, module: modules.value[0]?.id || null, name: '', method: 'POST', path: '', default_headers: {} })
  visible.value = true
}
function openEdit(row) {
  Object.assign(form, { ...row, default_headers: { ...(row.default_headers || {}) } })
  visible.value = true
}
async function save() {
  const payload = { ...form, default_headers: form.default_headers || {} }
  if (form.id) await apiDefinitionApi.update(form.id, payload)
  else await apiDefinitionApi.create(payload)
  ElMessage.success('已保存')
  visible.value = false
  await load()
}
async function remove(row) {
  await ElMessageBox.confirm(`删除接口 ${row.name}?`)
  await apiDefinitionApi.remove(row.id)
  await load()
}
onMounted(load)
</script>

<style scoped>
.drawer-form {
  padding-right: 8px;
}
.drawer-footer {
  position: sticky;
  bottom: 0;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 14px 0 0;
  background: #fff;
}
</style>
