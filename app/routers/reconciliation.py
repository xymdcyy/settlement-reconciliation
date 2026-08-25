# 对账运行 + 结果查询 + 导出 API

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Customer
from app.schemas import (
    HistoryResponse,
    MarkDiffRequest,
    MatchSummaryResponse,
    ReconciliationRunResponse,
    RunReconciliationRequest,
)
from app.services.match_service import MatchService
from app.services.export_service import ExportService
from app.services.reconciliation_upload_service import ReconciliationUploadService
from app.services.pending_pool_service import PendingPoolService

router = APIRouter(prefix="/api/reconciliation", tags=["reconciliation"])


@router.post("/upload-statement")
def upload_statement(
    customer_id: int = Form(...),
    period: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传客户对账单"""
    try:
        file_content = file.file.read()
        result = ReconciliationUploadService.upload_statement(
            customer_id=customer_id,
            period=period,
            file_content=file_content,
            db=db,
        )
        return result
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@router.post("/mark-diff")
def mark_diff(
    request: MarkDiffRequest,
    db: Session = Depends(get_db),
):
    """标记差异（时间差/真差异）→ 挂入未决池"""
    try:
        PendingPoolService.mark_diff(request.receipt_id, request.diff_type, request.diff_note, db)
        return {"status": "success", "message": "已标记差异，挂入未决池"}
    except ValueError as e:
        return {"status": "error", "message": str(e)}


@router.post("/run", response_model=ReconciliationRunResponse)
def run_reconciliation(
    request: RunReconciliationRequest,
    db: Session = Depends(get_db),
):
    """运行自动匹配"""
    result = MatchService.run(request.customer_id, request.period, db)
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


@router.get("/export")
def export_reconciliation(
    customer_id: int = Query(..., description="客户 ID"),
    period: str = Query(..., description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """导出对账结果 Excel"""
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    customer_name = customer.name if customer else f"客户{customer_id}"

    output = ExportService.export_reconciliation(customer_id, period, customer_name, db)

    # RFC 5987 编码中文文件名，兼容所有浏览器
    filename = f"对账结果_{customer_name}_{period}.xlsx"
    encoded_filename = quote(filename)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.get("/history", response_model=HistoryResponse)
def get_reconciliation_history(
    customer_id: int = Query(None, description="客户 ID（可选）"),
    start_month: str = Query(None, description="起始月份 YYYYMM"),
    end_month: str = Query(None, description="结束月份 YYYYMM"),
    db: Session = Depends(get_db),
):
    """获取历史对账记录摘要"""
    items = ExportService.get_history(db, customer_id, start_month, end_month)
    return {"items": items}