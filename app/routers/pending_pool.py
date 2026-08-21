# 未决池 API

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ErrorResponse, ResolvePendingRequest, SuccessResponse
from app.services.pending_pool_service import PendingPoolService

router = APIRouter(prefix="/api/pending-pool", tags=["pending-pool"])


@router.get("")
def get_pending_pool(
    customer_id: int = Query(..., description="客户ID"),
    db: Session = Depends(get_db),
):
    """获取未决差异池"""
    items = PendingPoolService.get_pending_pool(customer_id, db)
    return {"items": items, "total": len(items)}


@router.put("/{receipt_id}/resolve", response_model=SuccessResponse)
def resolve_pending(
    receipt_id: int,
    request: ResolvePendingRequest,
    db: Session = Depends(get_db),
):
    """标记未决差异为已解决"""
    try:
        receipt = PendingPoolService.resolve_pending(receipt_id, request.resolved_period, db)
        return SuccessResponse(message=f"已标记为解决，期间: {request.resolved_period}")
    except ValueError as e:
        return ErrorResponse(status="error", message=str(e))


@router.put("/{receipt_id}/to-real", response_model=SuccessResponse)
def to_real_diff(
    receipt_id: int,
    diff_note: str = None,
    db: Session = Depends(get_db),
):
    """转为真差异（需要调账）"""
    try:
        receipt = PendingPoolService.to_real_diff(receipt_id, diff_note, db)
        return SuccessResponse(message="已转为真差异")
    except ValueError as e:
        return ErrorResponse(status="error", message=str(e))
