# 台账 API

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ErrorResponse,
    ReceiptCreate,
    ReceiptListResponse,
    ReceiptResponse,
    ReceiptSplit,
    ReceiptUpdate,
    SuccessResponse,
)
from app.services.receipt_service import ReceiptService
from app.utils.excel_response import excel_response

router = APIRouter(prefix="/api/receipts", tags=["receipts"])


@router.post("/import", response_model=SuccessResponse)
def import_receipts(
    customer_id: int,
    period: str,
    receipts: list[ReceiptCreate],
    db: Session = Depends(get_db),
):
    """导入台账（层累追加）"""
    try:
        result = ReceiptService.import_receipts(customer_id, period, receipts, db)
        return SuccessResponse(**result)
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))


@router.get("", response_model=ReceiptListResponse)
def get_receipts(
    customer_id: int = Query(..., description="客户ID"),
    period: Optional[str] = Query(None, description="对账期间 YYYYMM"),
    billing_status: Optional[str] = Query(None, description="开票状态"),
    diff_type: Optional[str] = Query(None, description="差异类型"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询台账（筛选/分页）"""
    result = ReceiptService.get_receipts(
        customer_id=customer_id,
        db=db,
        period=period,
        billing_status=billing_status,
        diff_type=diff_type,
        search=search,
        page=page,
        page_size=page_size,
    )
    return result


@router.put("/{receipt_id}", response_model=ReceiptResponse)
def update_receipt(
    receipt_id: int,
    update: ReceiptUpdate,
    db: Session = Depends(get_db),
):
    """更新台账（编辑开票状态）"""
    receipt = ReceiptService.update_receipt(receipt_id, update, db)
    return receipt


@router.post("/{receipt_id}/split", response_model=SuccessResponse)
def split_receipt(
    receipt_id: int,
    split: ReceiptSplit,
    db: Session = Depends(get_db),
):
    """拆分行"""
    try:
        result = ReceiptService.split_receipt(receipt_id, split, db)
        return SuccessResponse(**result)
    except ValueError as e:
        return ErrorResponse(status="error", message=str(e))


@router.get("/export")
def export_receipts(
    customer_id: int = Query(..., description="客户ID"),
    period: Optional[str] = Query(None, description="对账期间 YYYYMM"),
    billing_status: Optional[str] = Query(None, description="开票状态"),
    search: Optional[str] = Query(None, description="搜索关键词"),
    db: Session = Depends(get_db),
):
    """导出台账为 Excel"""
    output_bytes = ReceiptService.export_receipts(
        customer_id=customer_id,
        period=period,
        db=db,
        billing_status=billing_status,
        search=search,
    )

    filename = f"台账_{customer_id}_{period or '全部'}"
    return excel_response(output_bytes, filename)


@router.get("/pending-pool")
def get_pending_pool(
    customer_id: int = Query(..., description="客户ID"),
    db: Session = Depends(get_db),
):
    """获取未决差异池"""
    items = ReceiptService.get_pending_pool(customer_id, db)
    return {"items": items}


@router.put("/pending-pool/{receipt_id}/resolve", response_model=ReceiptResponse)
def resolve_pending(
    receipt_id: int,
    resolved_period: str,
    db: Session = Depends(get_db),
):
    """标记未决差异为已解决"""
    receipt = ReceiptService.resolve_pending(receipt_id, resolved_period, db)
    return receipt
