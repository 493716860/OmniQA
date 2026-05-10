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
        <el-table-column label="环境">
          <template #default="{ row }">
            <el-button size="small" @click="selectedProject = row; loadEnvs(row.id)">查看环境</el-button>
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
        <el-table-column prop="timeout_seconds" label="Timeout" width="100" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { environmentApi, projectApi } from '../api/resources'

const projects = ref([])
const envs = ref([])
const selectedProject = ref(null)
const projectForm = reactive({ name: '' })
const envForm = reactive({ name: '', base_url: '' })

async function loadProjects() {
  projects.value = await projectApi.list()
}
async function createProject() {
  await projectApi.create(projectForm)
  projectForm.name = ''
  await loadProjects()
}
async function loadEnvs(project) {
  envs.value = await environmentApi.list({ project })
}
async function createEnv() {
  await environmentApi.create({ ...envForm, project: selectedProject.value.id })
  envForm.name = ''
  envForm.base_url = ''
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
