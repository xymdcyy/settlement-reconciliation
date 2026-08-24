# 开票服务

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Invoice, Receipt


class BillingService:
    """开票服务"""

    @staticmethod
    def get_pending_billing(
        customer_id: int,
        db: Session,
        period: Optional[str] = None,
    ) -> list[Receipt]:
        """
        获取可开票清单

        条件：
        - billing_status = 'unbilled'
        - diff_type IS NULL 或 diff_type = 'none'（无差异）
        - quantity > 0（非退货）
        """
        query = db.query(Receipt).filter(
            Receipt.customer_id == customer_id,
            Receipt.billing_status == "unbilled",
            Receipt.quantity > 0,
            (Receipt.diff_type.is_(None)) | (Receipt.diff_type == "none"),
        )

        if period:
            query = query.filter(Receipt.period == period)

        items = query.order_by(Receipt.receipt_date.asc()).all()
        return items

    @staticmethod
    def generate_billing_list(
        receipt_ids: list[int],
        db: Session,
    ) -> bytes:
        """
        生成开票清单（导出 Excel）

        调用 ExportService.export_billing_list_to_excel
        """
        from app.services.export_service import ExportService

        output = ExportService.export_billing_list_to_excel(
            receipt_ids=receipt_ids,
            db=db,
        )
        return output.getvalue()

    @staticmethod
    def import_billed_list(
        items: list[dict],
        db: Session,
    ) -> dict:
        """
        导入已开票清单（自动匹配回填发票号/日期）

        items: [{receipt_no, invoice_no, invoice_date, amount, quantity}]
        """
        matched = 0
        unmatched = []

        for item in items:
            receipt_no = item.get("receipt_no")
            invoice_no = item.get("invoice_no")
            invoice_date = item.get("invoice_date")
            amount = item.get("amount")
            quantity = item.get("quantity")

            # 查找台账记录（按单号+金额+数量匹配）
            receipt = (
                db.query(Receipt)
                .filter(
                    Receipt.receipt_no == receipt_no,
                    Receipt.amount == amount,
                    Receipt.quantity == quantity,
                    Receipt.billing_status == "unbilled",
                )
                .first()
            )

            if receipt:
                # 更新台账
                receipt.billing_status = "billed"
                receipt.invoice_no = invoice_no
                receipt.invoice_date = invoice_date
                receipt.updated_at = datetime.now()

                # 插入发票记录
                invoice = Invoice(
                    receipt_id=receipt.id,
                    invoice_no=invoice_no,
                    invoice_date=invoice_date,
                    amount=amount,
                    quantity=quantity,
                    invoice_type="blue",
                )
                db.add(invoice)
                matched += 1
            else:
                unmatched.append(item)

        db.commit()

        return {
            "status": "success",
            "matched": matched,
            "unmatched": len(unmatched),
            "unmatched_items": unmatched,
            "message": f"成功匹配 {matched} 条，未匹配 {len(unmatched)} 条",
        }

    @staticmethod
    def get_invoices(
        customer_id: int,
        db: Session,
        period: Optional[str] = None,
    ) -> list[Invoice]:
        """
        查询发票记录
        """
        query = (
            db.query(Invoice)
            .join(Receipt, Invoice.receipt_id == Receipt.id)
            .filter(Receipt.customer_id == customer_id)
        )

        if period:
            query = query.filter(Receipt.period == period)

        items = query.order_by(Invoice.invoice_date.desc()).all()
        return items
