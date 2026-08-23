<template>
  <div class="migration-page">
    <el-page-header title="数据迁移" />

    <el-steps :active="currentStep" align-center class="mt-4">
      <el-step title="上传Excel" />
      <el-step title="验证数据" />
      <el-step title="执行导入" />
      <el-step title="完成" />
    </el-steps>

    <el-card class="mt-4">
      <!-- Step 1: 上传 Excel -->
      <div v-if="currentStep === 0">
        <el-form label-width="120px">
          <el-form-item label="选择客户">
            <el-select v-model="selectedCustomerId" placeholder="请选择客户">
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
              v-model="period"
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

          <el-form-item>
            <el-button type="primary" @click="uploadFile" :disabled="!canUpload">
              下一步
            </el-button>
          </el-form-item>
        </el-form>
      </div>

      <!-- Step 2: 验证数据 -->
      <div v-if="currentStep === 1">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Excel 行数">{{ validation.total_rows }}</el-descriptions-item>
          <el-descriptions-item label="解析行数">{{ validation.imported_rows }}</el-descriptions-item>
          <el-descriptions-item label="警告数">{{ validation.warnings?.length || 0 }}</el-descriptions-item>
          <el-descriptions-item label="错误数">{{ validation.errors?.length || 0 }}</el-descriptions-item>
        </el-descriptions>

        <el-alert v-if="validation.warnings?.length" type="warning" class="mt-4">
          <template #title>
            <div>
              <p>警告信息：</p>
              <ul>
                <li v-for="(w, i) in validation.warnings" :key="i">{{ w }}</li>
              </ul>
            </div>
          </template>
        </el-alert>

        <div class="mt-4">
          <el-button @click="currentStep = 0">上一步</el-button>
          <el-button type="primary" @click="executeImport" :disabled="validation.errors?.length > 0">
            执行导入
          </el-button>
        </div>
      </div>

      <!-- Step 3: 导入中 -->
      <div v-if="currentStep === 2">
        <el-progress :percentage="importProgress" :status="importStatus" />
        <p class="mt-4">{{ importMessage }}</p>
      </div>

      <!-- Step 4: 完成 -->
      <div v-if="currentStep === 3">
        <el-result icon="success" title="导入成功" sub-title="数据已成功迁移到系统中">
          <template #extra>
            <el-button type="primary" @click="reset">继续迁移</el-button>
            <el-button @click="$router.push('/')">返回工作台</el-button>
          </template>
        </el-result>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getCustomers, uploadMigrationExcel, validateMigration, importMigration } from '../api'
import { ElMessage } from 'element-plus'

const currentStep = ref(0)
const customers = ref([])
const selectedCustomerId = ref(null)
const period = ref('')
const selectedFile = ref(null)
const uploadedFilePath = ref('')
const validation = ref({})
const importProgress = ref(0)
const importStatus = ref('')
const importMessage = ref('')

const canUpload = computed(() => {
  return selectedCustomerId.value && period.value && selectedFile.value
})

const loadCustomers = async () => {
  try {
    const res = await getCustomers()
    customers.value = res.data || []
  } catch (error) {
    ElMessage.error('加载客户列表失败')
  }
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
}

const uploadFile = async () => {
  try {
    const formData = new FormData()
    formData.append('file', selectedFile.value)

    const res = await uploadMigrationExcel(formData)
    uploadedFilePath.value = res.data.file_path

    ElMessage.success('上传成功')

    // 验证数据
    const validateRes = await validateMigration(selectedCustomerId.value, uploadedFilePath.value)
    validation.value = validateRes.data

    currentStep.value = 1
  } catch (error) {
    ElMessage.error('上传失败')
  }
}

const executeImport = async () => {
  try {
    currentStep.value = 2
    importMessage.value = '正在导入数据...'
    importProgress.value = 50

    const res = await importMigration({
      customer_id: selectedCustomerId.value,
      file_path: uploadedFilePath.value,
      period: period.value,
    })

    importProgress.value = 100
    importStatus.value = 'success'
    importMessage.value = '导入完成'

    setTimeout(() => {
      currentStep.value = 3
    }, 1000)
  } catch (error) {
    importStatus.value = 'exception'
    importMessage.value = '导入失败: ' + error.message
    ElMessage.error('导入失败')
  }
}

const reset = () => {
  currentStep.value = 0
  selectedCustomerId.value = null
  period.value = ''
  selectedFile.value = null
  uploadedFilePath.value = ''
  validation.value = {}
  importProgress.value = 0
  importStatus.value = ''
  importMessage.value = ''
}

onMounted(() => {
  loadCustomers()
})
</script>

<style scoped>
.migration-page {
  padding: 20px;
}
</style>
