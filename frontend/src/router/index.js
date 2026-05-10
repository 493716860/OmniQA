import { createRouter, createWebHistory } from 'vue-router'

import MainLayout from '../layouts/MainLayout.vue'
import CasesView from '../views/CasesView.vue'
import DashboardView from '../views/DashboardView.vue'
import ApiDefinitionsView from '../views/ApiDefinitionsView.vue'
import CookiesView from '../views/CookiesView.vue'
import ImportView from '../views/ImportView.vue'
import LoginView from '../views/LoginView.vue'
import PlansView from '../views/PlansView.vue'
import ProjectsView from '../views/ProjectsView.vue'
import SchedulesView from '../views/SchedulesView.vue'
import ScenariosView from '../views/ScenariosView.vue'
import TaskDetailView from '../views/TaskDetailView.vue'
import TasksView from '../views/TasksView.vue'
import VariablesView from '../views/VariablesView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    {
      path: '/',
      component: MainLayout,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard', component: DashboardView },
        { path: 'projects', component: ProjectsView },
        { path: 'variables', component: VariablesView },
        { path: 'cookies', component: CookiesView },
        { path: 'api-definitions', component: ApiDefinitionsView },
        { path: 'import', component: ImportView },
        { path: 'cases', component: CasesView },
        { path: 'scenarios', component: ScenariosView },
        { path: 'plans', component: PlansView },
        { path: 'schedules', component: SchedulesView },
        { path: 'tasks', component: TasksView },
        { path: 'tasks/:id', component: TaskDetailView }
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
