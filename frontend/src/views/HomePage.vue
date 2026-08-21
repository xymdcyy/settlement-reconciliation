<template>
  <div class="home-page">
    <el-page-header title="工作台" />

    <el-card class="mt-4">
      <template #header>
        <div class="flex justify-between items-center">
          <span>我负责的客户 ({{ customers.length }}个)</span>
          <el-button type="primary" @click="$router.push('/admin')">系统管理</el-button>
        </div>
      </template>

      <el-table :data="customers" stripe>
        <el-table-column prop="name" label="客户名称" width="200" />
        <el-table-column label="未开票" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="warning">{{ row.unbilled_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="待核对" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.has_statement" type="info">{{ row.pending_count || 0 }}</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="未决差异" width="100" align="center">
          <template #default="{ row }">
            <el-tag type="danger">{{ row.pending_diff_count || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="goToCustomer(row.id)">
              进入
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCustomers } from '../api'

const router = useRouter()
const customers = ref([])

const loadCustomers = async () => {
  try {
    const res = await getCustomers()
    customers.value = res.data || []
  } catch (error) {
    console.error('加载客户列表失败:', error)
  }
}

const goToCustomer = (id) => {
  router.push(`/customer/${id}`)
}

onMounted(() => {
  loadCustomers()
})
</script>

<style scoped>
.home-page {
  padding: 20px;
}
</style>
