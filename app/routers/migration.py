# 迁移 API

from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    ErrorResponse,
    MigrationImportRequest,
    MigrationUploadResponse,
    MigrationValidateResponse,
    SuccessResponse,
)
from app.services.migration_service import MigrationService

router = APIRouter(prefix="/api/migration", tags=["migration"])


@router.post("/upload-excel", response_model=MigrationUploadResponse)
def upload_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """上传 Excel 台账"""
    try:
        # 保存文件到临时目录
        import os
        from pathlib import Path

        upload_dir = Path("uploads/migration")
        upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / file.filename
        with open(file_path, "wb") as f:
            content = file.file.read()
            f.write(content)

        # 解析 Excel（获取行数）
        df = MigrationService.parse_excel(str(file_path), 0, db)

        return MigrationUploadResponse(
            file_path=str(file_path),
            total_rows=len(df),
            message=f"成功上传 {file.filename}，共 {len(df)} 行",
        )
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))


@router.post("/validate", response_model=MigrationValidateResponse)
def validate_migration(
    customer_id: int,
    file_path: str,
    db: Session = Depends(get_db),
):
    """验证迁移数据"""
    try:
        # 解析 Excel
        df = MigrationService.parse_excel(file_path, customer_id, db)

        # 清洗数据
        receipts, warnings = MigrationService.clean_data(df, customer_id, db)

        # TODO: 这里应该先做试导入（不提交），然后验证
        # 现在先返回基本信息

        return MigrationValidateResponse(
            is_valid=True,
            total_rows=len(df),
            imported_rows=len(receipts),
            excel_total_amount=0.0,  # TODO: 计算
            imported_total_amount=0.0,  # TODO: 计算
            warnings=warnings,
            errors=[],
        )
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))


@router.post("/import", response_model=SuccessResponse)
def import_migration(
    request: MigrationImportRequest,
    db: Session = Depends(get_db),
):
    """执行迁移导入"""
    try:
        # 解析 Excel
        df = MigrationService.parse_excel(request.file_path, request.customer_id, db)

        # 清洗数据
        receipts, warnings = MigrationService.clean_data(df, request.customer_id, db)

        # 导入数据库
        result = MigrationService.import_to_db(
            receipts,
            request.customer_id,
            request.period,
            db,
        )

        # 验证导入
        validation = MigrationService.validate_import(
            request.customer_id,
            result["batch_id"],
            df,
            db,
        )

        if not validation["is_valid"]:
            return ErrorResponse(
                status="error",
                message="导入验证失败",
                detail=str(validation["errors"]),
            )

        return SuccessResponse(
            message=f"成功导入 {result['imported']} 条记录，验证通过",
        )
    except Exception as e:
        return ErrorResponse(status="error", message=str(e))
