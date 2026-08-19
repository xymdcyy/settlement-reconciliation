# 测试：模型创建

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    Customer,
    OurReceipt,
    CustomerSettlement,
    MatchResult,
    CorrectionLog,
    EngineConfig,
)


@pytest.fixture
def db_session():
    """创建内存 SQLite 数据库测试会话"""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


class TestModels:
    """数据库模型测试"""

    def test_create_customer(self, db_session):
        customer = Customer(name="天猫优品经销", slug="tmall-jingxiao", description="天猫优品经销模式")
        db_session.add(customer)
        db_session.commit()
        assert customer.id is not None
        assert customer.name == "天猫优品经销"
        assert customer.slug == "tmall-jingxiao"
        assert customer.is_active is True

    def test_create_our_receipt(self, db_session):
        customer = Customer(name="天猫优品经销", slug="tmall-jingxiao")
        db_session.add(customer)
        db_session.commit()

        receipt = OurReceipt(
            receipt_no="S1010260104000001",
            customer_id=customer.id,
            period="202601",
            model="75V69H",
            quantity=100,
            amount=693000.0,
            receipt_date="2026-01-04",
            doc_type="普通销售单",
            customer_name="天猫优品-经销",
            nc_order_no="PON2601010000001",
            raw_data={"test": "data"},
        )
        db_session.add(receipt)
        db_session.commit()
        assert receipt.id is not None
        assert receipt.receipt_no == "S1010260104000001"

    def test_create_customer_settlement(self, db_session):
        customer = Customer(name="天猫优品经销", slug="tmall-jingxiao")
        db_session.add(customer)
        db_session.commit()

        settlement = CustomerSettlement(
            customer_id=customer.id,
            period="202601",
            match_key="PON2601010000001",
            model="75V69H",
            quantity=100,
            amount=693000.0,
            raw_data={"业务主单据编码": "PON2601010000001"},
        )
        db_session.add(settlement)
        db_session.commit()
        assert settlement.id is not None
        assert settlement.match_key == "PON2601010000001"

    def test_create_match_result(self, db_session):
        customer = Customer(name="天猫优品经销", slug="tmall-jingxiao")
        db_session.add(customer)
        db_session.commit()

        receipt = OurReceipt(receipt_no="S1", customer_id=customer.id, period="202601")
        db_session.add(receipt)
        db_session.commit()

        settlement = CustomerSettlement(customer_id=customer.id, period="202601")
        db_session.add(settlement)
        db_session.commit()

        result = MatchResult(
            customer_id=customer.id,
            period="202601",
            receipt_id=receipt.id,
            settlement_id=settlement.id,
            match_type="凭证精确匹配",
            confidence=1.0,
            status="matched",
            source="auto",
            diff_amount=0.0,
        )
        db_session.add(result)
        db_session.commit()
        assert result.id is not None
        assert result.status == "matched"

    def test_create_correction_log(self, db_session):
        log = CorrectionLog(
            customer_id=1,
            period="202601",
            operation_type="manual_match",
            before_data={"status": "unmatched"},
            after_data={"status": "manual"},
            reason="人工确认匹配",
            operator_id=1,
        )
        db_session.add(log)
        db_session.commit()
        assert log.id is not None
        assert log.operation_type == "manual_match"

    def test_create_engine_config(self, db_session):
        customer = Customer(name="天猫优品经销", slug="tmall-jingxiao")
        db_session.add(customer)
        db_session.commit()

        config = EngineConfig(
            customer_id=customer.id,
            engine_name="TmallEngine",
            engine_version="v1.0.0",
            config_params={"threshold": 0.95},
        )
        db_session.add(config)
        db_session.commit()
        assert config.id is not None
        assert config.engine_name == "TmallEngine"

    def test_customer_relations(self, db_session):
        """测试客户与关联表的关系"""
        customer = Customer(name="天猫优品经销", slug="tmall-jingxiao")
        db_session.add(customer)
        db_session.commit()

        receipt = OurReceipt(receipt_no="S1", customer_id=customer.id, period="202601")
        db_session.add(receipt)
        db_session.commit()

        # 通过关系反向查询
        assert len(customer.receipts) == 1
        assert customer.receipts[0].receipt_no == "S1"