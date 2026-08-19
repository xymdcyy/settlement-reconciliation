# 手动纠正 API

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    CorrectionResponse,
    IgnoreRequest,
    ManualMatchRequest,
    NoteRequest,
    UnmatchRequest,
)
from app.services.correction_service import CorrectionService

router = APIRouter(prefix="/api/corrections", tags=["corrections"])


@router.post("/manual-match", response_model=CorrectionResponse)
def manual_match(request: ManualMatchRequest, db: Session = Depends(get_db)):
    """手动匹配一对记录"""
    result = CorrectionService.manual_match(
        customer_id=request.customer_id,
        period=request.period,
        receipt_id=request.receipt_id,
        settlement_id=request.settlement_id,
        db=db,
        operator_id=request.operator_id,
        reason=request.reason,
    )
    return CorrectionResponse(**result)


@router.post("/unmatch", response_model=CorrectionResponse)
def unmatch(request: UnmatchRequest, db: Session = Depends(get_db)):
    """解除匹配"""
    result = CorrectionService.unmatch(
        customer_id=request.customer_id,
        period=request.period,
        result_id=request.result_id,
        db=db,
        operator_id=request.operator_id,
        reason=request.reason,
    )
    return CorrectionResponse(**result)


@router.post("/ignore", response_model=CorrectionResponse)
def ignore(request: IgnoreRequest, db: Session = Depends(get_db)):
    """标记忽略"""
    result = CorrectionService.ignore(
        customer_id=request.customer_id,
        period=request.period,
        result_id=request.result_id,
        db=db,
        reason=request.reason,
        operator_id=request.operator_id,
    )
    return CorrectionResponse(**result)


@router.post("/note", response_model=CorrectionResponse)
def add_note(request: NoteRequest, db: Session = Depends(get_db)):
    """添加备注"""
    result = CorrectionService.add_note(
        customer_id=request.customer_id,
        period=request.period,
        result_id=request.result_id,
        remark=request.remark,
        db=db,
        operator_id=request.operator_id,
    )
    return CorrectionResponse(**result)