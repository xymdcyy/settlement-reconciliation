# Pydantic 数据模型

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# 客户 (Customer)
# ============================================================

class CustomerCreate(BaseModel):
    name: str = Field(..., description="客户名称")
    slug: str = Field(..., description="客户标识（英文小写）")
    description: Optional[str] = None
    is_active: bool = True


class CustomerResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ============================================================
# 我方签收记录 (OurReceipt)
# ============================================================

class OurReceiptResponse(BaseModel):
    id: int
    receipt_no: str
    customer_id: int
    period: str
    model: Optional[str] = None
    quantity: Optional[float] = None
    amount: Optional[float] = None
    unit_price: Optional[float] = None
    receipt_date: Optional[str] = None
    doc_type: Optional[str] = None
    customer_name: Optional[str] = None
    nc_order_no: Optional[str] = None
    product_line: Optional[str] = None
    batch_id: Optional[str] = None
    raw_data: Optional[Any] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OurReceiptUploadResponse(BaseModel):
    total: int = 0
    assigned_to_customers: dict[str, int] = {}
    unassigned: int = 0
    message: str = ""


# ============================================================
# 客户方结算单 (CustomerSettlement)
# ============================================================

class CustomerSettlementResponse(BaseModel):
    id: int
    customer_id: int
    period: str
    batch_id: Optional[str] = None
    match_key: Optional[str] = None
    model: Optional[str] = None
    quantity: Optional[float] = None
    amount: Optional[float] = None
    unit_price: Optional[float] = None
    settlement_date: Optional[str] = None
    doc_type: Optional[str] = None
    status: str
    raw_data: Optional[Any] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SettlementUploadResponse(BaseModel):
    total: int = 0
    parsed: int = 0
    with_match_key: int = 0
    message: str = ""


# ============================================================
# 匹配结果 (MatchResult)
# ============================================================

class MatchResultResponse(BaseModel):
    id: int
    customer_id: int
    period: str
    batch_id: Optional[str] = None
    receipt_id: Optional[int] = None
    settlement_id: Optional[int] = None
    match_type: Optional[str] = None
    confidence: Optional[float] = None
    status: str
    source: str
    diff_amount: Optional[float] = None
    diff_quantity: Optional[float] = None
    remark: Optional[str] = None
    operator_id: Optional[int] = None
    receipt: Optional[OurReceiptResponse] = None
    settlement: Optional[CustomerSettlementResponse] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MatchSummaryResponse(BaseModel):
    total_receipts: int = 0
    total_settlements: int = 0
    matched_count: int = 0
    unmatched_receipts: int = 0
    unmatched_settlements: int = 0
    manual_count: int = 0
    ignored_count: int = 0
    match_rate: float = 0.0
    total_amount_diff: float = 0.0


class ReconciliationRunResponse(BaseModel):
    status: str = "completed"
    summary: MatchSummaryResponse
    message: str = ""


# ============================================================
# 手动纠正 (Correction)
# ============================================================

class RunReconciliationRequest(BaseModel):
    customer_id: int = Field(..., description="客户 ID")
    period: str = Field(..., description="对账期间 YYYYMM")


class ManualMatchRequest(BaseModel):
    customer_id: int
    period: str
    receipt_id: int
    settlement_id: int
    operator_id: Optional[int] = None
    reason: Optional[str] = None


class UnmatchRequest(BaseModel):
    customer_id: int
    period: str
    result_id: int
    operator_id: Optional[int] = None
    reason: Optional[str] = None


class IgnoreRequest(BaseModel):
    customer_id: int
    period: str
    result_id: int
    reason: str = Field(..., description="忽略原因")
    operator_id: Optional[int] = None


class NoteRequest(BaseModel):
    customer_id: int
    period: str
    result_id: int
    remark: str
    operator_id: Optional[int] = None


class CorrectionResponse(BaseModel):
    success: bool = True
    message: str = ""
    result_id: Optional[int] = None


# ============================================================
# 历史查询
# ============================================================

class HistoryItem(BaseModel):
    period: str
    customer_id: int
    customer_name: str
    matched_count: int
    unmatched_receipts: int
    unmatched_settlements: int
    match_rate: float
    total_amount_diff: float
    run_at: Optional[datetime] = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem] = []


# ============================================================
# 通用
# ============================================================

class UploadResponse(BaseModel):
    success: bool = True
    message: str = ""
    data: Optional[Any] = None