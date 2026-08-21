# 数据模型

> 本文档定义系统的数据结构和关系。
> 所有数据库表、字段、约束都必须遵循本文档。

## 1. 核心实体关系

```
┌──────────────┐       ┌──────────────┐       ┌──────────────┐
│   users      │       │  customers   │       │  receipts    │
│   (用户)      │──────▶│   (客户)      │──────▶│  (台账行)     │
│              │ N:N   │              │ 1:N   │              │
│ 财务专员      │       │ - 基本信息    │       │ - 系统字段    │
│ 主管         │       │ - 归属财务    │       │ - 开票状态    │
└──────────────┘       │ - 扩展列配置  │       │ - 扩展字段    │
                       └──────┬───────┘       │ - 差异判断    │
                              │               └──────┬───────┘
                              │                      │
                              │ 1:N                  │ 1:N (父子)
                              │                      ▼
                       ┌──────┴───────┐       ┌──────────────┐
                       │ customer_    │       │  receipts    │
                       │ statements   │       │  (子行)       │
                       │ (客户对账单)  │       │  split_from  │
                       └──────┬───────┘       └──────────────┘
                              │
                              │ N:M (通过match_results)
                              ▼
                       ┌──────────────┐
                       │ match_results│
                       │ (匹配结果)    │
                       └──────────────┘

┌──────────────┐       ┌──────────────┐
│  invoices    │       │ adjustments  │
│  (发票记录)   │       │ (调账/红冲)   │
│              │       │              │
│ - 发票号      │       │ - 类型        │
│ - 开票日期    │       │ - 关联记录    │
│ - 关联台账行  │       │ - 红通号      │
└──────────────┘       └──────────────┘
```

## 2. 核心表设计

### 2.1 receipts（台账行）⭐核心表

**用途**：存储所有客户的台账记录（我方签收 + 开票状态）

| 字段 | 类型 | 说明 | 来源 |
|------|------|------|------|
| **主键与关联** | | | |
| id | BIGINT | 主键 | 系统 |
| customer_id | INT | 客户ID（外键） | 系统 |
| period | VARCHAR(6) | 对账期间 YYYYMM | 系统 |
| batch_id | VARCHAR(50) | 导入批次 | 系统 |
| **系统字段**（从94列提取） | | | |
| receipt_no | VARCHAR(50) | 新方舟销售单号 | 系统列 |
| model | VARCHAR(100) | 产品型号 | 系统列 |
| quantity | DECIMAL(12,2) | 签收数量 | 系统列 |
| amount | DECIMAL(14,2) | 签收金额 | 系统列 |
| unit_price | DECIMAL(14,4) | 单价 | 系统列 |
| receipt_date | DATE | 签收日期 | 系统列 |
| doc_type | VARCHAR(50) | 单据类型 | 系统列 |
| customer_name | VARCHAR(200) | 结算客户名称 | 系统列 |
| nc_order_no | VARCHAR(100) | NC订单号 | 系统列 |
| product_line | VARCHAR(50) | 产品线 | 系统列 |
| raw_data | JSONB | 原始94列完整数据 | 系统列 |
| **开票状态**（核心集）⭐ | | | |
| billing_status | VARCHAR(20) | 开票状态：unbilled/billed/split/partial | 手工 |
| invoice_no | VARCHAR(100) | 发票号 | 手工 |
| invoice_date | DATE | 开票日期 | 手工 |
| split_parent_id | BIGINT | 拆分父行ID（自引用） | 手工 |
| split_note | VARCHAR(200) | 拆分说明 | 手工 |
| remark | TEXT | 备注 | 手工 |
| **扩展字段**（客户级配置） | | | |
| extra_fields | JSONB | 扩展列值（如{红通号:xxx}） | 手工 |
| **差异判断** | | | |
| diff_type | VARCHAR(50) | 差异类型：time_diff/price_diff/qty_diff/none | 手工 |
| diff_note | TEXT | 差异说明 | 手工 |
| resolved_period | VARCHAR(6) | 解决期间（YYYYMM） | 手工 |
| **审计** | | | |
| created_at | TIMESTAMP | 创建时间 | 系统 |
| updated_at | TIMESTAMP | 更新时间 | 系统 |
| created_by | INT | 创建人 | 系统 |
| updated_by | INT | 更新人 | 系统 |

**索引**：
```sql
CREATE INDEX idx_customer_period ON receipts(customer_id, period);
CREATE INDEX idx_receipt_no ON receipts(receipt_no);
CREATE INDEX idx_billing_status ON receipts(billing_status);
CREATE INDEX idx_split_parent ON receipts(split_parent_id);
CREATE INDEX idx_diff_type ON receipts(diff_type) WHERE diff_type != 'none';
```

**约束**：
- `(receipt_no, split_parent_id)` 不唯一（允许拆分后多行同单号）
- `billing_status` 枚举：`unbilled`（未开）/ `billed`（已开）/ `split`（已拆分）/ `partial`（部分开票）
- `split_parent_id` 为 NULL 表示父行/未拆分行

**关键设计**：
1. **系统字段与开票状态合并在一张表**——避免多表同步
2. **raw_data JSONB** 保留完整94列，系统字段只是提取物
3. **extra_fields JSONB** 承载客户级扩展列，key为列名，value为值
4. **split_parent_id** 实现父子行关系，支持递归拆分

### 2.2 customers（客户）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| name | VARCHAR(200) | 客户名称 |
| slug | VARCHAR(50) | 客户标识（英文） |
| has_statement | BOOLEAN | 是否有对账单 |
| engine_name | VARCHAR(100) | 对账引擎（如有） |
| extra_fields_config | JSONB | 扩展列配置 [{name, type, required}] |
| is_active | BOOLEAN | 是否启用 |
| created_at | TIMESTAMP | 创建时间 |

**extra_fields_config 示例**：
```json
[
  {"name": "红通号", "type": "string", "required": false},
  {"name": "红票勾选台数", "type": "number", "required": false}
]
```

### 2.3 user_customer_assignments（用户-客户归属）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT | 主键 |
| user_id | INT | 用户ID（外键） |
| customer_id | INT | 客户ID（外键） |
| role | VARCHAR(20) | 角色：owner/viewer |
| created_at | TIMESTAMP | 创建时间 |

**约束**：`(user_id, customer_id)` 唯一

### 2.4 customer_statements（客户对账单）⭐核对桌专用

**用途**：存储客户提供的对账单记录（保留现有设计）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| customer_id | INT | 客户ID |
| period | VARCHAR(6) | 对账期间 |
| batch_id | VARCHAR(50) | 导入批次 |
| match_key | VARCHAR(200) | 引擎提取的匹配键 |
| model | VARCHAR(100) | 型号 |
| quantity | DECIMAL(12,2) | 数量 |
| amount | DECIMAL(14,2) | 金额 |
| unit_price | DECIMAL(14,4) | 单价 |
| settlement_date | DATE | 业务日期 |
| raw_data | JSONB | 客户原始数据 |
| status | VARCHAR(20) | pending/matched/unmatched/ignored |
| created_at | TIMESTAMP | 创建时间 |

### 2.5 match_results（匹配结果）⭐核对桌专用

**用途**：存储 receipts 与 customer_statements 的匹配关系（保留现有设计）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| customer_id | INT | 客户ID |
| period | VARCHAR(6) | 对账期间 |
| receipt_id | BIGINT | 我方记录ID（外键→receipts） |
| statement_id | BIGINT | 客户记录ID（外键→customer_statements） |
| match_type | VARCHAR(50) | 匹配类型 |
| confidence | DECIMAL(5,2) | 置信度 |
| status | VARCHAR(20) | matched/unmatched/manual/ignored |
| diff_amount | DECIMAL(14,2) | 金额差异 |
| diff_quantity | DECIMAL(12,2) | 数量差异 |
| remark | TEXT | 备注 |
| source | VARCHAR(20) | auto/manual |
| created_at | TIMESTAMP | 创建时间 |

### 2.6 invoices（发票记录）

**用途**：记录发票信息（一行台账可对应多张发票，拆分场景）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| receipt_id | BIGINT | 台账行ID（外键） |
| invoice_no | VARCHAR(100) | 发票号 |
| invoice_date | DATE | 开票日期 |
| amount | DECIMAL(14,2) | 开票金额 |
| quantity | DECIMAL(12,2) | 开票数量 |
| invoice_type | VARCHAR(20) | blue（蓝票）/ red（红票） |
| red_notice_no | VARCHAR(100) | 红字通知单号（红票） |
| original_invoice_id | BIGINT | 原蓝票ID（红票，自引用） |
| created_at | TIMESTAMP | 创建时间 |
| created_by | INT | 创建人 |

### 2.7 adjustments（调账/红冲记录）

**用途**：记录差异处理和红冲流程

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT | 主键 |
| customer_id | INT | 客户ID |
| receipt_id | BIGINT | 关联台账行 |
| adjustment_type | VARCHAR(50) | 类型：return/price_adjust/qty_adjust |
| original_receipt_no | VARCHAR(50) | 原单号 |
| adjustment_receipt_no | VARCHAR(50) | 调账单号 |
| red_notice_no | VARCHAR(100) | 红字通知单号 |
| status | VARCHAR(20) | pending/confirmed/completed |
| note | TEXT | 说明 |
| created_at | TIMESTAMP | 创建时间 |
| created_by | INT | 创建人 |

## 3. 数据流转

### 3.1 台账行生命周期

```
1. 导入（系统）
   ↓ billing_status = 'unbilled'
2. [有对账单客户] 核对
   ↓ match_results.status = 'matched'
3. 开票（手工）
   ↓ billing_status = 'billed', 填invoice_no/invoice_date
   ↓ 插入 invoices 记录
4. [拆分场景]
   ↓ 父行 billing_status = 'split'
   ↓ 生成子行，split_parent_id = 父行id
   ↓ 子行各自开票
5. [退货场景]
   ↓ 插入 adjustments 记录（类型=return）
   ↓ 查找蓝票 → 开红票
   ↓ 填 extra_fields.红通号
```

### 3.2 未决差异池流转

```
本月核对不一致
  ↓ diff_type = 'time_diff'
  ↓ resolved_period = NULL
挂入未决池
  ↓ 下月对账单来了，自动匹配成功
  ↓ resolved_period = '202609'
消解
  ↓ 或：挂账3个月未消解，人工判断为真差异
  ↓ diff_type = 'price_diff'
  ↓ 新方舟调账
转为真差异
```

## 4. 数据迁移映射

### 4.1 Excel台账 → receipts 表

| Excel列 | receipts字段 | 转换规则 |
|---------|-------------|----------|
| 新方舟销售单号 | receipt_no | 直接映射 |
| 产品型号 | model | 直接映射 |
| 签收数量 | quantity | 直接映射 |
| ... | ... | ... |
| 是否开票 | billing_status | 枚举转换：`已开/111→billed`, `未开/空→unbilled`, `已拆分→split` |
| 发票号 | invoice_no | 直接映射 |
| 开票日期 | invoice_date | 日期解析 |
| 拆分 | split_note | 直接映射 |
| 备注 | remark | 直接映射 |
| 红通号 | extra_fields.红通号 | JSONB |
| 其他94列 | raw_data | 整行JSON |

### 4.2 脏数据处理

| Excel值 | 转换后 | 说明 |
|---------|--------|------|
| `111` | `billed` | 识别为已开 |
| `重复开具：24932...` | `billed` + remark | 状态+备注拆分 |
| `手工标识已开` | `billed` | 识别为已开 |
| 空 | `unbilled` | 默认未开 |
| 日期格式混乱 | 尝试多种格式解析 | `2026-08-21` / `2026/8/21` / `43829`(Excel序列号) |

## 5. 关键设计决策

### 5.1 为什么不分离"我方签收"和"台账状态"？

**决策**：合并为一张 receipts 表

**理由**：
1. 开票状态是台账行的属性，不是独立实体
2. 避免两表 JOIN 和同步问题
3. 拆分场景下，父子行共享系统字段，只有状态不同

**代价**：表字段较多（20+平台字段 + JSONB），但可控

### 5.2 为什么扩展字段用 JSONB 而不是动态列？

**决策**：`extra_fields JSONB` + `customers.extra_fields_config`

**理由**：
1. 200 客户的扩展列各不相同，动态加列会导致 schema 爆炸
2. JSONB 支持灵活查询（PostgreSQL）
3. 配置驱动，审批后生效，防止随意扩展

**代价**：查询稍复杂，但可接受

### 5.3 为什么拆分用父子行而不是数量字段？

**决策**：`split_parent_id` 自引用

**理由**：
1. 拆分后子行可独立开票、独立红冲
2. 保留完整审计痕迹（父行不删除）
3. 支持递归拆分（子行再拆）

**约束**：子行不可跨父行合并

---

*文档版本：v2.0（架构重构版）*
*创建日期：2026-08-21*
*状态：待评审*
