/**
 * frontend/src/router/index.js
 *
 * 文件用途
 * -------
 * 前端路由表（Vue Router）。
 *
 * 关键点：
 * 1) 路由模式选择：
 *    - DEV：hash 路由（createWebHashHistory），避免刷新子路由时服务端未配置 history fallback 导致 404
 *    - PROD：history 路由（createWebHistory），配合后端 FrontendCatchAllView / Nginx 返回 index.html
 * 2) 布局路由：
 *    - /login 独立页面
 *    - / 下挂 MainLayout，并以 children 的方式组织各业务页面
 * 3) 轻量鉴权守卫：
 *    - 本地 localStorage 保存 nexus_user 即视为已登录
 *    - 未登录访问非 /login 会被重定向到登录页
 *
 * 与后端的对应关系：
 * - 路由 path 大多对应某个资源域的 CRUD 页面（项目/环境/用例/计划/任务/UI 自动化等）
 * - API 实际调用封装在 src/api/resources.js
 */

import { createRouter, createWebHashHistory, createWebHistory } from 'vue-router'

import MainLayout from '../layouts/MainLayout.vue'
import CasesView from '../views/CasesView.vue'
import DashboardView from '../views/DashboardView.vue'
import ApiDefinitionsView from '../views/ApiDefinitionsView.vue'
import ImportView from '../views/ImportView.vue'
import LoginView from '../views/LoginView.vue'
import PlansView from '../views/PlansView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import SchedulesView from '../views/SchedulesView.vue'
import ScenariosView from '../views/ScenariosView.vue'
import TaskCenterView from '../views/TaskCenterView.vue'
import TaskDetailView from '../views/TaskDetailView.vue'
import TasksView from '../views/TasksView.vue'
import VariablesView from '../views/VariablesView.vue'
import UiScenariosView from '../views/UiScenariosView.vue'
import UiPagesView from '../views/UiPagesView.vue'
import UiDatasetsView from '../views/UiDatasetsView.vue'
import UiRunsView from '../views/UiRunsView.vue'
import UiTasksView from '../views/UiTasksView.vue'
import UiTaskDetailView from '../views/UiTaskDetailView.vue'

const router = createRouter({
  // 开发环境优先用 hash 路由，避免刷新子路由时因服务端 history fallback 配置差异导致白页/404。
  // 生产环境仍使用 history 路由，配合 Nginx / 后端 catch-all 返回 index.html。
  history: import.meta.env.DEV ? createWebHashHistory() : createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: DashboardView },
        { path: 'task-center', component: TaskCenterView },
        { path: 'projects', component: ProjectsView },
        { path: 'variables', component: VariablesView },
        { path: 'api-definitions', component: ApiDefinitionsView },
        { path: 'import', component: ImportView },
        { path: 'cases', component: CasesView },
        { path: 'scenarios', component: ScenariosView },
        { path: 'plans', component: PlansView },
        { path: 'schedules', component: SchedulesView },
        { path: 'tasks', component: TasksView },
        { path: 'tasks/:id', component: TaskDetailView },
        { path: 'ui-scenarios', component: UiScenariosView },
        { path: 'ui-pages', component: UiPagesView },
        { path: 'ui-datasets', component: UiDatasetsView },
        { path: 'ui-runs', component: UiRunsView },
        { path: 'ui-tasks', component: UiTasksView },
        { path: 'ui-tasks/:id', component: UiTaskDetailView }
      ]
    }
  ]
})

router.beforeEach(to => {
  if (to.path !== '/login' && !localStorage.getItem('nexus_user')) {
    return '/login'
  }
})

export default router
