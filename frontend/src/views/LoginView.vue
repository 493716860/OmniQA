<template>
  <main class="login-page">
    <el-form class="login-card" :model="form" @submit.prevent="submit">
      <h1>Nexus API</h1>
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
