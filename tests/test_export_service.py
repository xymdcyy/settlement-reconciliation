# Excel 导出服务测试

import io
from datetime import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Customer, Receipt
from app.services.export_service import ExportService


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
        name="潍坊百货",
        slug="weifangbaihuo",
        has_statement=False,
    )
    db_session.add(customer)
    db_session.commit()
    db_session.refresh(customer)
    return customer


@pytest.fixture
def sample_receipts(db_session, sample_customer):
    """创建测试台账数据"""
    receipts = []
    for i in range(10):
        receipt = Receipt(
            customer_id=sample_customer.id,
            period="202608",
            receipt_no=f"S101{i:010d}",
            model=f"75V69H",
            quantity=5 + i,
            amount=34650.00 + i * 100,
            unit_price=6930.00,
            receipt_date="2026-08-15",
            doc_type="普通销售单",
            customer_name="山东潍坊百货集团股份有限公司中百配送中心",
            nc_order_no=f"PON{i:015d}",
            product_line="智屏",
            billing_status="unbilled" if i % 2 == 0 else "billed",
            invoice_no=f"24932{i:010d}" if i % 2 == 1 else None,
            invoice_date="2026-08-20" if i % 2 == 1 else None,
            raw_data={
                "新方舟销售单号": f"S101{i:010d}",
                "产品型号": "75V69H",
                "签收数量": 5 + i,
                "签收金额": 34650.00 + i * 100,
                "单价": 6930.00,
                "签收日期/完成日期": "2026-08-15",
                "单据类型": "普通销售单",
                "结算客户名称": "山东潍坊百货集团股份有限公司中百配送中心",
                "NC订单号": f"PON{i:015d}",
                "产品线": "智屏",
            },
        )
        db_session.add(receipt)
        receipts.append(receipt)
    db_session.commit()
    return receipts


class TestExportReceipts:
    """测试台账导出"""

    def test_export_receipts_all(self, db_session, sample_customer, sample_receipts):
        """测试导出全部台账"""
        output = ExportService.export_receipts_to_excel(
            customer_id=sample_customer.id,
            db=db_session,
        )

        assert isinstance(output, io.BytesIO)
        assert output.getvalue() != b""

        # 验证 Excel 内容
        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 10
        assert "新方舟销售单号" in df.columns
        assert "产品型号" in df.columns
        assert "签收数量" in df.columns
        assert "签收金额" in df.columns

    def test_export_receipts_filtered_by_period(self, db_session, sample_customer, sample_receipts):
        """测试按期间筛选导出"""
        # 创建一个不同期间的记录
        receipt_other = Receipt(
            customer_id=sample_customer.id,
            period="202607",
            receipt_no="S1019999999999",
            model="75V69H",
            quantity=1,
            amount=6930.00,
            billing_status="unbilled",
            raw_data={},
        )
        db_session.add(receipt_other)
        db_session.commit()

        output = ExportService.export_receipts_to_excel(
            customer_id=sample_customer.id,
            db=db_session,
            period="202608",
        )

        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 10  # 只包含 202608 期间的记录

    def test_export_receipts_filtered_by_status(self, db_session, sample_customer, sample_receipts):
        """测试按状态筛选导出"""
        output = ExportService.export_receipts_to_excel(
            customer_id=sample_customer.id,
            db=db_session,
            billing_status="billed",
        )

        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 5  # 只有 5 条 billed 记录

    def test_export_receipts_filtered_by_search(self, db_session, sample_customer, sample_receipts):
        """测试按搜索关键词筛选导出"""
        output = ExportService.export_receipts_to_excel(
            customer_id=sample_customer.id,
            db=db_session,
            search="S1010000000001",
        )

        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 1
        assert df.iloc[0]["新方舟销售单号"] == "S1010000000001"

    def test_export_receipts_column_names_from_raw_data(self, db_session, sample_customer, sample_receipts):
        """测试导出的列名与原始台账一致（从 raw_data 提取）"""
        output = ExportService.export_receipts_to_excel(
            customer_id=sample_customer.id,
            db=db_session,
        )

        df = pd.read_excel(output, sheet_name=0)
        # 验证列名与 raw_data 的 key 一致
        expected_columns = list(sample_receipts[0].raw_data.keys())
        for col in expected_columns:
            assert col in df.columns

    def test_export_receipts_performance(self, db_session, sample_customer):
        """测试导出性能（1 万行 < 5 秒）"""
        # 创建 1 万条记录
        import time
        receipts = []
        for i in range(10000):
            receipt = Receipt(
                customer_id=sample_customer.id,
                period="202608",
                receipt_no=f"S101{i:010d}",
                model="75V69H",
                quantity=5,
                amount=34650.00,
                billing_status="unbilled",
                raw_data={"新方舟销售单号": f"S101{i:010d}", "产品型号": "75V69H"},
            )
            receipts.append(receipt)
        db_session.bulk_save_objects(receipts)
        db_session.commit()

        start_time = time.time()
        output = ExportService.export_receipts_to_excel(
            customer_id=sample_customer.id,
            db=db_session,
        )
        elapsed_time = time.time() - start_time

        assert elapsed_time < 5.0, f"导出 1 万行耗时 {elapsed_time:.2f} 秒，超过 5 秒"
        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 10000


class TestExportBillingList:
    """测试开票清单导出"""

    def test_export_billing_list(self, db_session, sample_customer, sample_receipts):
        """测试导出开票清单"""
        # 筛选未开票的记录
        receipt_ids = [r.id for r in sample_receipts if r.billing_status == "unbilled"]

        output = ExportService.export_billing_list_to_excel(
            receipt_ids=receipt_ids,
            db=db_session,
        )

        assert isinstance(output, io.BytesIO)
        assert output.getvalue() != b""

        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 5  # 5 条未开票记录
        assert "新方舟销售单号" in df.columns
        assert "产品型号" in df.columns
        assert "签收数量" in df.columns
        assert "签收金额" in df.columns

    def test_export_billing_list_empty(self, db_session, sample_customer):
        """测试导出空清单"""
        output = ExportService.export_billing_list_to_excel(
            receipt_ids=[],
            db=db_session,
        )

        assert isinstance(output, io.BytesIO)
        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 0


class TestExportRedFlushConfirmation:
    """测试红冲确认单导出"""

    def test_export_red_flush_confirmation(self, db_session, sample_customer, sample_receipts):
        """测试导出红冲确认单"""
        # 创建退货记录
        return_receipt = Receipt(
            customer_id=sample_customer.id,
            period="202608",
            receipt_no="S1019999999998",
            model="75V69H",
            quantity=-3,
            amount=-20790.00,
            unit_price=6930.00,
            billing_status="unbilled",
            raw_data={},
        )
        db_session.add(return_receipt)
        db_session.commit()

        # 匹配蓝票（已开票的记录）
        blue_receipts = [r for r in sample_receipts if r.billing_status == "billed"]
        matches = [
            {
                "return_receipt": return_receipt,
                "blue_receipt": blue_receipts[0],
            }
        ]

        output = ExportService.export_red_flush_confirmation_to_excel(
            matches=matches,
            db=db_session,
        )

        assert isinstance(output, io.BytesIO)
        assert output.getvalue() != b""

        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 1
        assert "退货单号" in df.columns
        assert "产品型号" in df.columns
        assert "退货数量" in df.columns
        assert "蓝票号" in df.columns
        assert "开票日期" in df.columns

    def test_export_red_flush_confirmation_empty(self, db_session, sample_customer):
        """测试导出空确认单"""
        output = ExportService.export_red_flush_confirmation_to_excel(
            matches=[],
            db=db_session,
        )

        assert isinstance(output, io.BytesIO)
        df = pd.read_excel(output, sheet_name=0)
        assert len(df) == 0
