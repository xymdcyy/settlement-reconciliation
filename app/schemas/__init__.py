# Pydantic 数据模型 v2.0

from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ========== 用户相关 ==========

class UserBase(BaseModel):
    username: str
    real_name: Optional[str] = None
    role: str = "staff"


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 客户相关 ==========

class ExtraFieldConfig(BaseModel):
    """扩展列配置"""
    name: str
    type: str  # string/number/date
    required: bool = False
    comment: Optional[str] = None


class CustomerBase(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    has_statement: bool = False
    engine_name: Optional[str] = None


class CustomerCreate(CustomerBase):
    extra_fields_config: Optional[list[ExtraFieldConfig]] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    has_statement: Optional[bool] = None
    engine_name: Optional[str] = None
    extra_fields_config: Optional[list[ExtraFieldConfig]] = None
    is_active: Optional[bool] = None


class CustomerResponse(CustomerBase):
    id: int
    extra_fields_config: Optional[list[dict]] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ========== 台账相关 ==========

class ReceiptBase(BaseModel):
    """台账基础字段"""
    receipt_no: str
    model: Optional[str] = None
    quantity: Optional[float] = None
    amount: Optional[float] = None
    unit_price: Optional[float] = None
    receipt_date: Optional[str] = None
    doc_type: Optional[str] = None
    customer_name: Optional[str] = None
    nc_order_no: Optional[str] = None
    product_line: Optional[str] = None


class ReceiptCreate(ReceiptBase):
    """创建台账（导入时）"""
    customer_id: int
    period: str
    batch_id: Optional[str] = None
    raw_data: Optional[dict] = None


class ReceiptUpdate(BaseModel):
    """更新台账（编辑开票状态）"""
    billing_status: Optional[str] = None
    invoice_no: Optional[str] = None
    invoice_date: Optional[str] = None
    remark: Optional[str] = None
    extra_fields: Optional[dict] = None
    diff_type: Optional[str] = None
    diff_note: Optional[str] = None


class ReceiptSplit(BaseModel):
    """拆分行"""
    quantities: list[float] = Field(..., description="拆分后的数量列表，如 [3, 2]")
    split_note: Optional[str] = None


class ReceiptResponse(ReceiptBase):
    """台账响应"""
    id: int
    customer_id: int
    period: str
    batch_id: Optional[str]

    # 开票状态
    billing_status: str
    invoice_no: Optional[str]
    invoice_date: Optional[str]
    remark: Optional[str]

    # 拆分
    split_parent_id: Optional[int]
    split_note: Optional[str]

    # 扩展字段
    extra_fields: Optional[dict]

    # 差异
    diff_type: Optional[str]
    diff_note: Optional[str]
    resolved_period: Optional[str]

    # 审计
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ReceiptListResponse(BaseModel):
    """台账列表响应"""
    items: list[ReceiptResponse]
    total: int
    page: int
    page_size: int


# ========== 对账相关 ==========

class RunReconciliationRequest(BaseModel):
    customer_id: int
    period: str


class MatchSummaryResponse(BaseModel):
    """匹配摘要"""
    total_receipts: int = 0
    total_statements: int = 0
    matched: int = 0
    unmatched_receipts: int = 0
    unmatched_statements: int = 0
    match_rate: float = 0.0


class ReconciliationRunResponse(BaseModel):
    status: str
    summary: MatchSummaryResponse
    message: str


class MarkDiffRequest(BaseModel):
    """标记差异"""
    receipt_id: int
    diff_type: str  # time_diff/price_diff/qty_diff/...
    diff_note: Optional[str] = None


class HistoryItem(BaseModel):
    """历史对账项"""
    customer_id: int
    customer_name: str
    period: str
    total_receipts: int
    matched: int
    match_rate: float


class HistoryResponse(BaseModel):
    """历史对账响应"""
    items: list[HistoryItem]


# ========== 开票相关 ==========

class BillingPendingItem(BaseModel):
    """可开票项"""
    receipt_id: int
    receipt_no: str
    model: str
    quantity: float
    amount: float
    customer_name: str


class GenerateBillingRequest(BaseModel):
    """生成开票清单"""
    receipt_ids: list[int]


class ImportBilledRequest(BaseModel):
    """导入已开票清单"""
    items: list[dict]  # [{receipt_no, invoice_no, invoice_date, amount, quantity}]


# ========== 红冲相关 ==========

class ReturnItem(BaseModel):
    """退货记录"""
    receipt_id: int
    receipt_no: str
    model: str
    quantity: float
    amount: float
    unit_price: float


class BlueInvoiceMatch(BaseModel):
    """蓝票匹配结果"""
    return_receipt_id: int
    blue_invoice_no: Optional[str]
    blue_invoice_date: Optional[str]
    blue_receipt_id: Optional[int]


# ========== 未决池相关 ==========

class PendingPoolItem(BaseModel):
    """未决差异项"""
    receipt_id: int
    receipt_no: str
    model: str
    quantity: float
    amount: float
    diff_type: str
    diff_note: Optional[str]
    pending_months: int  # 挂账月数


class ResolvePendingRequest(BaseModel):
    """解决未决差异"""
    receipt_id: int
    resolved_period: str


# ========== 人工纠正相关（保留 v1.0）==========

class ManualMatchRequest(BaseModel):
    """人工匹配请求"""
    receipt_id: int
    settlement_id: int
    remark: Optional[str] = None


class UnmatchRequest(BaseModel):
    """解除匹配请求"""
    result_id: int
    reason: Optional[str] = None


class IgnoreRequest(BaseModel):
    """忽略请求"""
    settlement_id: int
    reason: Optional[str] = None


class NoteRequest(BaseModel):
    """备注请求"""
    result_id: int
    note: str


class CorrectionResponse(BaseModel):
    """人工纠正响应"""
    status: str
    message: str


# ========== 迁移相关 ==========

class MigrationUploadResponse(BaseModel):
    """迁移上传响应"""
    file_path: str
    total_rows: int
    message: str


class MigrationValidateResponse(BaseModel):
    """迁移验证响应"""
    is_valid: bool
    total_rows: int
    imported_rows: int
    excel_total_amount: float
    imported_total_amount: float
    warnings: list[str]
    errors: list[str]


class MigrationImportRequest(BaseModel):
    """迁移导入请求"""
    customer_id: int
    file_path: str
    period: str
    rules_file: Optional[str] = None  # 清洗规则文件路径


# ========== 通用响应 ==========

class SuccessResponse(BaseModel):
    """成功响应"""
    status: str = "success"
    message: str


class ErrorResponse(BaseModel):
    """错误响应"""
    status: str = "error"
    message: str
    detail: Optional[str] = None
