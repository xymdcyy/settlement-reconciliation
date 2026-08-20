# 匹配调度服务

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.engines import get_engine
from app.engines.base import OurReceipt as EngineReceipt
from app.engines.base import CustomerSettlement as EngineSettlement
from app.models import (
    CustomerSettlement,
    MatchResult,
    OurReceipt,
)


class MatchService:
    """匹配调度服务"""

    @staticmethod
    def run(customer_id: int, period: str, db: Session) -> dict:
        """
        运行自动匹配

        1. 从数据库加载双方数据
        2. 调用引擎执行匹配
        3. 匹配结果存入数据库
        """
        # 获取引擎
        engine = get_engine(customer_id)
        if engine is None:
            raise ValueError(f"客户 {customer_id} 未找到匹配引擎")

        # 加载我方数据
        our_receipts = db.query(OurReceipt).filter(
            OurReceipt.customer_id == customer_id,
            OurReceipt.period == period,
        ).all()

        # 加载客户方数据（未忽略的）
        settlements = db.query(CustomerSettlement).filter(
            CustomerSettlement.customer_id == customer_id,
            CustomerSettlement.period == period,
            CustomerSettlement.status != "ignored",
        ).all()

        if not our_receipts:
            return {"status": "skipped", "message": "无我方签收记录", "summary": {}}
        if not settlements:
            return {"status": "skipped", "message": "无客户方结算单", "summary": {}}

        # 转换为引擎数据类
        engine_receipts = [MatchService._to_engine_receipt(r) for r in our_receipts]
        engine_settlements = [MatchService._to_engine_settlement(s) for s in settlements]

        # 执行匹配
        result = engine.match(engine_receipts, engine_settlements)

        # 清空该客户+期间的历史匹配结果
        db.query(MatchResult).filter(
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        ).delete()

        # 存入匹配结果
        batch_id = f"match-{period}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 已匹配的记录
        for pair in result.matched_pairs:
            match = MatchResult(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                receipt_id=pair.receipt_id,
                settlement_id=pair.settlement_id,
                match_type=pair.match_type,
                confidence=pair.confidence,
                status="matched",
                source="auto",
                diff_amount=pair.diff_amount,
                diff_quantity=pair.diff_quantity,
                remark=pair.detail.get("remark", "") if isinstance(pair.detail, dict) else "",
            )
            db.add(match)

        # 未匹配的我方记录
        for rid in result.unmatched_receipts:
            match = MatchResult(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                receipt_id=rid,
                settlement_id=None,
                match_type="未匹配",
                confidence=0.0,
                status="unmatched",
                source="auto",
            )
            db.add(match)

        # 未匹配的客户方记录
        for sid in result.unmatched_settlements:
            match = MatchResult(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                receipt_id=None,
                settlement_id=sid,
                match_type="未匹配",
                confidence=0.0,
                status="unmatched",
                source="auto",
            )
            db.add(match)

        # 已排除的客户方记录
        for sid in result.excluded_settlements:
            match = MatchResult(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                receipt_id=None,
                settlement_id=sid,
                match_type="已排除",
                confidence=0.0,
                status="ignored",
                source="auto",
            )
            db.add(match)

        db.commit()

        # 计算统计摘要
        total_settlements = len(settlements)
        matched_count = len(result.matched_pairs)
        unmatched_receipts = len(result.unmatched_receipts)
        unmatched_settlements = len(result.unmatched_settlements)
        # 匹配率口径 = 已匹配入库行 / 入库行总数（matched + unmatched_settlement）。
        # 与 get_summary / export / history 一致。我方签收笔数（万级）远多于入库行，
        # 若用签收笔数作分母会严重低估；用去重结算单数又会因一对多入库行而虚高。
        total_settlement_rows = matched_count + unmatched_settlements
        match_rate = round(matched_count / total_settlement_rows * 100, 2) if total_settlement_rows > 0 else 0.0

        # 计算金额差异
        total_amount_diff = sum(p.diff_amount for p in result.matched_pairs)

        summary = {
            "total_receipts": len(our_receipts),
            "total_settlements": total_settlements,
            "matched_count": matched_count,
            "unmatched_receipts": unmatched_receipts,
            "unmatched_settlements": unmatched_settlements,
            "manual_count": 0,
            "ignored_count": len(result.excluded_settlements),
            "match_rate": match_rate,
            "total_amount_diff": round(total_amount_diff, 2),
        }

        return {"status": "completed", "summary": summary, "message": "匹配完成"}

    @staticmethod
    def get_summary(customer_id: int, period: str, db: Session) -> dict:
        """获取对账统计摘要"""
        results = db.query(MatchResult).filter(
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        ).all()

        total = len(results)
        if total == 0:
            return {
                "total_receipts": 0,
                "total_settlements": 0,
                "matched_count": 0,
                "unmatched_receipts": 0,
                "unmatched_settlements": 0,
                "manual_count": 0,
                "ignored_count": 0,
                "match_rate": 0.0,
                "total_amount_diff": 0.0,
            }

        matched_count = sum(1 for r in results if r.status == "matched")
        unmatched_count = sum(1 for r in results if r.status == "unmatched")
        manual_count = sum(1 for r in results if r.status == "manual")
        ignored_count = sum(1 for r in results if r.status == "ignored")

        # 我方记录数
        receipt_ids = set(r.receipt_id for r in results if r.receipt_id is not None)
        settlement_ids = set(r.settlement_id for r in results if r.settlement_id is not None)

        # 匹配率口径 = 已匹配入库行 / 入库行总数（matched+manual + 未匹配入库行），行级，
        # 与 run / export / history 一致（一张凭证拆多行的入库按行计）。
        matched_settlement_rows = sum(1 for r in results if r.status in ("matched", "manual") and r.settlement_id is not None)
        unmatched_settlement_rows = sum(1 for r in results if r.status == "unmatched" and r.settlement_id is not None)
        total_settlements_for_rate = matched_settlement_rows + unmatched_settlement_rows
        match_rate = round(matched_settlement_rows / total_settlements_for_rate * 100, 2) if total_settlements_for_rate > 0 else 0.0

        total_diff = sum(r.diff_amount or 0 for r in results if r.status == "matched")

        return {
            "total_receipts": len(receipt_ids),
            "total_settlements": len(settlement_ids),
            "matched_count": matched_count,
            "unmatched_receipts": sum(1 for r in results if r.status == "unmatched" and r.receipt_id is not None),
            "unmatched_settlements": sum(1 for r in results if r.status == "unmatched" and r.settlement_id is not None),
            "manual_count": manual_count,
            "ignored_count": ignored_count,
            "match_rate": match_rate,
            "total_amount_diff": round(total_diff, 2),
        }

    @staticmethod
    def get_results(
        customer_id: int,
        period: str,
        db: Session,
        status_filter: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        """查询匹配结果"""
        query = db.query(MatchResult).filter(
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        )

        if status_filter and status_filter != "all":
            query = query.filter(MatchResult.status == status_filter)

        # 搜索
        if search:
            query = query.filter(
                (MatchResult.remark.contains(search))
            )

        total = query.count()

        # 分页
        query = query.order_by(MatchResult.id)
        query = query.offset((page - 1) * page_size).limit(page_size)

        results = query.all()

        # 加载关联数据
        receipt_ids = [r.receipt_id for r in results if r.receipt_id is not None]
        settlement_ids = [r.settlement_id for r in results if r.settlement_id is not None]

        receipts = {r.id: r for r in db.query(OurReceipt).filter(OurReceipt.id.in_(receipt_ids)).all()} if receipt_ids else {}
        settlements = {s.id: s for s in db.query(CustomerSettlement).filter(CustomerSettlement.id.in_(settlement_ids)).all()} if settlement_ids else {}

        items = []
        for r in results:
            item = {
                "id": r.id,
                "match_type": r.match_type,
                "confidence": float(r.confidence) if r.confidence else None,
                "status": r.status,
                "source": r.source,
                "diff_amount": float(r.diff_amount) if r.diff_amount else None,
                "diff_quantity": float(r.diff_quantity) if r.diff_quantity else None,
                "remark": r.remark,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            # 关联我方数据
            if r.receipt_id and r.receipt_id in receipts:
                rec = receipts[r.receipt_id]
                item["receipt"] = {
                    "id": rec.id,
                    "receipt_no": rec.receipt_no,
                    "model": rec.model,
                    "quantity": float(rec.quantity) if rec.quantity else None,
                    "amount": float(rec.amount) if rec.amount else None,
                    "receipt_date": rec.receipt_date,
                    "doc_type": rec.doc_type,
                    "customer_name": rec.customer_name,
                    "nc_order_no": rec.nc_order_no,
                }
            else:
                item["receipt"] = None

            # 关联客户方数据
            if r.settlement_id and r.settlement_id in settlements:
                s = settlements[r.settlement_id]
                item["settlement"] = {
                    "id": s.id,
                    "match_key": s.match_key,
                    "model": s.model,
                    "quantity": float(s.quantity) if s.quantity else None,
                    "amount": float(s.amount) if s.amount else None,
                    "settlement_date": s.settlement_date,
                }
            else:
                item["settlement"] = None

            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }

    # ============================================================
    # 辅助方法
    # ============================================================

    @staticmethod
    def _to_engine_receipt(r: OurReceipt) -> EngineReceipt:
        """数据库模型 → 引擎数据类"""
        return EngineReceipt(
            id=r.id,
            receipt_no=r.receipt_no or "",
            model=r.model or "",
            quantity=float(r.quantity) if r.quantity else 0,
            amount=float(r.amount) if r.amount else 0,
            unit_price=float(r.unit_price) if r.unit_price else 0,
            receipt_date=r.receipt_date or "",
            doc_type=r.doc_type or "",
            customer_name=r.customer_name or "",
            nc_order_no=r.nc_order_no or "",
            raw_data=r.raw_data or {},
        )

    @staticmethod
    def _to_engine_settlement(s: CustomerSettlement) -> EngineSettlement:
        """数据库模型 → 引擎数据类"""
        return EngineSettlement(
            id=s.id,
            match_key=s.match_key or "",
            model=s.model or "",
            quantity=float(s.quantity) if s.quantity else 0,
            amount=float(s.amount) if s.amount else 0,
            unit_price=float(s.unit_price) if s.unit_price else 0,
            settlement_date=s.settlement_date or "",
            raw_data=s.raw_data or {},
        )