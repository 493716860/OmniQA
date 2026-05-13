<template>
  <main class="login-page">
    <el-form class="login-card" :model="form" @submit.prevent="submit">
      <h1>OminiQA</h1>
      <el-form-item>
        <el-input v-model="form.username" placeholder="用户名" />
      </el-form-item>
      <el-form-item>
        <el-input v-model="form.password" type="password" placeholder="密码" show-password />
      </el-form-item>
      <el-button type="primary" native-type="submit" :loading="loading">登录</el-button>
    </el-form>
  </main>
</template>

<script setup>
/*
 * 文件说明：
 * 1. 登录页面，负责采集用户名和密码并触发认证流程，是应用未登录状态下的主要入口。
 * 2. 页面通过 stores/auth.js 调用登录动作，再配合 vue-router 在成功后跳转到主路由，由 MainLayout 承载后续业务页面。
 * 3. 该文件只处理最基本的登录交互与加载状态，不承担权限控制细节，具体鉴权校验由路由与后端接口共同保障。
 */
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const loading = ref(false)
const form = reactive({ username: '', password: '' })

async function submit() {
  loading.value = true
  try {
    await auth.login(form)
    router.push('/')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
}
.login-card {
  width: 360px;
  padding: 28px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}
.login-card h1 {
  margin: 0 0 24px;
}
.login-card .el-button {
  width: 100%;
}
</style>
