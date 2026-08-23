<template>
  <div class="pending-pool-tab">
    <el-card>
      <template #header>
        <span>未决差异池 ({{ tableData.length }}条)</span>
      </template>

      <!-- 数据表格 -->
      <el-table :data="tableData" stripe v-loading="loading">
        <el-table-column prop="receipt_no" label="单号" width="180" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            {{ formatAmount(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="diff_type" label="差异类型" width="120" align="center">
          <template #default="{ row }">
            <el-tag :type="getDiffType(row.diff_type)">
              {{ getDiffText(row.diff_type) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="pending_months" label="挂账时长" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.pending_months > 3 ? 'danger' : 'warning'">
              {{ row.pending_months }}个月
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="diff_note" label="说明" />
        <el-table-column label="操作" width="200" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="resolveItem(row)">标记已解决</el-button>
            <el-button size="small" type="danger" @click="toRealDiff(row)">转真差异</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getPendingPoolItems, resolvePendingItem, toRealDiff as apiToRealDiff } from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps({
  customerId: {
    type: Number,
    required: true
  }
})

const loading = ref(false)
const tableData = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await getPendingPoolItems(props.customerId)
    tableData.value = res.data.items || []
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const formatAmount = (amount) => {
  return amount ? `￥${parseFloat(amount).toFixed(2)}` : '-'
}

const getDiffType = (type) => {
  const map = {
    time_diff: 'warning',
    price_diff: 'danger',
    qty_diff: 'danger',
  }
  return map[type] || 'info'
}

const getDiffText = (type) => {
  const map = {
    time_diff: '时间差',
    price_diff: '价格差',
    qty_diff: '数量差',
    customer_not_received: '客户未收货',
    our_not_received: '我方未签收',
  }
  return map[type] || type
}

const resolveItem = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入解决期间 (YYYYMM)', '标记已解决', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /^\d{6}$/,
      inputErrorMessage: '格式错误，请输入 YYYYMM',
    })

    await resolvePendingItem(row.receipt_id, value)
    ElMessage.success('标记成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('标记失败')
    }
  }
}

const toRealDiff = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入差异说明', '转为真差异', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputType: 'textarea',
    })

    await apiToRealDiff(row.receipt_id, value)
    ElMessage.success('转换成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('转换失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.pending-pool-tab {
  padding: 20px 0;
}
</style>
