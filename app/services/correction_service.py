# 手动纠正服务

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.models import CorrectionLog, MatchResult


class CorrectionService:
    """手动纠正服务"""

    @staticmethod
    def manual_match(
        customer_id: int,
        period: str,
        receipt_id: int,
        settlement_id: int,
        db: Session,
        operator_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> dict:
        """手动匹配一对记录"""
        # 查找原有的未匹配结果
        old_match = db.query(MatchResult).filter(
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
            MatchResult.receipt_id == receipt_id,
        ).first()

        old_settlement_match = db.query(MatchResult).filter(
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
            MatchResult.settlement_id == settlement_id,
        ).first()

        before_data = {
            "receipt_match_id": old_match.id if old_match else None,
            "receipt_status": old_match.status if old_match else None,
            "settlement_match_id": old_settlement_match.id if old_settlement_match else None,
            "settlement_status": old_settlement_match.status if old_settlement_match else None,
        }

        # 删除旧的未匹配记录
        if old_match:
            db.delete(old_match)
        if old_settlement_match and old_settlement_match.id != (old_match.id if old_match else None):
            db.delete(old_settlement_match)

        # 创建新的匹配结果
        new_match = MatchResult(
            customer_id=customer_id,
            period=period,
            receipt_id=receipt_id,
            settlement_id=settlement_id,
            match_type="人工匹配",
            confidence=1.0,
            status="manual",
            source="manual",
            remark=reason or "",
            operator_id=operator_id,
        )
        db.add(new_match)
        db.flush()

        # 记录操作日志
        log = CorrectionLog(
            customer_id=customer_id,
            period=period,
            result_id=new_match.id,
            operation_type="manual_match",
            before_data=before_data,
            after_data={"match_id": new_match.id, "status": "manual"},
            reason=reason or "人工匹配",
            operator_id=operator_id,
        )
        db.add(log)
        db.commit()

        return {"success": True, "result_id": new_match.id, "message": "手动匹配成功"}

    @staticmethod
    def unmatch(
        customer_id: int,
        period: str,
        result_id: int,
        db: Session,
        operator_id: Optional[int] = None,
        reason: Optional[str] = None,
    ) -> dict:
        """解除匹配"""
        match = db.query(MatchResult).filter(
            MatchResult.id == result_id,
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        ).first()

        if not match:
            return {"success": False, "message": "未找到匹配记录"}

        before_data = {
            "status": match.status,
            "receipt_id": match.receipt_id,
            "settlement_id": match.settlement_id,
        }

        # 分别创建两条未匹配记录
        if match.receipt_id:
            r_unmatch = MatchResult(
                customer_id=customer_id,
                period=period,
                receipt_id=match.receipt_id,
                settlement_id=None,
                match_type="未匹配",
                confidence=0.0,
                status="unmatched",
                source="manual",
                remark=reason or "解除匹配",
                operator_id=operator_id,
            )
            db.add(r_unmatch)

        if match.settlement_id:
            s_unmatch = MatchResult(
                customer_id=customer_id,
                period=period,
                settlement_id=match.settlement_id,
                receipt_id=None,
                match_type="未匹配",
                confidence=0.0,
                status="unmatched",
                source="manual",
                remark=reason or "解除匹配",
                operator_id=operator_id,
            )
            db.add(s_unmatch)

        # 删除原匹配
        db.delete(match)
        db.flush()

        # 记录操作日志
        log = CorrectionLog(
            customer_id=customer_id,
            period=period,
            result_id=result_id,
            operation_type="unmatch",
            before_data=before_data,
            after_data={"status": "unmatched"},
            reason=reason or "解除匹配",
            operator_id=operator_id,
        )
        db.add(log)
        db.commit()

        return {"success": True, "message": "解除匹配成功"}

    @staticmethod
    def ignore(
        customer_id: int,
        period: str,
        result_id: int,
        db: Session,
        reason: str = "忽略",
        operator_id: Optional[int] = None,
    ) -> dict:
        """标记忽略"""
        match = db.query(MatchResult).filter(
            MatchResult.id == result_id,
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        ).first()

        if not match:
            return {"success": False, "message": "未找到匹配记录"}

        before_data = {"status": match.status, "remark": match.remark}

        match.status = "ignored"
        match.source = "manual"
        match.remark = reason
        match.operator_id = operator_id
        db.flush()

        log = CorrectionLog(
            customer_id=customer_id,
            period=period,
            result_id=result_id,
            operation_type="ignore",
            before_data=before_data,
            after_data={"status": "ignored", "reason": reason},
            reason=reason,
            operator_id=operator_id,
        )
        db.add(log)
        db.commit()

        return {"success": True, "message": "已忽略"}

    @staticmethod
    def add_note(
        customer_id: int,
        period: str,
        result_id: int,
        remark: str,
        db: Session,
        operator_id: Optional[int] = None,
    ) -> dict:
        """添加备注"""
        match = db.query(MatchResult).filter(
            MatchResult.id == result_id,
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        ).first()

        if not match:
            return {"success": False, "message": "未找到匹配记录"}

        before_data = {"remark": match.remark}

        match.remark = (match.remark or "") + f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {remark}"
        match.operator_id = operator_id
        db.flush()

        log = CorrectionLog(
            customer_id=customer_id,
            period=period,
            result_id=result_id,
            operation_type="add_note",
            before_data=before_data,
            after_data={"remark": match.remark},
            reason=remark,
            operator_id=operator_id,
        )
        db.add(log)
        db.commit()

        return {"success": True, "message": "备注已添加"}