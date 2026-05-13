/*
 * 文件说明：
 * 1. 按业务域集中声明前端访问后端的资源接口，覆盖认证、项目环境、接口测试、场景编排、任务执行与 UI 自动化等模块。
 * 2. 各 views、stores 与复合组件通过这里暴露的 API 对象发起请求，避免在页面中散落具体 URL，统一维护后端接口映射。
 * 3. 本文件依赖 http.js 提供的通用请求实例，是“页面/状态层”和“后端 REST 接口”之间的适配层。
 */
import { http } from './http'

export const authApi = {
  login: data => http.post('/auth/login/', data),
  logout: () => http.post('/auth/logout/'),
  me: () => http.get('/auth/me/')
}

export const projectApi = {
  list: () => http.get('/projects/'),
  create: data => http.post('/projects/', data),
  update: (id, data) => http.patch(`/projects/${id}/`, data),
  remove: id => http.delete(`/projects/${id}/`)
}

export const environmentApi = {
  list: params => http.get('/environments/', { params }),
  create: data => http.post('/environments/', data),
  update: (id, data) => http.patch(`/environments/${id}/`, data),
  remove: id => http.delete(`/environments/${id}/`)
}

export const projectVariableApi = {
  list: params => http.get('/project-variables/', { params }),
  create: data => http.post('/project-variables/', data),
  update: (id, data) => http.patch(`/project-variables/${id}/`, data),
  remove: id => http.delete(`/project-variables/${id}/`)
}

export const environmentVariableApi = {
  list: params => http.get('/environment-variables/', { params }),
  create: data => http.post('/environment-variables/', data),
  update: (id, data) => http.patch(`/environment-variables/${id}/`, data),
  remove: id => http.delete(`/environment-variables/${id}/`)
}

export const environmentCookieApi = {
  list: params => http.get('/environment-cookies/', { params }),
  update: (id, data) => http.patch(`/environment-cookies/${id}/`, data),
  remove: id => http.delete(`/environment-cookies/${id}/`),
  clear: data => http.post('/environment-cookies/clear/', data)
}

export const importApi = {
  excel: form => http.post('/imports/excel/', form, { headers: { 'Content-Type': 'multipart/form-data' } }),
  curl: data => http.post('/imports/curl/', data)
}

export const dashboardApi = {
  quality: () => http.get('/dashboard/quality/')
}

export const moduleApi = {
  list: params => http.get('/modules/', { params }),
  create: data => http.post('/modules/', data),
  update: (id, data) => http.patch(`/modules/${id}/`, data),
  remove: id => http.delete(`/modules/${id}/`)
}

export const caseApi = {
  list: params => http.get('/cases/', { params }),
  create: data => http.post('/cases/', data),
  update: (id, data) => http.patch(`/cases/${id}/`, data),
  remove: id => http.delete(`/cases/${id}/`)
}

export const apiDefinitionApi = {
  list: params => http.get('/api-definitions/', { params }),
  create: data => http.post('/api-definitions/', data),
  update: (id, data) => http.patch(`/api-definitions/${id}/`, data),
  remove: id => http.delete(`/api-definitions/${id}/`),
  debug: data => http.post('/api-definitions/debug/', data)
}

export const scenarioApi = {
  list: params => http.get('/scenarios/', { params }),
  create: data => http.post('/scenarios/', data),
  update: (id, data) => http.patch(`/scenarios/${id}/`, data),
  remove: id => http.delete(`/scenarios/${id}/`)
}

export const scenarioStepApi = {
  list: params => http.get('/scenario-steps/', { params }),
  create: data => http.post('/scenario-steps/', data),
  update: (id, data) => http.patch(`/scenario-steps/${id}/`, data),
  remove: id => http.delete(`/scenario-steps/${id}/`)
}

export const planApi = {
  list: params => http.get('/test-plans/', { params }),
  create: data => http.post('/test-plans/', data),
  update: (id, data) => http.patch(`/test-plans/${id}/`, data),
  remove: id => http.delete(`/test-plans/${id}/`),
  preview: data => http.post('/test-plans/preview/', data),
  cases: id => http.get(`/test-plans/${id}/cases/`)
}

export const taskApi = {
  list: params => http.get('/test-tasks/', { params }),
  create: data => http.post('/test-tasks/', data),
  detail: id => http.get(`/test-tasks/${id}/`),
  remove: id => http.delete(`/test-tasks/${id}/`),
  cancel: id => http.post(`/test-tasks/${id}/cancel/`),
  results: (id, params) => http.get(`/test-tasks/${id}/results/`, { params }),
  stepResults: (id, params) => http.get(`/test-tasks/${id}/step-results/`, { params }),
  events: (id, params) => http.get(`/test-tasks/${id}/events/`, { params }),
  allure: id => http.get(`/test-tasks/${id}/allure/`)
}

export const scheduleApi = {
  list: () => http.get('/schedules/'),
  create: data => http.post('/schedules/', data),
  update: (id, data) => http.patch(`/schedules/${id}/`, data),
  remove: id => http.delete(`/schedules/${id}/`),
  enable: id => http.post(`/schedules/${id}/enable/`),
  disable: id => http.post(`/schedules/${id}/disable/`),
  runNow: id => http.post(`/schedules/${id}/run-now/`)
}

// -----------------------------
// UI 自动化（Playwright）
// -----------------------------

export const uiScenarioApi = {
  list: params => http.get('/ui-scenarios/', { params }),
  create: data => http.post('/ui-scenarios/', data),
  update: (id, data) => http.patch(`/ui-scenarios/${id}/`, data),
  remove: id => http.delete(`/ui-scenarios/${id}/`)
}

export const uiStepApi = {
  list: params => http.get('/ui-steps/', { params }),
  create: data => http.post('/ui-steps/', data),
  update: (id, data) => http.patch(`/ui-steps/${id}/`, data),
  remove: id => http.delete(`/ui-steps/${id}/`)
}

export const uiTaskApi = {
  list: params => http.get('/ui-tasks/', { params }),
  create: data => http.post('/ui-tasks/', data),
  detail: id => http.get(`/ui-tasks/${id}/`),
  remove: id => http.delete(`/ui-tasks/${id}/`),
  cancel: id => http.post(`/ui-tasks/${id}/cancel/`),
  report: id => http.get(`/ui-tasks/${id}/report/`),
  results: (id, params) => http.get(`/ui-tasks/${id}/results/`, { params }),
  artifacts: id => http.get(`/ui-tasks/${id}/artifacts/`),
  events: (id, params) => http.get(`/ui-tasks/${id}/events/`, { params })
}

export const uiPlanApi = {
  list: params => http.get('/ui-plans/', { params }),
  create: data => http.post('/ui-plans/', data),
  update: (id, data) => http.patch(`/ui-plans/${id}/`, data),
  remove: id => http.delete(`/ui-plans/${id}/`),
  detail: id => http.get(`/ui-plans/${id}/`),
  run: (id, data) => http.post(`/ui-plans/${id}/run/`, data)
}

export const uiExecTaskApi = {
  list: params => http.get('/ui-exec-tasks/', { params }),
  detail: id => http.get(`/ui-exec-tasks/${id}/`),
  cancel: id => http.post(`/ui-exec-tasks/${id}/cancel/`),
  remove: id => http.delete(`/ui-exec-tasks/${id}/`)
}

export const uiPageApi = {
  list: params => http.get('/ui-pages/', { params }),
  create: data => http.post('/ui-pages/', data),
  update: (id, data) => http.patch(`/ui-pages/${id}/`, data),
  remove: id => http.delete(`/ui-pages/${id}/`)
}

export const uiElementApi = {
  list: params => http.get('/ui-elements/', { params }),
  create: data => http.post('/ui-elements/', data),
  update: (id, data) => http.patch(`/ui-elements/${id}/`, data),
  remove: id => http.delete(`/ui-elements/${id}/`)
}

export const uiPageMethodApi = {
  list: params => http.get('/ui-page-methods/', { params }),
  create: data => http.post('/ui-page-methods/', data),
  update: (id, data) => http.patch(`/ui-page-methods/${id}/`, data),
  remove: id => http.delete(`/ui-page-methods/${id}/`)
}

export const uiMethodStepApi = {
  list: params => http.get('/ui-method-steps/', { params }),
  create: data => http.post('/ui-method-steps/', data),
  update: (id, data) => http.patch(`/ui-method-steps/${id}/`, data),
  remove: id => http.delete(`/ui-method-steps/${id}/`)
}

export const uiDatasetApi = {
  list: params => http.get('/ui-datasets/', { params }),
  create: data => http.post('/ui-datasets/', data),
  update: (id, data) => http.patch(`/ui-datasets/${id}/`, data),
  remove: id => http.delete(`/ui-datasets/${id}/`)
}

export const uiDatasetRowApi = {
  list: params => http.get('/ui-dataset-rows/', { params }),
  create: data => http.post('/ui-dataset-rows/', data),
  update: (id, data) => http.patch(`/ui-dataset-rows/${id}/`, data),
  remove: id => http.delete(`/ui-dataset-rows/${id}/`)
}

export const uiScenarioStepApi = {
  list: params => http.get('/ui-scenario-steps/', { params }),
  create: data => http.post('/ui-scenario-steps/', data),
  update: (id, data) => http.patch(`/ui-scenario-steps/${id}/`, data),
  remove: id => http.delete(`/ui-scenario-steps/${id}/`)
}

export const uiRunApi = {
  list: params => http.get('/ui-runs/', { params }),
  create: data => http.post('/ui-runs/', data),
  detail: id => http.get(`/ui-runs/${id}/`)
}
