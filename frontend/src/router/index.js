import { createRouter, createWebHistory } from 'vue-router'
import HomePage from '../views/HomePage.vue'
import CustomerDetailPage from '../views/CustomerDetailPage.vue'
import SystemAdminPage from '../views/SystemAdminPage.vue'
import MigrationPage from '../views/MigrationPage.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: HomePage,
    meta: { title: '工作台' }
  },
  {
    path: '/customer/:id',
    name: 'CustomerDetail',
    component: CustomerDetailPage,
    meta: { title: '客户详情' }
  },
  {
    path: '/admin',
    name: 'SystemAdmin',
    component: SystemAdminPage,
    meta: { title: '系统管理' }
  },
  {
    path: '/migration',
    name: 'Migration',
    component: MigrationPage,
    meta: { title: '数据迁移' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  document.title = to.meta.title ? `${to.meta.title} - 结算对账中心` : '结算对账中心'
  next()
})

export default router
