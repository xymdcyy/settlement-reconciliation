# 测试：匹配调度服务 + 手动纠正服务

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.engines import register_engine
from app.models import (
    CorrectionLog,
    Customer,
    CustomerSettlement,
    MatchResult,
    OurReceipt,
)
from app.services.correction_service import CorrectionService
from app.services.match_service import MatchService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def customer(db_session):
    c = Customer(name="TMALL-USER", slug="tmall-jingxiao")
    db_session.add(c)
    db_session.commit()
    return c


@pytest.fixture
def test_data(db_session, customer):
    """创建测试数据"""
    # 注册引擎（使用模板引擎简化测试）
    register_engine(customer.id, "app.engines.template.engine", "TemplateEngine")

    # 我方签收记录
    r1 = OurReceipt(receipt_no="S1", customer_id=customer.id, period="202601",
                    model="75N9M", quantity=100, amount=693000.0,
                    nc_order_no="PON001")
    r2 = OurReceipt(receipt_no="S2", customer_id=customer.id, period="202601",
                    model="65N9M", quantity=50, amount=163700.0,
                    nc_order_no="PON002")
    r3 = OurReceipt(receipt_no="S3", customer_id=customer.id, period="202601",
                    model="85Q10K", quantity=30, amount=450000.0,
                    nc_order_no="PON003")
    db_session.add_all([r1, r2, r3])

    # 客户方结算单
    s1 = CustomerSettlement(customer_id=customer.id, period="202601",
                            match_key="PON001", model="75N9M",
                            quantity=100, amount=693000.0)
    s2 = CustomerSettlement(customer_id=customer.id, period="202601",
                            match_key="PON002", model="65N9M",
                            quantity=50, amount=163700.0)
    s3 = CustomerSettlement(customer_id=customer.id, period="202601",
                            match_key="PON999", model="85Q10K",
                            quantity=30, amount=450000.0)
    db_session.add_all([s1, s2, s3])
    db_session.commit()

    return {"customer": customer, "receipts": [r1, r2, r3], "settlements": [s1, s2, s3]}


class TestMatchService:

    def test_run_match(self, db_session, test_data):
        """运行匹配，结果正确存入数据库"""
        result = MatchService.run(test_data["customer"].id, "202601", db_session)

        assert result["status"] == "completed"
        assert result["summary"]["matched_count"] >= 2
        assert result["summary"]["match_rate"] > 0

        # 验证数据库中有匹配结果
        matches = db_session.query(MatchResult).all()
        assert len(matches) > 0

    def test_run_without_receipts(self, db_session, customer):
        """无我方数据时跳过"""
        result = MatchService.run(customer.id, "202601", db_session)
        assert result["status"] == "skipped"
        assert "无我方签收记录" in result["message"]

    def test_run_without_settlements(self, db_session, customer):
        """无客户方数据时跳过"""
        r = OurReceipt(receipt_no="S1", customer_id=customer.id, period="202601",
                       model="75N9M", quantity=100, amount=693000.0)
        db_session.add(r)
        db_session.commit()

        result = MatchService.run(customer.id, "202601", db_session)
        assert result["status"] == "skipped"
        assert "无客户方结算单" in result["message"]

    def test_get_summary(self, db_session, test_data):
        """获取统计摘要"""
        # 先运行匹配
        MatchService.run(test_data["customer"].id, "202601", db_session)

        summary = MatchService.get_summary(test_data["customer"].id, "202601", db_session)
        assert summary["matched_count"] >= 2
        assert summary["match_rate"] > 0

    def test_match_rate_is_settlement_driven(self, db_session, customer):
        """匹配率以结算单为口径：我方笔数远多于结算单时，全部结算单匹配即 100%。

        回归测试：旧实现用“我方签收笔数”作分母（此处 2/5=40%），
        会把匹配率严重低估；正确口径为 已匹配结算单/结算单总数 = 2/2 = 100%。
        """
        register_engine(customer.id, "app.engines.template.engine", "TemplateEngine")

        # 5 笔我方签收，仅 2 笔能对上结算单
        for i, pon in enumerate(["PON001", "PON002", "PONX1", "PONX2", "PONX3"], start=1):
            db_session.add(OurReceipt(receipt_no=f"S{i}", customer_id=customer.id,
                                      period="202607", model="75N9M", quantity=1,
                                      amount=100.0, nc_order_no=pon))
        # 2 笔结算单，均可匹配
        db_session.add(CustomerSettlement(customer_id=customer.id, period="202607",
                                          match_key="PON001", model="75N9M",
                                          quantity=1, amount=100.0))
        db_session.add(CustomerSettlement(customer_id=customer.id, period="202607",
                                          match_key="PON002", model="75N9M",
                                          quantity=1, amount=100.0))
        db_session.commit()

        result = MatchService.run(customer.id, "202607", db_session)
        assert result["summary"]["matched_count"] == 2
        assert result["summary"]["unmatched_receipts"] == 3
        assert result["summary"]["match_rate"] == 100.0  # 2/2，而非旧口径 2/5=40%

        summary = MatchService.get_summary(customer.id, "202607", db_session)
        assert summary["match_rate"] == 100.0

    def test_get_results(self, db_session, test_data):
        """查询匹配结果"""
        MatchService.run(test_data["customer"].id, "202601", db_session)

        results = MatchService.get_results(test_data["customer"].id, "202601", db_session)
        assert results["total"] > 0
        assert len(results["items"]) > 0
        assert results["items"][0]["receipt"] is not None or results["items"][0]["settlement"] is not None

    def test_get_results_with_status_filter(self, db_session, test_data):
        """按状态筛选"""
        MatchService.run(test_data["customer"].id, "202601", db_session)

        matched = MatchService.get_results(test_data["customer"].id, "202601",
                                           db_session, status_filter="matched")
        assert matched["total"] >= 2

        unmatched = MatchService.get_results(test_data["customer"].id, "202601",
                                             db_session, status_filter="unmatched")
        assert unmatched["total"] >= 1


class TestCorrectionService:

    @pytest.fixture(autouse=True)
    def setup(self, db_session, test_data):
        self.customer_id = test_data["customer"].id
        self.period = "202601"
        self.db = db_session
        self.receipts = test_data["receipts"]
        self.settlements = test_data["settlements"]
        # 先运行匹配
        MatchService.run(self.customer_id, self.period, self.db)

    def test_manual_match(self):
        """手动匹配一对记录"""
        # 找一个未匹配的
        results = MatchService.get_results(self.customer_id, self.period, self.db,
                                           status_filter="unmatched")
        unmatched = [r for r in results["items"] if r["receipt"] and r["settlement"] is None]
        if not unmatched:
            return  # 没有可匹配的

        r = unmatched[0]
        result = CorrectionService.manual_match(
            customer_id=self.customer_id,
            period=self.period,
            receipt_id=r["receipt"]["id"],
            settlement_id=self.settlements[2].id,  # PON999
            db=self.db,
            reason="人工匹配测试",
        )
        assert result["success"] is True
        assert result["result_id"] is not None

        # 验证数据库
        match = self.db.query(MatchResult).filter(MatchResult.id == result["result_id"]).first()
        assert match is not None
        assert match.status == "manual"
        assert match.source == "manual"

        # 验证审计日志
        logs = self.db.query(CorrectionLog).all()
        assert len(logs) >= 1
        assert logs[-1].operation_type == "manual_match"

    def test_unmatch(self):
        """解除匹配"""
        # 找一个已匹配的
        results = MatchService.get_results(self.customer_id, self.period, self.db,
                                           status_filter="matched")
        if not results["items"]:
            return

        result_id = results["items"][0]["id"]
        result = CorrectionService.unmatch(
            customer_id=self.customer_id,
            period=self.period,
            result_id=result_id,
            db=self.db,
            reason="解除匹配测试",
        )
        assert result["success"] is True

        # 验证审计日志
        logs = self.db.query(CorrectionLog).filter(
            CorrectionLog.operation_type == "unmatch"
        ).all()
        assert len(logs) >= 1

    def test_ignore(self):
        """标记忽略"""
        results = MatchService.get_results(self.customer_id, self.period, self.db,
                                           status_filter="unmatched")
        if not results["items"]:
            return

        result_id = results["items"][0]["id"]
        result = CorrectionService.ignore(
            customer_id=self.customer_id,
            period=self.period,
            result_id=result_id,
            db=self.db,
            reason="费用单据，不参与对账",
        )
        assert result["success"] is True

        # 验证状态更新
        match = self.db.query(MatchResult).filter(MatchResult.id == result_id).first()
        assert match.status == "ignored"

    def test_add_note(self):
        """添加备注"""
        results = MatchService.get_results(self.customer_id, self.period, self.db)
        if not results["items"]:
            return

        result_id = results["items"][0]["id"]
        result = CorrectionService.add_note(
            customer_id=self.customer_id,
            period=self.period,
            result_id=result_id,
            db=self.db,
            remark="需要人工确认",
        )
        assert result["success"] is True

        # 验证备注已更新
        match = self.db.query(MatchResult).filter(MatchResult.id == result_id).first()
        assert match.remark is not None
        assert "需要人工确认" in match.remark

    def test_correction_logs_audit(self):
        """所有手动操作记录审计日志"""
        # 执行多个操作
        results = MatchService.get_results(self.customer_id, self.period, self.db,
                                           status_filter="unmatched")
        if results["items"]:
            CorrectionService.ignore(
                customer_id=self.customer_id, period=self.period,
                result_id=results["items"][0]["id"], db=self.db, reason="忽略",
            )

        # 检查审计日志
        logs = self.db.query(CorrectionLog).all()
        assert len(logs) >= 1

        # 验证日志字段
        log = logs[0]
        assert log.operation_type is not None
        assert log.before_data is not None
        assert log.after_data is not None