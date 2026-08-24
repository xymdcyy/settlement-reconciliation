# 台账服务

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import Receipt
from app.schemas import ReceiptCreate, ReceiptSplit, ReceiptUpdate


class ReceiptService:
    """台账服务"""

    @staticmethod
    def import_receipts(
        customer_id: int,
        period: str,
        receipts: list[ReceiptCreate],
        db: Session,
    ) -> dict:
        """
        导入台账（层累追加）

        1. 生成批次ID
        2. 批量插入 receipts
        3. 返回导入结果
        """
        batch_id = f"import-{period}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        count = 0
        for r in receipts:
            receipt = Receipt(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                receipt_no=r.receipt_no,
                model=r.model,
                quantity=r.quantity,
                amount=r.amount,
                unit_price=r.unit_price,
                receipt_date=r.receipt_date,
                doc_type=r.doc_type,
                customer_name=r.customer_name,
                nc_order_no=r.nc_order_no,
                product_line=r.product_line,
                raw_data=r.raw_data,
                billing_status="unbilled",  # 默认未开票
            )
            db.add(receipt)
            count += 1

        db.commit()

        return {
            "status": "success",
            "batch_id": batch_id,
            "imported": count,
            "message": f"成功导入 {count} 条台账记录",
        }

    @staticmethod
    def get_receipts(
        customer_id: int,
        db: Session,
        period: Optional[str] = None,
        billing_status: Optional[str] = None,
        diff_type: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """
        查询台账（筛选/分页）
        """
        query = db.query(Receipt).filter(Receipt.customer_id == customer_id)

        # 筛选
        if period:
            query = query.filter(Receipt.period == period)
        if billing_status:
            query = query.filter(Receipt.billing_status == billing_status)
        if diff_type:
            query = query.filter(Receipt.diff_type == diff_type)
        if search:
            query = query.filter(
                (Receipt.receipt_no.contains(search))
                | (Receipt.model.contains(search))
            )

        # 总数
        total = query.count()

        # 分页
        items = (
            query.order_by(Receipt.receipt_date.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @staticmethod
    def update_receipt(
        receipt_id: int,
        update: ReceiptUpdate,
        db: Session,
    ) -> Receipt:
        """
        更新台账（编辑开票状态）
        """
        receipt = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not receipt:
            raise ValueError(f"台账记录不存在: {receipt_id}")

        # 更新字段
        if update.billing_status is not None:
            receipt.billing_status = update.billing_status
        if update.invoice_no is not None:
            receipt.invoice_no = update.invoice_no
        if update.invoice_date is not None:
            receipt.invoice_date = update.invoice_date
        if update.remark is not None:
            receipt.remark = update.remark
        if update.extra_fields is not None:
            receipt.extra_fields = update.extra_fields
        if update.diff_type is not None:
            receipt.diff_type = update.diff_type
        if update.diff_note is not None:
            receipt.diff_note = update.diff_note

        receipt.updated_at = datetime.now()
        db.commit()
        db.refresh(receipt)

        return receipt

    @staticmethod
    def split_receipt(
        receipt_id: int,
        split: ReceiptSplit,
        db: Session,
    ) -> dict:
        """
        拆分行

        1. 父行标记为已拆分
        2. 生成子行（继承父行字段，仅数量/金额不同）
        """
        parent = db.query(Receipt).filter(Receipt.id == receipt_id).first()
        if not parent:
            raise ValueError(f"台账记录不存在: {receipt_id}")

        if parent.billing_status == "split":
            raise ValueError("该行已拆分，不能重复拆分")

        # 验证拆分数量
        total_qty = sum(split.quantities)
        if abs(total_qty - float(parent.quantity)) > 0.01:
            raise ValueError(f"拆分数量之和({total_qty})与原数量({parent.quantity})不一致")

        # 父行标记为已拆分
        parent.billing_status = "split"
        parent.split_note = split.split_note or f"拆分为 {len(split.quantities)} 行"

        # 生成子行
        children = []
        unit_price = float(parent.unit_price) if parent.unit_price else 0

        for idx, qty in enumerate(split.quantities, start=1):
            child = Receipt(
                customer_id=parent.customer_id,
                period=parent.period,
                batch_id=parent.batch_id,
                receipt_no=parent.receipt_no,  # 子行与父行同单号
                model=parent.model,
                quantity=qty,
                amount=round(qty * unit_price, 2),
                unit_price=parent.unit_price,
                receipt_date=parent.receipt_date,
                doc_type=parent.doc_type,
                customer_name=parent.customer_name,
                nc_order_no=parent.nc_order_no,
                product_line=parent.product_line,
                raw_data=parent.raw_data,
                billing_status="unbilled",
                split_parent_id=parent.id,
                split_note=f"拆分自 {parent.receipt_no} (第{idx}行)",
                extra_fields=parent.extra_fields,
            )
            db.add(child)
            children.append(child)

        db.commit()

        return {
            "status": "success",
            "parent_id": parent.id,
            "children_ids": [c.id for c in children],
            "message": f"成功拆分为 {len(children)} 行",
        }

    @staticmethod
    def export_receipts(
        customer_id: int,
        period: Optional[str],
        db: Session,
        billing_status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> bytes:
        """
        导出台账为 Excel

        调用 ExportService.export_receipts_to_excel
        """
        from app.services.export_service import ExportService

        output = ExportService.export_receipts_to_excel(
            customer_id=customer_id,
            db=db,
            period=period,
            billing_status=billing_status,
            search=search,
        )
        return output.getvalue()

    @staticmethod
    def get_pending_pool(
        customer_id: int,
        db: Session,
    ) -> list[Receipt]:
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
            .order_by(Receipt.receipt_date.asc())  # 按日期升序，越早的越优先
            .all()
        )

        return items

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
