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
        @mark-diff="onMarkDiff"
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

    <!-- 手动匹配对话框 -->
    <el-dialog v-model="matchDialogVisible" title="手动匹配" width="700px">
      <div v-if="matchSourceRow" class="match-source">
        <div class="match-source-title">源记录：</div>
        <div v-if="matchSourceRow.receipt">
          我方：{{ matchSourceRow.receipt.receipt_no }} / {{ matchSourceRow.receipt.model }} /
          {{ matchSourceRow.receipt.quantity }}台 / ¥{{ matchSourceRow.receipt.amount }}
        </div>
        <div v-else-if="matchSourceRow.settlement">
          客户：{{ matchSourceRow.settlement.match_key }} / {{ matchSourceRow.settlement.model }} /
          {{ matchSourceRow.settlement.quantity }}台 / ¥{{ matchSourceRow.settlement.amount }}
        </div>
      </div>

      <el-divider />

      <div class="match-candidate-title">选择要匹配的{{ matchNeedSide === 'receipt' ? '我方' : '客户' }}记录：</div>
      <el-radio-group v-model="matchSelectedId" class="match-candidate-list">
        <el-radio
          v-for="c in matchCandidates"
          :key="matchNeedSide === 'receipt' ? c.receipt.id : c.settlement.id"
          :value="matchNeedSide === 'receipt' ? c.receipt.id : c.settlement.id"
          class="match-candidate-item"
        >
          <template v-if="matchNeedSide === 'receipt'">
            {{ c.receipt.receipt_no }} / {{ c.receipt.model }} / {{ c.receipt.quantity }}台 / ¥{{ c.receipt.amount }}
          </template>
          <template v-else>
            {{ c.settlement.match_key }} / {{ c.settlement.model }} / {{ c.settlement.quantity }}台 / ¥{{ c.settlement.amount }}
          </template>
        </el-radio>
      </el-radio-group>
      <el-empty v-if="matchCandidates.length === 0" description="无可匹配候选" :image-size="60" />

      <el-input
        v-model="matchReason"
        placeholder="匹配原因（可选）"
        class="mt-4"
      />

      <template #footer>
        <el-button @click="matchDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmManualMatch" :disabled="!matchSelectedId">确定匹配</el-button>
      </template>
    </el-dialog>

    <!-- 标记差异对话框 -->
    <el-dialog v-model="diffDialogVisible" title="标记差异" width="500px">
      <div v-if="diffRow" class="match-source">
        <div class="match-source-title">我方记录：</div>
        <div>
          {{ diffRow.receipt.receipt_no }} / {{ diffRow.receipt.model }} /
          {{ diffRow.receipt.quantity }}台 / ¥{{ diffRow.receipt.amount }}
        </div>
      </div>

      <el-form label-width="100px" class="mt-4">
        <el-form-item label="差异类型">
          <el-radio-group v-model="diffType">
            <el-radio value="time_diff">时间差（挂起等下月）</el-radio>
            <el-radio value="price_diff">价格差（真差异）</el-radio>
            <el-radio value="qty_diff">数量差（真差异）</el-radio>
            <el-radio value="customer_not_received">客户未收货</el-radio>
            <el-radio value="our_not_received">我方未签收</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="差异说明">
          <el-input
            v-model="diffNote"
            type="textarea"
            :rows="3"
            placeholder="请说明差异原因，便于后续追溯"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="diffDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="confirmMarkDiff">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { runReconciliation, getReconciliationStatus, getReconciliationResults, postJson, downloadExcelGet, API_URL } from '../../api'
import { ElMessage, ElMessageBox } from 'element-plus'
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

    const response = await fetch(`${API_URL}/reconciliation/upload-statement`, {
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
  downloadExcelGet(`/reconciliation/export?customer_id=${props.customerId}&period=${period.value}`)
}

// 人工纠正（Ticket 06）
const onManualMatch = (row) => {
  // 判断我方/客户哪侧缺失，提示选择另一侧
  if (row.receipt && !row.settlement) {
    // 我方未匹配 → 选择客户记录
    openMatchDialog(row, 'settlement')
  } else if (row.settlement && !row.receipt) {
    // 客户未匹配 → 选择我方记录
    openMatchDialog(row, 'receipt')
  } else {
    ElMessage.warning('该行无需手动匹配')
  }
}

const matchDialogVisible = ref(false)
const matchSourceRow = ref(null)
const matchNeedSide = ref('') // 'receipt' | 'settlement'
const matchCandidates = ref([])
const matchSelectedId = ref(null)
const matchReason = ref('')

const openMatchDialog = async (row, needSide) => {
  matchSourceRow.value = row
  matchNeedSide.value = needSide
  matchSelectedId.value = null
  matchReason.value = ''

  // 加载另一侧的未匹配候选（用 status=unmatched 查询）
  try {
    const res = await getReconciliationResults({
      customer_id: props.customerId,
      period: period.value,
      status: 'unmatched',
      page: 1,
      page_size: 200,
    })
    const items = res.data.items || []
    // 过滤出另一侧存在、本侧缺失的记录
    matchCandidates.value = items.filter(it =>
      needSide === 'receipt' ? (it.receipt && !it.settlement) : (it.settlement && !it.receipt)
    )
    matchDialogVisible.value = true
  } catch (error) {
    ElMessage.error('加载候选失败')
  }
}

const confirmManualMatch = async () => {
  if (!matchSelectedId.value) {
    ElMessage.warning('请选择要匹配的记录')
    return
  }
  const source = matchSourceRow.value
  const receiptId = matchNeedSide.value === 'receipt' ? matchSelectedId.value : source.receipt.id
  const settlementId = matchNeedSide.value === 'settlement' ? matchSelectedId.value : source.settlement.id

  try {
    const result = await postJson('/corrections/manual-match', {
      customer_id: props.customerId,
      period: period.value,
      receipt_id: receiptId,
      settlement_id: settlementId,
      reason: matchReason.value || '人工匹配',
    })
    if (result.success !== false) {
      ElMessage.success('手动匹配成功')
      matchDialogVisible.value = false
      onPeriodChange()
    } else {
      ElMessage.error(result.message || '匹配失败')
    }
  } catch (error) {
    ElMessage.error('匹配失败: ' + error.message)
  }
}

const onUnmatch = async (row) => {
  try {
    await ElMessageBox.confirm('确定解除该匹配吗？将拆分为两条未匹配记录。', '解除匹配', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    const result = await postJson('/corrections/unmatch', {
      customer_id: props.customerId,
      period: period.value,
      result_id: row.id,
      reason: '解除匹配',
    })
    if (result.success !== false) {
      ElMessage.success('已解除匹配')
      onPeriodChange()
    } else {
      ElMessage.error(result.message || '操作失败')
    }
  } catch (error) {
    ElMessage.error('操作失败: ' + error.message)
  }
}

const onIgnore = async (row) => {
  let reason = '忽略'
  try {
    const { value } = await ElMessageBox.prompt('请输入忽略原因（如：费用单据）', '标记忽略', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputValue: '费用单据',
    })
    reason = value || '忽略'
  } catch {
    return
  }
  try {
    const result = await postJson('/corrections/ignore', {
      customer_id: props.customerId,
      period: period.value,
      result_id: row.id,
      reason,
    })
    if (result.success !== false) {
      ElMessage.success('已忽略')
      onPeriodChange()
    } else {
      ElMessage.error(result.message || '操作失败')
    }
  } catch (error) {
    ElMessage.error('操作失败: ' + error.message)
  }
}

// 标记差异（Ticket 07）
const diffDialogVisible = ref(false)
const diffRow = ref(null)
const diffType = ref('time_diff')
const diffNote = ref('')

const onMarkDiff = (row) => {
  diffRow.value = row
  diffType.value = 'time_diff'
  diffNote.value = ''
  diffDialogVisible.value = true
}

const confirmMarkDiff = async () => {
  try {
    const result = await postJson('/reconciliation/mark-diff', {
      receipt_id: diffRow.value.receipt.id,
      diff_type: diffType.value,
      diff_note: diffNote.value,
    })
    if (result.status === 'success') {
      ElMessage.success('已标记差异，挂入未决池')
      diffDialogVisible.value = false
      onPeriodChange()
    } else {
      ElMessage.error(result.message || '标记失败')
    }
  } catch (error) {
    ElMessage.error('标记失败: ' + error.message)
  }
}

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
.match-source {
  padding: 12px;
  background: #f0f9ff;
  border-radius: 6px;
  border: 1px solid #bae6fd;
}
.match-source-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: #0369a1;
}
.match-candidate-title {
  font-weight: 600;
  margin-bottom: 12px;
  color: #303133;
}
.match-candidate-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 300px;
  overflow-y: auto;
}
.match-candidate-item {
  display: block;
  padding: 8px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  margin-right: 0 !important;
}
.match-candidate-item:hover {
  background: #f5f7fa;
}
</style>
