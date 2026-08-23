import axios from 'axios'

const api = axios.create({
  baseURL: 'http://localhost:8000/api',
  timeout: 30000,
})

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
