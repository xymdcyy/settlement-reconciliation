# 红冲 API

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ErrorResponse, ReturnReceiptIdsRequest, SuccessResponse
from app.services.red_flush_service import RedFlushService
from app.utils.excel_response import excel_response

router = APIRouter(prefix="/api/red-flush", tags=["red-flush"])


@router.get("/returns")
def get_return_receipts(
    customer_id: int = Query(..., description="客户ID"),
    period: Optional[str] = Query(None, description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """获取本月退货记录"""
    items = RedFlushService.get_return_receipts(customer_id, db, period)
    return {"items": items, "total": len(items)}


@router.post("/find-blue/{return_receipt_id}")
def find_blue_invoice(
    return_receipt_id: int,
    db: Session = Depends(get_db),
):
    """自动查找蓝票"""
    try:
        blue_receipt = RedFlushService.find_blue_invoice(return_receipt_id, db)
        if blue_receipt:
            return {
                "status": "success",
                "blue_invoice_no": blue_receipt.invoice_no,
                "blue_invoice_date": blue_receipt.invoice_date,
                "blue_receipt_id": blue_receipt.id,
            }
        else:
            return {
                "status": "success",
                "blue_invoice_no": None,
                "message": "未找到匹配的蓝票",
            }
    except ValueError as e:
        return ErrorResponse(status="error", message=str(e))


@router.post("/batch-find-blue")
def batch_find_blue_invoices(
    request: ReturnReceiptIdsRequest,
    db: Session = Depends(get_db),
):
    """批量查找蓝票"""
    result = RedFlushService.batch_find_blue_invoices(request.return_receipt_ids, db)
    return result


@router.post("/generate")
def generate_confirmation(
    request: ReturnReceiptIdsRequest,
    db: Session = Depends(get_db),
):
    """生成确认单（导出 Excel 给税务）"""
    try:
        output_bytes = RedFlushService.generate_confirmation(request.return_receipt_ids, db)
        return excel_response(output_bytes, f"红冲确认单_{len(request.return_receipt_ids)}条")
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))


@router.put("/record-red-no/{return_receipt_id}")
def record_red_notice(
    return_receipt_id: int,
    red_notice_no: str,
    db: Session = Depends(get_db),
):
    """回录红通号"""
    try:
        receipt = RedFlushService.record_red_notice(return_receipt_id, red_notice_no, db)
        return {"status": "success", "receipt_id": receipt.id}
    except ValueError as e:
        return ErrorResponse(status="error", message=str(e))
