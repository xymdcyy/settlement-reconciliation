<template>
  <div class="customers-page">
    <div class="page-header">
      <h2 class="page-title">客户管理</h2>
      <el-button type="primary" @click="openCreate">新建客户</el-button>
    </div>

    <div class="page-card" v-loading="loading">
      <el-table :data="customers" style="width: 100%">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="name" label="客户名称" min-width="140">
          <template #default="{ row }">
            <span style="font-weight:600">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="slug" label="标识" width="110" />
        <el-table-column label="归属关键词" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="k in row.match_keywords || []" :key="k" size="small" style="margin-right:4px">{{ k }}</el-tag>
            <span v-if="!(row.match_keywords && row.match_keywords.length)" style="color:#c0c4cc">—</span>
          </template>
        </el-table-column>
        <el-table-column label="匹配引擎" min-width="150">
          <template #default="{ row }">
            <span v-if="row.engine_config">{{ row.engine_config.engine_name }}
              <span style="color:#909399;font-size:12px">{{ row.engine_config.engine_version }}</span>
            </span>
            <el-tag v-else type="danger" size="small">未绑定</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="primary" plain @click="openEngine(row)">引擎</el-button>
            <el-popconfirm title="确定停用该客户？历史数据保留" @confirm="handleDelete(row)">
              <template #reference>
                <el-button size="small" type="danger" plain :disabled="!row.is_active">停用</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 新建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="editing ? '编辑客户' : '新建客户'" width="520px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户名称" required>
          <el-input v-model="form.name" placeholder="如：重庆百货智屏" />
        </el-form-item>
        <el-form-item label="标识 slug" required>
          <el-input v-model="form.slug" placeholder="英文小写，如：chongbai" :disabled="editing" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="归属关键词" >
          <el-select v-model="form.match_keywords" multiple filterable allow-create default-first-option
                     placeholder="输入关键词后回车（结算客户名称含全部关键词即归属）" style="width:100%">
          </el-select>
          <div class="form-hint">如「重百」：签收明细“结算客户名称”含全部关键词即归属本客户</div>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 引擎绑定对话框 -->
    <el-dialog v-model="engineVisible" title="绑定匹配引擎" width="480px">
      <el-form :model="engineForm" label-width="100px">
        <el-form-item label="客户">
          <span style="font-weight:600">{{ engineForm.customerName }}</span>
        </el-form-item>
        <el-form-item label="匹配引擎" required>
          <el-select v-model="engineForm.engine_name" placeholder="选择引擎" style="width:100%">
            <el-option v-for="e in engines" :key="e" :label="e" :value="e" />
          </el-select>
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="engineForm.engine_version" placeholder="如 v5.0.0" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="engineForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="engineVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="handleBindEngine">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getCustomers, getAvailableEngines, createCustomer, updateCustomer, deleteCustomer, bindEngine,
} from '../api/index.js'

const customers = ref([])
const engines = ref([])
const loading = ref(false)
const saving = ref(false)

const dialogVisible = ref(false)
const engineVisible = ref(false)
const editing = ref(null)

const emptyForm = { name: '', slug: '', description: '', is_active: true, match_keywords: [] }
const form = reactive({ ...emptyForm })
const engineForm = reactive({ customer_id: null, customerName: '', engine_name: '', engine_version: '', is_active: true })

async function load() {
  loading.value = true
  try {
    customers.value = await getCustomers()
  } catch {
    customers.value = []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editing.value = null
  Object.assign(form, { ...emptyForm })
  dialogVisible.value = true
}

function openEdit(row) {
  editing.value = row
  Object.assign(form, {
    name: row.name, slug: row.slug, description: row.description,
    is_active: row.is_active, match_keywords: row.match_keywords || [],
  })
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.name || !form.slug) {
    ElMessage.warning('请填写客户名称与标识')
    return
  }
  saving.value = true
  try {
    if (editing.value) {
      await updateCustomer(editing.value.id, { ...form })
      ElMessage.success('已更新')
    } else {
      await createCustomer({ ...form })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  await deleteCustomer(row.id)
  ElMessage.success(`已停用「${row.name}」`)
  await load()
}

function openEngine(row) {
  Object.assign(engineForm, {
    customer_id: row.id,
    customerName: row.name,
    engine_name: row.engine_config?.engine_name || '',
    engine_version: row.engine_config?.engine_version || '',
    is_active: row.engine_config?.is_active ?? true,
  })
  engineVisible.value = true
}

async function handleBindEngine() {
  if (!engineForm.engine_name) {
    ElMessage.warning('请选择引擎')
    return
  }
  saving.value = true
  try {
    await bindEngine(engineForm.customer_id, {
      engine_name: engineForm.engine_name,
      engine_version: engineForm.engine_version,
      is_active: engineForm.is_active,
    })
    ElMessage.success('引擎已绑定')
    engineVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await load()
  try {
    engines.value = await getAvailableEngines()
  } catch {
    engines.value = []
  }
})
</script>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-header .page-title { margin: 0; }
.form-hint {
  font-size: 12px;
  color: #909399;
  line-height: 1.4;
  margin-top: 4px;
}
</style>
