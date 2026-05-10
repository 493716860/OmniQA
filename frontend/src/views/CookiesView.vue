<template>
  <section>
    <h1 class="page-title">Cookie 管理器</h1>
    <div class="panel">
      <div class="toolbar">
        <el-select v-model="project" placeholder="项目" style="width: 180px" @change="loadEnvs">
          <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-select v-model="environment" placeholder="环境" style="width: 220px" @change="loadCookies">
          <el-option v-for="e in envs" :key="e.id" :label="e.name" :value="e.id" />
        </el-select>
        <el-input v-model="domainKeyword" placeholder="按域名过滤" clearable style="width: 220px" @change="loadCookies" />
        <el-button type="primary" @click="loadCookies">刷新</el-button>
        <el-button type="danger" :disabled="!environment" @click="clearEnvironment">清空当前环境</el-button>
      </div>
      <el-alert
        title="Cookie 会在接口执行时自动写入和更新。一般不需要手动维护；这里主要用于查看、禁用或清空。"
        type="info"
        show-icon
        :closable="false"
      />

      <div v-for="group in groupedCookies" :key="group.domain" class="domain-group">
        <div class="domain-head">
          <strong>{{ group.domain || '(host only)' }}</strong>
          <span>{{ group.items.length }} 个 Cookie</span>
          <el-button size="small" type="danger" text @click="clearDomain(group.domain)">清空域名</el-button>
        </div>
        <el-table :data="group.items" size="small">
          <el-table-column prop="name" label="Name" width="180" />
          <el-table-column label="Value">
            <template #default="{ row }">
              <span class="cookie-value">{{ row.value }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="path" label="Path" width="120" />
          <el-table-column label="Expires" width="190">
            <template #default="{ row }">{{ row.expires_at || 'Session' }}</template>
          </el-table-column>
          <el-table-column label="属性" width="150">
            <template #default="{ row }">
              <el-tag v-if="row.secure" size="small">Secure</el-tag>
              <el-tag v-if="row.http_only" size="small" type="warning">HttpOnly</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="启用" width="90">
            <template #default="{ row }">
              <el-switch v-model="row.enabled" @change="toggle(row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="90">
            <template #default="{ row }">
              <el-button size="small" type="danger" text @click="remove(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <el-empty v-if="cookies.length === 0" description="暂无 Cookie，执行登录接口后会自动写入" />
    </div>
  </section>
</template>

<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, onMounted, ref } from 'vue'
import { environmentApi, environmentCookieApi, projectApi } from '../api/resources'

const projects = ref([])
const envs = ref([])
const cookies = ref([])
const project = ref(null)
const environment = ref(null)
const domainKeyword = ref('')

const groupedCookies = computed(() => {
  const groups = new Map()
  cookies.value.forEach(item => {
    if (!groups.has(item.domain)) groups.set(item.domain, [])
    groups.get(item.domain).push(item)
  })
  return [...groups.entries()].map(([domain, items]) => ({ domain, items }))
})

async function load() {
  const data = await projectApi.list()
  projects.value = data.results || data
  if (!project.value && projects.value.length) project.value = projects.value[0].id
  await loadEnvs()
}

async function loadEnvs() {
  const data = await environmentApi.list({ project: project.value })
  envs.value = data.results || data
  environment.value = envs.value[0]?.id || null
  await loadCookies()
}

async function loadCookies() {
  if (!environment.value) {
    cookies.value = []
    return
  }
  const data = await environmentCookieApi.list({
    environment: environment.value,
    domain: domainKeyword.value || undefined
  })
  cookies.value = data.results || data
}

async function toggle(row) {
  await environmentCookieApi.update(row.id, { enabled: row.enabled })
  ElMessage.success(row.enabled ? 'Cookie 已启用' : 'Cookie 已停用')
}

async function remove(row) {
  await ElMessageBox.confirm(`删除 Cookie ${row.name}?`)
  await environmentCookieApi.remove(row.id)
  await loadCookies()
}

async function clearEnvironment() {
  await ElMessageBox.confirm('清空当前环境下所有 Cookie?')
  const result = await environmentCookieApi.clear({ environment: environment.value })
  ElMessage.success(`已清空 ${result.deleted} 条 Cookie`)
  await loadCookies()
}

async function clearDomain(domain) {
  await ElMessageBox.confirm(`清空域名 ${domain} 下的 Cookie?`)
  const result = await environmentCookieApi.clear({ environment: environment.value, domain })
  ElMessage.success(`已清空 ${result.deleted} 条 Cookie`)
  await loadCookies()
}

onMounted(load)
</script>

<style scoped>
.domain-group {
  margin-top: 18px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: hidden;
}
.domain-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
}
.domain-head span {
  color: #64748b;
}
.cookie-value {
  display: block;
  max-width: 520px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
}
</style>
