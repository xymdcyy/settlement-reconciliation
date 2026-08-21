# 结算对账平台设计方案

## 文档信息

| 项目 | 内容 |
|------|------|
| 文档版本 | v1.0 |
| 创建日期 | 2026-08-19 |
| 业务场景 | 我方出货记录（新方舟系统）与客户方结算单/入库记录的自动核对 |
| 数据来源 | 我方：新方舟系统导出签收明细；客户方：各客户提供的结算单/入库单 |

---

## 一、业务背景与目标

### 1.1 业务场景

我方（TCL）向多个渠道客户（重百、天猫优品等）供应产品。每月需要对账：

- **我方签收记录（新方舟系统）**：标准化的 98 列签收明细，涵盖所有渠道客户
- **客户方结算单/入库记录**：每个客户提供不同的格式，无统一标准

核对的本质是：**在我方标准化数据和客户方非标准化数据之间建立桥接，识别出双方一致的记录和存在差异的记录。**

### 1.2 项目目标

1. 搭建一个结算对账平台，将核对工作从人工 Excel 操作升级为 Web 在线比对
2. 支持多客户、多品类，每个客户的核对逻辑可独立扩展
3. 历史数据持久化，可追溯、可分析
4. 匹配率达到 95% 以上，剩余差异在 Web 工作台上人工处理

### 1.3 关键设计原则

| 原则 | 说明 |
|------|------|
| **我方数据标准化** | 新方舟系统签收数据是核心资产，98 列结构化字段，所有客户共用 |
| **客户方数据差异化** | 每个客户格式不同，用 JSONB 保留原始数据，标准化字段做桥接 |
| **引擎插件化** | 匹配逻辑每个客户独立实现，互不干扰，通过统一接口接入平台 |
| **人工兜底** | 自动匹配无法 100% 完美，Web 工作台提供手动纠正入口 |

---

## 二、数据模型设计

### 2.1 核心实体关系

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│    our_receipts   │     │customer_settlements│    │  match_results   │
│  (我方签收记录)    │────▶│  (客户方结算单)    │────▶│  (匹配结果)       │
│                   │     │                   │     │                  │
│  标准化 98 列      │     │ 标准化字段+JSONB   │     │ 关联双方记录      │
│  所有客户共用      │     │ 所有客户共用       │     │ 含匹配类型/置信度  │
└──────────────────┘     └──────────────────┘     └──────────────────┘
         │                       │                        │
         │                       │                        │
         ▼                       ▼                        ▼
┌───────────────────────────────────────────────────────────────────┐
│                         engine_configs                            │
│                    (引擎配置：客户→引擎版本映射)                     │
└───────────────────────────────────────────────────────────────────┘
```

### 2.2 我方签收记录表（our_receipts）

**来源**：新方舟系统导出，98 列签收明细

**设计思路**：所有客户共用一张表，只提取对账所需的核心字段，完整原始数据存入 JSONB。

```sql
CREATE TABLE our_receipts (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    receipt_no      VARCHAR(50) NOT NULL,    -- 新方舟销售单号 (唯一主键)
    customer_id     INT NOT NULL,            -- 关联客户
    period          VARCHAR(6) NOT NULL,     -- 对账期间 YYYYMM
    model           VARCHAR(100),            -- 产品型号 (如 75V69H)
    quantity        DECIMAL(12,2),           -- 签收数量
    amount          DECIMAL(14,2),           -- 签收金额
    unit_price      DECIMAL(14,4),           -- 单价
    receipt_date    DATE,                    -- 签收日期
    doc_type        VARCHAR(50),             -- 单据类型 (普通销售单/样机转销售单/退货单)
    customer_name   VARCHAR(200),            -- 结算客户名称
    nc_order_no     VARCHAR(100),            -- NC订单号 (PON开头)
    product_line    VARCHAR(50),             -- 产品线 (智屏/空调/冰洗/CIoT/雷鸟)
    raw_data        JSONB,                   -- 原始98列，保留全部信息
    batch_id        VARCHAR(50),             -- 导入批次
    created_at      TIMESTAMP DEFAULT NOW(),

    INDEX idx_customer_period (customer_id, period),
    INDEX idx_receipt_no (receipt_no),
    INDEX idx_model (model),
    INDEX idx_nc_order (nc_order_no)
);
```

**关键字段说明**：

| 字段 | 来源列 | 用途 |
|------|--------|------|
| receipt_no | 新方舟销售单号 | 唯一标识每一笔交易 |
| model | 产品型号 | 核心匹配字段之一 |
| quantity | 签收数量 | 核心匹配字段 |
| amount | 签收金额 | 金额核对 |
| unit_price | 单价 | 辅助匹配 |
| receipt_date | 签收日期/完成日期 | 时间窗口筛选 |
| doc_type | 单据类型 | 区分正常单/退货单/样机转销售 |
| customer_name | 结算客户名称 | 筛选客户归属 |
| nc_order_no | NC订单号 | 桥接匹配键（如天猫优品用 PON 号） |
| product_line | 产品线 | 品类筛选 |

### 2.3 客户方结算单表（customer_settlements）

**设计思路**：所有客户共用一张表，引擎从客户原始数据中提取标准化字段 + 匹配键。

```sql
CREATE TABLE customer_settlements (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,            -- 关联客户
    period          VARCHAR(6) NOT NULL,     -- 对账期间
    batch_id        VARCHAR(50),             -- 导入批次

    -- 标准化字段（引擎提取后填入）
    match_key       VARCHAR(200),            -- 引擎提取的匹配键 (如 PON26051857021704336)
    model           VARCHAR(100),            -- 引擎提取的型号 (如 75V69H)
    quantity        DECIMAL(12,2),           -- 数量
    amount          DECIMAL(14,2),           -- 金额
    unit_price      DECIMAL(14,4),           -- 单价
    settlement_date DATE,                    -- 业务日期

    -- 客户原始数据（保留一切）
    raw_data        JSONB,                   -- 客户原始Excel行 (列结构因客户而异)

    -- 附加信息
    doc_type        VARCHAR(50),             -- 客户单据类型 (如采购入库/退货/费用)
    status          VARCHAR(20) DEFAULT 'pending',  -- pending/matched/unmatched/ignored

    created_at      TIMESTAMP DEFAULT NOW(),

    INDEX idx_customer_period (customer_id, period),
    INDEX idx_match_key (match_key),
    INDEX idx_status (status)
);
```

**为什么 match_key 是核心字段？**

- 我方数据有 `receipt_no`、`nc_order_no`、`platform_order_no` 等多个订单号体系
- 客户方数据可能包含其中任意一个订单号的引用
- 引擎的任务就是**从客户数据中找到对应我方订单号的字段**，填入 `match_key`
- 匹配时优先用 `match_key` 精确匹配，失败再降级到型号+数量+金额组合匹配

**不同客户的 match_key 提取示例**：

| 客户 | 客户方字段 | match_key 提取逻辑 |
|------|-----------|-------------------|
| 天猫优品(经销) | 业务主单据编码 | 直接取 PON26051857021704336 |
| 天猫优品(寄售) | 交易主单/审批单号 | 优先取 NC 订单号，无则取审批单号 |
| 重百智屏 | 订单备注 | 正则提取 10 位采购凭证 (4702378037) |

### 2.4 匹配结果表（match_results）

```sql
CREATE TABLE match_results (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,
    period          VARCHAR(6) NOT NULL,
    batch_id        VARCHAR(50),

    -- 关联双方
    receipt_id      BIGINT,                  -- 我方记录ID (our_receipts.id)
    settlement_id   BIGINT,                  -- 客户方记录ID (customer_settlements.id)

    -- 匹配信息
    match_type      VARCHAR(50),             -- 凭证精确匹配/型号+数量匹配/人工匹配/聚合匹配
    confidence      DECIMAL(5,2),            -- 置信度 0.00-1.00
    status          VARCHAR(20) DEFAULT 'matched',  -- matched/unmatched/manual/ignored
    source          VARCHAR(20) DEFAULT 'auto',      -- auto/manual

    -- 差异信息
    diff_amount     DECIMAL(14,2),           -- 金额差异 (我方金额 - 客户金额)
    diff_quantity   DECIMAL(12,2),           -- 数量差异
    remark          TEXT,                    -- 备注

    -- 审计
    operator_id     INT,                     -- 人工操作人
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP,

    INDEX idx_customer_period (customer_id, period),
    INDEX idx_status (status),
    INDEX idx_receipt (receipt_id),
    INDEX idx_settlement (settlement_id)
);
```

**status 状态机**：

```
┌──────────┐    自动匹配    ┌──────────┐
│  pending  │──────────────▶│ matched  │
│  (导入待   │              │ (已匹配)  │
│   匹配)   │              └────┬─────┘
└────┬─────┘                   │
     │ 自动匹配失败             │ 人工确认
     ▼                         ▼
┌──────────┐              ┌──────────┐
│ unmatched │──▶人工纠正──▶│  manual  │
│ (未匹配)  │              │ (人工确认)│
└──────────┘              └──────────┘
     │
     │ 标记为不参与匹配
     ▼
┌──────────┐
│  ignored │
│ (已忽略)  │
└──────────┘
```

### 2.5 人工纠正日志表（correction_logs）

```sql
CREATE TABLE correction_logs (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT,
    period          VARCHAR(6),
    result_id       BIGINT,                  -- 关联 match_results
    operation_type  VARCHAR(50),             -- manual_match / unmatch / correct_remark / ignore
    before_data     JSONB,                   -- 操作前状态
    after_data      JSONB,                   -- 操作后状态
    reason          TEXT,                    -- 操作原因
    operator_id     INT,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

**所有人工操作记录留痕，支持审计追溯。**

### 2.6 引擎配置表（engine_configs）

```sql
CREATE TABLE engine_configs (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL UNIQUE,
    engine_name     VARCHAR(100),            -- 引擎类名 (如 TmallReceiptEngine)
    engine_version  VARCHAR(20),             -- 版本号 (如 v1.0.0)
    config_params   JSONB,                   -- 配置参数 (如匹配阈值、排除规则等)
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP
);
```

---

## 三、架构设计

### 3.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                             前端 (Web UI)                                │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 数据上传      │  │ 在线比对      │  │ 差异处理      │  │ 报表导出      │ │
│  │ (拖拽上传)    │  │ (左右对照)    │  │ (手动纠正)    │  │ (Excel下载)   │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        后端 API (FastAPI)                                │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │ 文件上传解析  │  │ 任务调度      │  │ 对账查询      │  │ 手动纠正      │ │
│  │ (Excel解析)  │  │ (运行匹配)    │  │ (历史追溯)    │  │ (日志记录)    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      匹配引擎层 (Plugin Engine)                          │
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    MatchEngine 接口 (抽象基类)                     │   │
│  │                                                                  │   │
│  │  + parse_customer_data(raw_data) → StandardizedCustomerData      │   │
│  │  + match(our_data, customer_data) → MatchResult[]                │   │
│  │  + get_exclude_rules() → Rule[]                                  │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                    ▲                    ▲                    ▲          │
│                    │                    │                    │          │
│  ┌─────────────────┴──┐  ┌─────────────┴──┐  ┌─────────────┴──┐       │
│  │ 重百引擎 (v2.0)    │  │ 天猫优品引擎    │  │ 引擎模板        │       │
│  │                    │  │ (v1.0)         │  │ (新客户起步)    │       │
│  │ 5层凭证匹配        │  │ PON号+金额+型号 │  │ 实现接口即可    │       │
│  │ 备注分类           │  │ 精准匹配→宽松   │  │                │       │
│  │ 聚合匹配           │  │ SAP比对        │  │                │       │
│  └────────────────────┘  └────────────────┘  └────────────────┘       │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        数据层 (PostgreSQL)                               │
│                                                                         │
│  our_receipts | customer_settlements | match_results | correction_logs  │
│  engine_configs | customers | users | periods                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 匹配引擎接口设计

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

# ============================================================
# 数据定义
# ============================================================

@dataclass
class OurReceipt:
    """我方标准化签收记录"""
    id: int
    receipt_no: str          # 新方舟销售单号
    model: str               # 产品型号
    quantity: float          # 签收数量
    amount: float            # 签收金额
    unit_price: float        # 单价
    receipt_date: str        # 签收日期
    doc_type: str            # 单据类型
    customer_name: str       # 结算客户名称
    nc_order_no: str         # NC订单号
    raw_data: dict           # 原始98列


@dataclass
class CustomerSettlement:
    """客户方结算单（引擎解析后）"""
    id: int
    match_key: str           # 引擎提取的匹配键
    model: str               # 引擎提取的型号
    quantity: float          # 数量
    amount: float            # 金额
    unit_price: float        # 单价
    settlement_date: str     # 业务日期
    raw_data: dict           # 客户原始数据


@dataclass
class MatchPair:
    """匹配对"""
    receipt_id: int          # 我方记录ID
    settlement_id: int       # 客户方记录ID
    match_type: str          # 匹配类型
    confidence: float        # 置信度
    diff_amount: float       # 金额差异
    diff_quantity: float     # 数量差异
    detail: dict             # 匹配详情


@dataclass
class MatchResult:
    """匹配结果"""
    matched_pairs: List[MatchPair]
    unmatched_receipts: List[int]      # 未匹配的我方记录ID
    unmatched_settlements: List[int]   # 未匹配的客户方记录ID
    excluded_settlements: List[int]    # 已排除的客户方记录ID
    engine_version: str
    summary: dict


# ============================================================
# 引擎接口
# ============================================================

class MatchEngine(ABC):
    """匹配引擎抽象基类"""

    @abstractmethod
    def parse_customer_data(self, raw_df) -> List[CustomerSettlement]:
        """
        解析客户方原始数据 → 标准化字段 + match_key

        这是每个客户引擎最核心的差异化逻辑：
        - 天猫优品: 从"业务主单据编码"提取 match_key，从"后端商品名称"提取型号
        - 重百: 从"订单备注"正则提取采购凭证做 match_key，映射列名
        """
        pass

    @abstractmethod
    def match(
        self,
        our_receipts: List[OurReceipt],
        customer_settlements: List[CustomerSettlement]
    ) -> MatchResult:
        """
        执行匹配逻辑

        返回匹配对 + 未匹配的双方记录
        """
        pass

    def get_exclude_rules(self) -> dict:
        """
        获取排除规则配置

        返回示例:
        {
            "exclude_doc_types": ["借机转销售单"],
            "exclude_remark_keywords": ["费用兑现", "价差"],
            "exclude_quantity_threshold": 100
        }
        """
        return {}

    @property
    def engine_name(self) -> str:
        return self.__class__.__name__

    @property
    def engine_version(self) -> str:
        return "v1.0.0"
```

### 3.3 引擎目录结构

```
app/engines/
├── __init__.py                  # 引擎注册表
├── base.py                     # 抽象基类 (MatchEngine)
├── tmall/                      # 天猫优品引擎
│   ├── __init__.py
│   ├── engine.py               # 天猫优品匹配引擎
│   └── config.py               # 天猫优品配置
├── chongbai/                   # 重百引擎
│   ├── __init__.py
│   ├── engine.py               # 重百匹配引擎
│   ├── classifiers.py          # 备注分类器 (从原reconcile_all.py抽取)
│   ├── extractors.py           # 凭证提取器 (从原reconcile_all.py抽取)
│   └── config.py               # 重百配置
└── template/                   # 新客户引擎模板
    ├── __init__.py
    └── engine.py                # 模板代码，新客户从此开始
```

### 3.4 引擎注册与加载

```python
# app/engines/__init__.py

import importlib
from typing import Dict
from .base import MatchEngine

# 引擎注册表：customer_id → (模块路径, 类名)
_ENGINE_REGISTRY: Dict[int, tuple] = {
    1: ("app.engines.chongbai.engine", "ChongbaiEngine"),
    2: ("app.engines.tmall.engine", "TmallEngine"),
    3: ("app.engines.tmall.engine", "TmallEngine"),  # 同一个引擎，不同客户ID
}

def get_engine(customer_id: int) -> MatchEngine:
    """根据客户ID获取引擎实例"""
    if customer_id not in _ENGINE_REGISTRY:
        raise ValueError(f"未找到客户 {customer_id} 的匹配引擎")

    module_path, class_name = _ENGINE_REGISTRY[customer_id]
    module = importlib.import_module(module_path)
    engine_class = getattr(module, class_name)
    return engine_class()

def register_engine(customer_id: int, module_path: str, class_name: str):
    """注册新引擎（新增客户时调用）"""
    _ENGINE_REGISTRY[customer_id] = (module_path, class_name)
```

---

## 四、交互流程设计

### 4.1 完整对账流程

```
┌─────────────────────────────────────────────────────────────────────────┐
│  对账流程（按月执行）                                                    │
│                                                                         │
│  Step 1: 导入我方签收记录                                                │
│  ├─ 上传新方舟系统导出的签收明细 Excel                                    │
│  ├─ 系统解析 98 列 → 标准化字段 + JSONB 原始数据存入 our_receipts          │
│  └─ 自动按结算客户名称分配到对应客户                                      │
│                                                                         │
│  Step 2: 导入客户方结算单                                                │
│  ├─ 上传客户提供的结算单 Excel                                            │
│  ├─ 系统根据客户 ID 调用对应的引擎解析数据                                 │
│  │   ├─ 引擎提取标准化字段 (match_key, model, qty, amount)               │
│  │   └─ 原始数据存入 customer_settlements.raw_data                       │
│  └─ 存入数据库                                                           │
│                                                                         │
│  Step 3: 执行自动匹配                                                    │
│  ├─ 调度引擎运行匹配                                                     │
│  ├─ 匹配结果存入 match_results                                           │
│  └─ 生成统计摘要（匹配率/金额差异/数量差异）                               │
│                                                                         │
│  Step 4: 在线比对与人工纠正                                              │
│  ├─ Web 工作台展示两侧数据                                               │
│  │   ├─ 左侧：我方签收记录（已匹配/未匹配）                                │
│  │   ├─ 右侧：客户方结算单（已匹配/未匹配/已排除）                          │
│  │   └─ 颜色标注匹配状态                                                 │
│  ├─ 人工操作：                                                           │
│  │   ├─ 拖拽匹配：将未匹配的双方记录手动配对                                │
│  │   ├─ 解除匹配：取消错误的自动匹配                                       │
│  │   ├─ 忽略：标记记录为不参与匹配（如费用单据）                            │
│  │   └─ 备注：添加说明文字                                                │
│  └─ 所有操作记录到 correction_logs                                       │
│                                                                         │
│  Step 5: 确认对账结果                                                    │
│  ├─ 统计最终匹配率                                                       │
│  ├─ 导出对账报告 Excel                                                   │
│  │   ├─ Sheet1: 汇总统计                                                 │
│  │   ├─ Sheet2: 差异明细（我方已签收客户未结算）                           │
│  │   ├─ Sheet3: 差异明细（客户已结算我方未签收）                           │
│  │   └─ Sheet4: 金额差异明细                                             │
│  └─ 提交确认，对账完成                                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.2 在线比对工作台 UI 设计

```
┌─────────────────────────────────────────────────────────────────────────┐
│  结算对账平台  │  重百  │  2026年4月  │  [导入数据]  [运行匹配]  [导出报表]  │
├─────────────────────────────────────────────────────────────────────────┤
│  匹配率: 95.1%  │  已匹配: 142  │  未匹配(我方): 8  │  未匹配(客户): 15  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌── 筛选 ──────────────────────────────────────────────────────────┐  │
│  │  [全部 ▼]  [已匹配]  [未匹配]  [已排除]  [搜索型号/单号...]       │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                         │
│  ┌── 左侧：我方签收记录 ────────────┬── 右侧：客户方结算单 ───────────┐  │
│  │                                  │                                  │  │
│  │  ✅ 新方舟S101...  75V69H  100台  │  ✅ PON260518...  75V69H  100台  │  │
│  │     ￥693,000                     │     ￥693,000                    │  │
│  │                                  │                                  │  │
│  │  ✅ 新方舟S101...  75V69H  200台  │  ✅ PON260518...  75V69H  200台  │  │
│  │     ￥1,386,000                   │     ￥1,386,000                  │  │
│  │                                  │                                  │  │
│  │  ❌ 新方舟S101...  85X11K  50台   │  ┌─ 未匹配记录 ───────────────┐ │  │
│  │     ￥425,000  [未匹配]           │  │ ▶ PON260518... 85X11K 50台  │ │  │
│  │                                  │  │   ￥425,000 [拖拽匹配]       │ │  │
│  │                                  │  └──────────────────────────────┘ │  │
│  │                                  │                                  │  │
│  │  ┌─ 已排除记录 ────────────────┐  │  ❌ PON260518...  55Z6H  80台   │  │
│  │  │ 无                           │  │     ￥351,200  [未匹配]         │  │
│  │  └──────────────────────────────┘  │                                  │  │
│  └──────────────────────────────────┴──────────────────────────────────┘  │
│                                                                         │
│  [点击未匹配行可进行手动操作]                                            │
│  ┌─ 操作面板 ─────────────────────────────────────────────────────────┐ │
│  │  我方: 新方舟S1011260104015270  85X11K  50台  ￥425,000            │ │
│  │  客户方: [选择匹配记录 ▼]  [搜索: ____________]                    │ │
│  │  [手动匹配]  [标记为已处理]  [忽略]  [备注: ____________________]  │ │
│  └───────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

**交互要点**：

1. **左右对照**：左侧为我方数据，右侧为客户方数据，匹配的行左右对齐
2. **颜色编码**：✅ 绿色=已匹配，❌ 红色=未匹配，⬜ 灰色=已排除
3. **拖拽操作**：从未匹配区域拖拽我方记录到客户方记录（或反向）产生手动匹配
4. **实时统计**：顶部状态栏随操作实时更新匹配率
5. **审计留痕**：每次手动操作都记录操作人、操作时间、操作前后状态

---

## 五、分阶段实施计划

### Phase 1：MVP — 天猫优品搬上 Web（2-3周）

**目标**：把天猫优品经销的核对功能从命令行搬到 Web 上，跑通全流程

**技术栈**：

| 层 | 技术选型 | 理由 |
|-----|---------|------|
| 后端 | FastAPI + SQLAlchemy | Python 生态，与现有代码兼容 |
| 数据库 | PostgreSQL | JSONB 支持，适合灵活数据结构 |
| 前端 | Vue 3 + Element Plus | 成熟的中后台方案 |
| 文件存储 | 本地文件系统 (后期可切 MinIO/S3) | MVP 阶段简化 |

**交付物**：

```
1. 数据导入
   ✅ 上传我方签收明细 Excel → 解析存入 our_receipts
   ✅ 上传天猫优品结算单 → 调用天猫引擎解析存入 customer_settlements
   ✅ 自动按客户名称分组

2. 自动匹配
   ✅ 集成天猫优品匹配引擎 (从现有脚本迁移)
   ✅ 匹配结果存入 match_results

3. 在线比对
   ✅ 左右对照表格展示匹配结果
   ✅ 颜色标注匹配状态
   ✅ 筛选（全部/已匹配/未匹配/已排除）

4. 手动纠正
   ✅ 手动匹配未匹配的记录
   ✅ 解除错误匹配
   ✅ 标记忽略
   ✅ 添加备注
   ✅ 操作日志

5. 报表导出
   ✅ 导出对账结果 Excel
   ✅ 汇总统计

6. 数据持久化
   ✅ 历史数据可查
   ✅ 按月筛选
```

**验证标准**：

- 天猫优品经销对账匹配率与现有脚本一致
- 全流程走通（上传→匹配→比对→纠正→导出）
- 手动操作记录可追溯

### Phase 2：多客户架构（2-3周）

**目标**：建立插件化引擎架构，接入重百引擎

**交付物**：

```
1. 引擎架构
   ✅ MatchEngine 抽象基类定义
   ✅ 引擎注册表
   ✅ 引擎目录结构
   ✅ 新客户引擎模板

2. 重百引擎迁移
   ✅ 从 reconcile_all.py 抽取重百引擎插件
   ✅ 备注分类器 → classifiers.py
   ✅ 凭证提取器 → extractors.py
   ✅ 5层匹配引擎 → engine.py

3. 客户管理
   ✅ 客户 CRUD 界面
   ✅ 客户与引擎绑定配置
   ✅ 多客户数据隔离

4. 验证
   ✅ 重百 4 个月匹配率回归验证
   ✅ 天猫优品不受影响
```

**关键风险**：重百引擎从单文件 2400 行抽取为插件时，需要确保不破坏原有逻辑。

### Phase 3：匹配率迭代（持续）

**目标**：持续提升各客户匹配率

**策略**：

```
1. 数据驱动
   - 统计未匹配记录的分布（按原因分类）
   - 分析未匹配的模式 → 改进匹配规则

2. 人工反哺
   - 手动纠正记录 → 可以分析出系统性匹配问题
   - 例如：如果某一类备注频繁被手动纠正，说明需要改进提取规则

3. 引擎版本管理
   - 每个引擎独立版本号
   - 允许回滚到旧版本
   - 支持并行运行新旧版本对比结果
```

---

## 六、目录结构

```
D:\结算对账中心\
├── main.py                        # 入口
├── pyproject.toml                 # 项目配置
├── .python-version                # Python 3.10
├── CLAUDE.md                      # 项目指南
├── README.md                      # 项目说明
│
├── app/                           # 后端应用
│   ├── __init__.py
│   ├── main.py                    # FastAPI 应用入口
│   ├── config.py                  # 配置文件
│   │
│   ├── routers/                   # API 路由
│   │   ├── __init__.py
│   │   ├── upload.py              # 文件上传
│   │   ├── reconciliation.py      # 对账操作
│   │   ├── results.py             # 匹配结果查询
│   │   └── corrections.py         # 手动纠正
│   │
│   ├── models/                    # SQLAlchemy 模型
│   │   ├── __init__.py
│   │   ├── our_receipt.py
│   │   ├── customer_settlement.py
│   │   ├── match_result.py
│   │   ├── correction_log.py
│   │   └── engine_config.py
│   │
│   ├── schemas/                   # Pydantic 数据模型
│   │   ├── __init__.py
│   │   ├── receipt.py
│   │   ├── settlement.py
│   │   └── match.py
│   │
│   ├── services/                  # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── upload_service.py      # 上传解析服务
│   │   ├── match_service.py       # 匹配调度服务
│   │   ├── report_service.py      # 报表生成服务
│   │   └── correction_service.py  # 人工纠正服务
│   │
│   ├── engines/                   # 匹配引擎（插件化）
│   │   ├── __init__.py            # 引擎注册表
│   │   ├── base.py                # MatchEngine 抽象基类
│   │   ├── tmall/                 # 天猫优品引擎
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   └── config.py
│   │   ├── chongbai/              # 重百引擎
│   │   │   ├── __init__.py
│   │   │   ├── engine.py
│   │   │   ├── classifiers.py
│   │   │   ├── extractors.py
│   │   │   └── config.py
│   │   └── template/              # 新客户引擎模板
│   │       ├── __init__.py
│   │       └── engine.py
│   │
│   └── utils/                     # 工具函数
│       ├── __init__.py
│       ├── excel_parser.py        # Excel 解析通用工具
│       └── date_utils.py          # 日期工具
│
├── frontend/                      # 前端（Vue 3）
│   ├── package.json
│   ├── src/
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── views/
│   │   │   ├── Upload.vue         # 数据上传页
│   │   │   ├── Workspace.vue      # 在线比对工作台
│   │   │   ├── History.vue        # 历史对账查询
│   │   │   └── Customers.vue      # 客户管理
│   │   ├── components/
│   │   │   ├── ComparisonTable.vue # 左右对照表格
│   │   │   ├── MatchStatus.vue     # 匹配状态标签
│   │   │   ├── CorrectionPanel.vue # 手动纠正面板
│   │   │   └── SummaryBar.vue      # 统计摘要栏
│   │   └── api/
│   │       └── index.js
│   └── vite.config.js
│
└── docs/                          # 文档
    ├── design.md                  # 本设计方案
    └── engine-guide.md            # 引擎开发指南
```

---

## 七、引擎开发指南（供后续技术人员参考）

### 7.1 新增客户流程

```python
# 1. 在 app/engines/ 下创建客户目录
#    app/engines/new_customer/
#    ├── __init__.py
#    └── engine.py

# 2. 继承 MatchEngine 实现接口
from app.engines.base import MatchEngine, CustomerSettlement, OurReceipt, MatchResult

class NewCustomerEngine(MatchEngine):
    """新客户匹配引擎"""

    engine_version = "v1.0.0"

    def parse_customer_data(self, raw_df) -> list[CustomerSettlement]:
        """
        解析客户方数据

        关键：找到能匹配我方NC订单号/新方舟单号的字段作为 match_key
        """
        settlements = []
        for _, row in raw_df.iterrows():
            settlements.append(CustomerSettlement(
                id=row.name,
                match_key=str(row.get("客户订单号", "")),     # 桥接字段
                model=self._extract_model(row.get("商品名称", "")),  # 提取型号
                quantity=float(row.get("数量", 0)),
                amount=float(row.get("金额", 0)),
                unit_price=float(row.get("单价", 0)),
                settlement_date=str(row.get("日期", "")),
                raw_data=row.to_dict(),
            ))
        return settlements

    def match(self, our_receipts, customer_settlements) -> MatchResult:
        """执行匹配逻辑"""
        # 实现匹配算法
        ...

    def _extract_model(self, product_name: str) -> str:
        """从商品名称中提取型号"""
        # 客户特有的型号提取逻辑
        ...

# 3. 在引擎注册表中注册
# app/engines/__init__.py 添加一行：
# register_engine(3, "app.engines.new_customer.engine", "NewCustomerEngine")

# 4. 在数据库 engine_configs 插入一条记录
# INSERT INTO engine_configs (customer_id, engine_name, engine_version, config_params)
# VALUES (3, "NewCustomerEngine", "v1.0.0", '{"threshold": 0.95}');
```

### 7.2 引擎开发原则

1. **不要修改平台底座代码**：引擎只放在 `app/engines/` 下，不修改 `services/` 和 `routers/`
2. **不要修改其他客户的引擎**：每个引擎独立，互不依赖
3. **保持向后兼容**：升级引擎版本时，确保旧版本的匹配结果可查询
4. **可测试**：每个引擎应提供测试数据，支持回归验证

---

## 八、技术选型理由

| 选型 | 方案 | 理由 |
|------|------|------|
| 后端框架 | FastAPI | Python 生态，异步支持，自动生成 OpenAPI 文档 |
| ORM | SQLAlchemy | 成熟稳定，支持 PostgreSQL JSONB |
| 数据库 | PostgreSQL | JSONB 支持灵活数据模型，适合客户方数据差异化 |
| 前端 | Vue 3 + Element Plus | 中后台场景成熟，组件丰富 |
| 文件存储 | 本地文件系统 → MinIO | MVP 简化，后期可扩展 |
| 匹配引擎 | 插件化 Python 类 | 与现有代码兼容，每个客户独立 |
| 任务调度 | 同步调用（MVP）→ Celery（后期） | MVP 简化，量大时异步化 |

---

## 九、附录：参考项目数据对照

### 我方签收记录核心字段（新方舟系统导出，98 列）

| 类别 | 字段 | 说明 | 匹配用途 |
|------|------|------|---------|
| 主键 | 新方舟销售单号 | S1010YYYYMMDDxxxxx | 唯一标识 |
| 产品 | 产品型号 | 如 75V69H | 核心匹配字段 |
| 产品 | 产品名称 | 如"电视-75-75V69H-枪色" | 辅助提取型号 |
| 产品 | 产品编码 | S11010101872 | 辅助匹配 |
| 数量 | 签收数量 | 数值 | 核心匹配字段 |
| 金额 | 签收金额 | 金额 | 核心匹配字段 |
| 金额 | 单价 | 单价 | 辅助匹配 |
| 日期 | 签收日期/完成日期 | 日期 | 时间窗口筛选 |
| 客户 | 结算客户名称 | 如"张家口天猫优品电子商务有限公司-经销" | 客户归属 |
| 客户 | 收货客户名称 | 同上或不同 | 辅助识别 |
| 订单 | 订单备注 | 文本 | 桥接字段（提取客户方订单号） |
| 订单 | 订单行备注 | 文本 | 同上 |
| 订单 | NC订单号 | PONxxxxxxxxxxxx | 重要桥接字段 |
| 订单 | 平台订单号 | 平台级订单号 | 桥接字段 |
| 订单 | 客户订单号 | 客户自定义 | 桥接字段 |
| 地址 | 到货地址 | 文本 | 辅助匹配 |
| 类型 | 单据类型 | 普通销售单/样机转销售单/退货单 | 区分方向 |
| 品类 | 产品线/产品大类/中类/小类 | 分类 | 品类筛选 |

### 客户方数据差异示例

| 维度 | 天猫优品(经销) | 重百智屏 |
|------|---------------|---------|
| 文件格式 | 32列Excel，标准结算单 | 台账Excel，80+工作表 |
| 桥接字段 | 业务主单据编码(PON号) | 订单备注中的采购凭证(10位数字) |
| 型号来源 | 后端商品名称提取 | 规格型号列直接有 |
| 匹配策略 | 单轮精确+宽松 | 5层+核对月优先 |
| 特殊处理 | 无（标准电商结算） | 样转销/厂送/费用兑现/补差价差等15种备注分类 |
| 排除规则 | 无 | 费用兑现/CB编号/残次退厂/厂送等 |

---

*文档结束*