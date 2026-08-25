import axios from 'axios'

// 后端地址：优先取环境变量 VITE_API_BASE，默认 localhost
// 所有组件统一从这里取，不要硬编码 http://localhost:8000
export const API_BASE = import.meta.env?.VITE_API_BASE || 'http://localhost:8000'
export const API_URL = `${API_BASE}/api`

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
})

/**
 * 通用 Excel 下载：POST JSON → 接收 blob → 触发浏览器下载
 * @param {string} path API 路径（如 /billing/generate）
 * @param {object} payload POST body
 * @param {string} filename 下载文件名
 */
export async function downloadExcel(path, payload, filename) {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error('下载失败')
  const blob = await response.blob()
  const url = window.URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  window.URL.revokeObjectURL(url)
}

/**
 * 通用 Excel 下载：GET → 新窗口打开（带 query string）
 * @param {string} path API 路径（含 query）
 */
export function downloadExcelGet(path) {
  window.open(`${API_URL}${path}`, '_blank')
}

/**
 * 通用 JSON POST（返回解析后的 JSON）
 * @param {string} path API 路径
 * @param {object} payload POST body
 */
export async function postJson(path, payload) {
  const response = await fetch(`${API_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return response.json()
}

// ========== 客户相关 ==========

export const getCustomers = () => api.get('/customers')
export const getCustomer = (id) => api.get(`/customers/${id}`)
export const createCustomer = (data) => api.post('/customers', data)
export const updateCustomer = (id, data) => api.put(`/customers/${id}`, data)
export const deleteCustomer = (id) => api.delete(`/customers/${id}`)

// ========== 台账相关 ==========

export const getReceipts = (params) => api.get('/receipts', { params })
export const updateReceipt = (id, data) => api.put(`/receipts/${id}`, data)
export const splitReceipt = (id, data) => api.post(`/receipts/${id}/split`, data)
export const exportReceipts = (params) => api.get('/receipts/export', { params })
export const getPendingPool = (customerId) => api.get('/receipts/pending-pool', { params: { customer_id: customerId } })
export const resolvePending = (id, resolvedPeriod) => api.put(`/receipts/pending-pool/${id}/resolve`, { resolved_period: resolvedPeriod })

// ========== 核对相关 ==========

export const runReconciliation = (data) => api.post('/reconciliation/run', data)
export const getReconciliationStatus = (params) => api.get('/reconciliation/status', { params })
export const getReconciliationResults = (params) => api.get('/reconciliation/results', { params })
export const markDiff = (data) => api.post('/reconciliation/mark-diff', data)

// ========== 开票相关 ==========

export const getPendingBilling = (customerId, period) => api.get('/billing/pending', { params: { customer_id: customerId, period } })
export const generateBillingList = (receiptIds) => api.post('/billing/generate', { receipt_ids: receiptIds })
export const importBilledList = (items) => api.post('/billing/import-billed', { items })
export const getInvoices = (customerId, period) => api.get('/billing/invoices', { params: { customer_id: customerId, period } })

// ========== 红冲相关 ==========

export const getReturnReceipts = (customerId, period) => api.get('/red-flush/returns', { params: { customer_id: customerId, period } })
export const findBlueInvoice = (returnReceiptId) => api.post(`/red-flush/find-blue/${returnReceiptId}`)
export const batchFindBlueInvoices = (returnReceiptIds) => api.post('/red-flush/batch-find-blue', returnReceiptIds)
export const generateConfirmation = (returnReceiptIds) => api.post('/red-flush/generate', returnReceiptIds)
export const recordRedNotice = (returnReceiptId, redNoticeNo) => api.put(`/red-flush/record-red-no/${returnReceiptId}`, null, { params: { red_notice_no: redNoticeNo } })

// ========== 未决池相关 ==========

export const getPendingPoolItems = (customerId) => api.get('/pending-pool', { params: { customer_id: customerId } })
export const resolvePendingItem = (receiptId, resolvedPeriod) => api.put(`/pending-pool/${receiptId}/resolve`, { resolved_period: resolvedPeriod })
export const toRealDiff = (receiptId, diffNote) => api.put(`/pending-pool/${receiptId}/to-real`, null, { params: { diff_note: diffNote } })

// ========== 迁移相关 ==========

export const uploadMigrationExcel = (formData) => api.post('/migration/upload-excel', formData, {
  headers: { 'Content-Type': 'multipart/form-data' }
})
export const validateMigration = (customerId, filePath) => api.post('/migration/validate', null, { params: { customer_id: customerId, file_path: filePath } })
export const importMigration = (data) => api.post('/migration/import', data)

export default api
