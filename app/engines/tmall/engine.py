# 天猫优品匹配引擎

import re

from app.engines.base import (
    CustomerSettlement,
    MatchEngine,
    MatchPair,
    MatchResult,
    OurReceipt,
)
from app.engines.tmall.config import (
    ENGINE_VERSION,
    RECEIPT_COLS,
    SETTLEMENT_COLS,
)


class TmallEngine(MatchEngine):
    """天猫优品匹配引擎

    匹配逻辑（从原有脚本迁移）：
    1. 精确匹配：match_key(订单号)|金额|型号 完全一致
    2. 宽松匹配：match_key|型号 一致，签收金额 >= 结算金额
    """

    engine_version = ENGINE_VERSION

    # ============================================================
    # 实现 MatchEngine 接口
    # ============================================================

    def parse_customer_data(self, raw_df) -> list[CustomerSettlement]:
        """解析天猫优品结算单 → 标准化字段"""
        settlements = []
        for _, row in raw_df.iterrows():
            product_name = self._safe_str(row.get(SETTLEMENT_COLS["product_name"], ""))
            settlements.append(CustomerSettlement(
                id=row.name,
                match_key=self._safe_str(row.get(SETTLEMENT_COLS["order_id"], "")),
                model=self._extract_model(product_name),
                quantity=float(row.get(SETTLEMENT_COLS["quantity"], 0) or 0),
                amount=float(row.get(SETTLEMENT_COLS["amount"], 0) or 0),
                unit_price=float(row.get(SETTLEMENT_COLS["unit_price"], 0) or 0),
                settlement_date=self._safe_str(row.get(SETTLEMENT_COLS["date"], "")),
                raw_data=row.to_dict(),
            ))
        return settlements

    def match(
        self,
        our_receipts: list[OurReceipt],
        customer_settlements: list[CustomerSettlement],
    ) -> MatchResult:
        """执行两轮匹配"""
        # 构建签收侧索引
        receipt_map = {}  # match_key -> list[OurReceipt]
        for r in our_receipts:
            key = self._make_receipt_key(r)
            receipt_map.setdefault(key, []).append(r)
            # 宽松键：订单号|型号
            loose_key = self._make_loose_key(r)
            receipt_map.setdefault(loose_key, []).append(r)

        # 按精确键聚合签收金额
        receipt_amount_map = {}
        for r in our_receipts:
            key = self._make_receipt_key(r)
            receipt_amount_map[key] = receipt_amount_map.get(key, 0) + r.amount

        # 按宽松键聚合签收金额
        receipt_loose_agg = {}
        for r in our_receipts:
            loose_key = self._make_loose_key(r)
            if loose_key not in receipt_loose_agg:
                receipt_loose_agg[loose_key] = {"total_amount": 0.0, "receipts": []}
            receipt_loose_agg[loose_key]["total_amount"] += r.amount
            receipt_loose_agg[loose_key]["receipts"].append(r)

        matched_pairs = []
        unmatched_settlements = []
        amount_diff_settlements = []
        matched_settlement_ids = set()
        matched_receipt_ids = set()

        for s in customer_settlements:
            s_key = self._make_settlement_key(s)

            # 空 match_key
            if not s.match_key:
                unmatched_settlements.append(s.id)
                continue

            # 第一轮：精确匹配
            if s_key in receipt_amount_map:
                matching_receipts = [r for r in our_receipts
                                     if self._make_receipt_key(r) == s_key
                                     and r.id not in matched_receipt_ids]

                if len(matching_receipts) == 1:
                    r = matching_receipts[0]
                    if abs(s.amount - r.amount) < 0.01:
                        matched_pairs.append(self._make_pair(r, s, "精确匹配", 1.0))
                        matched_settlement_ids.add(s.id)
                        matched_receipt_ids.add(r.id)
                    else:
                        amount_diff_settlements.append(s.id)
                elif len(matching_receipts) > 1:
                    amount_diff_settlements.append(s.id)
                else:
                    # 精确键匹配但记录已被占用 → 走宽松匹配
                    self._try_loose_match(s, our_receipts, receipt_loose_agg,
                                          matched_receipt_ids, matched_pairs,
                                          matched_settlement_ids, amount_diff_settlements)
                continue

            # 第二轮：宽松匹配
            self._try_loose_match(s, our_receipts, receipt_loose_agg,
                                  matched_receipt_ids, matched_pairs,
                                  matched_settlement_ids, amount_diff_settlements)

        # 未匹配的签收记录
        unmatched_settlement_ids = [s.id for s in customer_settlements
                                     if s.id not in matched_settlement_ids
                                     and s.id not in unmatched_settlements
                                     and s.id not in amount_diff_settlements]
        unmatched_settlements.extend(unmatched_settlement_ids)

        # 未匹配的我方记录
        unmatched_receipt_ids = [r.id for r in our_receipts
                                  if r.id not in matched_receipt_ids]

        return MatchResult(
            matched_pairs=matched_pairs,
            unmatched_receipts=unmatched_receipt_ids,
            unmatched_settlements=unmatched_settlements,
            excluded_settlements=[],
            engine_version=self.engine_version,
            summary={
                "total_receipts": len(our_receipts),
                "total_settlements": len(customer_settlements),
                "matched": len(matched_pairs),
                "unmatched_receipts": len(unmatched_receipt_ids),
                "unmatched_settlements": len(unmatched_settlement_ids),
                "amount_diff": len(amount_diff_settlements),
            },
        )

    # ============================================================
    # 内部方法
    # ============================================================

    def _try_loose_match(self, s, our_receipts, receipt_loose_agg,
                         matched_receipt_ids, matched_pairs,
                         matched_settlement_ids, amount_diff_settlements):
        """尝试宽松匹配"""
        s_loose_key = self._make_loose_settlement_key(s)
        if s_loose_key not in receipt_loose_agg:
            return

        agg = receipt_loose_agg[s_loose_key]
        if agg["total_amount"] >= s.amount - 0.01:
            # 找第一个未匹配的签收记录
            for r in agg["receipts"]:
                if r.id not in matched_receipt_ids:
                    matched_pairs.append(self._make_pair(r, s, "宽松匹配", 0.85))
                    matched_settlement_ids.add(s.id)
                    matched_receipt_ids.add(r.id)
                    return

        # 金额不足
        amount_diff_settlements.append(s.id)

    def _make_settlement_key(self, s: CustomerSettlement) -> str:
        """创建结算单匹配键: 订单号|金额|型号"""
        amount = f"{s.amount:.2f}" if s.amount else ""
        return f"{s.match_key}|{amount}|{s.model}"

    def _make_receipt_key(self, r: OurReceipt) -> str:
        """创建签收单匹配键: 订单号|金额|型号"""
        order_no = self._receipt_order_no(r)
        amount = f"{r.amount:.2f}" if r.amount else ""
        return f"{order_no}|{amount}|{r.model}"

    def _make_loose_key(self, r: OurReceipt) -> str:
        """创建宽松匹配键: 订单号|型号"""
        order_no = self._receipt_order_no(r)
        return f"{order_no}|{r.model}"

    def _receipt_order_no(self, r: OurReceipt) -> str:
        """签收单优先级订单号：审批单号 > NC订单号 > 平台订单号（与原脚本 get_order_number 一致）。

        审批单号/平台订单号未提升为独立字段，从 raw_data 中读取；
        NC订单号优先取标准化字段 r.nc_order_no，回退到 raw_data。
        """
        raw = r.raw_data or {}
        approval = self._safe_str(raw.get(RECEIPT_COLS["approval_no"], ""))
        if approval:
            return approval
        nc = self._safe_str(r.nc_order_no) or self._safe_str(raw.get(RECEIPT_COLS["nc_order_no"], ""))
        if nc:
            return nc
        return self._safe_str(raw.get(RECEIPT_COLS["platform_no"], ""))

    def _make_loose_settlement_key(self, s: CustomerSettlement) -> str:
        """创建结算单宽松匹配键: 订单号|型号"""
        return f"{s.match_key}|{s.model}"

    def _make_pair(self, r: OurReceipt, s: CustomerSettlement,
                   match_type: str, confidence: float) -> MatchPair:
        """创建匹配对"""
        return MatchPair(
            receipt_id=r.id,
            settlement_id=s.id,
            match_type=match_type,
            confidence=confidence,
            diff_amount=round(r.amount - s.amount, 2),
            diff_quantity=round(r.quantity - s.quantity, 2),
            detail={"receipt_no": r.receipt_no, "match_key": s.match_key},
        )

    @staticmethod
    def _extract_model(product_name: str) -> str:
        """从后端商品名称中提取型号

        示例: "TCL 75N9M 75英寸 黑色 官方标配" → "75N9M"
        """
        if not product_name:
            return ""
        pattern = r"(\d+[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)?(?:\s+[A-Z][a-z]+)?)"
        match = re.search(pattern, product_name)
        return match.group(1) if match else ""

    @staticmethod
    def _safe_str(value, default="") -> str:
        """安全地转换为字符串（None 与 pandas NaN 均视为空，向原脚本 pd.notna 行为看齐）"""
        if value is None:
            return default
        if isinstance(value, float) and value != value:  # NaN
            return default
        return str(value).strip()