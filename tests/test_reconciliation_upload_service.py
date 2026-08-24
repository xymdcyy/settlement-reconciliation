# 对账单上传服务测试

import io
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.engines import register_engine
from app.engines.base import CustomerSettlement as EngineSettlement
from app.engines.base import MatchEngine, MatchResult, OurReceipt
from app.models import Customer, CustomerStatement
from app.services.reconciliation_upload_service import ReconciliationUploadService


# 创建测试引擎
class TestEngine(MatchEngine):
    """测试引擎"""

    def parse_customer_data(self, raw_df):
        """解析客户对账单"""
        settlements = []
        for idx, row in raw_df.iterrows():
            settlements.append(EngineSettlement(
                id=idx,
                match_key=str(row.get("业务主单据编码", "")),
                model=str(row.get("后端商品名称", "")),
                quantity=float(row.get("数量", 0)),
                amount=float(row.get("金额", 0)),
                unit_price=float(row.get("单价", 0)),
                settlement_date=str(row.get("日期", "")),
                raw_data=row.to_dict(),
            ))
        return settlements

    def match(self, our_receipts, customer_settlements):
        """执行匹配"""
        return MatchResult(
            matched_pairs=[],
            unmatched_receipts=[],
            unmatched_settlements=[],
            excluded_settlements=[],
            engine_version="v1.0.0",
            summary={},
        )


@pytest.fixture
def db_session():
    """创建测试数据库会话"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_customer(db_session):
    """创建测试客户"""
    customer = Customer(
        name="天猫优品",
        slug="tmall",
        has_statement=True,
        engine_name="test",
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)

    # 注册测试引擎
    register_engine(customer.id, "tests.test_reconciliation_upload_service", "TestEngine")

    return customer


@pytest.fixture
def sample_excel_file():
    """创建测试 Excel 文件"""
    df = pd.DataFrame({
        "业务主单据编码": ["PON26051857021704336", "PON26051857021704337", "PON26051857021704338"],
        "后端商品名称": ["75V69H", "75V69H", "85X11K"],
        "数量": [5, 3, 2],
        "金额": [34650.00, 20790.00, 17000.00],
        "单价": [6930.00, 6930.00, 8500.00],
        "日期": ["2026-08-15", "2026-08-16", "2026-08-17"],
    })

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="对账单", index=False)
    output.seek(0)
    return output.getvalue()


class TestUploadStatement:
    """测试上传对账单"""

    def test_upload_statement_success(self, db_session, sample_customer, sample_excel_file):
        """测试成功上传对账单"""
        result = ReconciliationUploadService.upload_statement(
            customer_id=sample_customer.id,
            period="202608",
            file_content=sample_excel_file,
            db=db_session,
        )

        assert result["status"] == "success"
        assert result["parsed_count"] == 3
        assert "成功解析 3 条记录" in result["message"]

        # 验证数据库中的记录
        statements = db_session.query(CustomerStatement).filter(
            CustomerStatement.customer_id == sample_customer.id,
            CustomerStatement.period == "202608",
        ).all()

        assert len(statements) == 3
        assert statements[0].match_key == "PON26051857021704336"
        assert statements[0].model == "75V69H"
        assert statements[0].quantity == 5
        assert statements[0].status == "pending"

    def test_upload_statement_no_engine(self, db_session):
        """测试客户没有配置引擎"""
        customer = Customer(
            name="无引擎客户",
            slug="no-engine",
            has_statement=False,
        )
        db_session.add(customer)
        db_session.commit()
        db_session.refresh(customer)

        with pytest.raises(ValueError):  # 不指定具体的错误消息
            ReconciliationUploadService.upload_statement(
                customer_id=customer.id,
                period="202608",
                file_content=b"fake excel content",
                db=db_session,
            )

    def test_upload_statement_invalid_excel(self, db_session, sample_customer):
        """测试上传无效的 Excel 文件"""
        with pytest.raises(ValueError):  # 不指定具体的错误消息
            ReconciliationUploadService.upload_statement(
                customer_id=sample_customer.id,
                period="202608",
                file_content=b"invalid excel content",
                db=db_session,
            )

    def test_upload_statement_empty_excel(self, db_session, sample_customer):
        """测试上传空的 Excel 文件"""
        # 创建空的 Excel 文件
        df = pd.DataFrame()
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="对账单", index=False)
        output.seek(0)

        result = ReconciliationUploadService.upload_statement(
            customer_id=sample_customer.id,
            period="202608",
            file_content=output.getvalue(),
            db=db_session,
        )

        assert result["status"] == "success"
        assert result["parsed_count"] == 0

    def test_upload_statement_batch_id(self, db_session, sample_customer, sample_excel_file):
        """测试批次 ID 生成"""
        result = ReconciliationUploadService.upload_statement(
            customer_id=sample_customer.id,
            period="202608",
            file_content=sample_excel_file,
            db=db_session,
        )

        # 验证批次 ID 格式
        statements = db_session.query(CustomerStatement).filter(
            CustomerStatement.customer_id == sample_customer.id,
            CustomerStatement.period == "202608",
        ).all()

        assert all(s.batch_id is not None for s in statements)
        assert all(s.batch_id.startswith("upload-202608-") for s in statements)

    def test_upload_statement_replace_existing(self, db_session, sample_customer, sample_excel_file):
        """测试重复上传时替换现有记录"""
        # 第一次上传
        ReconciliationUploadService.upload_statement(
            customer_id=sample_customer.id,
            period="202608",
            file_content=sample_excel_file,
            db=db_session,
        )

        # 第二次上传（相同的 Excel）
        result = ReconciliationUploadService.upload_statement(
            customer_id=sample_customer.id,
            period="202608",
            file_content=sample_excel_file,
            db=db_session,
        )

        # 验证只有一批记录（旧记录被删除）
        statements = db_session.query(CustomerStatement).filter(
            CustomerStatement.customer_id == sample_customer.id,
            CustomerStatement.period == "202608",
        ).all()

        assert len(statements) == 3  # 只有新上传的记录
