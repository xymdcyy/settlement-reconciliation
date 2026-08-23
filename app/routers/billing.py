# 开票 API

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ErrorResponse,
    GenerateBillingRequest,
    ImportBilledRequest,
    SuccessResponse,
)
from app.services.billing_service import BillingService

router = APIRouter(prefix="/api/billing", tags=["billing"])


@router.get("/pending")
def get_pending_billing(
    customer_id: int = Query(..., description="客户ID"),
    period: Optional[str] = Query(None, description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """获取可开票清单"""
    items = BillingService.get_pending_billing(customer_id, db, period)
    return {"items": items, "total": len(items)}


@router.post("/generate", response_model=SuccessResponse)
def generate_billing_list(
    request: GenerateBillingRequest,
    db: Session = Depends(get_db),
):
    """生成开票清单（导出 Excel）"""
    try:
        output = BillingService.generate_billing_list(request.receipt_ids, db)
        # TODO: 实现 Excel 导出后，返回文件下载
        return SuccessResponse(message="生成功能待实现")
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))


@router.post("/import-billed", response_model=SuccessResponse)
def import_billed_list(
    request: ImportBilledRequest,
    db: Session = Depends(get_db),
):
    """导入已开票清单（自动匹配回填发票号/日期）"""
    try:
        result = BillingService.import_billed_list(request.items, db)
        return SuccessResponse(**result)
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))


@router.get("/invoices")
def get_invoices(
    customer_id: int = Query(..., description="客户ID"),
    period: Optional[str] = Query(None, description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """查询发票记录"""
    items = BillingService.get_invoices(customer_id, db, period)
    return {"items": items, "total": len(items)}
