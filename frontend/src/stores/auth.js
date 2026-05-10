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
