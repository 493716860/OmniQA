import axios from 'axios'
import { ElMessage } from 'element-plus'

export const http = axios.create({
  baseURL: '/api',
  withCredentials: true,
  timeout: 15000
})

http.interceptors.response.use(
  response => response.data,
  error => {
    const message = error.response?.data?.detail || error.response?.data?.non_field_errors?.[0] || error.message
    ElMessage.error(message)
    if (error.response?.status === 403 || error.response?.status === 401) {
      localStorage.removeItem('nexus_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
