<template>
  <el-container class="shell">
    <el-aside width="220px" class="aside">
      <div class="brand">Nexus API</div>
      <el-menu router :default-active="$route.path" background-color="#111827" text-color="#d1d5db" active-text-color="#fff">
        <el-menu-item index="/dashboard">工作台</el-menu-item>
        <el-menu-item index="/projects">项目环境</el-menu-item>
        <el-menu-item index="/variables">变量管理</el-menu-item>
        <el-menu-item index="/cookies">Cookie 管理器</el-menu-item>
        <el-menu-item index="/api-definitions">接口管理</el-menu-item>
        <el-menu-item index="/import">Excel 导入</el-menu-item>
        <el-menu-item index="/cases">用例列表</el-menu-item>
        <el-menu-item index="/scenarios">场景用例</el-menu-item>
        <el-menu-item index="/plans">测试计划</el-menu-item>
        <el-menu-item index="/schedules">定时任务</el-menu-item>
        <el-menu-item index="/tasks">执行任务</el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <span>{{ auth.user?.username }}</span>
        <el-button size="small" @click="handleLogout">退出</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

async function handleLogout() {
  await auth.logout()
  router.push('/login')
}
</script>

<style scoped>
.shell {
  min-height: 100vh;
}
.aside {
  background: #111827;
}
.brand {
  height: 56px;
  padding: 16px 20px;
  color: white;
  font-size: 18px;
  font-weight: 700;
}
.header {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  background: #fff;
  border-bottom: 1px solid #e5e7eb;
}
</style>
