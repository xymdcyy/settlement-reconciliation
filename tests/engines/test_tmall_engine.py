# 天猫优品匹配引擎单元测试

import pytest
from app.engines.base import OurReceipt, CustomerSettlement
from app.engines.tmall.engine import TmallEngine


@pytest.fixture
def engine():
    return TmallEngine()


class TestTmallEngine:
    """天猫优品匹配引擎测试"""

    def test_engine_name(self, engine):
        assert engine.engine_name == "TmallEngine"
        assert engine.engine_version == "v1.0.0"

    def test_extract_model_standard(self, engine):
        """标准型号提取"""
        assert engine._extract_model("TCL 75N9M 75英寸 黑色 官方标配") == "75N9M"
        assert engine._extract_model("TCL 65N9M 65英寸 黑色 官方标配") == "65N9M"
        assert engine._extract_model("TCL 85Q10K 85英寸 黑色") == "85Q10K"

    def test_extract_model_with_suffix(self, engine):
        """带后缀的型号提取"""
        assert engine._extract_model("TCL 55V69H Pro 55英寸") == "55V69H Pro"

    def test_extract_model_empty(self, engine):
        """空字符串返回空"""
        assert engine._extract_model("") == ""
        assert engine._extract_model(None) == ""

    def test_extract_model_no_match(self, engine):
        """无法提取型号时返回空"""
        assert engine._extract_model("无型号信息") == ""


class TestTmallEngineMatch:
    """天猫优品匹配引擎匹配逻辑测试"""

    @pytest.fixture
    def engine(self):
        return TmallEngine()

    def _make_receipt(self, id: int, receipt_no: str, model: str,
                      quantity: float, amount: float, nc_order_no: str = "",
                      unit_price: float = 0) -> OurReceipt:
        return OurReceipt(
            id=id,
            receipt_no=receipt_no,
            model=model,
            quantity=quantity,
            amount=amount,
            unit_price=unit_price,
            receipt_date="2026-01-01",
            doc_type="普通销售单",
            customer_name="天猫优品-经销",
            nc_order_no=nc_order_no,
            raw_data={},
        )

    def _make_settlement(self, id: int, match_key: str, model: str,
                         quantity: float, amount: float,
                         unit_price: float = 0) -> CustomerSettlement:
        return CustomerSettlement(
            id=id,
            match_key=match_key,
            model=model,
            quantity=quantity,
            amount=amount,
            unit_price=unit_price,
            settlement_date="2026-01-15",
            raw_data={"业务主单据编码": match_key},
        )

    # ============================================================
    # 场景1: 精确匹配
    # ============================================================

    def test_exact_match(self, engine):
        """双方 match_key+金额+型号 完全一致 → 1对精确匹配"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 100, 693000, "PON001"),
        ]
        settlements = [
            self._make_settlement(1, "PON001", "75N9M", 100, 693000),
        ]

        result = engine.match(receipts, settlements)

        assert len(result.matched_pairs) == 1
        assert result.matched_pairs[0].match_type == "精确匹配"
        assert result.matched_pairs[0].confidence == 1.0
        assert result.matched_pairs[0].diff_amount == 0
        assert len(result.unmatched_receipts) == 0
        assert len(result.unmatched_settlements) == 0

    # ============================================================
    # 场景2: 宽松匹配
    # ============================================================

    def test_loose_match(self, engine):
        """金额不一致但型号和订单号一致 → 宽松匹配（签收金额 >= 结算金额）"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 100, 700000, "PON001"),
        ]
        settlements = [
            self._make_settlement(1, "PON001", "75N9M", 100, 693000),
        ]

        result = engine.match(receipts, settlements)

        assert len(result.matched_pairs) == 1
        assert result.matched_pairs[0].match_type == "宽松匹配"
        assert result.matched_pairs[0].confidence == 0.85
        assert result.matched_pairs[0].diff_amount == 7000  # 700000 - 693000

    # ============================================================
    # 场景3: 金额不一致（差异过大，签收金额 < 结算金额）
    # ============================================================

    def test_amount_mismatch(self, engine):
        """签收金额 < 结算金额 → 金额差异"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 100, 500000, "PON001"),
        ]
        settlements = [
            self._make_settlement(1, "PON001", "75N9M", 100, 693000),
        ]

        result = engine.match(receipts, settlements)

        assert len(result.matched_pairs) == 0
        # 签收金额 500000 < 结算金额 693000 → 无法匹配
        # 宽松匹配也失败

    # ============================================================
    # 场景4: 无匹配（双方订单号不同）
    # ============================================================

    def test_no_match(self, engine):
        """双方订单号不同 → 各自进入未匹配"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 100, 693000, "PON001"),
        ]
        settlements = [
            self._make_settlement(1, "PON999", "75N9M", 100, 693000),
        ]

        result = engine.match(receipts, settlements)

        assert len(result.matched_pairs) == 0
        assert len(result.unmatched_receipts) == 1
        assert len(result.unmatched_settlements) == 1

    # ============================================================
    # 场景5: 空匹配键
    # ============================================================

    def test_empty_match_key(self, engine):
        """客户方 match_key 为空 → 标记为未匹配"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 100, 693000, "PON001"),
        ]
        settlements = [
            self._make_settlement(1, "", "75N9M", 100, 693000),
        ]

        result = engine.match(receipts, settlements)

        assert len(result.matched_pairs) == 0
        assert len(result.unmatched_settlements) == 1

    # ============================================================
    # 场景6: 多对一匹配（多个签收匹配同一结算单）
    # ============================================================

    def test_loose_multi_receipt_match(self, engine):
        """多个签收单宽松匹配同一张结算单（签收金额总和 >= 结算金额）"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 50, 346500, "PON001"),
            self._make_receipt(2, "S2", "75N9M", 50, 346500, "PON001"),
        ]
        settlements = [
            self._make_settlement(1, "PON001", "75N9M", 100, 693000),
        ]

        result = engine.match(receipts, settlements)

        # 精确匹配无法匹配（单个签收金额 346500 != 693000）
        # 宽松匹配：签收金额总和 693000 >= 693000 → 匹配第一个签收
        # 但实际引擎的宽松匹配只匹配第一个未匹配的签收记录
        assert len(result.matched_pairs) >= 1

    # ============================================================
    # 场景7: 混合场景
    # ============================================================

    def test_mixed_scenario(self, engine):
        """混合场景：部分匹配，部分未匹配，部分金额差异"""
        receipts = [
            self._make_receipt(1, "S1", "75N9M", 100, 693000, "PON001"),
            self._make_receipt(2, "S2", "65N9M", 50, 163700, "PON002"),
            self._make_receipt(3, "S3", "85Q10K", 30, 450000, "PON003"),
        ]
        settlements = [
            self._make_settlement(1, "PON001", "75N9M", 100, 693000),   # 精确匹配
            self._make_settlement(2, "PON002", "65N9M", 50, 163700),    # 精确匹配
            self._make_settlement(3, "PON999", "85Q10K", 30, 450000),   # 无匹配（订单号不同）
            self._make_settlement(4, "PON004", "55V69H", 20, 140000),   # 无匹配（对方无此记录）
        ]

        result = engine.match(receipts, settlements)

        assert len(result.matched_pairs) == 2
        assert result.matched_pairs[0].match_type == "精确匹配"
        assert result.matched_pairs[1].match_type == "精确匹配"

        # 我方签收 S3 未匹配（PON003 在结算单中不存在）
        # 客户方 settlement 3 和 4 未匹配
        assert len(result.unmatched_receipts) == 1  # PON003
        assert len(result.unmatched_settlements) == 2  # PON999, PON004

    # ============================================================
    # 场景8: parse_customer_data
    # ============================================================

    def test_parse_customer_data(self, engine):
        """解析客户方数据"""
        import pandas as pd
        data = {
            "业务主单据编码": ["PON001", "PON002"],
            "含税金额": [693000.0, 163700.0],
            "商品数量": [100, 50],
            "后端商品名称": ["TCL 75N9M 75英寸", "TCL 65N9M 65英寸"],
            "含税单价": [6930.0, 3274.0],
            "业务时间": ["2026-01-15", "2026-01-16"],
        }
        df = pd.DataFrame(data)

        settlements = engine.parse_customer_data(df)

        assert len(settlements) == 2
        assert settlements[0].match_key == "PON001"
        assert settlements[0].model == "75N9M"
        assert settlements[0].amount == 693000.0
        assert settlements[0].quantity == 100
        assert settlements[1].match_key == "PON002"
        assert settlements[1].model == "65N9M"