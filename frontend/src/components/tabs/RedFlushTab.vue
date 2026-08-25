<template>
  <div class="red-flush-tab">
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>红冲工具</span>
          <div>
            <el-button type="primary" @click="batchFindBlue" :disabled="selectedRows.length === 0">
              批量查找蓝票 ({{ selectedRows.length }})
            </el-button>
            <el-button @click="generateConfirm" :disabled="selectedRows.length === 0">
              生成确认单
            </el-button>
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
        <el-table-column prop="receipt_no" label="退货单号" width="180" />
        <el-table-column prop="model" label="型号" width="120" />
        <el-table-column prop="quantity" label="数量" width="80" align="right" />
        <el-table-column prop="amount" label="金额" width="120" align="right">
          <template #default="{ row }">
            {{ formatAmount(row.amount) }}
          </template>
        </el-table-column>
        <el-table-column prop="blue_invoice_no" label="匹配蓝票" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.blue_invoice_no" type="success">{{ row.blue_invoice_no }}</el-tag>
            <el-tag v-else type="danger">未找到</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="blue_invoice_date" label="开票日期" width="120" />
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="findBlue(row)">查找蓝票</el-button>
            <el-button size="small" @click="recordRed(row)" :disabled="!row.blue_invoice_no">
              回录红通号
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getReturnReceipts, findBlueInvoice, batchFindBlueInvoices, recordRedNotice, downloadExcel } from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'

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

const loadData = async () => {
  loading.value = true
  try {
    const res = await getReturnReceipts(props.customerId, period.value)
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

const findBlue = async (row) => {
  try {
    const res = await findBlueInvoice(row.id)
    if (res.data.blue_invoice_no) {
      row.blue_invoice_no = res.data.blue_invoice_no
      row.blue_invoice_date = res.data.blue_invoice_date
      ElMessage.success('找到蓝票')
    } else {
      ElMessage.warning('未找到匹配的蓝票')
    }
  } catch (error) {
    ElMessage.error('查找失败')
  }
}

const batchFindBlue = async () => {
  try {
    const receiptIds = selectedRows.value.map(r => r.id)
    const res = await batchFindBlueInvoices({ return_receipt_ids: receiptIds })

    // 更新表格数据
    res.data.results.forEach(result => {
      const row = tableData.value.find(r => r.id === result.return_receipt_id)
      if (row) {
        row.blue_invoice_no = result.blue_invoice_no
        row.blue_invoice_date = result.blue_invoice_date
      }
    })

    ElMessage.success(`批量查找完成: 成功 ${res.data.matched} 条，失败 ${res.data.unmatched} 条`)
  } catch (error) {
    ElMessage.error('批量查找失败')
  }
}

const generateConfirm = async () => {
  try {
    const receiptIds = selectedRows.value.map(r => r.id)
    await downloadExcel('/red-flush/generate', { return_receipt_ids: receiptIds }, `红冲确认单_${receiptIds.length}条.xlsx`)
    ElMessage.success('生成成功')
  } catch (error) {
    ElMessage.error('生成失败: ' + error.message)
  }
}

const recordRed = async (row) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入红通号', '回录红通号', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
    })

    await recordRedNotice(row.id, value)
    ElMessage.success('回录成功')
    loadData()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('回录失败')
    }
  }
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.red-flush-tab {
  padding: 20px 0;
}
</style>
