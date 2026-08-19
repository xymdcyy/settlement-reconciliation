# 测试：MatchEngine 抽象基类

import pytest
from app.engines.base import (
    MatchEngine,
    CustomerSettlement,
    MatchPair,
    MatchResult,
    OurReceipt,
)


def test_engine_abstract_class_cannot_be_instantiated():
    """MatchEngine 是抽象类，不能直接实例化"""
    with pytest.raises(TypeError):
        MatchEngine()  # type: ignore


def test_our_receipt_dataclass():
    """OurReceipt 数据类创建正确"""
    r = OurReceipt(
        id=1,
        receipt_no="S1010260104000001",
        model="75V69H",
        quantity=100,
        amount=693000.0,
        unit_price=6930.0,
        receipt_date="2026-01-04",
        doc_type="普通销售单",
        customer_name="天猫优品-经销",
        nc_order_no="PON2601010000001",
        raw_data={"extra": "data"},
    )
    assert r.id == 1
    assert r.receipt_no == "S1010260104000001"
    assert r.model == "75V69H"
    assert r.quantity == 100


def test_customer_settlement_dataclass():
    """CustomerSettlement 数据类创建正确"""
    s = CustomerSettlement(
        id=1,
        match_key="PON2601010000001",
        model="75V69H",
        quantity=100,
        amount=693000.0,
        unit_price=6930.0,
        settlement_date="2026-01-15",
        raw_data={"业务主单据编码": "PON2601010000001"},
    )
    assert s.id == 1
    assert s.match_key == "PON2601010000001"
    assert s.model == "75V69H"


def test_match_pair_dataclass():
    """MatchPair 数据类创建正确"""
    p = MatchPair(
        receipt_id=1,
        settlement_id=2,
        match_type="凭证精确匹配",
        confidence=1.0,
        diff_amount=0.0,
        diff_quantity=0.0,
    )
    assert p.receipt_id == 1
    assert p.settlement_id == 2
    assert p.confidence == 1.0


def test_match_result_dataclass():
    """MatchResult 数据类创建正确"""
    result = MatchResult(
        matched_pairs=[
            MatchPair(receipt_id=1, settlement_id=1, match_type="精确匹配",
                      confidence=1.0, diff_amount=0.0, diff_quantity=0.0),
        ],
        unmatched_receipts=[2],
        unmatched_settlements=[2],
        excluded_settlements=[],
        engine_version="v1.0.0",
        summary={"matched": 1, "total": 2},
    )
    assert len(result.matched_pairs) == 1
    assert result.unmatched_receipts == [2]
    assert result.engine_version == "v1.0.0"


def test_match_result_match_rate():
    """MatchResult.match_rate 计算正确"""
    result = MatchResult(
        matched_pairs=[
            MatchPair(receipt_id=1, settlement_id=1, match_type="精确匹配",
                      confidence=1.0, diff_amount=0.0, diff_quantity=0.0),
        ],
        unmatched_receipts=[2],
        unmatched_settlements=[2],
        excluded_settlements=[],
        engine_version="v1.0.0",
        summary={},
    )
    assert result.match_rate == 50.0

    # 全部匹配
    result = MatchResult(
        matched_pairs=[
            MatchPair(receipt_id=1, settlement_id=1, match_type="精确匹配",
                      confidence=1.0, diff_amount=0.0, diff_quantity=0.0),
        ],
        unmatched_receipts=[],
        unmatched_settlements=[],
        excluded_settlements=[],
        engine_version="v1.0.0",
        summary={},
    )
    assert result.match_rate == 100.0

    # 无数据
    result = MatchResult(
        matched_pairs=[],
        unmatched_receipts=[],
        unmatched_settlements=[],
        excluded_settlements=[],
        engine_version="v1.0.0",
        summary={},
    )
    assert result.match_rate == 0.0