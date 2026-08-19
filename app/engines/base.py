# 匹配引擎抽象基类

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class OurReceipt:
    """我方标准化签收记录"""
    id: int
    receipt_no: str
    model: str
    quantity: float
    amount: float
    unit_price: float
    receipt_date: str
    doc_type: str
    customer_name: str
    nc_order_no: str
    raw_data: dict


@dataclass
class CustomerSettlement:
    """客户方结算单（引擎解析后）"""
    id: int
    match_key: str
    model: str
    quantity: float
    amount: float
    unit_price: float
    settlement_date: str
    raw_data: dict


@dataclass
class MatchPair:
    """匹配对"""
    receipt_id: int
    settlement_id: int
    match_type: str
    confidence: float
    diff_amount: float
    diff_quantity: float
    detail: dict = field(default_factory=dict)


@dataclass
class MatchResult:
    """匹配结果"""
    matched_pairs: list[MatchPair]
    unmatched_receipts: list[int]
    unmatched_settlements: list[int]
    excluded_settlements: list[int]
    engine_version: str
    summary: dict

    @property
    def match_rate(self) -> float:
        total = len(self.matched_pairs) + len(self.unmatched_receipts)
        if total == 0:
            return 0.0
        return len(self.matched_pairs) / total * 100


class MatchEngine(ABC):
    """匹配引擎抽象基类"""

    @abstractmethod
    def parse_customer_data(self, raw_df: Any) -> list[CustomerSettlement]:
        """
        解析客户方原始数据 → 标准化字段 + match_key

        这是每个客户引擎最核心的差异化逻辑：
        - 天猫优品: 从"业务主单据编码"提取 match_key，从"后端商品名称"提取型号
        - 重百: 从"订单备注"正则提取采购凭证做 match_key，映射列名
        """
        pass

    @abstractmethod
    def match(
        self,
        our_receipts: list[OurReceipt],
        customer_settlements: list[CustomerSettlement],
    ) -> MatchResult:
        """
        执行匹配逻辑

        返回匹配对 + 未匹配的双方记录
        """
        pass

    def get_exclude_rules(self) -> dict:
        """
        获取排除规则配置

        返回示例:
        {
            "exclude_doc_types": ["借机转销售单"],
            "exclude_remark_keywords": ["费用兑现", "价差"],
            "exclude_quantity_threshold": 100
        }
        """
        return {}

    @property
    def engine_name(self) -> str:
        return self.__class__.__name__

    @property
    def engine_version(self) -> str:
        return "v1.0.0"