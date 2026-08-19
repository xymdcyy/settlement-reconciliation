<template>
  <div class="upload-page">
    <h2 class="page-title">上传对账单</h2>

    <!-- 我方签收明细 -->
    <div class="page-card" style="margin-bottom: 20px">
      <h3 style="margin-bottom: 16px;">
        <el-icon size="18"><Upload /></el-icon>
        我方签收明细
      </h3>
      <el-form :model="ourForm" label-width="100px">
        <el-form-item label="对账期间">
          <el-date-picker
            v-model="ourForm.period"
            type="month"
            placeholder="选择对账月份"
            value-format="YYYYMM"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="签收文件">
          <div
            class="upload-zone"
            :class="{ 'is-dragover': ourDragover }"
            @dragover.prevent="ourDragover = true"
            @dragleave.prevent="ourDragover = false"
            @drop.prevent="onOurDrop"
            @click="triggerOurInput"
          >
            <el-icon size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <p style="margin-top: 12px; color: #909399;">
              {{ ourForm.file ? ourForm.file.name : '拖拽文件到此处，或点击选择文件' }}
            </p>
            <p style="font-size: 12px; color: #c0c4cc; margin-top: 4px;">支持 .xlsx / .xls 格式</p>
          </div>
          <input
            ref="ourInputRef"
            type="file"
            accept=".xlsx,.xls"
            style="display: none"
            @change="onOurFileChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="ourUploading"
            :disabled="!canUploadOur"
            @click="handleOurUpload"
          >
            {{ ourUploading ? '上传中...' : '上传我方签收明细' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 我方上传进度 -->
      <el-progress
        v-if="ourUploading"
        :percentage="ourProgress"
        :stroke-width="8"
        style="margin-top: 12px;"
      />

      <!-- 我方上传结果 -->
      <el-alert
        v-if="ourResult"
        :type="ourResult.success ? 'success' : 'error'"
        :title="ourResult.message"
        show-icon
        style="margin-top: 12px;"
        closable
      />
    </div>

    <!-- 客户方结算单 -->
    <div class="page-card" style="margin-bottom: 20px">
      <h3 style="margin-bottom: 16px;">
        <el-icon size="18"><Document /></el-icon>
        客户方结算单
      </h3>
      <el-form :model="settlementForm" label-width="100px">
        <el-form-item label="选择客户">
          <el-select
            v-model="settlementForm.customerId"
            placeholder="请选择客户"
            style="width: 200px"
            @change="loadCustomers"
          >
            <el-option
              v-for="c in customers"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="对账期间">
          <el-date-picker
            v-model="settlementForm.period"
            type="month"
            placeholder="选择对账月份"
            value-format="YYYYMM"
            style="width: 200px"
          />
        </el-form-item>
        <el-form-item label="结算文件">
          <div
            class="upload-zone"
            :class="{ 'is-dragover': settlementDragover }"
            @dragover.prevent="settlementDragover = true"
            @dragleave.prevent="settlementDragover = false"
            @drop.prevent="onSettlementDrop"
            @click="triggerSettlementInput"
          >
            <el-icon size="48" color="#c0c4cc"><UploadFilled /></el-icon>
            <p style="margin-top: 12px; color: #909399;">
              {{ settlementForm.file ? settlementForm.file.name : '拖拽文件到此处，或点击选择文件' }}
            </p>
            <p style="font-size: 12px; color: #c0c4cc; margin-top: 4px;">支持 .xlsx / .xls 格式</p>
          </div>
          <input
            ref="settlementInputRef"
            type="file"
            accept=".xlsx,.xls"
            style="display: none"
            @change="onSettlementFileChange"
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            :loading="settlementUploading"
            :disabled="!canUploadSettlement"
            @click="handleSettlementUpload"
          >
            {{ settlementUploading ? '上传中...' : '上传客户方结算单' }}
          </el-button>
        </el-form-item>
      </el-form>

      <!-- 客户方上传进度 -->
      <el-progress
        v-if="settlementUploading"
        :percentage="settlementProgress"
        :stroke-width="8"
        style="margin-top: 12px;"
      />

      <!-- 客户方上传结果 -->
      <el-alert
        v-if="settlementResult"
        :type="settlementResult.success ? 'success' : 'error'"
        :title="settlementResult.message"
        show-icon
        style="margin-top: 12px;"
        closable
      />
    </div>

    <!-- 上传历史 -->
    <div class="page-card">
      <h3 style="margin-bottom: 16px;">
        <el-icon size="18"><Clock /></el-icon>
        上传历史
      </h3>
      <el-table :data="history" stripe style="width: 100%" v-loading="historyLoading">
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag v-if="row.type === 'our'" type="success" size="small">我方签收</el-tag>
            <el-tag v-else type="warning" size="small">客户结算</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="period" label="对账期间" width="100" />
        <el-table-column prop="customer_name" label="客户" min-width="120" />
        <el-table-column prop="total" label="总行数" width="80" />
        <el-table-column prop="created_at" label="上传时间" min-width="160" />
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
      <el-empty v-if="!history.length && !historyLoading" description="暂无上传记录" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Upload, UploadFilled, Document, Clock } from '@element-plus/icons-vue'
import { uploadOurReceipts, uploadSettlement, getCustomers, getUploadHistory } from '../api/index.js'

const router = useRouter()

// ============================================================
// 我方签收上传
// ============================================================
const ourForm = ref({ file: null, period: '' })
const ourInputRef = ref(null)
const ourDragover = ref(false)
const ourUploading = ref(false)
const ourProgress = ref(0)
const ourResult = ref(null)

const canUploadOur = computed(() => ourForm.value.file && ourForm.value.period)

function triggerOurInput() {
  ourInputRef.value?.click()
}

function onOurDrop(e) {
  ourDragover.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    ourForm.value.file = file
  }
}

function onOurFileChange(e) {
  const file = e.target?.files?.[0]
  if (file) {
    ourForm.value.file = file
  }
}

async function handleOurUpload() {
  if (!canUploadOur.value) return
  ourUploading.value = true
  ourProgress.value = 10
  ourResult.value = null
  try {
    const data = await uploadOurReceipts(ourForm.value.file, ourForm.value.period)
    ourProgress.value = 100
    ourResult.value = {
      success: true,
      message: `上传成功！共 ${data.total} 条记录，其中 ${Object.values(data.assigned_to_customers || {}).reduce((a, b) => a + b, 0)} 条已分配到客户，${data.unassigned} 条未分配。`,
    }
    loadHistory()
  } catch (e) {
    ourResult.value = { success: false, message: '上传失败，请重试' }
  } finally {
    ourUploading.value = false
  }
}

// ============================================================
// 客户方结算单上传
// ============================================================
const settlementForm = ref({ file: null, customerId: '', period: '' })
const settlementInputRef = ref(null)
const settlementDragover = ref(false)
const settlementUploading = ref(false)
const settlementProgress = ref(0)
const settlementResult = ref(null)
const customers = ref([])

const canUploadSettlement = computed(
  () => settlementForm.value.file && settlementForm.value.customerId && settlementForm.value.period,
)

function triggerSettlementInput() {
  settlementInputRef.value?.click()
}

function onSettlementDrop(e) {
  settlementDragover.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file && (file.name.endsWith('.xlsx') || file.name.endsWith('.xls'))) {
    settlementForm.value.file = file
  }
}

function onSettlementFileChange(e) {
  const file = e.target?.files?.[0]
  if (file) {
    settlementForm.value.file = file
  }
}

async function handleSettlementUpload() {
  if (!canUploadSettlement.value) return
  settlementUploading.value = true
  settlementProgress.value = 10
  settlementResult.value = null
  try {
    const data = await uploadSettlement(
      settlementForm.value.file,
      settlementForm.value.customerId,
      settlementForm.value.period,
    )
    settlementProgress.value = 100
    settlementResult.value = {
      success: true,
      message: `上传成功！共 ${data.total} 条，解析 ${data.parsed} 条，其中 ${data.with_match_key} 条含匹配键。`,
    }
    loadHistory()
  } catch (e) {
    settlementResult.value = { success: false, message: '上传失败，请重试' }
  } finally {
    settlementUploading.value = false
  }
}

// ============================================================
// 客户列表
// ============================================================
async function loadCustomers() {
  try {
    customers.value = await getCustomers()
  } catch {
    // 静默失败
  }
}

// ============================================================
// 上传历史
// ============================================================
const history = ref([])
const historyLoading = ref(false)

async function loadHistory() {
  historyLoading.value = true
  try {
    history.value = await getUploadHistory(20)
  } catch {
    history.value = []
  } finally {
    historyLoading.value = false
  }
}

onMounted(() => {
  loadCustomers()
  loadHistory()
})
</script>

<style scoped>
.upload-page {
  max-width: 900px;
}
</style>