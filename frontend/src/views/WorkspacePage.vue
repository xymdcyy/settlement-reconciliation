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
          <el-button type="primary" :disabled="!canQuery" @click="loadData" :loading="loading">
            查询
          </el-button>
          <el-button :disabled="!canQuery" @click="runMatch" :loading="loading">
            运行对账
          </el-button>
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
      <ComparisonTable
        v-else
        :items="results"
        :total="total"
        @manual-match="openManualMatch"
        @unmatch="openUnmatch"
        @ignore="openIgnore"
      />
      <div v-if="results.length" style="margin-top: 16px; display: flex; justify-content: flex-end;">
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadResults"
        />
      </div>
    </div>

    <!-- 纠正面板（对话框） -->
    <CorrectionPanel
      ref="correctionPanelRef"
      :customer-id="query.customerId"
      :period="query.period"
      @success="loadData"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import {
  getCustomers,
  runReconciliation,
  getReconciliationStatus,
  getReconciliationResults,
} from '../api/index.js'
import ComparisonTable from '../components/ComparisonTable.vue'
import CorrectionPanel from '../components/CorrectionPanel.vue'

const route = useRoute()

// 查询条件 — 从路由参数读取初始值（历史页面跳转时传入）
const query = ref({ customerId: route.query.customer_id || '', period: route.query.period || '' })
const customers = ref([])
const canQuery = computed(() => query.value.customerId && query.value.period)

// 统计摘要
const summary = ref(null)

// 结果列表
const results = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const statusFilter = ref('')
const searchText = ref('')

// 纠正面板引用
const correctionPanelRef = ref(null)

// 加载数据
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

// 纠正操作 — 委托给 CorrectionPanel 组件
function openManualMatch(row) {
  correctionPanelRef.value?.openManualMatch(row)
}

function openUnmatch(row) {
  correctionPanelRef.value?.openUnmatch(row)
}

function openIgnore(row) {
  correctionPanelRef.value?.openIgnore(row)
}

// 初始化
onMounted(async () => {
  try {
    customers.value = await getCustomers()
  } catch {
    customers.value = []
  }
  // 如果从历史页面携带参数跳转，自动加载数据
  if (query.value.customerId && query.value.period) {
    await loadData()
  }
})

// 监听路由参数变化（同一页面内参数变化时重新加载）
watch(
  () => [route.query.customer_id, route.query.period],
  ([newCid, newPeriod]) => {
    if (newCid && newPeriod) {
      query.value.customerId = newCid
      query.value.period = newPeriod
      loadData()
    }
  }
)
</script>