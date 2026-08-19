<template>
  <div class="correction-panel">
    <!-- 手动匹配 -->
    <el-dialog v-model="matchVisible" title="手动匹配" width="600px" :close-on-click-modal="false">
      <div v-if="currentRow" class="panel-content">
        <el-alert type="info" :closable="false" style="margin-bottom: 16px;">
          <template #title>
            待匹配我方记录：{{ currentRow.receipt?.model || '-' }} |
            ¥{{ currentRow.receipt?.amount || 0 }} |
            {{ currentRow.receipt?.quantity || 0 }} 台
          </template>
        </el-alert>
        <el-form label-width="100px">
          <el-form-item label="匹配结算单">
            <el-select
              v-model="selectedSettlementId"
              placeholder="请选择结算记录"
              filterable
              style="width: 100%"
              @visible-change="loadUnmatchedSettlements"
            >
              <el-option
                v-for="s in unmatchedSettlements"
                :key="s.id"
                :label="`${s.match_key || s.model || '未知'} | ¥${s.amount || 0} x${s.quantity || 0}`"
                :value="s.id"
              />
            </el-select>
          </el-form-item>
          <el-form-item label="原因">
            <el-input v-model="reason" type="textarea" rows="2" placeholder="可选，填写匹配理由" />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="matchVisible = false">取消</el-button>
        <el-button
          type="primary"
          :disabled="!selectedSettlementId"
          :loading="submitting"
          @click="confirmMatch"
        >确认匹配</el-button>
      </template>
    </el-dialog>

    <!-- 解除匹配 -->
    <el-dialog v-model="unmatchVisible" title="解除匹配" width="400px">
      <p>确定要解除这条匹配记录吗？</p>
      <el-form label-width="80px" style="margin-top: 16px;">
        <el-form-item label="原因">
          <el-input v-model="reason" type="textarea" rows="2" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="unmatchVisible = false">取消</el-button>
        <el-button type="danger" :loading="submitting" @click="confirmUnmatch">确认解除</el-button>
      </template>
    </el-dialog>

    <!-- 忽略 -->
    <el-dialog v-model="ignoreVisible" title="标记忽略" width="400px">
      <el-form label-width="80px">
        <el-form-item label="忽略原因">
          <el-input v-model="reason" type="textarea" rows="3" placeholder="请填写忽略原因（必填）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="ignoreVisible = false">取消</el-button>
        <el-button
          type="warning"
          :disabled="!reason"
          :loading="submitting"
          @click="confirmIgnore"
        >确认忽略</el-button>
      </template>
    </el-dialog>

    <!-- 操作成功提示 -->
    <el-alert
      v-if="successMessage"
      type="success"
      :title="successMessage"
      show-icon
      closable
      style="margin-bottom: 12px;"
      @close="successMessage = ''"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  manualMatch,
  unmatch,
  ignoreResult,
  getReconciliationResults,
} from '../api/index.js'

const props = defineProps({
  customerId: { type: [Number, String], required: true },
  period: { type: String, required: true },
})

const emit = defineEmits(['success'])

// 状态
const matchVisible = ref(false)
const unmatchVisible = ref(false)
const ignoreVisible = ref(false)
const submitting = ref(false)
const currentRow = ref(null)
const selectedSettlementId = ref(null)
const reason = ref('')
const successMessage = ref('')
const unmatchedSettlements = ref([])

// 手动匹配
function openManualMatch(row) {
  currentRow.value = row
  selectedSettlementId.value = null
  reason.value = ''
  matchVisible.value = true
}

async function loadUnmatchedSettlements() {
  try {
    const data = await getReconciliationResults({
      customer_id: props.customerId,
      period: props.period,
      status: 'unmatched',
      page_size: 200,
    })
    // 只保留 settlement 不为空的未匹配记录
    unmatchedSettlements.value = (data.items || [])
      .filter(item => item.settlement)
      .map(item => item.settlement)
  } catch {
    unmatchedSettlements.value = []
  }
}

async function confirmMatch() {
  submitting.value = true
  try {
    await manualMatch({
      customer_id: Number(props.customerId),
      period: props.period,
      receipt_id: currentRow.value.receipt_id,
      settlement_id: selectedSettlementId.value,
      reason: reason.value || undefined,
    })
    matchVisible.value = false
    ElMessage.success('手动匹配成功')
    emit('success')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    submitting.value = false
  }
}

// 解除匹配
function openUnmatch(row) {
  currentRow.value = row
  reason.value = ''
  unmatchVisible.value = true
}

async function confirmUnmatch() {
  submitting.value = true
  try {
    await unmatch({
      customer_id: Number(props.customerId),
      period: props.period,
      result_id: currentRow.value.id,
      reason: reason.value || '手动解除',
    })
    unmatchVisible.value = false
    ElMessage.success('已解除匹配')
    emit('success')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    submitting.value = false
  }
}

// 忽略
function openIgnore(row) {
  currentRow.value = row
  reason.value = ''
  ignoreVisible.value = true
}

async function confirmIgnore() {
  submitting.value = true
  try {
    await ignoreResult({
      customer_id: Number(props.customerId),
      period: props.period,
      result_id: currentRow.value.id,
      reason: reason.value,
    })
    ignoreVisible.value = false
    ElMessage.success('已忽略该记录')
    emit('success')
  } catch {
    // 错误已在拦截器中处理
  } finally {
    submitting.value = false
  }
}

// 暴露方法供父组件调用
defineExpose({
  openManualMatch,
  openUnmatch,
  openIgnore,
})
</script>