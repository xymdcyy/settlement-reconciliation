# 报表导出服务

"""对账结果导出为 Excel（多工作表）"""

from io import BytesIO
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models import CustomerStatement, MatchResult, Receipt


class ExportService:
    """报表导出服务"""

    @staticmethod
    def _write_df_to_excel(df: pd.DataFrame, sheet_name: str) -> BytesIO:
        """
        将 DataFrame 写入 Excel 并调整列宽（三个导出方法共用）。

        返回定位到起始位置的 BytesIO。
        """
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            for col in ws.columns:
                max_len = 0
                for cell in col:
                    try:
                        cell_len = len(str(cell.value or ""))
                        if cell_len > max_len:
                            max_len = cell_len
                    except Exception:
                        pass
                adjusted_width = min(max_len + 4, 50)
                ws.column_dimensions[col[0].column_letter].width = adjusted_width
        output.seek(0)
        return output

    @staticmethod
    def export_receipts_to_excel(
        customer_id: int,
        db: Session,
        period: Optional[str] = None,
        billing_status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> BytesIO:
        """
        导出台账为 Excel

        列名从 raw_data 中提取（与原始台账一致）
        支持筛选：期间/状态/搜索
        """
        # 查询数据
        query = db.query(Receipt).filter(Receipt.customer_id == customer_id)

        if period:
            query = query.filter(Receipt.period == period)
        if billing_status:
            query = query.filter(Receipt.billing_status == billing_status)
        if search:
            query = query.filter(
                (Receipt.receipt_no.contains(search))
                | (Receipt.model.contains(search))
            )

        receipts = query.order_by(Receipt.receipt_date.desc()).all()

        # 如果没有数据，返回空 Excel
        if not receipts:
            return ExportService._write_df_to_excel(pd.DataFrame(), "台账")

        # 从 raw_data 提取列名（与原始台账一致）
        # 取所有记录 raw_data keys 的并集，保持首次出现的顺序，
        # 避免只取第一行导致后续行独有的列（如红通号）被静默丢弃
        columns = list(dict.fromkeys(
            key for r in receipts for key in (r.raw_data or {}).keys()
        ))

        # 构建 DataFrame
        data = []
        for r in receipts:
            raw = r.raw_data or {}
            data.append({col: raw.get(col, "") for col in columns})

        df = pd.DataFrame(data, columns=columns)
        return ExportService._write_df_to_excel(df, "台账")

    @staticmethod
    def export_billing_list_to_excel(
        receipt_ids: list[int],
        db: Session,
    ) -> BytesIO:
        """
        导出开票清单为 Excel

        包含：单号/型号/数量/金额/客户/签收日期
        """
        receipts = db.query(Receipt).filter(Receipt.id.in_(receipt_ids)).all() if receipt_ids else []

        # 构建 DataFrame
        data = []
        for r in receipts:
            data.append({
                "新方舟销售单号": r.receipt_no,
                "产品型号": r.model,
                "签收数量": float(r.quantity) if r.quantity else 0,
                "签收金额": float(r.amount) if r.amount else 0,
                "单价": float(r.unit_price) if r.unit_price else 0,
                "结算客户名称": r.customer_name,
                "签收日期": r.receipt_date,
                "单据类型": r.doc_type,
                "NC订单号": r.nc_order_no,
                "产品线": r.product_line,
            })

        df = pd.DataFrame(data) if data else pd.DataFrame(columns=[
            "新方舟销售单号", "产品型号", "签收数量", "签收金额", "单价",
            "结算客户名称", "签收日期", "单据类型", "NC订单号", "产品线",
        ])
        return ExportService._write_df_to_excel(df, "开票清单")

    @staticmethod
    def export_red_flush_confirmation_to_excel(
        matches: list[dict],
        db: Session,
    ) -> BytesIO:
        """
        导出红冲确认单为 Excel

        matches: [{"return_receipt": Receipt, "blue_receipt": Receipt}]
        包含：退货单号/型号/退货数量/退货金额/蓝票号/开票日期
        """
        # 构建 DataFrame
        data = []
        for match in matches:
            return_r = match.get("return_receipt")
            blue_r = match.get("blue_receipt")

            if not return_r:
                continue

            data.append({
                "退货单号": return_r.receipt_no,
                "产品型号": return_r.model,
                "退货数量": float(return_r.quantity) if return_r.quantity else 0,
                "退货金额": float(return_r.amount) if return_r.amount else 0,
                "单价": float(return_r.unit_price) if return_r.unit_price else 0,
                "蓝票号": blue_r.invoice_no if blue_r else "",
                "开票日期": blue_r.invoice_date if blue_r else "",
                "蓝票单号": blue_r.receipt_no if blue_r else "",
            })

        df = pd.DataFrame(data) if data else pd.DataFrame(columns=[
            "退货单号", "产品型号", "退货数量", "退货金额", "单价",
            "蓝票号", "开票日期", "蓝票单号",
        ])
        return ExportService._write_df_to_excel(df, "红冲确认单")

    @staticmethod
    def export_reconciliation(customer_id: int, period: str, customer_name: str, db: Session) -> BytesIO:
        """
        导出对账结果 Excel，包含 5 个工作表

        - Sheet1: 对账汇总
        - Sheet2: 匹配明细
        - Sheet3: 我方已签收客户未结算
        - Sheet4: 客户已结算我方未签收
        - Sheet5: 金额差异明细
        """
        # 加载匹配结果
        results = db.query(MatchResult).filter(
            MatchResult.customer_id == customer_id,
            MatchResult.period == period,
        ).all()

        # 加载关联数据
        receipt_ids = [r.receipt_id for r in results if r.receipt_id]
        settlement_ids = [r.settlement_id for r in results if r.settlement_id]

        receipts = {r.id: r for r in db.query(Receipt).filter(Receipt.id.in_(receipt_ids)).all()} if receipt_ids else {}
        settlements = {s.id: s for s in db.query(CustomerStatement).filter(CustomerStatement.id.in_(settlement_ids)).all()} if settlement_ids else {}

        # ============================================================
        # Sheet1: 对账汇总
        # ============================================================
        # 手动匹配 (manual) 也计入已匹配
        matched = [r for r in results if r.status in ("matched", "manual")]
        unmatched_receipt = [r for r in results if r.status == "unmatched" and r.receipt_id]
        unmatched_settlement = [r for r in results if r.status == "unmatched" and r.settlement_id]
        ignored = [r for r in results if r.status == "ignored"]

        # 匹配率口径 = 已匹配入库行 / 入库行总数（matched + 未匹配入库行），行级，
        # 与 run / get_summary / history 一致（一对多入库行按行计）。
        total_settlements_for_rate = len(matched) + len(unmatched_settlement)
        match_rate = round(len(matched) / total_settlements_for_rate * 100, 2) if total_settlements_for_rate > 0 else 0
        total_diff = sum(r.diff_amount or 0 for r in matched)

        summary_data = [
            ["客户名称", customer_name],
            ["对账期间", period],
            ["", ""],
            ["指标", "数值"],
            ["我方签收总记录数", len(set(r.receipt_id for r in results if r.receipt_id))],
            ["客户方结算总记录数", len(set(r.settlement_id for r in results if r.settlement_id))],
            ["已匹配数", len(matched)],
            ["未匹配我方数", len(unmatched_receipt)],
            ["未匹配客户方数", len(unmatched_settlement)],
            ["已排除数", len(ignored)],
            ["匹配率", f"{match_rate}%"],
            ["总金额差异", round(total_diff, 2)],
        ]
        df_summary = pd.DataFrame(summary_data, columns=["项目", "内容"])

        # ============================================================
        # Sheet2: 匹配明细
        # ============================================================
        match_detail = []
        for r in matched:
            rec = receipts.get(r.receipt_id)
            s = settlements.get(r.settlement_id)
            match_detail.append({
                "匹配类型": r.match_type,
                "置信度": float(r.confidence) if r.confidence is not None else "",
                "我方-销售单号": rec.receipt_no if rec else "",
                "我方-型号": rec.model if rec else "",
                "我方-数量": float(rec.quantity) if rec and rec.quantity is not None else "",
                "我方-金额": float(rec.amount) if rec and rec.amount is not None else "",
                "我方-日期": rec.receipt_date if rec else "",
                "客户-匹配键": s.match_key if s else "",
                "客户-型号": s.model if s else "",
                "客户-数量": float(s.quantity) if s and s.quantity is not None else "",
                "客户-金额": float(s.amount) if s and s.amount is not None else "",
                "客户-日期": s.settlement_date if s else "",
                "金额差异": float(r.diff_amount) if r.diff_amount is not None else "",
                "数量差异": float(r.diff_quantity) if r.diff_quantity is not None else "",
                "备注": r.remark or "",
            })
        df_match = pd.DataFrame(match_detail) if match_detail else pd.DataFrame(columns=[
            "匹配类型", "置信度", "我方-销售单号", "我方-型号", "我方-数量", "我方-金额", "我方-日期",
            "客户-匹配键", "客户-型号", "客户-数量", "客户-金额", "客户-日期", "金额差异", "数量差异", "备注",
        ])

        # ============================================================
        # Sheet3: 我方已签收客户未结算
        # ============================================================
        our_only = []
        for r in unmatched_receipt:
            rec = receipts.get(r.receipt_id)
            our_only.append({
                "销售单号": rec.receipt_no if rec else "",
                "型号": rec.model if rec else "",
                "数量": float(rec.quantity) if rec and rec.quantity is not None else "",
                "金额": float(rec.amount) if rec and rec.amount is not None else "",
                "签收日期": rec.receipt_date if rec else "",
                "单据类型": rec.doc_type if rec else "",
                "NC订单号": rec.nc_order_no if rec else "",
            })
        df_our_only = pd.DataFrame(our_only) if our_only else pd.DataFrame(columns=[
            "销售单号", "型号", "数量", "金额", "签收日期", "单据类型", "NC订单号",
        ])

        # ============================================================
        # Sheet4: 客户已结算我方未签收
        # ============================================================
        settlement_only = []
        for r in unmatched_settlement:
            s = settlements.get(r.settlement_id)
            settlement_only.append({
                "匹配键": s.match_key if s else "",
                "型号": s.model if s else "",
                "数量": float(s.quantity) if s and s.quantity is not None else "",
                "金额": float(s.amount) if s and s.amount is not None else "",
                "业务日期": s.settlement_date if s else "",
                "单据类型": s.doc_type if s else "",
            })
        df_settlement_only = pd.DataFrame(settlement_only) if settlement_only else pd.DataFrame(columns=[
            "匹配键", "型号", "数量", "金额", "业务日期", "单据类型",
        ])

        # ============================================================
        # Sheet5: 金额差异明细
        # ============================================================
        diff_detail = []
        for r in matched:
            rec = receipts.get(r.receipt_id)
            s = settlements.get(r.settlement_id)
            # 明确检查 diff_amount 是否不为 None（包括 Decimal('0.00')）
            if r.diff_amount is not None:
                diff_detail.append({
                    "匹配类型": r.match_type,
                    "我方-销售单号": rec.receipt_no if rec else "",
                    "我方-型号": rec.model if rec else "",
                    "我方金额": float(rec.amount) if rec and rec.amount is not None else 0,
                    "客户金额": float(s.amount) if s and s.amount is not None else 0,
                    "金额差异": float(r.diff_amount),
                    "数量差异": float(r.diff_quantity) if r.diff_quantity is not None else 0,
                })
        df_diff = pd.DataFrame(diff_detail) if diff_detail else pd.DataFrame(columns=[
            "匹配类型", "我方-销售单号", "我方-型号", "我方金额", "客户金额", "金额差异", "数量差异",
        ])

        # ============================================================
        # 写入 Excel
        # ============================================================
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df_summary.to_excel(writer, sheet_name="对账汇总", index=False)
            df_match.to_excel(writer, sheet_name="匹配明细", index=False)
            df_our_only.to_excel(writer, sheet_name="我方已签收客户未结算", index=False)
            df_settlement_only.to_excel(writer, sheet_name="客户已结算我方未签收", index=False)
            df_diff.to_excel(writer, sheet_name="金额差异明细", index=False)

            # 调整列宽
            for sheet_name in writer.sheets:
                ws = writer.sheets[sheet_name]
                for col in ws.columns:
                    max_len = 0
                    for cell in col:
                        try:
                            cell_len = len(str(cell.value or ""))
                            if cell_len > max_len:
                                max_len = cell_len
                        except Exception:
                            pass
                    adjusted_width = min(max_len + 4, 50)
                    ws.column_dimensions[col[0].column_letter].width = adjusted_width

        output.seek(0)
        return output

    @staticmethod
    def get_history(db: Session, customer_id: int = None, start_month: str = None, end_month: str = None) -> list:
        """获取历史对账记录摘要"""
        from app.models import Customer

        query = db.query(MatchResult)
        if customer_id:
            query = query.filter(MatchResult.customer_id == customer_id)
        if start_month:
            query = query.filter(MatchResult.period >= start_month)
        if end_month:
            query = query.filter(MatchResult.period <= end_month)

        all_results = query.order_by(MatchResult.period.desc()).all()

        # 按 customer_id + period 分组
        groups = {}
        for r in all_results:
            key = (r.customer_id, r.period)
            if key not in groups:
                groups[key] = {"results": []}
            groups[key]["results"].append(r)

        # 获取客户名称（避免空集合 IN() 查询）
        customer_ids = {k[0] for k in groups}
        if customer_ids:
            customers = {c.id: c.name for c in db.query(Customer).filter(Customer.id.in_(customer_ids)).all()}
        else:
            customers = {}

        result = []
        for (cid, per), data in groups.items():
            grp = data["results"]
            # manual 状态也计入已匹配
            matched = sum(1 for r in grp if r.status in ("matched", "manual"))
            unmatched_receipt = sum(1 for r in grp if r.status == "unmatched" and r.receipt_id is not None)
            unmatched_settlement = sum(1 for r in grp if r.status == "unmatched" and r.settlement_id is not None)
            # 匹配率口径 = 已匹配入库行 / 入库行总数（matched + 未匹配入库行），行级。
            total_settlements_for_rate = matched + unmatched_settlement
            match_rate = round(matched / total_settlements_for_rate * 100, 2) if total_settlements_for_rate > 0 else 0
            total_diff = sum(r.diff_amount or 0 for r in grp)

            result.append({
                "period": per,
                "customer_id": cid,
                "customer_name": customers.get(cid, f"ID:{cid}"),
                "matched_count": matched,
                "unmatched_receipts": unmatched_receipt,
                "unmatched_settlements": unmatched_settlement,
                "match_rate": match_rate,
                "total_amount_diff": round(total_diff, 2),
                "total": len(grp),
            })

        return result