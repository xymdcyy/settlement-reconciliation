# 对账运行 + 结果查询 API

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    MatchSummaryResponse,
    ReconciliationRunResponse,
)
from app.services.match_service import MatchService

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


@router.post("/run", response_model=ReconciliationRunResponse)
def run_reconciliation(
    customer_id: int = Query(..., description="客户 ID"),
    period: str = Query(..., description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """运行自动匹配"""
    result = MatchService.run(customer_id, period, db)
    return ReconciliationRunResponse(
        status=result["status"],
        summary=MatchSummaryResponse(**result["summary"]) if result["summary"] else MatchSummaryResponse(),
        message=result["message"],
    )


@router.get("/status", response_model=MatchSummaryResponse)
def get_reconciliation_status(
    customer_id: int = Query(..., description="客户 ID"),
    period: str = Query(..., description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """获取对账统计摘要"""
    summary = MatchService.get_summary(customer_id, period, db)
    return MatchSummaryResponse(**summary)


@router.get("/results")
def get_reconciliation_results(
    customer_id: int = Query(..., description="客户 ID"),
    period: str = Query(..., description="对账期间 YYYYMM"),
    status: str = Query("all", description="筛选状态: all/matched/unmatched/manual/ignored"),
    search: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页条数"),
    db: Session = Depends(get_db),
):
    """查询匹配结果"""
    return MatchService.get_results(
        customer_id, period, db,
        status_filter=status,
        search=search,
        page=page,
        page_size=page_size,
    )