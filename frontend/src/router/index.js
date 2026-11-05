import { createRouter, createWebHistory } from 'vue-router'

const sections = [
  'dashboard',
  'sources',
  'ingestion',
  'datasets',
  'analytics',
  'kpis',
  'trends',
  'insights',
  'reports',
  'alerts',
  'settings',
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/dashboard' },
    ...sections.map((section) => ({
      path: `/${section}`,
      name: section,
      component: () => import('@/views/WorkspaceView.vue'),
      meta: { section },
    })),
    { path: '/:pathMatch(.*)*', redirect: '/dashboard' },
  ],
})

export default router
