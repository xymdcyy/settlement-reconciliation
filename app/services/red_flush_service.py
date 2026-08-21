# 红冲服务

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Adjustment, Receipt


class RedFlushService:
    """红冲服务"""

    PRICE_TOLERANCE = 0.01  # 单价容差

    @staticmethod
    def get_return_receipts(
        customer_id: int,
        db: Session,
        period: Optional[str] = None,
    ) -> list[Receipt]:
        """
        获取本月退货记录

        条件：
        - quantity < 0（退货）
        - doc_type 包含"退货"
        """
        query = db.query(Receipt).filter(
            Receipt.customer_id == customer_id,
            Receipt.quantity < 0,
        )

        if period:
            query = query.filter(Receipt.period == period)

        items = query.order_by(Receipt.receipt_date.desc()).all()
        return items

    @staticmethod
    def find_blue_invoice(
        return_receipt_id: int,
        db: Session,
    ) -> Optional[Receipt]:
        """
        自动查找蓝票

        匹配条件：
        - 同型号
        - 单价容差 ≤0.01
        - 签收数量 > 0（蓝字）
        - billing_status = 'billed'（已开票）
        - 取开票日期最新的一张
        """
        # 获取退货记录
        return_receipt = db.query(Receipt).filter(Receipt.id == return_receipt_id).first()
        if not return_receipt:
            raise ValueError(f"退货记录不存在: {return_receipt_id}")

        # 查找匹配的蓝票
        matched = (
            db.query(Receipt)
            .filter(
                Receipt.customer_id == return_receipt.customer_id,
                Receipt.model == return_receipt.model,
                Receipt.quantity > 0,  # 蓝字
                Receipt.billing_status == "billed",  # 已开票
                Receipt.invoice_no.isnot(None),  # 有发票号
            )
            .all()
        )

        # 手动筛选单价容差
        candidates = []
        return_unit_price = abs(float(return_receipt.unit_price)) if return_receipt.unit_price else 0

        for r in matched:
            r_unit_price = float(r.unit_price) if r.unit_price else 0
            if abs(r_unit_price - return_unit_price) <= RedFlushService.PRICE_TOLERANCE:
                candidates.append(r)

        if not candidates:
            return None

        # 按开票日期降序排序，取最新的一张
        candidates.sort(key=lambda x: x.invoice_date or "", reverse=True)
        return candidates[0]

    @staticmethod
    def batch_find_blue_invoices(
        return_receipt_ids: list[int],
        db: Session,
    ) -> dict:
        """
        批量查找蓝票
        """
        results = []

        for rid in return_receipt_ids:
            blue_receipt = RedFlushService.find_blue_invoice(rid, db)
            results.append({
                "return_receipt_id": rid,
                "blue_invoice_no": blue_receipt.invoice_no if blue_receipt else None,
                "blue_invoice_date": blue_receipt.invoice_date if blue_receipt else None,
                "blue_receipt_id": blue_receipt.id if blue_receipt else None,
            })

        matched = sum(1 for r in results if r["blue_invoice_no"] is not None)

        return {
            "status": "success",
            "total": len(results),
            "matched": matched,
            "unmatched": len(results) - matched,
            "results": results,
        }

    @staticmethod
    def generate_confirmation(
        return_receipt_ids: list[int],
        db: Session,
    ) -> bytes:
        """
        生成确认单（导出 Excel 给税务）

        TODO: 实现 Excel 导出逻辑
        """
        # 先批量查找蓝票
        result = RedFlushService.batch_find_blue_invoices(return_receipt_ids, db)

        # 这里先返回空字节，后续实现 Excel 导出
        return b""

    @staticmethod
    def record_red_notice(
        return_receipt_id: int,
        red_notice_no: str,
        db: Session,
    ) -> Receipt:
        """
        回录红通号
        """
        receipt = db.query(Receipt).filter(Receipt.id == return_receipt_id).first()
        if not receipt:
            raise ValueError(f"退货记录不存在: {return_receipt_id}")

        # 更新扩展字段
        if not receipt.extra_fields:
            receipt.extra_fields = {}
        receipt.extra_fields["红通号"] = red_notice_no
        receipt.updated_at = datetime.now()

        db.commit()
        db.refresh(receipt)

        return receipt

    @staticmethod
    def create_adjustment(
        customer_id: int,
        receipt_id: int,
        adjustment_type: str,
        note: Optional[str],
        db: Session,
    ) -> Adjustment:
        """
        创建调账/红冲记录
        """
        adjustment = Adjustment(
            customer_id=customer_id,
            receipt_id=receipt_id,
            adjustment_type=adjustment_type,
            note=note,
            status="pending",
        )
        db.add(adjustment)
        db.commit()
        db.refresh(adjustment)

        return adjustment
