# 上传解析服务

import io
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.engines import get_engine
from app.models import Customer, CustomerSettlement, OurReceipt, UploadHistory


class UploadService:
    """上传解析服务"""

    # 我方签收单标准化字段映射
    OUR_RECEIPT_FIELDS = {
        "receipt_no": "新方舟销售单号",
        "model": "产品型号",
        "quantity": "签收数量",
        "amount": "签收金额",
        "unit_price": "单价",
        "receipt_date": "签收日期/完成日期",
        "doc_type": "单据类型",
        "customer_name": "结算客户名称",
        "nc_order_no": "NC订单号",
        "product_line": "产品线",
    }

    @staticmethod
    def save_uploaded_file(upload_file: UploadFile, customer_id: int, period: str) -> Path:
        """保存上传的文件到本地文件系统"""
        upload_dir = Path(settings.UPLOAD_DIR) / str(customer_id) / period
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名，避免中文名问题
        ext = Path(upload_file.filename or "unknown.xlsx").suffix if upload_file.filename else ".xlsx"
        safe_name = f"{uuid.uuid4().hex}{ext}"
        file_path = upload_dir / safe_name

        with open(file_path, "wb") as f:
            content = upload_file.file.read()
            f.write(content)

        return file_path

    # ============================================================
    # 我方签收记录上传
    # ============================================================

    @classmethod
    def parse_our_receipts(cls, file_path: Path, period: str, db: Session) -> dict:
        """
        解析我方签收明细 Excel

        Returns:
            dict: {total, assigned_to_customers, unassigned, message}
        """
        # 读取 Excel
        df = cls._read_excel_safe(file_path)
        total = len(df)
        if total == 0:
            return {"total": 0, "assigned_to_customers": {}, "unassigned": 0, "message": "Excel 文件为空"}

        # 获取所有客户（用于将“结算客户名称”解析到客户）
        customers = [c for c in db.query(Customer).all() if c.is_active]
        resolve_cache: dict[str, Optional[int]] = {}

        assigned = {}  # customer_id -> count
        unassigned = 0
        batch_id = f"our-{period}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        for _, row in df.iterrows():
            customer_name = cls._safe_str(row.get("结算客户名称", ""))
            if customer_name not in resolve_cache:
                resolve_cache[customer_name] = cls._resolve_customer_id(customer_name, customers)
            customer_id = resolve_cache[customer_name]

            if customer_id is None:
                unassigned += 1
                continue

            receipt = OurReceipt(
                receipt_no=cls._safe_str(row.get("新方舟销售单号", "")),
                customer_id=customer_id,
                period=period,
                model=cls._safe_str(row.get("产品型号", "")),
                quantity=cls._safe_float(row.get("签收数量")),
                amount=cls._safe_float(row.get("签收金额")),
                unit_price=cls._safe_float(row.get("单价")),
                receipt_date=cls._safe_date_str(row.get("签收日期/完成日期")),
                doc_type=cls._safe_str(row.get("单据类型", "")),
                customer_name=customer_name,
                nc_order_no=cls._safe_str(row.get("NC订单号", "")),
                product_line=cls._safe_str(row.get("产品线", "")),
                batch_id=batch_id,
                raw_data=cls._row_to_json(row),
            )
            db.add(receipt)
            assigned[customer_name] = assigned.get(customer_name, 0) + 1

        db.commit()

        # 记录上传历史
        history = UploadHistory(
            upload_type="our",
            customer_id=0,
            customer_name="我方签收",
            period=period,
            file_name=file_path.name,
            total=total,
            parsed=sum(assigned.values()),
            status="success",
            message=f"导入成功：{sum(assigned.values())} 条分配到客户，{unassigned} 条未分配",
        )
        db.add(history)
        db.commit()

        return {
            "total": total,
            "assigned_to_customers": assigned,
            "unassigned": unassigned,
            "message": f"导入成功：{sum(assigned.values())} 条分配到客户，{unassigned} 条未分配",
        }

    # ============================================================
    # 客户方结算单上传
    # ============================================================

    @classmethod
    def parse_customer_settlements(
        cls, file_path: Path, customer_id: int, period: str, db: Session
    ) -> dict:
        """
        解析客户方结算单 Excel

        Returns:
            dict: {total, parsed, with_match_key, message}
        """
        # 读取 Excel
        df = cls._read_excel_safe(file_path)
        total = len(df)
        if total == 0:
            return {"total": 0, "parsed": 0, "with_match_key": 0, "message": "Excel 文件为空"}

        # 获取引擎解析
        engine = get_engine(customer_id)
        if engine is None:
            return {"total": total, "parsed": 0, "with_match_key": 0,
                    "message": f"客户 {customer_id} 未找到匹配引擎"}

        try:
            settlements = engine.parse_customer_data(df)
        except Exception as e:
            return {"total": total, "parsed": 0, "with_match_key": 0,
                    "message": f"引擎解析失败: {str(e)}"}

        # 存入数据库
        batch_id = f"settlement-{period}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        with_match_key = 0

        for s in settlements:
            db_settlement = CustomerSettlement(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                match_key=s.match_key,
                model=s.model,
                quantity=s.quantity,
                amount=s.amount,
                unit_price=s.unit_price,
                settlement_date=s.settlement_date,
                status="pending",
                raw_data=s.raw_data,
            )
            db.add(db_settlement)
            if s.match_key:
                with_match_key += 1

        db.commit()

        # 记录上传历史
        history = UploadHistory(
            upload_type="settlement",
            customer_id=customer_id,
            customer_name=f"客户ID:{customer_id}",
            period=period,
            file_name=file_path.name,
            total=total,
            parsed=len(settlements),
            status="success",
            message=f"解析成功：{len(settlements)} 条，其中 {with_match_key} 条含匹配键",
        )
        db.add(history)
        db.commit()

        return {
            "total": total,
            "parsed": len(settlements),
            "with_match_key": with_match_key,
            "message": f"解析成功：{len(settlements)} 条，其中 {with_match_key} 条含匹配键",
        }

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _read_excel_safe(file_path: Path) -> pd.DataFrame:
        """安全读取 Excel 文件（先读入内存再关闭文件）"""
        # 先读入内存，再传给 pandas，避免 Windows 文件锁
        with open(file_path, "rb") as f:
            content = f.read()

        df = pd.read_excel(io.BytesIO(content), sheet_name=0)

        # 过滤掉表头重复行（签收单第2行可能是表头文字重复）
        for col in df.columns[:3]:
            mask = df[col].astype(str).str.strip() == str(col).strip()
            if mask.any():
                df = df[~mask]
                break

        return df.reset_index(drop=True)

    @staticmethod
    def _resolve_customer_id(customer_name: str, customers: list[Customer]) -> Optional[int]:
        """将我方明细的“结算客户名称”解析到客户 ID。

        匹配优先级：
        1. 精确匹配：Customer.name == 结算客户名称
        2. 关键词匹配：结算客户名称包含该客户 match_keywords 中的全部关键词
           （例如客户关键词 ["天猫优品", "经销"] 可归属
           "张家口天猫优品电子商务有限公司-经销"）

        若关键词命中多个客户，视为歧义，返回 None（不分配），避免财务误配。
        """
        if not customer_name:
            return None
        # 1) 精确匹配
        for c in customers:
            if c.name and c.name == customer_name:
                return c.id
        # 2) 关键词全包含匹配
        hits = [
            c.id
            for c in customers
            if c.match_keywords and all(kw in customer_name for kw in c.match_keywords)
        ]
        if len(hits) == 1:
            return hits[0]
        return None

    @staticmethod
    def _safe_str(value, default="") -> str:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        return str(value).strip()

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _safe_date_str(value) -> Optional[str]:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return None
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")
        if isinstance(value, pd.Timestamp):
            return value.strftime("%Y-%m-%d")
        return str(value).strip()

    @staticmethod
    def _row_to_json(row) -> Optional[str]:
        """将 DataFrame 行转换为 JSON 字符串"""
        try:
            result = {}
            for col in row.index:
                val = row[col]
                if isinstance(val, float) and pd.isna(val):
                    result[col] = None
                elif isinstance(val, pd.Timestamp):
                    result[col] = val.isoformat()
                elif isinstance(val, datetime):
                    result[col] = val.isoformat()
                else:
                    result[col] = val
            return result
        except Exception:
            return None