# Phase 1: 结算对账平台 MVP — 天猫优品经销核对 Web 化

## Problem Statement

财务人员目前通过命令行脚本（`python 天猫优品-智屏-经销.py`）进行对账：上传 Excel 文件 → 运行脚本 → 下载 Excel 结果。这种工作方式存在以下问题：

1. **操作门槛高**：需要命令行操作，财务人员需要学习 Python 环境配置、文件路径管理等
2. **无数据持久化**：每次核对结果仅存为 Excel 文件，历史数据无法追溯查询
3. **无人工纠正界面**：差异记录只能通过 Excel 表格人工标记，操作不便且无法审计
4. **无扩展性**：每个客户一套独立脚本，新增客户需要复制整个代码文件

MVP 阶段的目标是：将**天猫优品经销**的核对功能搬上 Web，保留现有匹配逻辑，但提供 Web 上传、在线比对、人工纠正、历史查询和报表导出功能。

## Solution

建立一个结算对账 Web 平台，包含：

- **数据上传**：Web 页面上传我方签收明细 Excel 和客户方结算单 Excel
- **自动匹配**：继承现有天猫优品经销匹配引擎（PON 号 + 金额 + 型号匹配），跑在服务端
- **在线比对工作台**：左右对照表格展示匹配结果，颜色标注匹配状态
- **人工纠正**：手动匹配/解除匹配/忽略/添加备注，所有操作记录审计日志
- **报表导出**：一键导出对账结果 Excel
- **历史查询**：按月筛选历史对账记录

## User Stories

1. As a 财务人员, I want to upload my side's receipt Excel (新方舟签收明细) through a web page, so that I don't need to copy files to a specific directory or run commands
2. As a 财务人员, I want to upload the customer's settlement Excel (天猫优品结算单) through a web page, so that I can prepare both sides' data in one place
3. As a 财务人员, I want to click a single button to run the reconciliation, so that I don't need to remember command-line arguments
4. As a 财务人员, I want to see the reconciliation results in a side-by-side table (left: my receipts, right: customer settlements), so that I can visually inspect matched and unmatched records
5. As a 财务人员, I want matched records to be highlighted in green and unmatched records in red, so that I can quickly identify discrepancies
6. As a 财务人员, I want to filter records by match status (all/matched/unmatched/excluded), so that I can focus on the records that need attention
7. As a 财务人员, I want to search records by model number or order number, so that I can quickly locate specific transactions
8. As a 财务人员, I want to manually match an unmatched my-side record to an unmatched customer-side record by dragging or selecting from a dropdown, so that I can correct obvious mismatches
9. As a 财务人员, I want to unlink an incorrectly matched pair, so that I can fix false positives
10. As a 财务人员, I want to mark a record as "ignored" with a reason (e.g., "费用单据，不参与对账"), so that it's excluded from the reconciliation
11. As a 财务人员, I want to add notes to any record, so that I can document my reasoning for future reference
12. As a 财务人员, I want to see a summary bar showing match rate, total matched count, unmatched count on each side, so that I can assess the overall reconciliation status
13. As a 财务人员, I want to export the reconciliation results as an Excel file, so that I can share with stakeholders or archive
14. As a 财务人员, I want the exported Excel to contain separate sheets for summary statistics, matched details, unmatched records, and amount differences, so that I have all information organized
15. As a 财务人员, I want to view historical reconciliation records by month, so that I can track changes over time
16. As a 财务人员, I want all manual operations (match, unlink, ignore, note) to be logged with timestamp and operator, so that I can audit who changed what and when
17. As a 财务人员, I want to see how much of the total amount is reconciled vs. unmatched, so that I can assess financial impact
18. As a 财务人员, I want to know the match rate immediately after the automated matching completes, so that I can decide whether to proceed with manual correction or re-upload corrected data
19. As a system administrator, I want to add new customers with their own matching engine configuration, so that the platform can support multiple customers
20. As a system administrator, I want to upload our side's receipt data once and have it automatically assigned to the correct customer based on the settlement customer name, so that I don't need to manually split data per customer

## Implementation Decisions

### 1. Database Schema (SQLAlchemy models)

The following tables will be created in the MVP phase (all tables use `sqlalchemy` ORM with PostgreSQL):

**`our_receipts`** — Standardized our-side receipt records, shared across all customers.
- `id` (BigInt, PK, auto-increment)
- `receipt_no` (str, NOT NULL, indexed) — 新方舟销售单号
- `customer_id` (int, NOT NULL, FK to customers)
- `period` (str, 6 chars, NOT NULL, indexed) — YYYYMM
- `model` (str, nullable) — 产品型号
- `quantity` (Decimal, nullable) — 签收数量
- `amount` (Decimal, nullable) — 签收金额
- `unit_price` (Decimal, nullable) — 单价
- `receipt_date` (date, nullable) — 签收日期
- `doc_type` (str, nullable) — 单据类型
- `customer_name` (str, nullable) — 结算客户名称
- `nc_order_no` (str, nullable, indexed) — NC订单号
- `product_line` (str, nullable) — 产品线
- `raw_data` (JSONB, nullable) — 原始98列数据
- `batch_id` (str, nullable) — 导入批次
- `created_at` (timestamp)

**`customer_settlements`** — Customer-side settlement records, shared across all customers.
- `id` (BigInt, PK, auto-increment)
- `customer_id` (int, NOT NULL, FK)
- `period` (str, 6 chars, NOT NULL, indexed)
- `batch_id` (str, nullable)
- `match_key` (str, nullable, indexed) — 引擎提取的匹配键
- `model` (str, nullable) — 引擎提取的型号
- `quantity` (Decimal, nullable)
- `amount` (Decimal, nullable)
- `unit_price` (Decimal, nullable)
- `settlement_date` (date, nullable)
- `doc_type` (str, nullable)
- `status` (str, default 'pending') — pending/matched/unmatched/ignored
- `raw_data` (JSONB, nullable) — 客户原始Excel行
- `created_at` (timestamp)

**`match_results`** — Match results linking our_receipts to customer_settlements.
- `id` (BigInt, PK, auto-increment)
- `customer_id` (int, NOT NULL, FK)
- `period` (str, 6 chars, NOT NULL, indexed)
- `batch_id` (str, nullable)
- `receipt_id` (BigInt, FK to our_receipts.id, nullable)
- `settlement_id` (BigInt, FK to customer_settlements.id, nullable)
- `match_type` (str, nullable) — 凭证精确匹配/型号+数量匹配/人工匹配/宽松匹配
- `confidence` (Decimal, nullable)
- `status` (str, default 'matched') — matched/unmatched/manual/ignored
- `source` (str, default 'auto') — auto/manual
- `diff_amount` (Decimal, nullable)
- `diff_quantity` (Decimal, nullable)
- `remark` (text, nullable)
- `operator_id` (int, nullable)
- `created_at` (timestamp)
- `updated_at` (timestamp)

**`correction_logs`** — Audit log for all manual operations.
- `id` (BigInt, PK, auto-increment)
- `customer_id` (int, nullable)
- `period` (str, nullable)
- `result_id` (BigInt, FK, nullable)
- `operation_type` (str, nullable) — manual_match/unmatch/ignore/add_note
- `before_data` (JSONB, nullable)
- `after_data` (JSONB, nullable)
- `reason` (text, nullable)
- `operator_id` (int, nullable)
- `created_at` (timestamp)

**`engine_configs`** — Engine-to-customer mapping.
- `id` (int, PK, auto-increment)
- `customer_id` (int, NOT NULL, unique, FK)
- `engine_name` (str, nullable)
- `engine_version` (str, nullable)
- `config_params` (JSONB, nullable)
- `is_active` (bool, default True)
- `created_at` (timestamp)
- `updated_at` (timestamp)

**`customers`** — Customer registry.
- `id` (int, PK, auto-increment)
- `name` (str, NOT NULL)
- `slug` (str, NOT NULL, unique)
- `description` (text, nullable)
- `is_active` (bool, default True)
- `created_at` (timestamp)

### 2. Match Engine Interface (prototype-conformed)

```python
# core interface from design phase — encoded as prototype
# Each engine is an independent plugin, inheriting from MatchEngine base class

@dataclass
class OurReceipt:
    id: int
    receipt_no: str
    model: str
    quantity: float
    amount: float
    unit_price: float
    receipt_date: str
    doc_type: str
    customer_name: str
    nc_order_no: str
    raw_data: dict

@dataclass
class CustomerSettlement:
    id: int
    match_key: str
    model: str
    quantity: float
    amount: float
    unit_price: float
    settlement_date: str
    raw_data: dict

@dataclass
class MatchPair:
    receipt_id: int
    settlement_id: int
    match_type: str
    confidence: float
    diff_amount: float
    diff_quantity: float
    detail: dict

@dataclass
class MatchResult:
    matched_pairs: list[MatchPair]
    unmatched_receipts: list[int]
    unmatched_settlements: list[int]
    excluded_settlements: list[int]
    engine_version: str
    summary: dict

class MatchEngine(ABC):
    @abstractmethod
    def parse_customer_data(self, raw_df) -> list[CustomerSettlement]: ...
    @abstractmethod
    def match(self, our_receipts: list[OurReceipt],
              settlements: list[CustomerSettlement]) -> MatchResult: ...
    def get_exclude_rules(self) -> dict: ...
```

### 3. Tmall Engine (Phase 1 scope)

The Tmall engine will be migrated from the existing `天猫优品-智屏-经销.py` script. Key behaviors preserved:

- **Match key generation**: For settlements, `业务主单据编码|含税金额|型号`; for receipts, `优先级订单号(审批单号>NC订单号>平台订单号)|签收金额|型号`
- **Two-round matching**: Round 1 exact match (order_id + amount + model), Round 2 loose match (order_id + model, amount >= settlement amount)
- **Model extraction**: From `后端商品名称` using regex `(\d+[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?(?:\s+[A-Z][a-z]+)?)`
- **SAP comparison**: Optional step after matching, comparing matched invoice items against SAP summary data

### 4. API Endpoints

```
POST   /api/upload/our-receipts        — Upload our-side receipt Excel
POST   /api/upload/settlements          — Upload customer settlement Excel
POST   /api/reconciliation/run          — Run matching for a customer+period
GET    /api/reconciliation/status       — Get reconciliation status
GET    /api/reconciliation/results      — Get match results (with filters)
POST   /api/corrections/manual-match    — Manually match two records
POST   /api/corrections/unmatch         — Unlink a matched pair
POST   /api/corrections/ignore          — Mark a record as ignored
POST   /api/corrections/note            — Add note to a record
GET    /api/reconciliation/export       — Export results as Excel
GET    /api/history?customer_id&period  — Get historical reconciliation summaries
```

### 5. Frontend Routes

```
/upload              — Upload page (upload both side's Excel files)
/workspace            — Online comparison workspace (main reconciliation UI)
/history              — Historical reconciliation records
/customers            — Customer management (admin)
```

### 6. Key Technical Decisions

- **File parsing**: Use `pandas.read_excel()` for both sides; our-side data has a fixed 98-column schema; customer-side data is engine-specific
- **Period derivation**: Period is derived from the receipt date of our-side records; the system prompts the user to confirm the period during upload
- **Customer auto-detection**: Our-side receipts are assigned to a customer based on the `结算客户名称` field matching against the `customers` table
- **Match engine isolation**: Each engine is a separate Python module under `app/engines/`; the Tmall engine is the only one in Phase 1
- **Synchronous matching**: For MVP, matching runs synchronously in the HTTP request; async/celery deferred to Phase 2/3
- **File storage**: Uploaded Excel files are stored in a local `uploads/` directory, organized by `{customer_id}/{period}/`

## Testing Decisions

### Test Seam: Engine Level (Highest Seam)

The `TmallEngine` is a pure function: given standardized input data, it produces deterministic match results. This is the highest-value test seam because it tests the core business logic without needing the database, HTTP layer, or filesystem.

**What makes a good test:**
- Test external behavior only: given a set of receipts and settlements, verify the match results (matched pairs, unmatched records, diff amounts)
- Do NOT test internal implementation details (e.g., which regex was used for model extraction, or the order of iteration)
- Use small, hand-crafted datasets (5-10 records each) where the expected match outcome is known
- Cover edge cases: exact match, loose match, amount mismatch, empty match_key, duplicate match_key, model extraction from product name

**Test modules:**
- `tests/engines/test_tmall_engine.py` — Unit tests for the Tmall engine
- `tests/engines/test_base.py` — Unit tests for the base engine interface

**Prior art:** The existing `天猫优品-智屏-经销.py` script has no tests, but the `reconcile()` function is already structured as a pure data transformation (DataFrame in → dict out), which maps directly to the engine's `match()` method.

**Example test scenarios:**

| Scenario | Receipts | Settlements | Expected |
|----------|----------|-------------|----------|
| Exact match | 1 record (PON123, 100元, 75V69H) | 1 record (PON123, 100元, 75V69H) | 1 matched pair, 0 unmatched |
| Loose match | 1 record (PON123, 100元, 75V69H) | 1 record (PON123, 90元, 75V69H) | 1 loose matched pair, 0 unmatched |
| Amount mismatch | 1 record (PON123, 100元, 75V69H) | 1 record (PON123, 80元, 75V69H) | 1 amount_diff record |
| No match | 1 record (PON123, 100元, 75V69H) | 1 record (PON456, 100元, 75V69H) | 1 unmatched receipt, 1 unmatched settlement |
| Empty match_key | 1 record (PON123, 100元, 75V69H) | 1 record (empty, 100元, 75V69H) | 1 unmatched settlement (reason: 订单号为空) |
| Model extraction | N/A | 1 settlement with product_name "TCL 75N9M" | model should be "75N9M" |

### Test Seam: Service Level (Medium Seam)

The `MatchService` orchestrates loading data from DB → calling engine → storing results.

**What makes a good test:**
- Test the integration between the database layer and the engine layer
- Use a test database (SQLite or test PostgreSQL) with known data
- Verify that match results are correctly stored in `match_results` table

**Test modules:**
- `tests/services/test_match_service.py` — Integration tests for the match service

### Test Seam: API Level (Lower Seam, Phase 2)

The FastAPI endpoints can be tested with `TestClient` for request/response cycle verification. This is a lower priority for the initial MVP commit.

## Out of Scope

- **PostgreSQL dependency in development**: MVP will use SQLite for local development to simplify setup; only production will use PostgreSQL. The ORM layer abstracts this difference.
- **Authentication and user management**: MVP assumes a single user (the financial operator). Multi-user support with role-based access control is deferred.
- **Async task queue (Celery)**: Matching runs synchronously in the HTTP request. Async processing is only needed when matching takes >30s or when multiple customers run concurrently.
- **Multiple customers in Phase 1**: Only the 天猫优品经销 customer is configured. The multi-customer architecture (engine registry, customer management UI) is built but not populated with multiple customers.
- **SAP comparison**: The existing script's SAP comparison feature (matching against SAP summary data) is preserved in the engine but not exposed in the Phase 1 UI. It's called automatically during export.
- **Heavy Excel formatting**: The output Excel uses basic formatting (column widths, headers). Advanced formatting (conditional coloring, merged cells) is deferred.
- **CI/CD pipeline**: No automated deployment pipeline in Phase 1. Deployment is manual via `uvicorn` or `gunicorn`.
- **Performance optimization for large datasets**: The existing script handles datasets of 1,000-10,000 rows. If performance becomes an issue with larger datasets, optimization is deferred to Phase 2.

## Further Notes

- **Data migration from existing scripts**: No data migration is needed — the existing scripts output Excel files, and the new system starts fresh. Users can import historical data by uploading the Excel files through the new UI.
- **Backward compatibility**: The existing script (`天猫优品-智屏-经销.py`) continues to work independently. The new platform does not replace it; it provides an alternative Web-based workflow.
- **Match rate expectations**: The MVP should achieve the same match rate as the existing script (>95%). Any divergence indicates a bug in the engine migration.
- **Language**: All code comments, variable names, and UI text are in Chinese, consistent with the existing codebase.
- **Error handling during upload**: The system validates that uploaded Excel files have the expected columns. If columns are missing, the user sees a clear error message listing which columns were expected vs. found.
- **SAP template generation**: The existing script's SAP预制模板 feature is preserved in the engine but exposed as a separate export action, not as part of the main reconciliation flow.