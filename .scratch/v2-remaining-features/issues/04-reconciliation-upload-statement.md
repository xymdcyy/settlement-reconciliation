# 04 — 核对桌：上传对账单

**What to build:** 实现对账单上传功能，财务专员可以上传客户的对账单 Excel，系统调用对应的引擎解析，解析结果存入 `customer_statements` 表，并显示解析成功的记录数。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 实现 `POST /api/reconciliation/upload-statement`：接收 FormData（customer_id, period, file）
- [ ] 调用对应的引擎解析 Excel（复用现有引擎的 `parse_customer_data` 方法）
- [ ] 解析结果存入 `customer_statements` 表
- [ ] 返回解析成功的记录数
- [ ] 前端：上传按钮 + 解析结果提示
