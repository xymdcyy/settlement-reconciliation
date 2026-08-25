<template>
  <div class="customer-detail-page">
    <el-page-header :title="customer?.name || '客户详情'" @back="goHome" />

    <el-tabs v-model="activeTab" class="mt-4">
      <el-tab-pane label="台账" name="ledger">
        <LedgerTab :customer-id="customerId" />
      </el-tab-pane>

      <el-tab-pane label="核对" name="reconciliation" v-if="customer?.has_statement">
        <ReconciliationTab :customer-id="customerId" />
      </el-tab-pane>

      <el-tab-pane label="开票" name="billing">
        <BillingTab :customer-id="customerId" />
      </el-tab-pane>

      <el-tab-pane label="未决池" name="pending-pool">
        <PendingPoolTab :customer-id="customerId" />
      </el-tab-pane>

      <el-tab-pane label="红冲" name="red-flush">
        <RedFlushTab :customer-id="customerId" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getCustomer } from '../api'
import LedgerTab from '../components/tabs/LedgerTab.vue'
import ReconciliationTab from '../components/tabs/ReconciliationTab.vue'
import BillingTab from '../components/tabs/BillingTab.vue'
import PendingPoolTab from '../components/tabs/PendingPoolTab.vue'
import RedFlushTab from '../components/tabs/RedFlushTab.vue'

const route = useRoute()
const router = useRouter()
const customerId = computed(() => parseInt(route.params.id))
const customer = ref(null)
const activeTab = ref('ledger')

// 返回工作台（详情页若是首次进入/刷新，无历史可回退，直接跳首页）
const goHome = () => {
  router.push('/')
}

const loadCustomer = async () => {
  try {
    const res = await getCustomer(customerId.value)
    customer.value = res.data
  } catch (error) {
    console.error('加载客户信息失败:', error)
  }
}

onMounted(() => {
  loadCustomer()
})
</script>

<style scoped>
.customer-detail-page {
  padding: 20px;
}
</style>
