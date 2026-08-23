# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**结算对账中心 (Settlement Reconciliation Center)** — v2.0 架构重构版

基于台账中心的多客户结算对账管理平台。核心思想：**以台账为中心，三张桌子（台账/核对/开票）共享同一批数据**。

- **GitHub**: https://github.com/xymdcyy/settlement-reconciliation
- **Python 3.10+** (see `.python-version`)
- **架构文档**: `docs/architecture/`（必读）

## Commands

```bash
# 后端
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# 前端
cd frontend && npm run dev

# 测试
.venv/Scripts/python.exe -m pytest

# 推送 GitHub
.venv/Scripts/python.exe scripts/gh-push.py
```

> **本地环境须知（重要）**
> - **不要用裸 `python`**：本机 `python` 指向 Windows 商店占位 stub（无输出、退出码 49，解释器根本没运行）。一律用 uv 创建的 `.venv/Scripts/python.exe` 或 `uv run`。
> - **推送 GitHub 用 `gh-push.py`**：`git push`（github.com:443）常被防火墙拦截（而 api.github.com 可达）。改用 `.venv/Scripts/python.exe scripts/gh-push.py`——它经 GitHub API 精确复现本地 commit SHA、快进推送并同步本地跟踪 ref，保证本地/远端 SHA 一致、不产生分叉；对中文文件名安全。**勿用** `scripts/` 下的旧推送脚本（有中文路径 bug，已删除）。

## Architecture v2.0

### 核心概念

**以台账为中心**：
- 200 客户共用：台账 + 开票
- 50-80 客户额外：核对（引擎插件化）
- 所有功能都是台账上的视图和动作

**三张桌子**：
1. **台账桌**（LedgerTab）：200 客户的签收-开票台账管理
2. **核对桌**（ReconciliationTab）：50-80 客户的自动匹配 + 人工核对
3. **开票桌**（BillingTab）：可开票清单、生成清单、导入已开票

**工具**：
- **未决池**（PendingPoolTab）：跨月差异的滚动管理
- **红冲工具**（RedFlushTab）：自动查找蓝票、生成确认单

### 数据模型核心

```
receipts（台账行）⭐
  ├─ 系统字段（94列提取物）
  ├─ 开票状态（billing_status/invoice_no/invoice_date/remark）
  ├─ 扩展字段（extra_fields JSONB，客户级配置）
  ├─ 差异判断（diff_type/diff_note/resolved_period）
  └─ 父子行（split_parent_id，支持拆分）

customer_statements（客户对账单）→ 核对桌专用
match_results（匹配结果）→ 核对桌专用
invoices（发票记录）
adjustments（调账/红冲记录）
users / user_customer_assignments（用户和归属）
```

### 关键设计决策

1. **核心集 + 可选扩展列**：核心 5 列强制，扩展列审批制
2. **父子行模型**：拆分后父行标记为已拆分，子行继承父行字段
3. **财务-客户归属**：每个客户有一个财务负责，权限按归属控制
4. **引擎插件化**：保留现有架构（天猫/重百引擎）

详见 [docs/architecture/05-decisions.md](docs/architecture/05-decisions.md)

## Project Structure

```
D:\结算对账中心\
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── config.py                  # 配置
│   ├── database.py                # 数据库连接
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py              # SQLAlchemy 模型（Receipt/Invoice/Adjustment/User...）
│   │
│   ├── schemas/
│   │   └── __init__.py            # Pydantic 模型
│   │
│   ├── routers/
│   │   ├── receipts.py            # 台账 API
│   │   ├── reconciliation.py      # 核对 API（保留）
│   │   ├── corrections.py         # 人工纠正 API（保留）
│   │   ├── billing.py             # 开票 API
│   │   ├── red_flush.py           # 红冲 API
│   │   ├── pending_pool.py        # 未决池 API
│   │   ├── customers.py           # 客户管理 API
│   │   └── migration.py           # 迁移 API
│   │
│   ├── services/
│   │   ├── receipt_service.py     # 台账服务
│   │   ├── match_service.py       # 核对服务（保留）
│   │   ├── correction_service.py  # 人工纠正服务（保留）
│   │   ├── billing_service.py     # 开票服务
│   │   ├── red_flush_service.py   # 红冲服务
│   │   ├── pending_pool_service.py # 未决池服务
│   │   ├── migration_service.py   # 迁移服务
│   │   └── export_service.py      # 报表导出服务（保留）
│   │
│   ├── engines/                   # 匹配引擎（插件化，100% 保留）
│   │   ├── base.py                # MatchEngine 接口
│   │   ├── tmall/                 # 天猫引擎
│   │   ├── chongbai/              # 重百引擎
│   │   └── template/              # 模板引擎
│   │
│   └── utils/
│       ├── excel_parser.py        # Excel 解析工具
│       └── date_utils.py          # 日期工具
│
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── HomePage.vue           # 工作台首页
│       │   ├── CustomerDetailPage.vue # 客户详情页（5个Tab）
│       │   ├── SystemAdminPage.vue    # 系统管理
│       │   └── MigrationPage.vue      # 数据迁移
│       ├── components/
│       │   └── tabs/
│       │       ├── LedgerTab.vue          # 台账桌
│       │       ├── ReconciliationTab.vue  # 核对桌
│       │       ├── BillingTab.vue         # 开票桌
│       │       ├── PendingPoolTab.vue     # 未决池
│       │       └── RedFlushTab.vue        # 红冲工具
│       ├── router/
│       └── api/
│
├── scripts/
│   ├── migration/                 # 数据迁移工具
│   └── gh-push.py                 # Git 推送工具
│
├── tests/
│   ├── engines/                   # 引擎测试（保留）
│   └── ...
│
└── docs/
    ├── architecture/              # v2.0 架构文档 ⭐
    │   ├── README.md
    │   ├── 01-business-model.md
    │   ├── 02-data-model.md
    │   ├── 03-system-design.md
    │   ├── 04-migration-plan.md
    │   └── 05-decisions.md
    └── archive/                   # v1.0 归档文档
        ├── design-v1.md
        ├── spec-phase1.md
        └── phase1-mvp/
```

## Conventions

- **中文优先**：所有变量名、注释、输出、UI 文本都是中文
- **列名权威**：Excel 列名不修改
- **引擎独立**：每个客户的引擎独立，不修改其他客户的引擎
- **扩展列审批**：客户扩展列需要主管审批，不能随便添加
- **父子行模型**：拆分后父行标记为已拆分，子行继承父行字段

## Key Documents

| Document | Location | Purpose |
|----------|----------|---------|
| 架构总览 | `docs/architecture/README.md` | v2.0 架构导航 |
| 业务模型 | `docs/architecture/01-business-model.md` | 业务流程、角色、痛点 |
| 数据模型 | `docs/architecture/02-data-model.md` | 表结构、字段、关系 |
| 系统设计 | `docs/architecture/03-system-design.md` | 功能模块、UI、API |
| 迁移计划 | `docs/architecture/04-migration-plan.md` | 标准、工具、试点、推广 |
| 关键决策 | `docs/architecture/05-decisions.md` | 为什么这么设计 |
| v1.0 归档 | `docs/archive/` | 历史文档 |

## Migration from v1.0

### 保留

- `app/engines/` 整个目录（100% 保留）
- `customer_statements` / `match_results` / `correction_logs` 表
- 匹配引擎的插件化架构

### 改造

- `our_receipts` → `receipts`（加开票状态、扩展字段、父子行）
- 前端：从"上传→匹配"流程改为"台账常驻，核对是台账上的动作"

### 新建

- 工作台（首页）
- 台账桌、开票桌、未决池、红冲工具
- 系统管理（客户/扩展列/引擎/用户）
- 迁移工具（Excel解析/清洗/验证）

### 废弃

- `upload.py` / `upload_service.py` / `UploadPage.vue`（被 receipts 替代）
- `HistoryPage.vue`（被 LedgerTab 的筛选替代）
- 旧的推送脚本（api_push.py 等）

## Development Workflow

### 添加新客户

1. 系统管理页面新建客户
2. 如果有对账单，配置引擎
3. 运行迁移工具导入历史台账
4. 分配财务专员

### 添加新引擎

1. 在 `app/engines/` 下创建客户目录
2. 继承 `MatchEngine` 实现接口
3. 在 `app/engines/__init__.py` 注册
4. 在系统管理页面绑定客户

### 添加扩展列

1. 客户申请扩展列
2. 主管审批
3. 在系统管理页面配置 `customers.extra_fields_config`
4. 前端自动渲染扩展列

## Testing

```bash
# 运行所有测试
.venv/Scripts/python.exe -m pytest

# 运行引擎测试
.venv/Scripts/python.exe -m pytest tests/engines/ -v

# 运行特定测试
.venv/Scripts/python.exe -m pytest tests/test_receipt_service.py -v
```

## Deployment

**开发环境**：SQLite（无需安装数据库）

**生产环境**：PostgreSQL（通过环境变量 `DATABASE_URL` 切换）

```bash
# 生产环境
export DATABASE_URL="postgresql://user:password@host:5432/dbname"
.venv/Scripts/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Notes

- 本项目处于 **v2.0 架构重构阶段**，部分功能尚未完全实现
- 试点客户：潍坊百货、全福元、河北劲草、天猫优品
- 全量推广计划：6-12 个月，分 2 批次（有对账单 → 无对账单）

---

*最后更新：2026-08-21*
*架构版本：v2.0*
