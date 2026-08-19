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
 * 获取上传历史
 * @param {number} [limit=20]
 * @returns {Promise<Array>}
 */
export function getUploadHistory(limit = 20) {
  return api.get('/upload/history', { params: { limit } })
}

export default api