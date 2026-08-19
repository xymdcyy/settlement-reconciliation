# 上传 API 路由

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    OurReceiptUploadResponse,
    SettlementUploadResponse,
    UploadResponse,
)
from app.services.upload_service import UploadService

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("/our-receipts", response_model=OurReceiptUploadResponse)
async def upload_our_receipts(
    file: UploadFile = File(..., description="我方签收明细 Excel 文件"),
    period: str = Form(..., description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """上传我方签收明细 Excel"""
    # 保存文件
    file_path = UploadService.save_uploaded_file(file, customer_id=0, period=period)

    # 解析
    result = UploadService.parse_our_receipts(file_path, period, db)

    return OurReceiptUploadResponse(
        total=result["total"],
        assigned_to_customers=result["assigned_to_customers"],
        unassigned=result["unassigned"],
        message=result["message"],
    )


@router.post("/settlements", response_model=SettlementUploadResponse)
async def upload_settlements(
    file: UploadFile = File(..., description="客户方结算单 Excel 文件"),
    customer_id: int = Form(..., description="客户 ID"),
    period: str = Form(..., description="对账期间 YYYYMM"),
    db: Session = Depends(get_db),
):
    """上传客户方结算单 Excel"""
    # 保存文件
    file_path = UploadService.save_uploaded_file(file, customer_id=customer_id, period=period)

    # 解析
    result = UploadService.parse_customer_settlements(file_path, customer_id, period, db)

    return SettlementUploadResponse(
        total=result["total"],
        parsed=result["parsed"],
        with_match_key=result["with_match_key"],
        message=result["message"],
    )