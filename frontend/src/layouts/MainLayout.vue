<template>
  <el-container class="shell">
    <el-aside width="220px" class="aside">
      <div class="brand">OminiQA</div>
      <el-menu router :default-active="$route.path" background-color="#111827" text-color="#d1d5db" active-text-color="#fff">
        <el-menu-item index="/dashboard">工作台</el-menu-item>

        <el-sub-menu index="interface">
          <template #title>接口测试</template>
          <el-sub-menu index="interface-assets">
            <template #title>资产管理</template>
            <el-menu-item index="/api-definitions">接口管理</el-menu-item>
            <el-menu-item index="/cases">用例列表</el-menu-item>
            <el-menu-item index="/scenarios">场景用例</el-menu-item>
          </el-sub-menu>
          <el-menu-item index="/import">Excel 导入</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="ui">
          <template #title>UI 测试</template>
          <el-menu-item index="/ui-pages">页面对象(PO)</el-menu-item>
          <el-menu-item index="/ui-datasets">数据集(DDT)</el-menu-item>
          <el-menu-item index="/ui-scenarios">UI 场景</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="task">
          <template #title>任务管理</template>
          <el-menu-item index="/task-center">任务中心</el-menu-item>
        </el-sub-menu>

        <el-sub-menu index="env">
          <template #title>环境管理</template>
          <el-menu-item index="/projects">项目环境</el-menu-item>
          <el-menu-item index="/variables">变量管理</el-menu-item>
        </el-sub-menu>
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
/*
 * 文件说明：
 * 1. 登录后的主业务布局组件，统一提供侧边导航、顶部用户栏以及内部页面的路由承载区域。
 * 2. 该布局连接路由系统与各业务 views，是 Dashboard、项目环境、接口测试、UI 测试和任务管理页面的共同外壳。
 * 3. 文件内部通过 stores/auth.js 获取当前用户并执行退出登录，退出后再借助 vue-router 跳回登录页。
 */
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
