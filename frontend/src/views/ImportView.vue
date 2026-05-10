<template>
  <section>
    <h1 class="page-title">Excel 导入</h1>
    <div class="panel">
      <el-form label-width="110px" style="max-width: 680px">
        <el-form-item label="项目名称">
          <el-input v-model="form.project_name" placeholder="默认使用文件名" />
        </el-form-item>
        <el-form-item label="模块名称">
          <el-input v-model="form.module_name" placeholder="默认同项目名称" />
        </el-form-item>
        <el-form-item label="环境名称">
          <el-input v-model="form.environment_name" placeholder="测试环境(dev)" />
        </el-form-item>
        <el-form-item label="Base URL">
          <el-input v-model="form.base_url" placeholder="https://example.com" />
        </el-form-item>
        <el-form-item label="Excel 文件">
          <el-upload :auto-upload="false" :limit="1" :on-change="onFile">
            <el-button>选择文件</el-button>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="submit">开始导入</el-button>
          <el-button v-if="result" @click="$router.push('/cases')">查看用例</el-button>
          <el-button v-if="result" type="success" @click="$router.push('/plans')">创建测试计划</el-button>
        </el-form-item>
      </el-form>
      <el-alert v-if="result" type="success" show-icon :closable="false">
        <template #title>
          新增 {{ result.created }}，更新 {{ result.updated }}，失败 {{ result.failed }}
        </template>
      </el-alert>
      <el-table v-if="result?.errors?.length" :data="result.errors" style="margin-top: 16px">
        <el-table-column prop="sheet" label="Sheet" width="120" />
        <el-table-column prop="row" label="行" width="80" />
        <el-table-column prop="error" label="错误" />
      </el-table>
    </div>
  </section>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { importApi } from '../api/resources'

const loading = ref(false)
const file = ref(null)
const result = ref(null)
const form = reactive({ project_name: '', module_name: '', environment_name: '测试环境(dev)', base_url: '' })

function onFile(uploadFile) {
  file.value = uploadFile.raw
}
async function submit() {
  if (!file.value) return
  loading.value = true
  const body = new FormData()
  body.append('file', file.value)
  Object.entries(form).forEach(([key, value]) => body.append(key, value))
  try {
    result.value = await importApi.excel(body)
  } finally {
    loading.value = false
  }
}
</script>
