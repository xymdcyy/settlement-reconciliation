<template>
  <div class="system-admin-page">
    <el-page-header title="系统管理" @back="goHome" />

    <el-tabs v-model="activeTab" class="mt-4">
      <el-tab-pane label="客户管理" name="customers">
        <el-card>
          <template #header>
            <div class="flex justify-between items-center">
              <span>客户列表</span>
              <el-button type="primary" @click="showCreateDialog = true">新建客户</el-button>
            </div>
          </template>

          <el-table :data="customers" stripe>
            <el-table-column prop="name" label="客户名称" width="200" />
            <el-table-column prop="slug" label="标识" width="120" />
            <el-table-column label="对账单" width="100" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.has_statement" type="success">有</el-tag>
                <el-tag v-else type="info">无</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="engine_name" label="引擎" width="120" />
            <el-table-column label="扩展列" width="150">
              <template #default="{ row }">
                <el-tag v-if="row.extra_fields_config?.length" size="small">
                  {{ row.extra_fields_config.length }}个
                </el-tag>
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="状态" width="80" align="center">
              <template #default="{ row }">
                <el-tag v-if="row.is_active" type="success">启用</el-tag>
                <el-tag v-else type="danger">停用</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" align="center">
              <template #default="{ row }">
                <el-button size="small" @click="editCustomer(row)">编辑</el-button>
                <el-button size="small" type="danger" @click="deleteCustomer(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="用户管理" name="users">
        <el-card>
          <template #header>
            <span>用户列表</span>
          </template>
          <p>用户管理功能开发中...</p>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="引擎配置" name="engines">
        <el-card>
          <template #header>
            <span>引擎配置</span>
          </template>
          <p>引擎配置功能开发中...</p>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新建/编辑客户对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingCustomer ? '编辑客户' : '新建客户'"
      width="600px"
    >
      <el-form :model="form" label-width="100px">
        <el-form-item label="客户名称">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="标识">
          <el-input v-model="form.slug" placeholder="英文小写，如: weifangbaihuo" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" />
        </el-form-item>
        <el-form-item label="对账单">
          <el-switch v-model="form.has_statement" />
        </el-form-item>
        <el-form-item label="引擎" v-if="form.has_statement">
          <el-select v-model="form.engine_name">
            <el-option label="天猫" value="tmall" />
            <el-option label="重百" value="chongbai" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="saveCustomer">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getCustomers, createCustomer, updateCustomer, deleteCustomer as apiDeleteCustomer } from '../api'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()

// 返回工作台（系统管理页可能是首次进入/刷新的，无历史可回退，直接跳首页）
const goHome = () => {
  router.push('/')
}

const activeTab = ref('customers')
const customers = ref([])
const showCreateDialog = ref(false)
const editingCustomer = ref(null)
const form = ref({
  name: '',
  slug: '',
  description: '',
  has_statement: false,
  engine_name: null,
})

const loadCustomers = async () => {
  try {
    const res = await getCustomers()
    customers.value = res.data || []
  } catch (error) {
    ElMessage.error('加载客户列表失败')
  }
}

const editCustomer = (customer) => {
  editingCustomer.value = customer
  form.value = { ...customer }
  showCreateDialog.value = true
}

const saveCustomer = async () => {
  try {
    if (editingCustomer.value) {
      await updateCustomer(editingCustomer.value.id, form.value)
      ElMessage.success('更新成功')
    } else {
      await createCustomer(form.value)
      ElMessage.success('创建成功')
    }
    showCreateDialog.value = false
    editingCustomer.value = null
    form.value = {
      name: '',
      slug: '',
      description: '',
      has_statement: false,
      engine_name: null,
    }
    loadCustomers()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const deleteCustomer = async (customer) => {
  try {
    await ElMessageBox.confirm(`确定删除客户 ${customer.name} 吗？`, '警告', {
      type: 'warning',
    })
    await apiDeleteCustomer(customer.id)
    ElMessage.success('删除成功')
    loadCustomers()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

onMounted(() => {
  loadCustomers()
})
</script>

<style scoped>
.system-admin-page {
  padding: 20px;
}
</style>
