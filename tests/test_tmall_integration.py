# 天猫优品端到端集成测试（Ticket 08）

"""用真实天猫文件验证完整链路：读 Excel → 过滤表头重复行 → 引擎解析 → 匹配。

真实文件路径依赖本地环境，文件不存在时 skip（不影响 CI）。
"""
import io
from pathlib import Path

import pandas as pd
import pytest

from app.engines import get_engine_by_name
from app.engines.base import OurReceipt

# 真实文件路径（本地环境）
TMALL_DIR = Path(r"D:\代码仓库\天猫优品核对\input")
SETTLEMENT_FILE = TMALL_DIR / "需开票结算单-智屏-经销.xlsx"
RECEIPT_FILE = TMALL_DIR / "天猫优品-智屏-经销-签收明细表.xlsx"

SETTLEMENT_SHEET = "经销"
RECEIPT_SHEET = "sheet0"

# 原脚本的列映射（与引擎 config 一致）
RECEIPT_COLS = {
    "approval_no": "审批单号",
    "nc_order_no": "NC订单号",
    "platform_no": "平台订单号",
    "model": "产品型号",
    "amount": "签收金额",
    "quantity": "签收数量",
    "date": "签收日期/完成日期",
    "doc_type": "单据类型",
    "customer_name": "结算客户名称",
    "receipt_no": "新方舟销售单号",
}


def _files_available():
    return SETTLEMENT_FILE.exists() and RECEIPT_FILE.exists()


@pytest.mark.skipif(not _files_available(), reason="真实天猫文件不存在")
class TestTmallEndToEnd:
    """天猫优品真实数据端到端"""

    def _load_settlement(self):
        df = pd.read_excel(SETTLEMENT_FILE, sheet_name=SETTLEMENT_SHEET)
        return df

    def _load_receipt(self):
        df = pd.read_excel(RECEIPT_FILE, sheet_name=RECEIPT_SHEET)
        # 原脚本的关键清洗：过滤表头重复行（NC订单号=NC订单号）
        nc_col = RECEIPT_COLS["nc_order_no"]
        if nc_col in df.columns:
            df = df[df[nc_col].astype(str).str.strip() != nc_col]
        return df

    def test_parse_customer_data(self):
        """引擎能解析真实结算单，且 match_key 非空占比合理"""
        engine = get_engine_by_name("tmall")
        settlement_df = self._load_settlement()

        settlements = engine.parse_customer_data(settlement_df)
        assert len(settlements) == len(settlement_df)

        non_empty = sum(1 for s in settlements if s.match_key)
        # 绝大多数结算单应有业务主单据编码
        assert non_empty / len(settlements) > 0.9

    def test_extract_model_from_real_product_name(self):
        """型号提取在真实商品名称上有效"""
        engine = get_engine_by_name("tmall")
        settlement_df = self._load_settlement()
        settlements = engine.parse_customer_data(settlement_df)

        with_model = sum(1 for s in settlements if s.model)
        assert with_model / len(settlements) > 0.8

    def test_match_rate_against_real_data(self):
        """引擎匹配结果与原脚本历史核对结果一致（保真度基准）。

        原脚本历史核对结果（20260615-144149）：
          结算单 129 条，匹配成功 66 条，未匹配 63 条（签收表无此订单），
          金额差异 0，匹配率 51.16%。

        剩 63 条未匹配是时间窗口差异（结算单有、当月签收表无），非引擎缺陷。
        因此断言「匹配数 == 66」验证迁移保真度，而非套用 95% 理想值。
        """
        engine = get_engine_by_name("tmall")

        settlement_df = self._load_settlement()
        receipt_df = self._load_receipt()

        settlements = engine.parse_customer_data(settlement_df)

        receipts = []
        for idx, row in receipt_df.iterrows():
            receipts.append(OurReceipt(
                id=idx,
                receipt_no=self._safe_str(row.get("新方舟销售单号")),
                model=self._safe_str(row.get("产品型号")),
                quantity=float(row.get("签收数量") or 0),
                amount=float(row.get("签收金额") or 0),
                unit_price=0.0,
                receipt_date=self._safe_str(row.get("签收日期/完成日期")),
                doc_type=self._safe_str(row.get("单据类型")),
                customer_name=self._safe_str(row.get("结算客户名称")),
                nc_order_no=self._safe_str(row.get("NC订单号")),
                raw_data=row.to_dict(),
            ))

        result = engine.match(receipts, settlements)

        # 保真度基准：与原脚本历史结果逐项一致
        assert len(settlements) == 129
        assert len(result.matched_pairs) == 66, (
            f"匹配数 {len(result.matched_pairs)} 与原脚本 66 不一致"
        )
        # 未匹配结算单 = 63（时间窗口差异）
        assert len(result.unmatched_settlements) == 63
        # 金额差异应为 0（原脚本口径，引擎 summary.amount_diff）
        assert result.summary.get("amount_diff", 0) == 0

    @staticmethod
    def _safe_str(v, default=""):
        if v is None or (isinstance(v, float) and v != v):
            return default
        return str(v).strip()