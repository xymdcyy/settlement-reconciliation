<template>
  <div class="comparison-table">
    <el-table
      :data="items"
      stripe
      style="width: 100%"
      :row-class-name="rowClassName"
      :default-expand-all="false"
      @expand-change="onExpand"
      size="small"
    >
      <el-table-column type="expand" width="36">
        <template #default="{ row }">
          <div class="expand-detail">
            <!-- 左侧：我方签收 -->
            <div class="detail-side">
              <div class="detail-header">我方签收</div>
              <div class="detail-row">
                <span class="detail-label">销售单号：</span>
                <span>{{ row.receipt?.receipt_no || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">型号：</span>
                <span>{{ row.receipt?.model || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">数量：</span>
                <span>{{ row.receipt?.quantity ?? '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">金额：</span>
                <span>¥{{ row.receipt?.amount || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">日期：</span>
                <span>{{ row.receipt?.receipt_date || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">NC订单号：</span>
                <span>{{ row.receipt?.nc_order_no || '-' }}</span>
              </div>
            </div>
            <!-- 右侧：客户方结算 -->
            <div class="detail-side">
              <div class="detail-header">客户方结算</div>
              <div class="detail-row">
                <span class="detail-label">匹配键：</span>
                <span>{{ row.settlement?.match_key || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">型号：</span>
                <span>{{ row.settlement?.model || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">数量：</span>
                <span>{{ row.settlement?.quantity ?? '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">金额：</span>
                <span>¥{{ row.settlement?.amount || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">日期：</span>
                <span>{{ row.settlement?.settlement_date || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">单据类型：</span>
                <span>{{ row.settlement?.doc_type || '-' }}</span>
              </div>
            </div>
            <!-- 差异对比 -->
            <div class="detail-diff" v-if="row.status === 'matched'">
              <div class="detail-header">差异对比</div>
              <div class="detail-row">
                <span class="detail-label">金额差异：</span>
                <span :class="diffClass(row.diff_amount)">{{ row.diff_amount ? (row.diff_amount > 0 ? '+' : '') + row.diff_amount : '无差异' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">数量差异：</span>
                <span :class="diffClass(row.diff_quantity)">{{ row.diff_quantity ? (row.diff_quantity > 0 ? '+' : '') + row.diff_quantity : '无差异' }}</span>
              </div>
            </div>
            <!-- 备注 -->
            <div class="detail-remark" v-if="row.remark">
              <div class="detail-header">备注</div>
              <p>{{ row.remark }}</p>
            </div>
          </div>
        </template>
      </el-table-column>

      <!-- 状态列 -->
      <el-table-column prop="status" label="状态" width="80" fixed>
        <template #default="{ row }">
          <el-tag v-if="row.status === 'matched'" type="success" size="small" effect="dark">已匹配</el-tag>
          <el-tag v-else-if="row.status === 'unmatched'" type="danger" size="small" effect="dark">未匹配</el-tag>
          <el-tag v-else-if="row.status === 'ignored'" type="info" size="small" effect="dark">已排除</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <!-- 匹配类型 -->
      <el-table-column prop="match_type" label="匹配" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.match_type === 'exact'" type="success" size="small">精确</el-tag>
          <el-tag v-else-if="row.match_type === 'loose'" type="warning" size="small">宽松</el-tag>
          <el-tag v-else-if="row.match_type === 'manual'" type="primary" size="small">手动</el-tag>
          <span v-else>-</span>
        </template>
      </el-table-column>

      <!-- 我方侧字段 -->
      <el-table-column label="我方型号" min-width="120">
        <template #default="{ row }">
          <span>{{ row.receipt?.model || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="我方数量" width="70" align="right">
        <template #default="{ row }">
          <span>{{ row.receipt?.quantity ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="我方金额" width="100" align="right">
        <template #default="{ row }">
          <span>{{ row.receipt?.amount ? '¥' + formatNum(row.receipt.amount) : '-' }}</span>
        </template>
      </el-table-column>

      <!-- 客户方侧字段 -->
      <el-table-column label="客户型号" min-width="120">
        <template #default="{ row }">
          <span>{{ row.settlement?.model || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="客户数量" width="70" align="right">
        <template #default="{ row }">
          <span>{{ row.settlement?.quantity ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="客户金额" width="100" align="right">
        <template #default="{ row }">
          <span>{{ row.settlement?.amount ? '¥' + formatNum(row.settlement.amount) : '-' }}</span>
        </template>
      </el-table-column>

      <!-- 差异 -->
      <el-table-column label="差异" width="80" align="right">
        <template #default="{ row }">
          <span v-if="row.diff_amount" :class="diffClass(row.diff_amount)">
            {{ row.diff_amount > 0 ? '+' : '' }}{{ formatNum(row.diff_amount) }}
          </span>
          <span v-else class="no-diff">-</span>
        </template>
      </el-table-column>

      <!-- 操作列 -->
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <!-- 拖拽手柄：仅未匹配行可拖 -->
          <el-tooltip
            v-if="row.status === 'unmatched'"
            content="拖到我方/客户记录上完成配对"
            placement="top"
          >
            <span
              class="drag-handle"
              draggable="true"
              :class="{ 'is-dragging': dragSource && dragSource.id === row.id }"
              @dragstart="onDragStart($event, row)"
              @dragend="onDragEnd"
            >⠿</span>
          </el-tooltip>

          <el-button
            v-if="row.status === 'unmatched' && canDropTarget(row)"
            size="small"
            type="success"
            plain
            class="drop-target"
            :class="{ 'is-over': dragOverId === row.id }"
            @dragover.prevent="onDragOver($event, row)"
            @dragleave="onDragLeave"
            @drop.prevent="onDrop($event, row)"
          >放置配对</el-button>

          <el-button
            v-if="row.status === 'unmatched'"
            type="primary"
            size="small"
            @click="$emit('manual-match', row)"
          >手动匹配</el-button>
          <el-button
            v-else-if="row.status === 'matched'"
            type="danger"
            size="small"
            plain
            @click="$emit('unmatch', row)"
          >解除</el-button>
          <el-button
            v-if="row.status === 'unmatched' && row.receipt"
            type="warning"
            size="small"
            plain
            @click="$emit('mark-diff', row)"
          >标记差异</el-button>
          <el-button
            v-if="row.status !== 'ignored'"
            type="info"
            size="small"
            plain
            @click="$emit('ignore', row)"
          >忽略</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="table-footer" v-if="hasData">
      <span class="table-footer-info">共 {{ total }} 条记录</span>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  items: { type: Array, default: () => [] },
  total: { type: Number, default: 0 },
})

const emit = defineEmits(['manual-match', 'unmatch', 'ignore', 'mark-diff', 'drag-match'])

const hasData = computed(() => props.items.length > 0)

// ============================================================
// 拖拽匹配（Ticket 06）
// ============================================================
const dragSource = ref(null)
const dragOverId = ref(null)

// 判断某行是否能作为 drop 目标：
// 只有当拖拽源与目标是「互补」时才可以（我方未匹配 ↔ 客户未匹配）
function canDropTarget(row) {
  if (!dragSource.value || row.status !== 'unmatched') return false
  if (dragSource.value.id === row.id) return false
  const src = dragSource.value
  const srcHasReceipt = !!src.receipt
  const dstHasReceipt = !!row.receipt
  // 一侧有 receipt（我方未匹配）、另一侧有 settlement（客户未匹配）
  return srcHasReceipt !== dstHasReceipt
}

function onDragStart(event, row) {
  dragSource.value = row
  event.dataTransfer.effectAllowed = 'move'
  event.dataTransfer.setData('text/plain', String(row.id))
}

function onDragEnd() {
  dragSource.value = null
  dragOverId.value = null
}

function onDragOver(event, row) {
  dragOverId.value = row.id
  event.dataTransfer.dropEffect = 'move'
}

function onDragLeave() {
  dragOverId.value = null
}

function onDrop(event, row) {
  const src = dragSource.value
  dragOverId.value = null
  dragSource.value = null
  if (!src || !canDropTarget(row)) return
  // 归一化：确保 receipt 侧在前、settlement 侧在后
  const receiptRow = src.receipt ? src : row
  const settlementRow = src.settlement ? src : row
  emit('drag-match', { receiptRow, settlementRow })
}

function rowClassName({ row }) {
  if (row.status === 'matched') return 'row-matched'
  if (row.status === 'unmatched') return 'row-unmatched'
  if (row.status === 'ignored') return 'row-ignored'
  return ''
}

function diffClass(val) {
  if (!val) return 'no-diff'
  return val > 0 ? 'diff-positive' : 'diff-negative'
}

function formatNum(val) {
  if (val == null) return '-'
  return Number(val).toFixed(2)
}

function onExpand(row, expanded) {
  // 展开行逻辑
}
</script>

<style scoped>
.expand-detail {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 0;
}
.detail-side {
  flex: 1;
  min-width: 250px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.detail-header {
  font-weight: 600;
  margin-bottom: 8px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
  color: #303133;
}
.detail-row {
  font-size: 13px;
  margin-bottom: 4px;
  color: #606266;
}
.detail-label {
  color: #909399;
}
.detail-diff, .detail-remark {
  flex: 0 0 100%;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
  border: 1px solid #ebeef5;
}
.diff-positive { color: #f56c6c; font-weight: 600; }
.diff-negative { color: #67c23a; font-weight: 600; }
.no-diff { color: #c0c4cc; }
.drag-handle {
  display: inline-block;
  cursor: grab;
  font-size: 16px;
  color: #909399;
  padding: 4px 8px;
  margin-right: 4px;
  user-select: none;
  vertical-align: middle;
  border-radius: 4px;
}
.drag-handle:active { cursor: grabbing; }
.drag-handle.is-dragging { opacity: 0.4; background: #ecf5ff; }
.drop-target { margin-right: 4px; }
.drop-target.is-over { border-color: #67c23a; color: #67c23a; background: #f0f9eb; }
.table-footer {
  display: flex;
  justify-content: flex-end;
  padding: 12px 0;
  font-size: 13px;
  color: #909399;
}
</style>