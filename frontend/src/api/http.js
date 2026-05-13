/*
 * 文件说明：
 * 1. 统一封装 Axios 实例，负责前端所有 HTTP 请求的基础配置，如 baseURL、超时和跨域凭证。
 * 2. 作为 `src/api/resources.js` 中各资源 API 的底层通信入口，
 *    页面与 store 不直接依赖 axios，而是经由该实例间接访问后端。
 * 3. 响应拦截器集中处理报错提示与登录失效跳转，与 stores/auth.js 的本地用户态共同组成会话失效处理链路。
 */
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
