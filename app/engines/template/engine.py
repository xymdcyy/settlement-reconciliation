# 引擎模板 — 新客户起步模板

from app.engines.base import (
    CustomerSettlement,
    MatchEngine,
    MatchResult,
    OurReceipt,
)


class TemplateEngine(MatchEngine):
    """模板引擎：新客户从此开始"""

    engine_version = "v0.1.0"

    def parse_customer_data(self, raw_df) -> list[CustomerSettlement]:
        """
        解析客户方原始数据 → 标准化字段 + match_key

        1. 找到能匹配我方 NC 订单号/新方舟单号的字段作为 match_key
        2. 从商品名称中提取型号
        3. 提取金额、数量、单价
        """
        settlements = []
        for _, row in raw_df.iterrows():
            settlements.append(CustomerSettlement(
                id=row.name,
                match_key=str(row.get("客户订单号", "")),
                model=self._extract_model(str(row.get("商品名称", ""))),
                quantity=float(row.get("数量", 0) or 0),
                amount=float(row.get("金额", 0) or 0),
                unit_price=float(row.get("单价", 0) or 0),
                settlement_date=str(row.get("日期", "")),
                raw_data=row.to_dict(),
            ))
        return settlements

    def match(self, our_receipts: list[OurReceipt],
              settlements: list[CustomerSettlement]) -> MatchResult:
        """执行匹配逻辑（模板：简化的 match_key 匹配）"""
        matched_pairs = []
        unmatched_receipts = []
        unmatched_settlements = []
        excluded_settlements = []

        settlement_map = {s.match_key: s for s in settlements if s.match_key}

        for receipt in our_receipts:
            if receipt.nc_order_no in settlement_map:
                settlement = settlement_map[receipt.nc_order_no]
                matched_pairs.append(
                    self._create_match_pair(receipt, settlement, "match_key匹配", 0.9)
                )
                del settlement_map[receipt.nc_order_no]
            else:
                unmatched_receipts.append(receipt.id)

        unmatched_settlements = [s.id for s in settlements
                                 if s.id not in {p.settlement_id for p in matched_pairs}
                                 and s.id not in excluded_settlements]

        return MatchResult(
            matched_pairs=matched_pairs,
            unmatched_receipts=unmatched_receipts,
            unmatched_settlements=unmatched_settlements,
            excluded_settlements=excluded_settlements,
            engine_version=self.engine_version,
            summary={
                "total_receipts": len(our_receipts),
                "total_settlements": len(settlements),
                "matched": len(matched_pairs),
                "unmatched_receipts": len(unmatched_receipts),
                "unmatched_settlements": len(unmatched_settlements),
            },
        )

    def _create_match_pair(self, receipt: OurReceipt,
                           settlement: CustomerSettlement,
                           match_type: str,
                           confidence: float):
        """创建匹配对"""
        from app.engines.base import MatchPair
        return MatchPair(
            receipt_id=receipt.id,
            settlement_id=settlement.id,
            match_type=match_type,
            confidence=confidence,
            diff_amount=receipt.amount - settlement.amount,
            diff_quantity=receipt.quantity - settlement.quantity,
        )

    @staticmethod
    def _extract_model(product_name: str) -> str:
        """从商品名称中提取型号"""
        import re
        if not product_name:
            return ""
        match = re.search(r'(\d+[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?)', product_name)
        return match.group(1) if match else ""