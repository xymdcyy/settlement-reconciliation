# 测试：上传服务

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Customer
from app.services.upload_service import UploadService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def sample_customer(db_session):
    customer = Customer(name="TMALL-USER", slug="tmall-jingxiao", description="天猫优品经销")
    db_session.add(customer)
    db_session.commit()
    return customer


def _create_excel(data: dict) -> str:
    """创建临时 Excel 文件，返回路径"""
    import time
    df = pd.DataFrame(data)
    tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
    tmp.close()
    df.to_excel(tmp.name, index=False)
    # 等待文件释放
    time.sleep(0.1)
    return tmp.name


class TestUploadService:

    def test_parse_our_receipts_empty(self, db_session):
        """空文件返回正确统计"""
        df = pd.DataFrame()
        tmp = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
        tmp.close()
        df.to_excel(tmp.name, index=False)

        result = UploadService.parse_our_receipts(Path(tmp.name), "202601", db_session)

        assert result["total"] == 0
        assert "Excel" in result["message"]
        os.unlink(tmp.name)

    def test_parse_our_receipts_with_customer(self, db_session, sample_customer):
        """有客户匹配时，记录分配到对应客户"""
        f = _create_excel({
            "新方舟销售单号": ["S1", "S2"],
            "产品型号": ["75V69H", "65N9M"],
            "签收数量": [100, 50],
            "签收金额": [693000.0, 163700.0],
            "单价": [6930.0, 3274.0],
            "签收日期/完成日期": ["2026-01-04", "2026-01-05"],
            "单据类型": ["普通销售单", "普通销售单"],
            "结算客户名称": ["TMALL-USER", "TMALL-USER"],
            "NC订单号": ["PON001", "PON002"],
        })

        result = UploadService.parse_our_receipts(Path(f), "202601", db_session)

        assert result["total"] == 2
        assert "TMALL-USER" in result["assigned_to_customers"]
        assert result["assigned_to_customers"]["TMALL-USER"] == 2
        assert result["unassigned"] == 0
        os.unlink(f)

    def test_parse_our_receipts_unassigned(self, db_session):
        """无匹配客户时，记录标记为未分配"""
        f = _create_excel({
            "新方舟销售单号": ["S1"],
            "结算客户名称": ["UNKNOWN-CUSTOMER"],
            "产品型号": ["75V69H"],
            "签收数量": [100],
            "签收金额": [693000.0],
        })

        result = UploadService.parse_our_receipts(Path(f), "202601", db_session)

        assert result["total"] == 1
        assert result["unassigned"] == 1
        assert len(result["assigned_to_customers"]) == 0
        os.unlink(f)

    def test_save_uploaded_file(self):
        """保存上传文件到本地"""
        class MockFile:
            filename = "test.xlsx"
            file = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)
            file.write(b"test content")
            file.seek(0)

        path = UploadService.save_uploaded_file(MockFile(), 1, "202601")
        assert path.exists()
        assert path.parent.name == "202601"
        assert path.parent.parent.name == "1"
        assert path.suffix == ".xlsx"
        os.unlink(path)
        MockFile.file.close()

    def test_our_receipts_stored_in_db(self, db_session, sample_customer):
        """我方签收记录正确存入数据库"""
        f = _create_excel({
            "新方舟销售单号": ["S1010260104000001"],
            "产品型号": ["75V69H"],
            "签收数量": [100],
            "签收金额": [693000.0],
            "单价": [6930.0],
            "签收日期/完成日期": ["2026-01-04"],
            "单据类型": ["普通销售单"],
            "结算客户名称": ["TMALL-USER"],
            "NC订单号": ["PON001"],
        })

        UploadService.parse_our_receipts(Path(f), "202601", db_session)

        from app.models import OurReceipt
        receipts = db_session.query(OurReceipt).all()
        assert len(receipts) == 1
        assert receipts[0].receipt_no == "S1010260104000001"
        assert receipts[0].model == "75V69H"
        assert receipts[0].quantity == 100
        assert receipts[0].amount == 693000.0
        assert receipts[0].customer_id == sample_customer.id
        assert receipts[0].period == "202601"
        os.unlink(f)


class TestResolveCustomerId:
    """客户归属解析：精确匹配 + 关键词匹配 + 歧义保护"""

    def test_exact_name_match(self):
        c = Customer(id=1, name="天猫优品经销", slug="tmall")
        assert UploadService._resolve_customer_id("天猫优品经销", [c]) == 1

    def test_keyword_match_branch_legal_name(self):
        """分公司法人全称含全部关键词时归属该客户（核心修复场景）"""
        c = Customer(id=7, name="天猫优品经销", slug="tmall",
                     match_keywords=["天猫优品", "经销"])
        name = "张家口天猫优品电子商务有限公司-经销"
        assert UploadService._resolve_customer_id(name, [c]) == 7

    def test_keyword_requires_all_keywords(self):
        """仅命中部分关键词不归属（如缺少“经销”，避免误配直营实体）"""
        c = Customer(id=7, name="天猫优品经销", slug="tmall",
                     match_keywords=["天猫优品", "经销"])
        assert UploadService._resolve_customer_id("北京天猫优品电子商务有限公司-直营", [c]) is None

    def test_ambiguous_keyword_hit_returns_none(self):
        """关键词命中多个客户视为歧义，不分配"""
        c1 = Customer(id=1, name="天猫优品经销", slug="a", match_keywords=["天猫优品"])
        c2 = Customer(id=2, name="天猫优品直营", slug="b", match_keywords=["天猫优品"])
        assert UploadService._resolve_customer_id("张家口天猫优品有限公司", [c1, c2]) is None

    def test_empty_name_returns_none(self):
        c = Customer(id=1, name="天猫优品经销", slug="tmall", match_keywords=["天猫优品", "经销"])
        assert UploadService._resolve_customer_id("", [c]) is None

    def test_no_keywords_no_exact_returns_none(self):
        c = Customer(id=1, name="天猫优品经销", slug="tmall")  # 无关键词
        assert UploadService._resolve_customer_id("张家口天猫优品电子商务有限公司-经销", [c]) is None

    def test_parse_our_receipts_assigns_by_keyword(self, db_session):
        """集成：通过关键词把分公司法人名的明细分配到客户"""
        customer = Customer(name="天猫优品经销", slug="tmall",
                            match_keywords=["天猫优品", "经销"])
        db_session.add(customer)
        db_session.commit()

        legal_name = "张家口天猫优品电子商务有限公司-经销"
        f = _create_excel({
            "新方舟销售单号": ["S1", "S2"],
            "产品型号": ["75V69H", "65N9M"],
            "签收数量": [100, 50],
            "签收金额": [693000.0, 163700.0],
            "结算客户名称": [legal_name, legal_name],
            "NC订单号": ["PON001", "PON002"],
        })

        result = UploadService.parse_our_receipts(Path(f), "202607", db_session)
        assert result["total"] == 2
        assert result["unassigned"] == 0
        assert result["assigned_to_customers"].get(legal_name) == 2

        from app.models import OurReceipt
        assert all(r.customer_id == customer.id for r in db_session.query(OurReceipt).all())
        os.unlink(f)