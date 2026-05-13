/*
 * 文件说明：
 * 1. Pinia 认证状态仓库，负责维护当前登录用户信息，以及登录、退出登录等会话操作。
 * 2. 该仓库依赖 `src/api/resources.js` 中的 authApi，
 *    并与 localStorage 配合实现页面刷新后的登录态恢复。
 * 3. `src/layouts/MainLayout.vue`、`src/views/LoginView.vue` 等页面通过它获取用户态与触发鉴权动作。
 */
import { defineStore } from 'pinia'
import { authApi } from '../api/resources'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    user: JSON.parse(localStorage.getItem('nexus_user') || 'null')
  }),
  actions: {
    async login(form) {
      this.user = await authApi.login(form)
      localStorage.setItem('nexus_user', JSON.stringify(this.user))
    },
    async logout() {
      await authApi.logout()
      this.user = null
      localStorage.removeItem('nexus_user')
    }
  }
})
