# 人工纠正服务测试

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CorrectionLog, Customer, CustomerStatement, MatchResult, Receipt
from app.services.correction_service import CorrectionService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def customer(db_session):
    c = Customer(name="天猫优品", slug="tmall", has_statement=True)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


@pytest.fixture
def receipt(db_session, customer):
    r = Receipt(
        customer_id=customer.id, period="202608", receipt_no="S101001",
        model="75V69H", quantity=5, amount=34650.0, billing_status="unbilled",
    )
    db_session.add(r)
    db_session.commit()
    db_session.refresh(r)
    return r


@pytest.fixture
def settlement(db_session, customer):
    s = CustomerStatement(
        customer_id=customer.id, period="202608", match_key="PON001",
        model="75V69H", quantity=5, amount=34650.0, status="unmatched",
    )
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


class TestManualMatch:
    def test_manual_match_creates_result_and_log(self, db_session, customer, receipt, settlement):
        result = CorrectionService.manual_match(
            customer_id=customer.id, period="202608",
            receipt_id=receipt.id, settlement_id=settlement.id, db=db_session,
        )
        assert result["success"] is True

        match = db_session.query(MatchResult).filter(
            MatchResult.receipt_id == receipt.id,
            MatchResult.statement_id == settlement.id,
        ).first()
        assert match is not None
        assert match.status == "manual"
        assert match.source == "manual"

        log = db_session.query(CorrectionLog).filter(
            CorrectionLog.result_id == match.id
        ).first()
        assert log is not None
        assert log.operation_type == "manual_match"

    def test_manual_match_removes_old_unmatched(self, db_session, customer, receipt, settlement):
        # 先有未匹配记录
        old = MatchResult(
            customer_id=customer.id, period="202608",
            receipt_id=receipt.id, statement_id=None,
            match_type="未匹配", status="unmatched",
        )
        db_session.add(old)
        db_session.commit()

        CorrectionService.manual_match(
            customer_id=customer.id, period="202608",
            receipt_id=receipt.id, settlement_id=settlement.id, db=db_session,
        )

        # 旧的未匹配记录应被删除
        remaining = db_session.query(MatchResult).filter(
            MatchResult.receipt_id == receipt.id, MatchResult.status == "unmatched"
        ).count()
        assert remaining == 0


class TestUnmatch:
    def test_unmatch_splits_into_two(self, db_session, customer, receipt, settlement):
        match = MatchResult(
            customer_id=customer.id, period="202608",
            receipt_id=receipt.id, statement_id=settlement.id,
            match_type="精确匹配", status="matched",
        )
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)

        result = CorrectionService.unmatch(
            customer_id=customer.id, period="202608",
            result_id=match.id, db=db_session,
        )
        assert result["success"] is True

        unmatched = db_session.query(MatchResult).filter(
            MatchResult.customer_id == customer.id, MatchResult.status == "unmatched"
        ).all()
        assert len(unmatched) == 2  # 我方一条 + 客户一条

    def test_unmatch_not_found(self, db_session, customer):
        result = CorrectionService.unmatch(
            customer_id=customer.id, period="202608",
            result_id=99999, db=db_session,
        )
        assert result["success"] is False


class TestIgnore:
    def test_ignore_marks_status(self, db_session, customer, settlement):
        match = MatchResult(
            customer_id=customer.id, period="202608",
            statement_id=settlement.id, receipt_id=None,
            match_type="未匹配", status="unmatched",
        )
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)

        result = CorrectionService.ignore(
            customer_id=customer.id, period="202608",
            result_id=match.id, db=db_session, reason="费用单据",
        )
        assert result["success"] is True

        db_session.refresh(match)
        assert match.status == "ignored"
        assert match.remark == "费用单据"


class TestAddNote:
    def test_add_note_appends(self, db_session, customer, receipt):
        match = MatchResult(
            customer_id=customer.id, period="202608",
            receipt_id=receipt.id, statement_id=None,
            match_type="未匹配", status="unmatched", remark="原始备注",
        )
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)

        result = CorrectionService.add_note(
            customer_id=customer.id, period="202608",
            result_id=match.id, remark="追加说明", db=db_session,
        )
        assert result["success"] is True

        db_session.refresh(match)
        assert "原始备注" in match.remark
        assert "追加说明" in match.remark
