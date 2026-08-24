<template>
  <div class="reconciliation-tab">
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>对账核对</span>
          <div>
            <el-button type="primary" @click="showUploadDialog = true">上传对账单</el-button>
            <el-button type="success" @click="runMatch" :loading="running">运行匹配</el-button>
            <el-button @click="exportResult" :disabled="!hasResults">导出结果</el-button>
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
            @change="onPeriodChange"
          />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="statusFilter" style="width: 120px" @change="loadResults">
            <el-option label="全部" value="all" />
            <el-option label="已匹配" value="matched" />
            <el-option label="未匹配" value="unmatched" />
            <el-option label="人工" value="manual" />
            <el-option label="已排除" value="ignored" />
          </el-select>
        </el-form-item>
        <el-form-item label="搜索">
          <el-input
            v-model="searchText"
            placeholder="单号/型号"
            clearable
            style="width: 200px"
            @change="loadResults"
          />
        </el-form-item>
      </el-form>

      <!-- 匹配摘要 -->
      <div class="summary-bar" v-if="summary.total_settlements > 0">
        <div class="summary-item">
          <span class="summary-label">匹配率</span>
          <span class="summary-value highlight">{{ summary.match_rate }}%</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">已匹配</span>
          <span class="summary-value success">{{ summary.matched_count }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">未匹配(我方)</span>
          <span class="summary-value danger">{{ summary.unmatched_receipts }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">未匹配(客户)</span>
          <span class="summary-value danger">{{ summary.unmatched_settlements }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">我方总数</span>
          <span class="summary-value">{{ summary.total_receipts }}</span>
        </div>
        <div class="summary-item">
          <span class="summary-label">客户总数</span>
          <span class="summary-value">{{ summary.total_settlements }}</span>
        </div>
      </div>

      <!-- 提示信息 -->
      <el-alert v-if="!hasStatements" type="info" :closable="false" class="mb-4">
        请先上传客户对账单
      </el-alert>
      <el-alert v-else-if="!hasResults" type="warning" :closable="false" class="mb-4">
        对账单已上传，请点击"运行匹配"开始核对
      </el-alert>

      <!-- 左右对照表格 -->
      <ComparisonTable
        v-if="hasResults"
        :items="results"
        :total="total"
        @manual-match="onManualMatch"
        @unmatch="onUnmatch"
        @ignore="onIgnore"
      />

      <!-- 分页 -->
      <el-pagination
        v-if="hasResults"
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        @size-change="loadResults"
        @current-change="loadResults"
        class="mt-4"
      />
    </el-card>

    <!-- 上传对话框 -->
    <el-dialog v-model="showUploadDialog" title="上传对账单" width="500px">
      <el-form label-width="100px">
        <el-form-item label="对账期间">
          <el-date-picker
            v-model="uploadPeriod"
            type="month"
            placeholder="选择月份"
            format="YYYYMM"
            value-format="YYYYMM"
          />
        </el-form-item>
        <el-form-item label="Excel 文件">
          <el-upload
            :auto-upload="false"
            :on-change="handleFileChange"
            :limit="1"
            accept=".xlsx,.xls"
          >
            <el-button type="primary">选择文件</el-button>
          </el-upload>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showUploadDialog = false">取消</el-button>
        <el-button type="primary" @click="uploadFile" :disabled="!canUpload" :loading="uploading">上传</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { runReconciliation, getReconciliationStatus, getReconciliationResults } from '../../api'
import { ElMessage } from 'element-plus'
import ComparisonTable from '../ComparisonTable.vue'

const props = defineProps({
  customerId: {
    type: Number,
    required: true
  }
})

const period = ref('')
const statusFilter = ref('all')
const searchText = ref('')
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const results = ref([])
const running = ref(false)
const uploading = ref(false)

const summary = ref({
  total_receipts: 0,
  total_settlements: 0,
  matched_count: 0,
  unmatched_receipts: 0,
  unmatched_settlements: 0,
  match_rate: 0,
})

const showUploadDialog = ref(false)
const uploadPeriod = ref('')
const selectedFile = ref(null)

const hasStatements = computed(() => summary.value.total_settlements > 0)
const hasResults = computed(() => results.value.length > 0 || summary.value.matched_count > 0 || summary.value.unmatched_receipts > 0)
const canUpload = computed(() => uploadPeriod.value && selectedFile.value)

const onPeriodChange = () => {
  page.value = 1
  loadStatus()
  loadResults()
}

const loadStatus = async () => {
  if (!period.value) return
  try {
    const res = await getReconciliationStatus({
      customer_id: props.customerId,
      period: period.value,
    })
    summary.value = { ...summary.value, ...(res.data || {}) }
  } catch (error) {
    console.error('加载状态失败:', error)
  }
}

const loadResults = async () => {
  if (!period.value) return
  try {
    const res = await getReconciliationResults({
      customer_id: props.customerId,
      period: period.value,
      status: statusFilter.value,
      search: searchText.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    results.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (error) {
    console.error('加载结果失败:', error)
  }
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

const uploadFile = async () => {
  uploading.value = true
  try {
    const formData = new FormData()
    formData.append('customer_id', props.customerId)
    formData.append('period', uploadPeriod.value)
    formData.append('file', selectedFile.value)

    const response = await fetch('http://localhost:8000/api/reconciliation/upload-statement', {
      method: 'POST',
      body: formData,
    })
    const result = await response.json()

    if (result.status === 'success') {
      ElMessage.success(result.message)
      showUploadDialog.value = false
      period.value = uploadPeriod.value
      onPeriodChange()
    } else {
      ElMessage.error(result.message || '上传失败')
    }
  } catch (error) {
    ElMessage.error('上传失败: ' + error.message)
  } finally {
    uploading.value = false
  }
}

const runMatch = async () => {
  if (!period.value) {
    ElMessage.warning('请先选择对账期间')
    return
  }
  running.value = true
  try {
    const res = await runReconciliation({
      customer_id: props.customerId,
      period: period.value,
    })
    if (res.data.status === 'success') {
      ElMessage.success(res.data.message)
    } else {
      ElMessage.warning(res.data.message)
    }
    onPeriodChange()
  } catch (error) {
    ElMessage.error('匹配失败: ' + error.message)
  } finally {
    running.value = false
  }
}

const exportResult = () => {
  const url = `http://localhost:8000/api/reconciliation/export?customer_id=${props.customerId}&period=${period.value}`
  window.open(url, '_blank')
}

// 人工操作（占位，Ticket 06/07 实现）
const onManualMatch = (row) => ElMessage.info('手动匹配（Ticket 06 实现）')
const onUnmatch = (row) => ElMessage.info('解除匹配（Ticket 06 实现）')
const onIgnore = (row) => ElMessage.info('忽略（Ticket 06 实现）')

onMounted(() => {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  period.value = `${year}${month}`
  loadStatus()
  loadResults()
})
</script>

<style scoped>
.reconciliation-tab {
  padding: 20px 0;
}
.summary-bar {
  display: flex;
  gap: 32px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  margin-bottom: 16px;
}
.summary-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.summary-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.summary-value {
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}
.summary-value.highlight { color: #409eff; }
.summary-value.success { color: #67c23a; }
.summary-value.danger { color: #f56c6c; }
.mb-4 { margin-bottom: 16px; }
.mt-4 { margin-top: 16px; }
</style>
