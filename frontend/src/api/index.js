import axios from 'axios'
import { ElMessage } from 'element-plus'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

// 响应拦截：统一错误处理
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const msg = error.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

// ============================================================
// 上传 API
// ============================================================

/**
 * 上传我方签收明细
 * @param {File} file - Excel 文件
 * @param {string} period - 对账期间 YYYYMM
 * @returns {Promise<{total, assigned_to_customers, unassigned, message}>}
 */
export function uploadOurReceipts(file, period) {
  const form = new FormData()
  form.append('file', file)
  form.append('period', period)
  return api.post('/upload/our-receipts', form)
}

/**
 * 上传客户方结算单
 * @param {File} file - Excel 文件
 * @param {number} customerId - 客户 ID
 * @param {string} period - 对账期间 YYYYMM
 * @returns {Promise<{total, parsed, with_match_key, message}>}
 */
export function uploadSettlement(file, customerId, period) {
  const form = new FormData()
  form.append('file', file)
  form.append('customer_id', String(customerId))
  form.append('period', period)
  return api.post('/upload/settlements', form)
}

// ============================================================
// 对账 API
// ============================================================

/**
 * 运行对账匹配
 * @param {number} customerId
 * @param {string} period
 * @returns {Promise<{status, summary, message}>}
 */
export function runReconciliation(customerId, period) {
  return api.post('/reconciliation/run', { customer_id: customerId, period })
}

/**
 * 获取对账结果摘要
 * @param {number} customerId
 * @param {string} period
 * @returns {Promise<MatchSummaryResponse>}
 */
export function getReconciliationStatus(customerId, period) {
  return api.get('/reconciliation/status', {
    params: { customer_id: customerId, period },
  })
}

/**
 * 获取对账结果明细
 * @param {object} params
 * @param {number} params.customer_id
 * @param {string} params.period
 * @param {string} [params.status] - matched / unmatched / ignored
 * @param {string} [params.search] - 搜索关键词
 * @param {number} [params.page]
 * @param {number} [params.page_size]
 * @returns {Promise<{items: Array, total: number}>}
 */
export function getReconciliationResults(params) {
  return api.get('/reconciliation/results', { params })
}

// ============================================================
// 纠正 API
// ============================================================

/**
 * 手动匹配
 */
export function manualMatch(data) {
  return api.post('/corrections/manual-match', data)
}

/**
 * 解除匹配
 */
export function unmatch(data) {
  return api.post('/corrections/unmatch', data)
}

/**
 * 忽略
 */
export function ignoreResult(data) {
  return api.post('/corrections/ignore', data)
}

/**
 * 添加备注
 */
export function addNote(data) {
  return api.post('/corrections/note', data)
}

// ============================================================
// 客户 API
// ============================================================

/**
 * 获取客户列表
 * @returns {Promise<Array<{id, name, slug}>>}
 */
export function getCustomers() {
  return api.get('/customers')
}

/**
 * 获取可绑定的匹配引擎列表
 * @returns {Promise<Array<string>>}
 */
export function getAvailableEngines() {
  return api.get('/customers/engines')
}

/** 新建客户 */
export function createCustomer(data) {
  return api.post('/customers', data)
}

/** 更新客户 */
export function updateCustomer(id, data) {
  return api.put(`/customers/${id}`, data)
}

/** 删除（停用）客户 */
export function deleteCustomer(id) {
  return api.delete(`/customers/${id}`)
}

/** 绑定/更新客户引擎 */
export function bindEngine(id, data) {
  return api.put(`/customers/${id}/engine`, data)
}

/**
 * 获取上传历史
 * @param {number} [limit=20]
 * @returns {Promise<Array>}
 */
export function getUploadHistory(limit = 20) {
  return api.get('/upload/history', { params: { limit } })
}

/**
 * 导出对账结果 Excel（通过 axios 下载，保留错误处理和认证）
 * @param {number} customerId
 * @param {string} period
 */
export function exportReconciliation(customerId, period) {
  // 通过 axios 直接请求以获取 blob 和响应头
  axios({
    method: 'get',
    url: '/api/reconciliation/export',
    params: { customer_id: customerId, period },
    responseType: 'blob',
    timeout: 120000,
  }).then((response) => {
    // 从响应头获取文件名
    const disposition = response.headers?.['content-disposition'] || ''
    let filename = `对账结果_${customerId}_${period}.xlsx`
    const match = disposition.match(/filename\*?=UTF-8''([^;]+)/i)
    if (match) {
      filename = decodeURIComponent(match[1])
    }
    // 创建下载链接
    const url = URL.createObjectURL(response.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }).catch((error) => {
    const msg = error.response?.data?.detail || error.message || '导出失败'
    ElMessage.error(msg)
  })
}

/**
 * 获取历史对账记录
 * @param {object} params
 * @param {number} [params.customer_id]
 * @param {string} [params.start_month]
 * @param {string} [params.end_month]
 * @returns {Promise<{items: Array}>}
 */
export function getReconciliationHistory(params) {
  return api.get('/reconciliation/history', { params })
}

export default api