import { http } from './http'

export const authApi = {
  login: data => http.post('/auth/login/', data),
  logout: () => http.post('/auth/logout/'),
  me: () => http.get('/auth/me/')
}

export const projectApi = {
  list: () => http.get('/projects/'),
  create: data => http.post('/projects/', data)
}

export const environmentApi = {
  list: params => http.get('/environments/', { params }),
  create: data => http.post('/environments/', data)
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
  excel: form => http.post('/imports/excel/', form, { headers: { 'Content-Type': 'multipart/form-data' } })
}

export const dashboardApi = {
  quality: () => http.get('/dashboard/quality/')
}

export const moduleApi = {
  list: params => http.get('/modules/', { params })
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
  remove: id => http.delete(`/api-definitions/${id}/`)
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
