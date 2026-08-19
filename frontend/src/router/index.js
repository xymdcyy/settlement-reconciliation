import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/upload',
  },
  {
    path: '/upload',
    name: 'Upload',
    component: () => import('../views/UploadPage.vue'),
    meta: { title: '上传对账单' },
  },
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('../views/WorkspacePage.vue'),
    meta: { title: '在线比对工作台' },
  },
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/HistoryPage.vue'),
    meta: { title: '历史查询' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router