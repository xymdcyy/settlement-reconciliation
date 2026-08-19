<template>
  <div class="workspace-page">
    <h2 class="page-title">在线比对工作台</h2>

    <!-- 选择器 -->
    <div class="page-card" style="margin-bottom: 20px">
      <el-form :inline="true" :model="query">
        <el-form-item label="客户">
          <el-select v-model="query.customerId" placeholder="请选择客户" style="width: 180px">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="对账期间">
          <el-date-picker
            v-model="query.period"
            type="month"
            placeholder="选择月份"
            value-format="YYYYMM"
            style="width: 160px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="!canQuery" @click="loadData">查询</el-button>
          <el-button :disabled="!canQuery" @click="runMatch">运行对账</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 统计摘要 -->
    <div v-if="summary" class="summary-bar">
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ summary.match_rate }}%</div>
        <div class="stat-label">匹配率</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value">{{ summary.matched_count }}</div>
        <div class="stat-label">已匹配</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value" style="color: #e6a23c">{{ summary.unmatched_receipts }}</div>
        <div class="stat-label">未匹配我方</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value" style="color: #e6a23c">{{ summary.unmatched_settlements }}</div>
        <div class="stat-label">未匹配客户方</div>
      </el-card>
      <el-card shadow="never" class="stat-card">
        <div class="stat-value" style="color: #f56c6c">{{ summary.total_amount_diff }}</div>
        <div class="stat-label">金额差异</div>
      </el-card>
    </div>

    <!-- 状态筛选 -->
    <div style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
      <el-radio-group v-model="statusFilter" @change="loadResults">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="matched">已匹配</el-radio-button>
        <el-radio-button value="unmatched">未匹配</el-radio-button>
        <el-radio-button value="ignored">已排除</el-radio-button>
      </el-radio-group>
      <el-input
        v-model="searchText"
        placeholder="搜索型号/订单号"
        clearable
        style="width: 220px; margin-left: auto;"
        @clear="loadResults"
        @keyup.enter="loadResults"
      />
    </div>

    <!-- 结果表格 -->
    <div class="page-card" v-loading="loading">
      <el-empty v-if="!results.length && !loading" description="请选择客户和期间后查询" />
      <el-table
        v-else
        :data="results"
        stripe
        style="width: 100%"
        :row-class-name="rowClassName"
        @expand-change="onExpandChange"
      >
        <el-table-column type="expand" width="40">
          <template #default="{ row }">
            <div style="padding: 12px 40px; font-size: 13px;">
              <div v-if="row.receipt">
                <strong>我方签收：</strong>
                {{ row.receipt.model }} / {{ row.receipt.quantity }} 台 / ¥{{ row.receipt.amount }}
                / {{ row.receipt.receipt_date }}
              </div>
              <div v-if="row.settlement">
                <strong>客户结算：</strong>
                {{ row.settlement.model }} / {{ row.settlement.quantity }} 台 / ¥{{ row.settlement.amount }}
                / {{ row.settlement.settlement_date }}
              </div>
              <div v-if="row.remark" style="margin-top: 8px;">
                <strong>备注：</strong>{{ row.remark }}
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="match_type" label="匹配类型" width="100">
          <template #default="{ row }">
            <el-tag v-if="row.match_type === 'exact'" type="success" size="small">精确匹配</el-tag>
            <el-tag v-else-if="row.match_type === 'loose'" type="warning" size="small">宽松匹配</el-tag>
            <el-tag v-else-if="row.match_type === 'manual'" type="primary" size="small">手动匹配</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="receipt.model" label="型号" min-width="140">
          <template #default="{ row }">
            {{ row.receipt?.model || row.settlement?.model || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="receipt.quantity" label="我方数量" width="80">
          <template #default="{ row }">{{ row.receipt?.quantity ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="settlement.quantity" label="客户数量" width="80">
          <template #default="{ row }">{{ row.settlement?.quantity ?? '-' }}</template>
        </el-table-column>
        <el-table-column prop="receipt.amount" label="我方金额" width="100">
          <template #default="{ row }">{{ row.receipt?.amount ? '¥' + row.receipt.amount : '-' }}</template>
        </el-table-column>
        <el-table-column prop="settlement.amount" label="客户金额" width="100">
          <template #default="{ row }">{{ row.settlement?.amount ? '¥' + row.settlement.amount : '-' }}</template>
        </el-table-column>
        <el-table-column prop="diff_amount" label="差异" width="90">
          <template #default="{ row }">
            <span :style="{ color: row.diff_amount > 0 ? '#f56c6c' : '#67c23a' }">
              {{ row.diff_amount ? (row.diff_amount > 0 ? '+' : '') + row.diff_amount : '-' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.status === 'matched'" type="success" size="small">已匹配</el-tag>
            <el-tag v-else-if="row.status === 'unmatched'" type="danger" size="small">未匹配</el-tag>
            <el-tag v-else-if="row.status === 'ignored'" type="info" size="small">已排除</el-tag>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'unmatched'"
              type="primary"
              size="small"
              @click="openManualMatch(row)"
            >手动匹配</el-button>
            <el-button
              v-else-if="row.status === 'matched'"
              type="danger"
              size="small"
              plain
              @click="handleUnmatch(row)"
            >解除</el-button>
            <el-button
              v-if="row.status !== 'ignored'"
              type="warning"
              size="small"
              plain
              @click="openIgnoreDialog(row)"
            >忽略</el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div style="margin-top: 16px; display: flex; justify-content: flex-end;">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadResults"
        />
      </div>
    </div>

    <!-- 手动匹配对话框 -->
    <el-dialog v-model="matchDialog.visible" title="手动匹配" width="600px">
      <div v-if="matchDialog.result">
        <p><strong>待匹配记录：</strong></p>
        <p>型号：{{ matchDialog.result.receipt?.model || '-' }}</p>
        <p>我方金额：¥{{ matchDialog.result.receipt?.amount || 0 }}</p>
        <p>我方数量：{{ matchDialog.result.receipt?.quantity || 0 }}</p>
        <el-divider />
        <el-form label-width="100px">
          <el-form-item label="匹配结算单">
            <el-select
              v-model="matchDialog.selectedSettlementId"
              placeholder="请选择结算记录"
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="s in unmatchedSettlements"
                :key="s.id"
                :label="`${s.match_key || s.model} - ¥${s.amount} x${s.quantity}`"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="matchDialog.reason" type="textarea" rows="2" placeholder="可选" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="matchDialog.visible = false">取消</el-button>
        <el-button type="primary" :disabled="!matchDialog.selectedSettlementId" @click="confirmManualMatch">确认匹配</el-button>
      </template>
    </el-dialog>

    <!-- 忽略对话框 -->
    <el-dialog v-model="ignoreDialog.visible" title="标记忽略" width="400px">
      <el-form label-width="80px">
        <el-form-item label="原因">
          <el-input v-model="ignoreDialog.reason" type="textarea" rows="3" placeholder="请填写忽略原因" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ignoreDialog.visible = false">取消</el-button>
        <el-button type="primary" :disabled="!ignoreDialog.reason" @click="confirmIgnore">确认忽略</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import {
  getCustomers,
  runReconciliation,
  getReconciliationStatus,
  getReconciliationResults,
  manualMatch,
  unmatch,
  ignoreResult,
} from '../api/index.js'

// ============================================================
// 查询条件
// ============================================================
const query = ref({ customerId: '', period: '' })
const customers = ref([])
const canQuery = computed(() => query.value.customerId && query.value.period)

// ============================================================
// 统计摘要
// ============================================================
const summary = ref(null)

// ============================================================
// 结果列表
// ============================================================
const results = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const statusFilter = ref('')
const searchText = ref('')

function rowClassName({ row }) {
  if (row.status === 'matched') return 'row-matched'
  if (row.status === 'unmatched') return 'row-unmatched'
  if (row.status === 'ignored') return 'row-ignored'
  return ''
}

// ============================================================
// 加载数据
// ============================================================
async function loadData() {
  loading.value = true
  try {
    await Promise.all([loadSummary(), loadResults()])
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    summary.value = await getReconciliationStatus(query.value.customerId, query.value.period)
  } catch {
    summary.value = null
  }
}

async function loadResults() {
  try {
    const data = await getReconciliationResults({
      customer_id: query.value.customerId,
      period: query.value.period,
      status: statusFilter.value || undefined,
      search: searchText.value || undefined,
      page: page.value,
      page_size: pageSize.value,
    })
    results.value = data.items || []
    total.value = data.total || 0
  } catch {
    results.value = []
    total.value = 0
  }
}

async function runMatch() {
  loading.value = true
  try {
    const data = await runReconciliation(query.value.customerId, query.value.period)
    if (data.summary) {
      summary.value = data.summary
    }
    await loadResults()
  } finally {
    loading.value = false
  }
}

// ============================================================
// 手动匹配
// ============================================================
const matchDialog = ref({
  visible: false,
  result: null,
  selectedSettlementId: null,
  reason: '',
})
const unmatchedSettlements = ref([])

function openManualMatch(row) {
  matchDialog.value = {
    visible: true,
    result: row,
    selectedSettlementId: null,
    reason: '',
  }
  // 获取未匹配的结算记录供选择
  // TODO: 如果后端有专门的 API 更好，暂时复用结果查询
}

async function confirmManualMatch() {
  try {
    await manualMatch({
      customer_id: query.value.customerId,
      period: query.value.period,
      receipt_id: matchDialog.value.result.receipt_id,
      settlement_id: matchDialog.value.selectedSettlementId,
      reason: matchDialog.value.reason || undefined,
    })
    matchDialog.value.visible = false
    await loadData()
  } catch {
    // 错误已在拦截器中处理
  }
}

// ============================================================
// 解除匹配
// ============================================================
async function handleUnmatch(row) {
  try {
    await unmatch({
      customer_id: query.value.customerId,
      period: query.value.period,
      result_id: row.id,
      reason: '手动解除',
    })
    await loadData()
  } catch {
    // 错误已在拦截器中处理
  }
}

// ============================================================
// 忽略
// ============================================================
const ignoreDialog = ref({
  visible: false,
  result: null,
  reason: '',
})

function openIgnoreDialog(row) {
  ignoreDialog.value = {
    visible: true,
    result: row,
    reason: '',
  }
}

async function confirmIgnore() {
  try {
    await ignoreResult({
      customer_id: query.value.customerId,
      period: query.value.period,
      result_id: ignoreDialog.value.result.id,
      reason: ignoreDialog.value.reason,
    })
    ignoreDialog.value.visible = false
    await loadData()
  } catch {
    // 错误已在拦截器中处理
  }
}

// ============================================================
// 展开行
// ============================================================
function onExpandChange(row, expanded) {
  // 展开行时显示详情
}

// ============================================================
// 初始化
// ============================================================
onMounted(async () => {
  try {
    customers.value = await getCustomers()
  } catch {
    customers.value = []
  }
})
</script>