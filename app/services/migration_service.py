# 迁移服务

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Customer, Receipt


class MigrationService:
    """迁移服务"""

    @staticmethod
    def parse_excel(
        file_path: str,
        customer_id: int,
        db: Session,
        sheet_name: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        解析 Excel 台账

        1. 自动识别主 sheet（通常是"全品类"或"全品类-X.XX"）
        2. 识别手工区列（新方舟销售单号之前的列）
        3. 识别系统区列（新方舟销售单号及之后）
        """
        # 读取 Excel
        xl = pd.ExcelFile(file_path)

        # 自动识别主 sheet
        if not sheet_name:
            # 优先选择"全品类"开头的 sheet
            for name in xl.sheet_names:
                if name.startswith("全品类"):
                    sheet_name = name
                    break
            # 如果没有，选择第一个 sheet
            if not sheet_name:
                sheet_name = xl.sheet_names[0]

        df = pd.read_excel(file_path, sheet_name=sheet_name)

        return df

    @staticmethod
    def clean_data(
        df: pd.DataFrame,
        customer_id: int,
        db: Session,
    ) -> list[dict]:
        """
        数据清洗

        1. 识别手工区列和系统区列
        2. 状态枚举值转换
        3. 日期格式统一
        4. 脏数据处理
        """
        # 查找"新方舟销售单号"列的位置
        try:
            receipt_no_col_idx = df.columns.tolist().index("新方舟销售单号")
        except ValueError:
            raise ValueError("Excel 中未找到'新方舟销售单号'列")

        # 手工区列（新方舟销售单号之前的列）
        manual_cols = df.columns[:receipt_no_col_idx].tolist()
        # 系统区列（新方舟销售单号及之后）
        system_cols = df.columns[receipt_no_col_idx:].tolist()

        # 获取客户扩展列配置
        customer = db.query(Customer).filter(Customer.id == customer_id).first()
        extra_fields_config = customer.extra_fields_config if customer else []

        receipts = []
        warnings = []

        for idx, row in df.iterrows():
            try:
                # 系统字段
                receipt_data = {
                    "receipt_no": str(row.get("新方舟销售单号", "")),
                    "model": str(row.get("产品型号", "")),
                    "quantity": float(row.get("签收数量", 0)),
                    "amount": float(row.get("签收金额", 0)),
                    "unit_price": float(row.get("单价", 0)) if pd.notna(row.get("单价")) else None,
                    "receipt_date": MigrationService._parse_date(row.get("签收日期/完成日期")),
                    "doc_type": str(row.get("单据类型", "")),
                    "customer_name": str(row.get("结算客户名称", "")),
                    "nc_order_no": str(row.get("NC订单号", "")) if pd.notna(row.get("NC订单号")) else None,
                    "product_line": str(row.get("产品线", "")) if pd.notna(row.get("产品线")) else None,
                    "raw_data": row.to_dict(),
                }

                # 开票状态（从手工区解析）
                billing_status_raw = row.get("是否开票") or row.get("是否还需开票")
                receipt_data["billing_status"] = MigrationService._parse_billing_status(billing_status_raw)

                # 发票信息
                receipt_data["invoice_no"] = str(row.get("发票号")) if pd.notna(row.get("发票号")) else None
                receipt_data["invoice_date"] = MigrationService._parse_date(row.get("开票日期"))

                # 拆分
                split_note = row.get("拆分")
                if pd.notna(split_note):
                    receipt_data["split_note"] = str(split_note)
                    if "已拆分" in str(split_note):
                        receipt_data["billing_status"] = "split"

                # 备注
                receipt_data["remark"] = str(row.get("备注")) if pd.notna(row.get("备注")) else None

                # 扩展字段
                extra_fields = {}
                for config in extra_fields_config or []:
                    field_name = config.get("name")
                    if field_name in row and pd.notna(row[field_name]):
                        extra_fields[field_name] = row[field_name]
                if extra_fields:
                    receipt_data["extra_fields"] = extra_fields

                receipts.append(receipt_data)

            except Exception as e:
                warnings.append(f"第 {idx+2} 行解析失败: {str(e)}")

        return receipts, warnings

    @staticmethod
    def _parse_billing_status(value) -> str:
        """解析开票状态枚举"""
        if pd.isna(value):
            return "unbilled"

        value_str = str(value).strip()

        # 已开
        if value_str in ["已开", "111", "手工标识已开", "25年已开", "26年已开", "前期已开"]:
            return "billed"

        # 未开
        if value_str in ["未开", "未开确定", ""]:
            return "unbilled"

        # 已拆分
        if value_str == "已拆分":
            return "split"

        # 重复开具（特殊处理，保留原值到remark）
        if "重复开具" in value_str:
            return "billed"

        # 默认未开
        return "unbilled"

    @staticmethod
    def _parse_date(value) -> Optional[str]:
        """解析日期（支持多种格式）"""
        if pd.isna(value):
            return None

        # 如果已经是日期类型
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d")

        # 如果是 Excel 序列号（数字）
        if isinstance(value, (int, float)):
            try:
                date_obj = datetime(1899, 12, 30) + timedelta(days=value)
                return date_obj.strftime("%Y-%m-%d")
            except:
                return None

        # 尝试 pandas 自动解析
        try:
            date_obj = pd.to_datetime(value)
            return date_obj.strftime("%Y-%m-%d")
        except:
            return None

    @staticmethod
    def import_to_db(
        receipts: list[dict],
        customer_id: int,
        period: str,
        db: Session,
    ) -> dict:
        """
        批量导入数据库
        """
        batch_id = f"migration-{period}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        count = 0
        errors = []

        for r in receipts:
            try:
                receipt = Receipt(
                    customer_id=customer_id,
                    period=period,
                    batch_id=batch_id,
                    **r,
                )
                db.add(receipt)
                count += 1
            except Exception as e:
                errors.append(f"导入失败: {r.get('receipt_no', 'unknown')}: {str(e)}")

        db.commit()

        return {
            "status": "success",
            "batch_id": batch_id,
            "imported": count,
            "errors": errors,
        }

    @staticmethod
    def validate_import(
        customer_id: int,
        batch_id: str,
        excel_df: pd.DataFrame,
        db: Session,
    ) -> dict:
        """
        验证导入结果

        1. 行数验证
        2. 金额验证
        3. 状态验证
        """
        # 查询导入的记录
        imported = (
            db.query(Receipt)
            .filter(
                Receipt.customer_id == customer_id,
                Receipt.batch_id == batch_id,
            )
            .all()
        )

        # 行数验证
        excel_rows = len(excel_df)
        imported_rows = len(imported)

        # 金额验证
        excel_total = excel_df["签收金额"].sum() if "签收金额" in excel_df.columns else 0
        imported_total = sum(float(r.amount) for r in imported if r.amount)

        # 状态验证
        billed_count = sum(1 for r in imported if r.billing_status == "billed")
        unbilled_count = sum(1 for r in imported if r.billing_status == "unbilled")

        is_valid = (
            excel_rows == imported_rows
            and abs(excel_total - imported_total) < 0.01
        )

        warnings = []
        errors = []

        if excel_rows != imported_rows:
            errors.append(f"行数不一致: Excel={excel_rows}, 导入={imported_rows}")

        if abs(excel_total - imported_total) >= 0.01:
            errors.append(f"金额不一致: Excel={excel_total}, 导入={imported_total}")

        return {
            "is_valid": is_valid,
            "total_rows": excel_rows,
            "imported_rows": imported_rows,
            "excel_total_amount": float(excel_total),
            "imported_total_amount": float(imported_total),
            "billed_count": billed_count,
            "unbilled_count": unbilled_count,
            "warnings": warnings,
            "errors": errors,
        }
