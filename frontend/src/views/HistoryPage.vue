<template>
  <div class="history-page">
    <h2 class="page-title">历史查询</h2>

    <!-- 筛选条件 -->
    <div class="page-card" style="margin-bottom: 20px">
      <el-form :inline="true" :model="filters">
        <el-form-item label="客户">
          <el-select v-model="filters.customerId" placeholder="全部客户" clearable style="width: 180px">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="起始月份">
          <el-date-picker
            v-model="filters.startMonth"
            type="month"
            placeholder="起始月份"
            value-format="YYYYMM"
            style="width: 150px"
          />
        </el-form-item>
        <el-form-item label="结束月份">
          <el-date-picker
            v-model="filters.endMonth"
            type="month"
            placeholder="结束月份"
            value-format="YYYYMM"
            style="width: 150px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="loadHistory">查询</el-button>
        </el-form-item>
      </el-form>
    </div>

    <!-- 历史记录 -->
    <div class="page-card" v-loading="loading">
      <el-empty v-if="!items.length && !loading" description="暂无历史对账记录" />

      <!-- 卡片视图 -->
      <div v-else class="history-grid">
        <el-card
          v-for="item in items"
          :key="`${item.customer_id}-${item.period}`"
          shadow="hover"
          class="history-card"
          @click="goToWorkspace(item)"
        >
          <div class="card-header">
            <span class="card-customer">{{ item.customer_name }}</span>
            <span class="card-period">{{ formatPeriod(item.period) }}</span>
          </div>
          <div class="card-body">
            <div class="card-stat">
              <div class="card-stat-value" :class="matchRateClass(item.match_rate)">{{ item.match_rate }}%</div>
              <div class="card-stat-label">匹配率</div>
            </div>
            <div class="card-stats-row">
              <div class="card-stat-item">
                <div class="card-stat-item-value">{{ item.matched_count }}</div>
                <div class="card-stat-item-label">已匹配</div>
              </div>
              <div class="card-stat-item">
                <div class="card-stat-item-value" style="color: #e6a23c">{{ item.unmatched_receipts }}</div>
                <div class="card-stat-item-label">未匹配我方</div>
              </div>
              <div class="card-stat-item">
                <div class="card-stat-item-value" style="color: #e6a23c">{{ item.unmatched_settlements }}</div>
                <div class="card-stat-item-label">未匹配客户</div>
              </div>
            </div>
            <div class="card-diff" v-if="item.total_amount_diff">
              金额差异：<span :class="item.total_amount_diff > 0 ? 'diff-positive' : 'diff-negative'">
                {{ item.total_amount_diff > 0 ? '+' : '' }}{{ item.total_amount_diff }}
              </span>
            </div>
          </div>
          <div class="card-footer">
            <el-button type="primary" size="small" @click.stop="handleExport(item)">导出</el-button>
            <el-button size="small" @click.stop="goToWorkspace(item)">查看详情</el-button>
          </div>
        </el-card>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCustomers, getReconciliationHistory, exportReconciliation } from '../api/index.js'

const router = useRouter()
const customers = ref([])
const items = ref([])
const loading = ref(false)

const filters = reactive({
  customerId: '',
  startMonth: '',
  endMonth: '',
})

function formatPeriod(period) {
  if (!period || period.length < 6) return period
  return `${period.slice(0, 4)}年${parseInt(period.slice(4))}月`
}

function matchRateClass(rate) {
  if (rate >= 95) return 'rate-high'
  if (rate >= 80) return 'rate-medium'
  return 'rate-low'
}

async function loadHistory() {
  loading.value = true
  try {
    const params = {}
    if (filters.customerId) params.customer_id = filters.customerId
    if (filters.startMonth) params.start_month = filters.startMonth
    if (filters.endMonth) params.end_month = filters.endMonth
    const data = await getReconciliationHistory(params)
    items.value = data.items || []
  } catch {
    items.value = []
  } finally {
    loading.value = false
  }
}

function goToWorkspace(item) {
  router.push(`/workspace?customer_id=${item.customer_id}&period=${item.period}`)
}

function handleExport(item) {
  exportReconciliation(item.customer_id, item.period)
}

onMounted(async () => {
  try {
    customers.value = await getCustomers()
  } catch {
    customers.value = []
  }
  await loadHistory()
})
</script>

<style scoped>
.history-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.history-card {
  cursor: pointer;
  transition: transform 0.2s;
}
.history-card:hover {
  transform: translateY(-2px);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 12px;
}
.card-customer {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}
.card-period {
  font-size: 13px;
  color: #909399;
}
.card-body {
  text-align: center;
  padding: 8px 0;
}
.card-stat {
  margin-bottom: 12px;
}
.card-stat-value {
  font-size: 32px;
  font-weight: 700;
}
.card-stat-label {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.card-stats-row {
  display: flex;
  justify-content: space-around;
  margin-bottom: 8px;
}
.card-stat-item {
  text-align: center;
}
.card-stat-item-value {
  font-size: 18px;
  font-weight: 600;
}
.card-stat-item-label {
  font-size: 11px;
  color: #909399;
  margin-top: 2px;
}
.card-diff {
  font-size: 13px;
  color: #606266;
  margin-top: 4px;
}
.card-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}
.rate-high { color: #67c23a; }
.rate-medium { color: #e6a23c; }
.rate-low { color: #f56c6c; }
.diff-positive { color: #f56c6c; }
.diff-negative { color: #67c23a; }
</style>