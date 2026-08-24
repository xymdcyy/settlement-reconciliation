# Spec: v2.0 剩余功能实现

## Problem Statement

v2.0 架构重构已完成，系统的骨架（数据模型、API 路由、前端页面）已搭建完毕，但多个核心功能只有占位实现（placeholder），无法支持试点客户的实际使用：

1. **Excel 导出功能缺失**：台账导出、开票清单导出、确认单导出都是 TODO，财务无法将系统数据导出给开票系统和税务
2. **核对桌未实现**：ReconciliationTab 只是占位文本，无法上传对账单、运行匹配、人工纠正，有对账单的客户（如天猫优品）无法使用核对功能
3. **权限控制缺失**：所有 API 都没有权限验证，无法限制财务专员只能访问自己负责的客户
4. **迁移工具规则库缺失**：MigrationService 的清洗逻辑是硬编码的，无法适应 200 个客户的列名差异，试点客户的迁移工作无法开展

这些问题阻塞了试点客户（潍坊百货、全福元、河北劲草、天猫优品）的数据迁移和日常使用。

## Solution

实现四个核心功能模块，使系统达到试点可用状态：

1. **Excel 导出服务**：实现台账导出、开票清单导出、确认单导出，支持筛选后导出，列名与原始台账一致
2. **核对桌完整实现**：复用现有引擎（天猫/重百），实现上传对账单、运行匹配、左右对照 UI、人工纠正、标记差异
3. **权限控制系统**：实现用户登录、财务-客户归属验证、API 权限检查，确保财务专员只能访问自己负责的客户
4. **迁移规则库**：实现 YAML 配置驱动的清洗规则，支持各客户的列名映射、状态值映射、特殊处理规则

## User Stories

### Excel 导出功能

1. As a 财务专员, I want to 导出台账为 Excel, so that 我可以离线查看或备份数据
2. As a 财务专员, I want to 按筛选条件（期间/状态/搜索）导出台账, so that 我只导出需要的数据
3. As a 财务专员, I want to 导出可开票清单为 Excel, so that 我可以发给开票系统进行开票
4. As a 财务专员, I want to 导出的 Excel 列名与原始台账一致, so that 我不需要重新学习列名含义
5. As a 财务专员, I want to 导出红冲确认单为 Excel, so that 我可以发给税务进行红字通知单流程
6. As a 财务专员, I want to 导出速度在 5 秒内完成（1 万行）, so that 我不会因为等待而中断工作

### 核对桌完整实现

7. As a 财务专员, I want to 上传客户对账单 Excel, so that 系统可以解析并进行匹配
8. As a 财务专员, I want to 运行自动匹配, so that 系统可以识别出一致的记录
9. As a 财务专员, I want to 看到左右对照的匹配结果, so that 我可以直观地确认匹配是否正确
10. As a 财务专员, I want to 看到匹配率和统计信息, so that 我可以了解对账的整体情况
11. As a 财务专员, I want to 拖拽未匹配的记录进行人工匹配, so that 我可以纠正系统的匹配错误
12. As a 财务专员, I want to 解除错误的匹配, so that 我可以重新进行匹配
13. As a 财务专员, I want to 标记记录为忽略（如费用单据）, so that 它们不参与匹配
14. As a 财务专员, I want to 标记差异类型（时间差/价格差/数量差）, so that 系统可以将它们挂入未决池
15. As a 财务专员, I want to 添加备注说明差异原因, so that 后续可以追溯
16. As a 财务专员, I want to 天猫优品的匹配率不低于 95%, so that 我可以信任系统的匹配结果

### 权限控制系统

17. As a 财务专员, I want to 登录系统, so that 系统可以识别我的身份
18. As a 财务专员, I want to 只能看到我负责的客户列表, so that 我不会被其他客户的信息干扰
19. As a 财务专员, I want to 只能查看和编辑我负责的客户的台账, so that 我不会误操作其他客户的数据
20. As a 主管, I want to 查看全部客户, so that 我可以监控全局情况
21. As a 主管, I want to 分配客户给财务专员, so that 我可以调整工作分工
22. As a 系统管理员, I want to 管理用户账号, so that 我可以控制谁能访问系统

### 迁移规则库

23. As a 财务专员, I want to 为每个客户配置清洗规则（YAML 文件）, so that 系统可以正确处理各客户的列名差异
24. As a 财务专员, I want to 配置列名映射（如"是否开票" → billing_status）, so that 系统可以识别各客户的手工区列
25. As a 财务专员, I want to 配置状态值映射（如"111" → billed）, so that 系统可以正确转换各客户的状态值
26. As a 财务专员, I want to 配置特殊处理规则（如"重复开具：xxx" → billed + remark）, so that 系统可以处理脏数据
27. As a 财务专员, I want to 为试点客户（潍坊百货/全福元/河北劲草/天猫优品）预先配置好规则, so that 我可以立即开始迁移
28. As a 主管, I want to 审批扩展列配置后才能生效, so that 我可以控制数据质量

## Implementation Decisions

### 模块划分

**Excel 导出服务**：
- 修改 `ExportService`（已有），新增三个方法：
  - `export_receipts_to_excel(receipts, customer)` → bytes
  - `export_billing_list_to_excel(receipts, customer)` → bytes
  - `export_red_flush_confirmation_to_excel(matches, customer)` → bytes
- 使用 `pandas.ExcelWriter` + `xlsxwriter` 引擎
- 列名从客户的 `raw_data` 中提取（保持与原始台账一致）

**核对桌完整实现**：
- 修改 `ReconciliationTab.vue`（前端），实现完整 UI：
  - 上传对账单（调用现有 `upload` API，但需要新建）
  - 运行匹配（调用现有 `run_reconciliation` API）
  - 左右对照表格（复用现有 `ComparisonTable.vue` 组件）
  - 人工纠正面板（复用现有 `CorrectionPanel.vue` 组件）
  - 标记差异（新增 API：`POST /api/reconciliation/mark-diff`）
- 修改 `MatchService`（后端），新增方法：
  - `upload_statement(customer_id, period, file)` → 解析并存入 `customer_statements`
  - `mark_diff(receipt_id, diff_type, diff_note)` → 更新 `receipts.diff_type/diff_note`

**权限控制系统**：
- 新增 `AuthService`：
  - `login(username, password)` → JWT token
  - `get_current_user(token)` → User
  - `has_permission(user, customer_id)` → bool
- 新增 `PermissionMiddleware`：
  - 在所有 API 路由前检查 token
  - 验证用户是否有权访问该客户（查询 `user_customer_assignments`）
- 修改 `HomePage.vue`：
  - 添加登录页面
  - 根据用户归属筛选客户列表

**迁移规则库**：
- 新增 `MigrationRuleEngine`：
  - `load_rules(customer_slug)` → dict（从 YAML 文件加载）
  - `apply_rules(df, rules)` → cleaned_df
- 新增 `scripts/migration/rules/` 目录，存放各客户的 YAML 规则文件
- 修改 `MigrationService.clean_data`：
  - 从 YAML 规则文件加载列名映射、状态值映射、特殊处理规则
  - 不再硬编码清洗逻辑

### Schema 变更

无需变更。所有功能都基于现有数据模型。

### API 契约

**新增 API**：

```
POST /api/auth/login
  Request: {username, password}
  Response: {token, user: {id, username, real_name, role}}

POST /api/reconciliation/upload-statement
  Request: FormData {customer_id, period, file}
  Response: {status, parsed_count, message}

POST /api/reconciliation/mark-diff
  Request: {receipt_id, diff_type, diff_note}
  Response: {status, message}

GET /api/receipts/export-excel
  Query: {customer_id, period?, billing_status?, search?}
  Response: Excel file (Content-Disposition: attachment)

GET /api/billing/export-billing-list
  Query: {customer_id, receipt_ids}
  Response: Excel file

GET /api/red-flush/export-confirmation
  Query: {customer_id, return_receipt_ids}
  Response: Excel file
```

**修改 API**：

```
所有 API 路由：
  新增 Depends(get_current_user) 进行权限验证
  新增 has_permission(user, customer_id) 检查
```

### 技术细节

**Excel 导出**：
- 使用 `pandas.DataFrame.to_excel()` 生成 Excel
- 使用 `io.BytesIO` 返回字节流
- 设置 `Content-Disposition: attachment; filename=...` 头

**权限验证**：
- 使用 JWT token（`python-jose` 库）
- Token 有效期：24 小时
- 密码哈希：`passlib.hash.bcrypt`

**YAML 规则文件格式**：
```yaml
customer: 潍坊百货
slug: weifangbaihuo

column_mapping:
  是否开票: billing_status
  发票号: invoice_no
  开票日期: invoice_date
  拆分: split_note
  备注: remark
  红通号: extra_fields.红通号
  红票勾选台数: extra_fields.红票勾选台数

status_mapping:
  已开: billed
  111: billed
  手工标识已开: billed
  未开: unbilled
  已拆分: split

special_rules:
  - pattern: "重复开具：(.+)"
    action: "billing_status=billed, remark=重复开具：\\1"
```

## Testing Decisions

### 什么是好的测试

- 只测试外部行为，不测试实现细节
- 使用真实的 Excel 文件进行测试（试点客户的样本数据）
- 测试边界情况（空数据、脏数据、大文件）

### 需要测试的模块

**Excel 导出服务**：
- `test_export_service.py`：
  - 导出的 Excel 列名与原始台账一致
  - 导出速度 < 5 秒（1 万行）
  - 支持筛选后导出
  - 空数据导出正常

**核对桌完整实现**：
- `test_reconciliation_ui.py`（前端测试，可选）：
  - 上传对账单后显示解析结果
  - 运行匹配后显示匹配率
  - 拖拽匹配功能正常
- `test_match_service.py`（已有，需扩展）：
  - 上传对账单解析正确
  - 标记差异功能正常

**权限控制系统**：
- `test_auth_service.py`：
  - 登录成功返回 token
  - 登录失败返回 401
  - 过期 token 返回 401
  - 无权限访问返回 403

**迁移规则库**：
- `test_migration_rules.py`：
  - 加载 YAML 规则文件成功
  - 列名映射正确
  - 状态值映射正确
  - 特殊处理规则正确
  - 试点客户的规则文件可用

### 测试的先例

- `tests/engines/test_tmall_engine.py`：引擎测试的先例
- `tests/test_match_service.py`：服务测试的先例

## Out of Scope

以下内容不在本 spec 范围内：

1. **全量客户的迁移规则配置**：只为试点客户（潍坊百货/全福元/河北劲草/天猫优品）配置规则，其余客户的规则在全量推广时再配置
2. **前端权限 UI**：只实现后端权限验证，前端的权限控制（如按钮禁用）在后续迭代中实现
3. **Excel 导出的样式定制**：只导出基本数据，不实现复杂的样式（如颜色、合并单元格）
4. **核对桌的性能优化**：先实现基本功能，性能优化（如虚拟滚动、增量加载）在后续迭代中实现
5. **未决池和红冲工具的增强**：这些功能已有基本实现，增强功能（如催办提醒、批量处理）在后续迭代中实现

## Further Notes

### 依赖关系

1. **Excel 导出服务** → 无依赖，可独立开发
2. **核对桌完整实现** → 依赖 Excel 导出服务（导出匹配结果）
3. **权限控制系统** → 无依赖，可独立开发
4. **迁移规则库** → 无依赖，可独立开发

**推荐开发顺序**：
1. Excel 导出服务（基础功能，其他功能依赖）
2. 迁移规则库（试点客户迁移的前提）
3. 权限控制系统（试点客户使用的前提）
4. 核对桌完整实现（最后，最复杂）

### 试点客户验收标准

**潍坊百货**：
- [ ] 台账成功导入（使用 YAML 规则）
- [ ] 台账导出 Excel 正常
- [ ] 开票清单导出 Excel 正常
- [ ] 红冲确认单导出 Excel 正常
- [ ] 财务专员只能看到潍坊百货

**全福元**：
- [ ] 台账成功导入（使用 YAML 规则）
- [ ] 台账导出 Excel 正常
- [ ] 开票清单导出 Excel 正常
- [ ] 财务专员只能看到全福元

**河北劲草**：
- [ ] 台账成功导入（使用 YAML 规则）
- [ ] 台账导出 Excel 正常
- [ ] 开票清单导出 Excel 正常
- [ ] 财务专员只能看到河北劲草

**天猫优品**：
- [ ] 台账成功导入（使用 YAML 规则）
- [ ] 对账单上传成功
- [ ] 自动匹配率 ≥ 95%
- [ ] 人工纠正功能正常
- [ ] 标记差异功能正常
- [ ] 财务专员只能看到天猫优品

---

*Spec 版本：v1.0*
*创建日期：2026-08-21*
*状态：ready-for-agent*
