import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { api, post } from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const canEdit = computed(() => ['admin', 'editor'].includes(user.value?.role))
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function authenticate(mode, credentials) {
    const { data } = await post(`/auth/${mode}`, credentials)
    sessionStorage.setItem('datapulse-token', data.access_token)
    user.value = data.user
  }

  async function restore() {
    if (sessionStorage.getItem('datapulse-token')) {
      const { data } = await api('/auth/me')
      user.value = data
    }
  }

  function replaceToken(token) {
    sessionStorage.setItem('datapulse-token', token)
  }

  function logout() {
    sessionStorage.removeItem('datapulse-token')
    user.value = null
  }

  return { user, canEdit, isAdmin, authenticate, restore, replaceToken, logout }
})
