<template>
  <div class="ledger-tab">
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>台账管理</span>
          <div>
            <el-button type="primary" @click="showImportDialog = true">导入新方舟导出</el-button>
            <el-button @click="exportData">导出Excel</el-button>
          </div>
        </div>
      </template>

      <!-- 筛选栏 -->
      <el-form inline class="mb-4">
        <el-form-item label="期间">
          <el-date-picker
            v-model="filters.period"
            type="month"
            placeholder="选择月份"
            format="YYYYMM"
            value-format="YYYYMM"
            @change="loadData"
          />
        </el-form-item>
        <el-form-item label="开票状态">
          <el-select v-model="filters.billing_status" placeholder="全部" clearable @change="loadData">
            <el-option label="未开" value="unbilled" />
            <el-option label="已开" value="billed" />
            <el-option label="已拆分" value="split" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="filters.search"
            placeholder="单号/型号"
            clearable
            @change="loadData"
          />
        </el-form-item>
      </el-form>

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
        <el-table-column prop="billing_status" label="开票状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.billing_status)">
              {{ getStatusText(row.billing_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="invoice_no" label="发票号" width="150" />
        <el-table-column prop="invoice_date" label="开票日期" width="120" />
        <el-table-column label="操作" width="180" align="center">
          <template #default="{ row }">
            <el-button size="small" @click="editReceipt(row)">编辑</el-button>
            <el-button size="small" @click="splitReceipt(row)" :disabled="row.billing_status === 'split'">
              拆分
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[20, 50, 100, 200]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadData"
        @current-change="loadData"
        class="mt-4"
      />
    </el-card>

    <!-- 编辑对话框 -->
    <el-dialog v-model="showEditDialog" title="编辑台账" width="600px">
      <el-form :model="editForm" label-width="100px">
        <el-form-item label="开票状态">
          <el-select v-model="editForm.billing_status">
            <el-option label="未开" value="unbilled" />
            <el-option label="已开" value="billed" />
          </el-select>
        </el-form-item>
        <el-form-item label="发票号">
          <el-input v-model="editForm.invoice_no" />
        </el-form-item>
        <el-form-item label="开票日期">
          <el-date-picker
            v-model="editForm.invoice_date"
            type="date"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 拆分对话框 -->
    <el-dialog v-model="showSplitDialog" title="拆分行" width="500px">
      <el-form label-width="100px">
        <el-form-item label="原数量">
          <el-input :value="splitForm.original_quantity" disabled />
        </el-form-item>
        <el-form-item label="拆分数量">
          <div v-for="(qty, idx) in splitForm.quantities" :key="idx" class="mb-2">
            <el-input-number v-model="splitForm.quantities[idx]" :min="0" :precision="2" />
            <el-button
              type="danger"
              size="small"
              @click="splitForm.quantities.splice(idx, 1)"
              :disabled="splitForm.quantities.length <= 2"
              class="ml-2"
            >
              删除
            </el-button>
          </div>
          <el-button size="small" @click="splitForm.quantities.push(0)">添加行</el-button>
        </el-form-item>
        <el-form-item label="拆分说明">
          <el-input v-model="splitForm.split_note" type="textarea" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showSplitDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmSplit">确定拆分</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getReceipts, updateReceipt, splitReceipt as apiSplitReceipt } from '../../api'
import { ElMessage } from 'element-plus'

const props = defineProps({
  customerId: {
    type: Number,
    required: true
  }
})

const loading = ref(false)
const tableData = ref([])
const filters = ref({
  period: '',
  billing_status: '',
  search: '',
})
const pagination = ref({
  page: 1,
  page_size: 50,
  total: 0,
})

const showEditDialog = ref(false)
const editForm = ref({})

const showSplitDialog = ref(false)
const splitForm = ref({
  receipt_id: null,
  original_quantity: 0,
  quantities: [0, 0],
  split_note: '',
})

const loadData = async () => {
  loading.value = true
  try {
    const res = await getReceipts({
      customer_id: props.customerId,
      ...filters.value,
      page: pagination.value.page,
      page_size: pagination.value.page_size,
    })
    tableData.value = res.data.items || []
    pagination.value.total = res.data.total || 0
  } catch (error) {
    ElMessage.error('加载数据失败')
  } finally {
    loading.value = false
  }
}

const formatAmount = (amount) => {
  return amount ? `￥${parseFloat(amount).toFixed(2)}` : '-'
}

const getStatusType = (status) => {
  const map = {
    unbilled: 'warning',
    billed: 'success',
    split: 'info',
  }
  return map[status] || 'info'
}

const getStatusText = (status) => {
  const map = {
    unbilled: '未开',
    billed: '已开',
    split: '已拆分',
  }
  return map[status] || status
}

const editReceipt = (row) => {
  editForm.value = { ...row }
  showEditDialog.value = true
}

const saveEdit = async () => {
  try {
    await updateReceipt(editForm.value.id, {
      billing_status: editForm.value.billing_status,
      invoice_no: editForm.value.invoice_no,
      invoice_date: editForm.value.invoice_date,
      remark: editForm.value.remark,
    })
    ElMessage.success('保存成功')
    showEditDialog.value = false
    loadData()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const splitReceipt = (row) => {
  splitForm.value = {
    receipt_id: row.id,
    original_quantity: row.quantity,
    quantities: [row.quantity / 2, row.quantity / 2],
    split_note: '',
  }
  showSplitDialog.value = true
}

const confirmSplit = async () => {
  try {
    const total = splitForm.value.quantities.reduce((a, b) => a + b, 0)
    if (Math.abs(total - splitForm.value.original_quantity) > 0.01) {
      ElMessage.error('拆分数量之和必须等于原数量')
      return
    }

    await apiSplitReceipt(splitForm.value.receipt_id, {
      quantities: splitForm.value.quantities,
      split_note: splitForm.value.split_note,
    })
    ElMessage.success('拆分成功')
    showSplitDialog.value = false
    loadData()
  } catch (error) {
    ElMessage.error('拆分失败: ' + error.message)
  }
}

const exportData = async () => {
  try {
    const params = {
      customer_id: props.customerId,
      period: filters.value.period || undefined,
      billing_status: filters.value.billing_status || undefined,
      search: filters.value.search || undefined,
    }

    // 构建查询字符串
    const queryString = new URLSearchParams(
      Object.entries(params).filter(([_, v]) => v !== undefined)
    ).toString()

    // 下载文件
    const url = `http://localhost:8000/api/receipts/export?${queryString}`
    window.open(url, '_blank')

    ElMessage.success('导出成功')
  } catch (error) {
    ElMessage.error('导出失败: ' + error.message)
  }
}

const showImportDialog = ref(false)

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.ledger-tab {
  padding: 20px 0;
}
</style>
