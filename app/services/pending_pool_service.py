# 未决池服务

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Receipt


class PendingPoolService:
    """未决池服务"""

    @staticmethod
    def get_pending_pool(
        customer_id: int,
        db: Session,
    ) -> list[dict]:
        """
        获取未决差异池

        查询条件：
        - diff_type != 'none' 且不为 NULL
        - resolved_period IS NULL
        """
        items = (
            db.query(Receipt)
            .filter(
                Receipt.customer_id == customer_id,
                Receipt.diff_type.isnot(None),
                Receipt.diff_type != "none",
                Receipt.resolved_period.is_(None),
            )
            .order_by(Receipt.receipt_date.asc())
            .all()
        )

        # 计算挂账月数
        result = []
        for item in items:
            pending_months = PendingPoolService._calculate_pending_months(item.receipt_date)
            result.append({
                "receipt_id": item.id,
                "receipt_no": item.receipt_no,
                "model": item.model,
                "quantity": float(item.quantity) if item.quantity else 0,
                "amount": float(item.amount) if item.amount else 0,
                "diff_type": item.diff_type,
                "diff_note": item.diff_note,
                "receipt_date": item.receipt_date,
                "pending_months": pending_months,
            })

        return result

    @staticmethod
    def _calculate_pending_months(receipt_date: Optional[str]) -> int:
        """
        计算挂账月数

        从 receipt_date 到当前日期的月数差
        """
        if not receipt_date:
            return 0

        try:
            receipt_dt = datetime.strptime(receipt_date, "%Y-%m-%d")
            now = datetime.now()
            months = (now.year - receipt_dt.year) * 12 + (now.month - receipt_dt.month)
            return max(0, months)
        except:
            return 0

    @staticmethod
    def mark_diff(
        receipt_id: int,
        diff_type: str,
        diff_note: Optional[str],
        db: Session,
    ) -> Receipt:
        """
        标记差异（时间差/真差异）→ 挂入未决池

        Args:
            receipt_id: 台账行 ID
            diff_type: 差异类型（time_diff/price_diff/qty_diff/...）
            diff_note: 差异说明

        Raises:
            ValueError: 非法差异类型或记录不存在
        """
        allowed = {"time_diff", "price_diff", "qty_diff", "customer_not_received", "our_not_received"}
        if diff_type not in allowed:
            raise ValueError(f"非法差异类型: {diff_type}，可选: {sorted(allowed)}")

        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise ValueError(f"台账记录不存在: {receipt_id}")

        receipt.diff_type = diff_type
        receipt.diff_note = diff_note
        receipt.resolved_period = None  # 挂入未决池
        receipt.updated_at = datetime.now()
        db.commit()
        db.refresh(receipt)

        return receipt

    @staticmethod
    def resolve_pending(
        receipt_id: int,
        resolved_period: str,
        db: Session,
    ) -> Receipt:
        """
        标记未决差异为已解决
        """
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise ValueError(f"台账记录不存在: {receipt_id}")

        receipt.resolved_period = resolved_period
        receipt.updated_at = datetime.now()
        db.commit()
        db.refresh(receipt)

        return receipt

    @staticmethod
    def to_real_diff(
        receipt_id: int,
        diff_note: Optional[str],
        db: Session,
    ) -> Receipt:
        """
        转为真差异（需要调账）
        """
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise ValueError(f"台账记录不存在: {receipt_id}")

        # 更新差异类型为真差异
        if receipt.diff_type == "time_diff":
            receipt.diff_type = "price_diff"  # 或其他真差异类型

        if diff_note:
            receipt.diff_note = f"{receipt.diff_note or ''} [转为真差异] {diff_note}".strip()

        receipt.updated_at = datetime.now()
        db.commit()
        db.refresh(receipt)

        return receipt
