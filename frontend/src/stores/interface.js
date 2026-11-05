import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export const useInterfaceStore = defineStore('interface', () => {
  const theme = ref(localStorage.getItem('datapulse-theme') === 'light' ? 'light' : 'dark')
  const collapsed = ref(localStorage.getItem('datapulse-sidebar') === 'collapsed')
  const range = ref({ from: '', to: '' })
  watch(
    theme,
    (value) => {
      document.documentElement.dataset.theme = value
      localStorage.setItem('datapulse-theme', value)
    },
    { immediate: true },
  )
  watch(collapsed, (value) =>
    localStorage.setItem('datapulse-sidebar', value ? 'collapsed' : 'expanded'),
  )
  function toggleTheme() {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
  }
  return { theme, collapsed, range, toggleTheme }
})
