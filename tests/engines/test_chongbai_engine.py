# 重百引擎单元测试

import pandas as pd
import pytest

from app.engines.chongbai.engine import (
    ChongbaiEngine,
    _MatchEngine,
    preprocess_qianshou,
)
from app.engines.chongbai.classifiers import ProjectClassifier, RemarkClassifier
from app.engines.chongbai.extractors import (
    SampleSaleExtractor,
    StoreExtractor,
    VoucherExtractor,
)


class TestVoucherExtractor:
    """采购凭证提取"""

    def test_pure_digital(self):
        assert VoucherExtractor.extract("4534720056", "纯数字") == "4534720056"

    def test_standard_format(self):
        # 店-人 凭证/单号，取 / 前的 10 位凭证
        assert VoucherExtractor.extract("北碚二店-冯芝江 4702259416/8800917937", "标准格式") == "4702259416"

    def test_shouhuoma_store_prefix(self):
        assert VoucherExtractor.extract("渝北店4701578322", "收货码") == "4701578322"

    def test_invalid_prefix_rejected(self):
        # 8800 开头为新方舟单号，不是采购凭证
        assert VoucherExtractor.extract("8800123456", "纯数字") is None

    def test_validate_prefix(self):
        assert VoucherExtractor.validate("4534720056") is True
        assert VoucherExtractor.validate("1234567890") is False
        assert VoucherExtractor.validate("453472005") is False  # 9 位

    def test_extract_all_multi(self):
        got = VoucherExtractor.extract_all("4534987056/4534987054", "其他")
        assert got == ["4534987056", "4534987054"]

    def test_phone_number_excluded(self):
        # 11 位手机号不应被当作凭证
        assert VoucherExtractor.extract("13883279911", "其他") is None


class TestStoreExtractor:
    def test_alias_match(self):
        assert StoreExtractor.match_stores("重庆重百商社电器有限公司沙坪坝中心店", "沙坪坝") is True

    def test_contain_match(self):
        assert StoreExtractor.match_stores("渝北店", "渝北重百") is True


class TestRemarkClassifier:
    def test_feiyong(self):
        assert RemarkClassifier.classify("重百费用兑现申请") == "费用兑现"

    def test_changsong(self):
        assert RemarkClassifier.classify("急厂送4701559138") == "厂送"

    def test_pure_digital(self):
        assert RemarkClassifier.classify("4534720056") == "纯数字"

    def test_should_exclude_changsong(self):
        ex, _ = RemarkClassifier.should_exclude("急厂送4701559138")
        assert ex is True

    def test_jiajie_exclude_doc_type(self):
        assert RemarkClassifier.classify("任意备注", "借机转销售单") == "借机转销售"
        ex, _ = RemarkClassifier.should_exclude("任意", "借机转销售单")
        assert ex is True


class TestProjectClassifier:
    def test_virtual_excluded(self):
        ex, _ = ProjectClassifier.should_exclude("商品虚进")
        assert ex is True

    def test_normal_not_excluded(self):
        ex, _ = ProjectClassifier.should_exclude("商品进")
        assert ex is False


def _qs_row(idx, model, qty, remark, voucher_doc="普通销售单", check=""):
    return {
        "新方舟销售单号": f"S{idx:016d}", "单据类型": voucher_doc, "签收日期": "2026-04-05",
        "产品型号": model, "签收数量": qty, "签收金额": 100.0,
        "订单备注": remark, "订单行备注": "", "核对月份": check, "项目分类": "", "手工备注": "",
    }


def _ruku_row(voucher, model, qty, desc="入库单"):
    return {
        "采购凭证": voucher, "规格型号": model, "数量": qty, "含税金额": 100.0,
        "门店名称": "渝北店", "单据描述": desc, "过账日期": "2026-04-01",
    }


class TestMatchEngineFidelity:
    """对迁移后 _MatchEngine 的行为级测试"""

    def _build(self, ruku_rows, qs_rows):
        ruku_df = pd.DataFrame(ruku_rows)
        qs_df = preprocess_qianshou(pd.DataFrame(qs_rows))
        ruku_df["_is_return"] = (pd.to_numeric(ruku_df["数量"], errors="coerce") < 0) | \
            ruku_df["单据描述"].astype(str).str.contains("退货")
        qs_df["_is_return"] = (pd.to_numeric(qs_df["签收数量"], errors="coerce") < 0) | \
            qs_df["单据类型"].astype(str).str.contains("退货")
        return ruku_df, qs_df

    def test_voucher_exact_match(self):
        ruku, qs = self._build([_ruku_row(4534720056, "85Q10L", 1)],
                               [_qs_row(1, "85Q10L", 1, "渝北店4534720056")])
        res = _MatchEngine().match(ruku, qs)
        assert len(res["matched_pairs"]) == 1
        assert res["matched_pairs"][0]["match_type"] == "凭证精确匹配"

    def test_sample_sale_gets_no_voucher(self):
        """样转销在预处理中被标记排除、提取凭证被清空（第1层不匹配凭证）"""
        _, qs = self._build(
            [_ruku_row(4535020948, "85Q10L Pro", 1)],
            [_qs_row(1, "85Q10L Pro", 1, "样转销 江南商都销售，85Q10L Pro，机身码：111101011100235",
                     voucher_doc="样机转销售单")],
        )
        assert bool(qs.iloc[0]["是否排除"]) is True
        assert qs.iloc[0]["提取凭证"] is None

    def test_return_direction_separated(self):
        """退货与入库正负方向分离：退货入库不应匹配普通签收"""
        ruku, qs = self._build([_ruku_row(4534720056, "85Q10L", -1, desc="退货单")],
                               [_qs_row(1, "85Q10L", 1, "渝北店4534720056")])
        res = _MatchEngine().match(ruku, qs)
        assert len(res["matched_pairs"]) == 0


class TestChongbaiEngineInterface:
    """平台接口适配层"""

    def test_parse_customer_data(self):
        df = pd.DataFrame([_ruku_row(4534720056.0, "85Q10L", 1)])
        engine = ChongbaiEngine()
        s = engine.parse_customer_data(df)
        assert len(s) == 1
        assert s[0].match_key == "4534720056"  # 浮点凭证去小数点
        assert s[0].model == "85Q10L"

    def test_engine_version(self):
        assert ChongbaiEngine().engine_version.startswith("v5")
