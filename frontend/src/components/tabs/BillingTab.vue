<template>
  <div class="billing-tab">
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>开票管理</span>
          <div>
            <el-button type="primary" @click="generateList" :disabled="selectedRows.length === 0">
              生成开票清单 ({{ selectedRows.length }})
            </el-button>
            <el-button @click="importBilled">导入已开票清单</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选栏 -->
      <el-form inline class="mb-4">
        <el-form-item label="期间">
          <el-date-picker
            v-model="period"
            type="month"
            placeholder="选择月份"
            format="YYYYMM"
            value-format="YYYYMM"
            @change="loadData"
          />
        </el-form-item>
      </el-form>

      <!-- 数据表格 -->
      <el-table
        :data="tableData"
        stripe
        v-loading="loading"
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="receipt_no" label="单号" width="180" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            {{ formatAmount(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="customer_name" label="客户" width="200" />
        <el-table-column prop="receipt_date" label="签收日期" width="120" />
      </el-table>

      <div class="mt-4">
        <el-text>已选 {{ selectedRows.length }} 条，总金额: {{ formatAmount(totalAmount) }}</el-text>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getPendingBilling, downloadExcel } from '../../api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  customerId: {
    type: Number,
    required: true
  }
})

const loading = ref(false)
const tableData = ref([])
const selectedRows = ref([])
const period = ref('')

const totalAmount = computed(() => {
  return selectedRows.value.reduce((sum, row) => sum + (parseFloat(row.amount) || 0), 0)
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await getPendingBilling(props.customerId, period.value)
    tableData.value = res.data.items || []
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const handleSelectionChange = (rows) => {
  selectedRows.value = rows
}

const formatAmount = (amount) => {
  return amount ? `￥${parseFloat(amount).toFixed(2)}` : '-'
}

const generateList = async () => {
  try {
    const receiptIds = selectedRows.value.map(r => r.id)
    await downloadExcel('/billing/generate', { receipt_ids: receiptIds }, `开票清单_${receiptIds.length}条.xlsx`)
    ElMessage.success('生成成功')
  } catch (error) {
    ElMessage.error('生成失败: ' + error.message)
  }
}

const importBilled = () => {
  ElMessage.info('导入功能开发中')
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.billing-tab {
  padding: 20px 0;
}
</style>
