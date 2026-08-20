# 重百智屏匹配引擎（Phase 2）
#
# 从原脚本 reconcile_all.py 迁移：
#   - MatchEngine（5 层匹配 + 核对月优先两轮 + 追踪调整单）→ 逐字移植为 _MatchEngine
#   - preprocess_qianshou（签收预处理）→ 逐字移植
#   - DataLoader 的时间窗口/客户列筛选 → _standardize_columns / _filter_by_target_month
# 平台适配层 ChongbaiEngine 负责在 OurReceipt/CustomerSettlement 与内部 DataFrame 之间转换。
#
# 数据方向对齐：重百入库明细 = 客户方(customer_settlements)，TCL 签收明细 = 我方(our_receipts)。

import re
from datetime import datetime

import pandas as pd
from dateutil.relativedelta import relativedelta

from app.engines.base import (
    CustomerSettlement,
    MatchEngine,
    MatchPair,
    MatchResult,
    OurReceipt,
)
from app.engines.chongbai.classifiers import ProjectClassifier, RemarkClassifier
from app.engines.chongbai.config import (
    ENGINE_VERSION,
    FILTER_GOU_DAN,
    LOOKBACK_MONTHS,
    QIANGSHOU_COLUMN_MAPPING,
    RUKU_COLUMN_MAPPING,
    VALID_VOUCHER_PREFIXES,
)
from app.engines.chongbai.extractors import (
    SampleSaleExtractor,
    StoreExtractor,
    VoucherExtractor,
)

# 引擎内部日志开关（迁移期用于逐层核对；平台生产可关闭）
_VERBOSE = False


def _p(*args, **kwargs):
    if _VERBOSE:
        print(*args, **kwargs)


# =============================================================================
# 列名标准化 + 时间窗口筛选（从 DataLoader 迁移）
# =============================================================================

def _standardize_columns(df, mapping):
    """标准化列名（同一标准名匹配第一个命中的源列）"""
    rename_map = {}
    for standard_name, possible_names in mapping.items():
        for col in df.columns:
            if col in possible_names:
                rename_map[col] = standard_name
                break
    if rename_map:
        df = df.rename(columns=rename_map)
    return df


def _filter_by_target_month(df, target_year, target_month, months_range=LOOKBACK_MONTHS):
    """按目标月份前后范围筛选签收记录，保留日期为空的记录（可能有凭证）。

    与原 DataLoader._filter_by_target_month 一致：日期在窗口内 或 日期为空 或
    台账"核对"列命中目标年月；并设置 _check_month_match 供匹配引擎优先使用。
    """
    date_col = None
    for col in df.columns:
        if "签收日期" in col or "完成日期" in col:
            date_col = col
            break

    if date_col is None:
        _p("警告: 未找到签收日期列，返回全部数据")
        df = df.copy()
        df["_check_month_match"] = False
        return df

    date_series = pd.to_datetime(df[date_col], errors="coerce")

    target_date = datetime(target_year, target_month, 15)
    start_date = target_date - relativedelta(months=months_range)
    end_date = target_date + relativedelta(months=months_range)
    _p(f"签收日期筛选范围: {start_date.date()} 至 {end_date.date()}")

    in_range = (date_series >= start_date) & (date_series <= end_date)
    date_is_null = date_series.isna()

    check_month_match = pd.Series(False, index=df.index)
    if "核对月份" in df.columns:
        target_ym = f"{target_year}{target_month:02d}"
        check_vals = df["核对月份"].astype(str)
        check_month_match = check_vals.apply(
            lambda v: target_ym in re.findall(r"\d{6}", str(v))
        )
        extra = check_month_match.sum()
        if extra > 0:
            _p(f"  台账核对月={target_ym}的记录: {extra} 条")

    filtered = df[in_range | date_is_null | check_month_match].copy()

    filtered["_check_month_match"] = False
    if "核对月份" in filtered.columns:
        target_ym = f"{target_year}{target_month:02d}"
        filtered["_check_month_match"] = filtered["核对月份"].astype(str).apply(
            lambda v: target_ym in re.findall(r"\d{6}", str(v))
        )

    return filtered


# =============================================================================
# 签收预处理（从 preprocess_qianshou 逐字迁移）
# =============================================================================

def preprocess_qianshou(df):
    """预处理签收数据：分类/排除/提取凭证/多凭证/项目辅助/手工纠正/门店/样转销"""
    if "是否勾单" in df.columns and FILTER_GOU_DAN:
        before = len(df)
        checked_mask = df["是否勾单"].astype(str).str.strip() == "勾单"
        df = df[~checked_mask].copy()
        _p(f"  已勾单过滤: 排除 {before - len(df)} 条已匹配记录")

    _p("  分类订单备注...")
    df["备注分类"] = df.apply(
        lambda row: RemarkClassifier.classify(row.get("订单备注", ""), row.get("单据类型", "")),
        axis=1,
    )

    exclude_results = df.apply(
        lambda row: RemarkClassifier.should_exclude(
            row.get("订单备注", ""),
            row.get("单据类型", ""),
            row.get("签收数量", 0) if "签收数量" in row else 0,
        ),
        axis=1,
    )
    df["是否排除"] = exclude_results.apply(lambda x: x[0])
    df["排除原因"] = exclude_results.apply(lambda x: x[1] if x[0] else "")

    _p("  提取采购凭证...")
    df["提取凭证"] = df.apply(
        lambda row: None
        if row["是否排除"]
        else VoucherExtractor.extract(row.get("订单备注", ""), row["备注分类"], row.get("订单行备注", "")),
        axis=1,
    )

    df["_all_vouchers"] = df.apply(
        lambda row: ""
        if row["是否排除"]
        else "|".join(
            VoucherExtractor.extract_all(row.get("订单备注", ""), row["备注分类"], row.get("订单行备注", ""))
        ),
        axis=1,
    )

    # ==== 项目分类辅助（台账"项目"列）====
    if "项目分类" in df.columns:
        _p("  利用项目分类辅助判断...")
        for idx in df.index:
            proj_label = df.loc[idx, "项目分类"]
            strategy = ProjectClassifier.classify(proj_label)

            if strategy["strategy"] == "排除-虚拟":
                if not df.loc[idx, "是否排除"]:
                    df.loc[idx, "是否排除"] = True
                    df.loc[idx, "排除原因"] = f"项目标记-虚拟调账({strategy['label']})"
                    df.loc[idx, "提取凭证"] = None
                    df.loc[idx, "_all_vouchers"] = ""
            elif strategy["strategy"] == "排除-价格错误":
                if not df.loc[idx, "是否排除"]:
                    df.loc[idx, "是否排除"] = True
                    df.loc[idx, "排除原因"] = f"项目标记-价格错误({strategy['label']})"
                    df.loc[idx, "提取凭证"] = None
                    df.loc[idx, "_all_vouchers"] = ""
            elif strategy["strategy"] == "样转销":
                if not df.loc[idx, "是否排除"]:
                    df.loc[idx, "是否排除"] = True
                    df.loc[idx, "排除原因"] = "样转销-历史入库已记录（样机已在上月入库，无需当月匹配）"
                    df.loc[idx, "提取凭证"] = None
                    df.loc[idx, "_all_vouchers"] = ""

    # ==== 手工备注纠正凭证（台账"备注"列，覆盖提取结果）====
    if "手工备注" in df.columns:
        _p("  利用手工备注纠正凭证...")
        for idx in df.index:
            if df.loc[idx, "是否排除"]:
                continue
            manual_note = df.loc[idx, "手工备注"]
            if pd.isna(manual_note) or str(manual_note).strip() == "":
                continue
            note = str(manual_note).strip()
            if not any(kw in note for kw in ["采购", "正确", "实际", "对应", "本身", "单号"]):
                continue

            correct_voucher = None
            patterns = [
                r"实[际際](?:上)?(?:对应(?:的)?)?(?:采购(?:单|凭证)?号?为?|对应|是)\s*(\d{10})",
                r"正确(?:的?)?(?:采购)?(?:单|凭证)?号?\s*[为是：:]\s*(\d{10})",
                r"应[为该是]\s*(\d{10})",
            ]
            for pat in patterns:
                m = re.search(pat, note)
                if m:
                    candidate = m.group(1)
                    if candidate and len(candidate) == 10 and candidate.isdigit():
                        if any(candidate.startswith(p) for p in VALID_VOUCHER_PREFIXES):
                            correct_voucher = candidate
                            break

            if correct_voucher:
                old_voucher = df.loc[idx, "提取凭证"] if pd.notna(df.loc[idx, "提取凭证"]) else "(空)"
                df.loc[idx, "提取凭证"] = correct_voucher
                df.loc[idx, "_all_vouchers"] = correct_voucher
                df.loc[idx, "排除原因"] = (
                    str(df.loc[idx, "排除原因"]).replace("nan", "")
                    + f";手工备注纠正({old_voucher}->{correct_voucher})"
                )

    _p("  提取门店信息...")
    df["提取门店"] = df.apply(lambda row: StoreExtractor.extract(row.get("订单备注", "")), axis=1)

    _p("  提取样转销信息...")
    df["样转销信息"] = df.apply(lambda row: SampleSaleExtractor.extract(row.get("订单备注", "")), axis=1)

    # 样转销且提取到样机型号的，标记排除（历史入库已记录）
    for idx in df.index:
        if not df.loc[idx, "是否排除"] and df.loc[idx, "备注分类"] == "样转销":
            info = df.loc[idx, "样转销信息"]
            if info and isinstance(info, dict) and "型号" in info:
                df.loc[idx, "是否排除"] = True
                df.loc[idx, "排除原因"] = "样转销-历史入库已记录"
                df.loc[idx, "提取凭证"] = None
                df.loc[idx, "_all_vouchers"] = ""

    return df


# =============================================================================
# 匹配引擎（从 MatchEngine 逐字迁移）
# =============================================================================

class _MatchEngine:
    """5 层匹配引擎（内部使用，操作 DataFrame）"""

    def match(self, ruku_df, qianshou_df):
        _p("开始匹配...")
        has_check_month = "_check_month_match" in qianshou_df.columns
        if has_check_month:
            qs_priority = qianshou_df[qianshou_df["_check_month_match"]].copy()
            qs_rest = qianshou_df[~qianshou_df["_check_month_match"]].copy()
            priority_count = len(qs_priority)
            rest_count = len(qs_rest)
            _p(f"  [核对月优先] 核对月匹配: {priority_count} 条, 其他: {rest_count} 条")

            matched_pairs, unmatched_ruku, _ = self._run_all_layers(ruku_df, qs_priority)

            if unmatched_ruku and rest_count > 0:
                _p(f"  [核对月优先] 第一轮后未匹配入库 {len(unmatched_ruku)} 条，扩展至全部签收记录")
                qs_full = pd.concat([qs_priority, qs_rest])
                layer2_pairs, unmatched_ruku, unmatched_qianshou = self._run_all_layers_from_ruku(
                    ruku_df, qs_full, unmatched_ruku
                )
                matched_pairs.extend(layer2_pairs)
            else:
                unmatched_qianshou = list(qs_rest.index) if rest_count > 0 else []
        else:
            matched_pairs, unmatched_ruku, unmatched_qianshou = self._run_all_layers(ruku_df, qianshou_df)

        _p("  追踪调整单...")
        matched_pairs = self._track_adjustment_orders(qianshou_df, matched_pairs, ruku_df)

        all_qs = set(qianshou_df.index)
        matched_qs = set(p["qianshou_idx"] for p in matched_pairs)
        final_unmatched_qianshou = list(all_qs - matched_qs)

        _p(f"匹配完成: 总匹配 {len(matched_pairs)} 对, 未匹配入库 {len(unmatched_ruku)} 条, 未匹配签收 {len(final_unmatched_qianshou)} 条")

        return {
            "matched_pairs": matched_pairs,
            "unmatched_ruku": unmatched_ruku,
            "unmatched_qianshou": final_unmatched_qianshou,
        }

    def _run_all_layers(self, ruku_df, qianshou_df):
        matched_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_voucher(ruku_df, qianshou_df)

        if unmatched_ruku and unmatched_qianshou:
            layer2_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_model_store_qty(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(layer2_pairs)

        if unmatched_ruku and unmatched_qianshou:
            layer3_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_model_qty(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(layer3_pairs)

        if unmatched_ruku and unmatched_qianshou:
            layer4_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_sample_sale(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(layer4_pairs)

        if unmatched_ruku and unmatched_qianshou:
            agg_pairs, unmatched_ruku, unmatched_qianshou = self._match_aggregated(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(agg_pairs)

        return matched_pairs, unmatched_ruku, unmatched_qianshou

    def _run_all_layers_from_ruku(self, ruku_df, qianshou_df, unmatched_ruku):
        all_qs = set(qianshou_df.index)
        already_matched_qs = set()
        unmatched_qianshou = list(all_qs - already_matched_qs)

        matched_pairs = []

        if unmatched_ruku and unmatched_qianshou:
            layer2_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_model_store_qty(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(layer2_pairs)

        if unmatched_ruku and unmatched_qianshou:
            layer3_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_model_qty(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(layer3_pairs)

        if unmatched_ruku and unmatched_qianshou:
            layer4_pairs, unmatched_ruku, unmatched_qianshou = self._match_by_sample_sale(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(layer4_pairs)

        if unmatched_ruku and unmatched_qianshou:
            agg_pairs, unmatched_ruku, unmatched_qianshou = self._match_aggregated(
                ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou
            )
            matched_pairs.extend(agg_pairs)

        return matched_pairs, unmatched_ruku, unmatched_qianshou

    def _track_adjustment_orders(self, qianshou_df, matched_pairs, ruku_df):
        adjustment_count = 0
        for pair in matched_pairs:
            qs_idx = pair["qianshou_idx"]
            if qs_idx not in qianshou_df.index:
                continue
            ruku_idx = pair["ruku_idx"]
            ruku_row = ruku_df.loc[ruku_idx]
            ruku_model = self._normalize_model(ruku_row.get("规格型号"))

            original_row = qianshou_df.loc[qs_idx]
            original_danhao = original_row.get("新方舟销售单号", "")
            original_amount = original_row.get("签收金额", 0)

            latest_adj_idx, adjustment_chain = self._find_latest_adjustment(
                qianshou_df, str(original_danhao), [], ruku_model, original_amount
            )

            if latest_adj_idx is not None:
                adj_row = qianshou_df.loc[latest_adj_idx]
                pair["original_qianshou_idx"] = qs_idx
                pair["qianshou_idx"] = latest_adj_idx
                pair["match_type"] = pair.get("match_type", "") + "-追踪调整单"
                pair["original_danhao"] = str(original_danhao)
                pair["adjustment_danhao"] = str(adj_row.get("新方舟销售单号", ""))
                pair["adjustment_chain"] = adjustment_chain
                adjustment_count += 1

        _p(f"    追踪到 {adjustment_count} 个调整单")
        return matched_pairs

    def _find_latest_adjustment(self, qianshou_df, original_danhao, chain, ruku_model=None, ruku_amount=None):
        all_adjustments = []
        for adj_idx, adj_row in qianshou_df.iterrows():
            adj_remark = str(adj_row.get("订单备注", ""))
            match = re.search(r"(?:原单号[：:]\s*)?(S\d{13,18})", adj_remark)
            if match:
                ref_danhao = match.group(1).strip()
                if ref_danhao == original_danhao or ref_danhao == original_danhao.lstrip("S"):
                    if any(kw in adj_remark for kw in ["利率", "一进一退", "一退一进", "价格错误"]):
                        continue
                    if ruku_model:
                        adj_model = self._normalize_model(adj_row.get("产品型号"))
                        if adj_model != ruku_model:
                            continue
                    if ruku_amount is not None:
                        adj_amount = adj_row.get("签收金额", 0)
                        if pd.notna(adj_amount) and float(ruku_amount) != 0:
                            amount_diff_rate = abs(float(ruku_amount) - float(adj_amount)) / abs(float(ruku_amount))
                            if amount_diff_rate > 0.8:
                                continue
                    all_adjustments.append((adj_idx, adj_row))

        if not all_adjustments:
            return None, chain

        def sort_key(item):
            adj_idx, adj_row = item
            date = adj_row.get("签收日期", pd.Timestamp.min)
            if pd.isna(date):
                date = pd.Timestamp.min
            danhao = str(adj_row.get("新方舟销售单号", ""))
            return (date, danhao)

        all_adjustments.sort(key=sort_key, reverse=True)

        latest_idx, latest_row = all_adjustments[0]
        latest_danhao = str(latest_row.get("新方舟销售单号", ""))
        new_chain = chain + [latest_danhao]

        next_adj, next_chain = self._find_latest_adjustment(
            qianshou_df, latest_danhao, new_chain, ruku_model, ruku_amount
        )

        if next_adj is not None:
            return next_adj, next_chain
        else:
            return latest_idx, new_chain

    def _match_by_voucher(self, ruku_df, qianshou_df):
        """第1层：凭证精确匹配（聚合+正负向分离）"""
        _p("  第1层: 凭证精确匹配...")

        voucher_index = {}
        for idx, row in qianshou_df.iterrows():
            voucher = row.get("提取凭证")
            if voucher and str(voucher).strip() != "":
                if voucher not in voucher_index:
                    voucher_index[voucher] = []
                voucher_index[voucher].append(idx)

        if "_all_vouchers" in qianshou_df.columns:
            for idx, row in qianshou_df.iterrows():
                all_v_str = row.get("_all_vouchers", "")
                if all_v_str and isinstance(all_v_str, str) and "|" in all_v_str:
                    for v in all_v_str.split("|"):
                        v = v.strip()
                        if v and v not in voucher_index:
                            voucher_index[v] = []
                        if v and idx not in voucher_index[v]:
                            voucher_index[v].append(idx)

        ruku_groups = {}
        for idx in ruku_df.index:
            row = ruku_df.loc[idx]
            voucher = row.get("采购凭证")
            if voucher is None or pd.isna(voucher) or str(voucher).strip() == "":
                continue
            try:
                voucher = str(int(float(voucher))).strip()
            except (ValueError, TypeError):
                continue
            model = self._normalize_model(row.get("规格型号"))
            is_return = row.get("_is_return", False)
            key = (voucher, model, is_return)
            if key not in ruku_groups:
                ruku_groups[key] = {"ruku_indices": [], "total_qty": 0}
            ruku_groups[key]["ruku_indices"].append(idx)
            ruku_groups[key]["total_qty"] += abs(float(row.get("数量", 0)))

        matched_pairs = []
        matched_ruku = set()
        matched_qianshou = set()

        for (voucher, model, is_return), group in ruku_groups.items():
            if voucher not in voucher_index:
                continue

            ruku_indices = group["ruku_indices"]
            ruku_total_qty = group["total_qty"]

            qs_candidates = []
            for qs_idx in voucher_index[voucher]:
                if qs_idx in matched_qianshou:
                    continue
                qs_row = qianshou_df.loc[qs_idx]
                if self._normalize_model(qs_row.get("产品型号")) != model:
                    continue
                if qs_row.get("_is_return", False) != is_return:
                    continue
                qs_candidates.append(qs_idx)

            if not qs_candidates:
                continue

            qs_total_qty = sum(abs(float(qianshou_df.loc[i, "签收数量"])) for i in qs_candidates)

            if abs(ruku_total_qty - qs_total_qty) < 0.01:
                is_one_to_one = len(ruku_indices) == 1 and len(qs_candidates) == 1
                for ri in ruku_indices:
                    matched_ruku.add(ri)
                    for qi in qs_candidates:
                        matched_qianshou.add(qi)
                        matched_pairs.append({
                            "ruku_idx": ri,
                            "qianshou_idx": qi,
                            "match_type": "凭证精确匹配" if is_one_to_one else "凭证匹配-聚合",
                            "confidence": 1.0 if is_one_to_one else 0.85,
                        })
            else:
                for ri in ruku_indices:
                    ruku_row = ruku_df.loc[ri]
                    if len(qs_candidates) == 1:
                        matched_ruku.add(ri)
                        matched_qianshou.add(qs_candidates[0])
                        matched_pairs.append({
                            "ruku_idx": ri,
                            "qianshou_idx": qs_candidates[0],
                            "match_type": "凭证匹配-数量不完全一致",
                            "confidence": 0.7,
                        })
                    else:
                        best = self._select_best_candidate(ruku_row, qs_candidates, qianshou_df)
                        matched_ruku.add(ri)
                        matched_qianshou.add(best)
                        matched_pairs.append({
                            "ruku_idx": ri,
                            "qianshou_idx": best,
                            "match_type": "凭证匹配-多对一",
                            "confidence": 0.75,
                            "all_candidates": qs_candidates,
                        })

        unmatched_ruku = [i for i in ruku_df.index if i not in matched_ruku]
        unmatched_qianshou = [i for i in qianshou_df.index if i not in matched_qianshou]

        _p(f"    匹配 {len(matched_pairs)} 对, 剩余未匹配入库 {len(unmatched_ruku)} 条, 签收 {len(unmatched_qianshou)} 条")
        return matched_pairs, unmatched_ruku, unmatched_qianshou

    def _select_best_candidate(self, ruku_row, candidates, qianshou_df):
        ruku_store = ruku_row.get("门店名称")
        ruku_amount = ruku_row.get("含税金额", 0)
        ruku_model = self._normalize_model(ruku_row.get("规格型号"))
        ruku_date = ruku_row.get("过账日期") or ruku_row.get("入库日期") or ruku_row.get("日期")

        ruku_voucher_raw = ruku_row.get("采购凭证", "")
        ruku_voucher = ""
        if pd.notna(ruku_voucher_raw):
            try:
                ruku_voucher = str(int(float(ruku_voucher_raw)))
            except Exception:
                ruku_voucher = str(ruku_voucher_raw).strip()

        voucher_match_candidates = []
        if ruku_voucher:
            for qs_idx in candidates:
                qs_row = qianshou_df.loc[qs_idx]
                qs_remark = str(qs_row.get("订单备注", ""))
                if ruku_voucher in qs_remark:
                    voucher_match_candidates.append(qs_idx)

        if voucher_match_candidates:
            for qs_idx in voucher_match_candidates:
                qs_row = qianshou_df.loc[qs_idx]
                qs_amount = qs_row.get("签收金额", 0)
                if pd.notna(ruku_amount) and pd.notna(qs_amount) and ruku_amount != 0:
                    amount_diff = abs(float(ruku_amount) - float(qs_amount))
                    if amount_diff < 100:
                        return qs_idx
            return voucher_match_candidates[0]

        exact_amount_candidates = []
        for qs_idx in candidates:
            qs_row = qianshou_df.loc[qs_idx]
            qs_amount = qs_row.get("签收金额", 0)
            if pd.notna(ruku_amount) and pd.notna(qs_amount) and ruku_amount != 0:
                amount_diff = abs(float(ruku_amount) - float(qs_amount))
                if amount_diff < 0.01:
                    exact_amount_candidates.append(qs_idx)

        if exact_amount_candidates:
            for qs_idx in exact_amount_candidates:
                qs_row = qianshou_df.loc[qs_idx]
                qs_store = qs_row.get("提取门店")
                if self._match_store(ruku_store, qs_store):
                    return qs_idx
            return exact_amount_candidates[0]

        best_score = -1
        best_candidate = candidates[0]

        for qs_idx in candidates:
            qs_row = qianshou_df.loc[qs_idx]
            score = 0

            qs_amount = qs_row.get("签收金额", 0)
            if pd.notna(ruku_amount) and pd.notna(qs_amount) and ruku_amount != 0:
                amount_diff = abs(float(ruku_amount) - float(qs_amount))
                if amount_diff < 0.01:
                    score += 10
                elif amount_diff < 10:
                    score += 7
                elif amount_diff < 100:
                    score += 3

            qs_store = qs_row.get("提取门店")
            if qs_store:
                score += 1
            if self._match_store(ruku_store, qs_store):
                score += 3

            qs_model = self._normalize_model(qs_row.get("产品型号"))
            if ruku_model and qs_model and ruku_model == qs_model:
                score += 2

            if qs_row.get("_check_month_match", False):
                score += 6

            qs_date = qs_row.get("签收日期")
            if pd.isna(qs_date):
                danhao = str(qs_row.get("新方舟销售单号", ""))
                m = re.match(r"S\d{4}(\d{2})(\d{2})(\d{2})\d+", danhao)
                if m:
                    qs_date = f"20{m.group(1)}-{m.group(2)}-{m.group(3)}"
            if pd.notna(ruku_date) and pd.notna(qs_date):
                try:
                    signed_diff = (pd.to_datetime(ruku_date) - pd.to_datetime(qs_date)).days
                    abs_diff = abs(signed_diff)
                    if abs_diff == 0:
                        score += 5
                    elif abs_diff <= 7:
                        score += 5 if signed_diff <= 0 else 3
                    elif abs_diff <= 30:
                        score += 4 if signed_diff <= 0 else 2
                    elif abs_diff <= 60:
                        score += 2 if signed_diff <= 0 else 1
                    elif abs_diff > 90:
                        score -= 5
                except Exception:
                    pass

            if score > best_score:
                best_score = score
                best_candidate = qs_idx

        return best_candidate

    def _normalize_model(self, model):
        if model is None or pd.isna(model):
            return ""
        m = str(model).strip()
        if " " in m:
            parts = m.split()
            for part in reversed(parts):
                if re.search(r"\d", part):
                    m = part
                    break
        return m.replace(" ", "").replace("-", "").upper()

    def _date_too_far(self, ruku_row, qs_row, max_days=90):
        ruku_date = ruku_row.get("过账日期") or ruku_row.get("入库日期") or ruku_row.get("日期")
        if pd.isna(ruku_date):
            return False

        qs_date = qs_row.get("签收日期")
        if pd.isna(qs_date):
            danhao = str(qs_row.get("新方舟销售单号", ""))
            match = re.match(r"S\d{4}(\d{2})(\d{2})(\d{2})\d+", danhao)
            if match:
                qs_date = f"20{match.group(1)}-{match.group(2)}-{match.group(3)}"
            else:
                return False

        try:
            diff = (pd.to_datetime(ruku_date) - pd.to_datetime(qs_date)).days
            return abs(diff) > max_days
        except Exception:
            return False

    def _match_store(self, ruku_store, qianshou_store):
        if ruku_store is None or qianshou_store is None:
            return False
        if pd.isna(ruku_store) or pd.isna(qianshou_store):
            return False
        ruku = str(ruku_store).strip()
        qs = str(qianshou_store).strip()
        if ruku == qs:
            return True
        if ruku in qs or qs in ruku:
            return True
        if StoreExtractor.match_stores(ruku, qs):
            return True
        return False

    def _match_by_model_store_qty(self, ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou):
        """第2层：型号+门店+数量匹配"""
        _p("  第2层: 型号+门店+数量匹配...")
        matched_pairs = []
        still_unmatched_ruku = []
        matched_qianshou = set()

        for ruku_idx in unmatched_ruku:
            ruku_row = ruku_df.loc[ruku_idx]
            ruku_store = ruku_row.get("门店名称")
            ruku_amount = ruku_row.get("含税金额", 0)

            candidates = []
            for qs_idx in unmatched_qianshou:
                if qs_idx in matched_qianshou:
                    continue
                qs_row = qianshou_df.loc[qs_idx]
                if self._normalize_model(ruku_row.get("规格型号")) != self._normalize_model(qs_row.get("产品型号")):
                    continue
                if ruku_row.get("_is_return", False) != qs_row.get("_is_return", False):
                    continue
                qs_store = qs_row.get("提取门店")
                if not self._match_store(ruku_store, qs_store):
                    continue
                ruku_qty = abs(ruku_row.get("数量", 0))
                qs_qty = abs(qs_row.get("签收数量", 0))
                if ruku_qty != qs_qty:
                    continue
                qs_amount = qs_row.get("签收金额", 0)
                if pd.notna(ruku_amount) and pd.notna(qs_amount) and ruku_amount != 0:
                    amount_diff = abs(float(ruku_amount) - float(qs_amount))
                    amount_diff_rate = amount_diff / max(abs(float(ruku_amount)), abs(float(qs_amount)), 1)
                    if amount_diff_rate > 0.2:
                        continue
                candidates.append(qs_idx)

            if len(candidates) == 1:
                matched_pairs.append({
                    "ruku_idx": ruku_idx, "qianshou_idx": candidates[0],
                    "match_type": "型号+门店+数量匹配", "confidence": 0.7,
                })
                matched_qianshou.add(candidates[0])
            elif len(candidates) > 1:
                best_idx = self._select_best_candidate(ruku_row, candidates, qianshou_df)
                matched_pairs.append({
                    "ruku_idx": ruku_idx, "qianshou_idx": best_idx,
                    "match_type": "需人工确认-多候选", "confidence": 0.5,
                    "all_candidates": candidates,
                })
                matched_qianshou.add(best_idx)
            else:
                still_unmatched_ruku.append(ruku_idx)

        remaining_qianshou = [idx for idx in unmatched_qianshou if idx not in matched_qianshou]
        _p(f"    匹配 {len(matched_pairs)} 对, 剩余未匹配入库 {len(still_unmatched_ruku)} 条, 签收 {len(remaining_qianshou)} 条")
        return matched_pairs, still_unmatched_ruku, remaining_qianshou

    def _match_by_model_qty(self, ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou):
        """第3层：型号+数量匹配（针对无门店信息的）"""
        _p("  第3层: 型号+数量匹配...")
        matched_pairs = []
        still_unmatched_ruku = []
        matched_qianshou = set()

        for ruku_idx in unmatched_ruku:
            ruku_row = ruku_df.loc[ruku_idx]
            ruku_amount = ruku_row.get("含税金额", 0)

            candidates = []
            for qs_idx in unmatched_qianshou:
                if qs_idx in matched_qianshou:
                    continue
                qs_row = qianshou_df.loc[qs_idx]
                if self._normalize_model(ruku_row.get("规格型号")) != self._normalize_model(qs_row.get("产品型号")):
                    continue
                if ruku_row.get("_is_return", False) != qs_row.get("_is_return", False):
                    continue
                ruku_qty = abs(ruku_row.get("数量", 0))
                qs_qty = abs(qs_row.get("签收数量", 0))
                if ruku_qty != qs_qty:
                    continue
                qs_amount = qs_row.get("签收金额", 0)
                if pd.notna(ruku_amount) and pd.notna(qs_amount) and ruku_amount != 0:
                    amount_diff = abs(float(ruku_amount) - float(qs_amount))
                    amount_diff_rate = amount_diff / max(abs(float(ruku_amount)), abs(float(qs_amount)), 1)
                    if amount_diff_rate > 0.2:
                        continue
                candidates.append(qs_idx)

            if len(candidates) == 1:
                if self._date_too_far(ruku_row, qianshou_df.loc[candidates[0]]):
                    still_unmatched_ruku.append(ruku_idx)
                    continue
                matched_pairs.append({
                    "ruku_idx": ruku_idx, "qianshou_idx": candidates[0],
                    "match_type": "型号+数量匹配", "confidence": 0.6,
                })
                matched_qianshou.add(candidates[0])
            elif len(candidates) > 1:
                best_idx = self._select_best_candidate(ruku_row, candidates, qianshou_df)
                if self._date_too_far(ruku_row, qianshou_df.loc[best_idx]):
                    still_unmatched_ruku.append(ruku_idx)
                    continue
                matched_pairs.append({
                    "ruku_idx": ruku_idx, "qianshou_idx": best_idx,
                    "match_type": "需人工确认-多候选(无门店)", "confidence": 0.4,
                    "all_candidates": candidates,
                })
                matched_qianshou.add(best_idx)
            else:
                still_unmatched_ruku.append(ruku_idx)

        remaining_qianshou = [idx for idx in unmatched_qianshou if idx not in matched_qianshou]
        _p(f"    匹配 {len(matched_pairs)} 对, 剩余未匹配入库 {len(still_unmatched_ruku)} 条, 签收 {len(remaining_qianshou)} 条")
        return matched_pairs, still_unmatched_ruku, remaining_qianshou

    def _match_by_sample_sale(self, ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou):
        """第4层：样转销匹配"""
        _p("  第4层: 样转销匹配...")
        matched_pairs = []
        still_unmatched_ruku = []
        matched_qianshou = set()

        sample_sale_qianshou = []
        for qs_idx in unmatched_qianshou:
            if qs_idx in matched_qianshou:
                continue
            qs_row = qianshou_df.loc[qs_idx]
            sample_info = qs_row.get("样转销信息")
            if sample_info and isinstance(sample_info, dict):
                sample_sale_qianshou.append(qs_idx)

        _p(f"    可用样转销记录: {len(sample_sale_qianshou)} 条")

        for ruku_idx in unmatched_ruku:
            ruku_row = ruku_df.loc[ruku_idx]
            best_match = None
            best_score = 0.0

            for qs_idx in sample_sale_qianshou:
                if qs_idx in matched_qianshou:
                    continue
                qs_row = qianshou_df.loc[qs_idx]
                score = SampleSaleExtractor.match_sample_sale(ruku_row, qs_row)
                if score > best_score:
                    best_score = score
                    best_match = qs_idx

            if best_match and best_score >= 0.6:
                matched_pairs.append({
                    "ruku_idx": ruku_idx, "qianshou_idx": best_match,
                    "match_type": f"样转销匹配({best_score:.1f})", "confidence": best_score,
                })
                matched_qianshou.add(best_match)
            else:
                still_unmatched_ruku.append(ruku_idx)

        remaining_qianshou = [idx for idx in unmatched_qianshou if idx not in matched_qianshou]
        _p(f"    匹配 {len(matched_pairs)} 对, 剩余未匹配入库 {len(still_unmatched_ruku)} 条, 签收 {len(remaining_qianshou)} 条")
        return matched_pairs, still_unmatched_ruku, remaining_qianshou

    def _match_aggregated(self, ruku_df, qianshou_df, unmatched_ruku, unmatched_qianshou):
        """第5层：聚合匹配（多对一）"""
        _p("  第5层: 聚合匹配(多对一)...")
        import itertools

        qs_to_ruku = {}
        for ruku_idx in unmatched_ruku:
            ruku_row = ruku_df.loc[ruku_idx]
            raw_voucher = ruku_row.get("采购凭证")
            if raw_voucher is None or pd.isna(raw_voucher) or str(raw_voucher).strip() == "":
                continue
            try:
                ruku_voucher = str(int(float(raw_voucher))).strip()
            except (ValueError, TypeError):
                continue

            ruku_model = self._normalize_model(ruku_row.get("规格型号"))
            ruku_qty = abs(float(ruku_row.get("数量", 0)))
            ruku_is_return = ruku_row.get("_is_return", False)

            for qs_idx in unmatched_qianshou:
                qs_row = qianshou_df.loc[qs_idx]
                if qs_row.get("是否排除", False):
                    continue
                if qs_row.get("_is_return", False) != ruku_is_return:
                    continue
                if self._normalize_model(qs_row.get("产品型号")) != ruku_model:
                    continue
                qs_primary = str(qs_row.get("提取凭证", ""))
                qs_all = str(qs_row.get("_all_vouchers", ""))
                voucher_match = (qs_primary == ruku_voucher)
                if not voucher_match and qs_all:
                    voucher_match = ruku_voucher in qs_all.split("|")
                if not voucher_match:
                    continue
                if qs_idx not in qs_to_ruku:
                    qs_to_ruku[qs_idx] = []
                qs_to_ruku[qs_idx].append((ruku_idx, ruku_qty))

        if not qs_to_ruku:
            return [], unmatched_ruku, unmatched_qianshou

        group_candidates = []
        for qs_idx, candidates in qs_to_ruku.items():
            qs_qty = abs(float(qianshou_df.loc[qs_idx].get("签收数量", 0)))
            if qs_qty == 0:
                continue
            best_subset = None
            best_ratio = float("inf")
            for r in range(1, min(len(candidates), 5) + 1):
                for subset in itertools.combinations(candidates, r):
                    subset_total = sum(qty for _, qty in subset)
                    if subset_total == 0:
                        continue
                    ratio = max(subset_total, qs_qty) / min(subset_total, qs_qty)
                    if ratio <= 1.05 and ratio < best_ratio:
                        best_subset = subset
                        best_ratio = ratio
            if best_subset:
                group_candidates.append((qs_idx, best_subset, best_ratio))

        if not group_candidates:
            return [], unmatched_ruku, unmatched_qianshou

        group_candidates.sort(key=lambda x: (x[2], len(x[1])))

        matched_pairs = []
        matched_ruku_set = set()
        matched_qianshou_set = set()

        for qs_idx, subset, ratio in group_candidates:
            subset_indices = [idx for idx, _ in subset]
            if any(idx in matched_ruku_set for idx in subset_indices):
                continue
            qs_qty = abs(float(qianshou_df.loc[qs_idx].get("签收数量", 0)))
            subset_total = sum(qty for _, qty in subset)
            for ruku_idx, ruku_qty in subset:
                matched_pairs.append({
                    "ruku_idx": ruku_idx,
                    "qianshou_idx": qs_idx,
                    "match_type": f"聚合匹配(多对一,入库{subset_total:.0f}≈签收{qs_qty:.0f})",
                })
                matched_ruku_set.add(ruku_idx)
            matched_qianshou_set.add(qs_idx)

        remaining_ruku = [idx for idx in unmatched_ruku if idx not in matched_ruku_set]
        remaining_qianshou = [idx for idx in unmatched_qianshou if idx not in matched_qianshou_set]

        _p(f"    匹配 {len(matched_pairs)} 对 (涉及 {len(matched_qianshou_set)} 张签收单), "
           f"剩余未匹配入库 {len(remaining_ruku)} 条, 签收 {len(remaining_qianshou)} 条")
        return matched_pairs, remaining_ruku, remaining_qianshou


# =============================================================================
# 平台适配层
# =============================================================================

class ChongbaiEngine(MatchEngine):
    """重百智屏匹配引擎（平台插件）

    - 客户方(customer_settlements) = 重百入库明细
    - 我方(our_receipts) = TCL 销售签收明细（含台账辅助列 核对/项目/备注）
    """

    engine_version = ENGINE_VERSION

    def parse_customer_data(self, raw_df) -> list[CustomerSettlement]:
        """解析重百入库明细 → CustomerSettlement 列表"""
        df = _standardize_columns(raw_df, RUKU_COLUMN_MAPPING)

        # 过滤空行（凭证/型号/数量全为空）
        if "采购凭证" in df.columns and "规格型号" in df.columns and "数量" in df.columns:
            empty_mask = df["采购凭证"].isna() & df["规格型号"].isna() & df["数量"].isna()
            df = df[~empty_mask].copy()

        settlements = []
        for _, row in df.iterrows():
            settlements.append(CustomerSettlement(
                id=row.name,
                match_key=self._clean_voucher(row.get("采购凭证")),
                model=self._safe_str(row.get("规格型号")),
                quantity=self._safe_float(row.get("数量")),
                amount=self._safe_float(row.get("含税金额")),
                unit_price=0.0,
                settlement_date=self._safe_str(row.get("过账日期")),
                raw_data=row.to_dict(),
            ))
        return settlements

    def match(
        self,
        our_receipts: list[OurReceipt],
        customer_settlements: list[CustomerSettlement],
    ) -> MatchResult:
        """执行重百 5 层匹配。内部转换为 DataFrame 复刻原脚本逻辑。"""
        if not our_receipts or not customer_settlements:
            return self._empty_result(our_receipts, customer_settlements)

        # 1) 构建入库 DataFrame（客户方）。索引直接用平台 settlement_id，
        #    避免 reset_index 改变索引空间——匹配引擎中 list(set(index)) 的迭代顺序
        #    对少数顺序敏感的边界匹配有影响，保留原始 id 可与来源数据保持一致。
        ruku_df = pd.DataFrame([{**(s.raw_data or {}), "_settlement_id": s.id} for s in customer_settlements])
        ruku_df = _standardize_columns(ruku_df, RUKU_COLUMN_MAPPING)
        ruku_df.index = pd.Index([s.id for s in customer_settlements])

        # 2) 构建签收 DataFrame（我方）。索引用平台 receipt_id。
        qs_df = pd.DataFrame([{**(r.raw_data or {}), "_receipt_id": r.id} for r in our_receipts])
        qs_df = _standardize_columns(qs_df, QIANGSHOU_COLUMN_MAPPING)
        qs_df.index = pd.Index([r.id for r in our_receipts])

        # 3) 推导目标年月（入库过账日期的主月份）并做时间窗口筛选
        target_year, target_month = self._infer_target_period(ruku_df)
        if target_year and target_month:
            qs_df = _filter_by_target_month(qs_df, target_year, target_month, LOOKBACK_MONTHS)
        else:
            qs_df = qs_df.copy()
            qs_df["_check_month_match"] = False

        # 4) 预处理签收
        qs_df = preprocess_qianshou(qs_df)

        # 5) 标记退货方向
        ruku_df["_is_return"] = (
            (pd.to_numeric(ruku_df["数量"], errors="coerce").fillna(0) < 0)
            | (ruku_df.get("单据描述", pd.Series(dtype=str)).astype(str).str.contains("退货", na=False))
        )
        qs_df["_is_return"] = (
            (pd.to_numeric(qs_df["签收数量"], errors="coerce").fillna(0) < 0)
            | (qs_df.get("单据类型", pd.Series(dtype=str)).astype(str).str.contains("退货", na=False))
        )

        # 6) 执行匹配
        result = _MatchEngine().match(ruku_df, qs_df)

        # 7) 映射回平台 id
        ruku_id = ruku_df["_settlement_id"].to_dict()
        qs_id = qs_df["_receipt_id"].to_dict()

        matched_pairs = []
        matched_settlement_ids = set()
        matched_receipt_ids = set()
        for pair in result["matched_pairs"]:
            sid = ruku_id.get(pair["ruku_idx"])
            rid = qs_id.get(pair["qianshou_idx"])
            if sid is None or rid is None:
                continue
            s_row = ruku_df.loc[pair["ruku_idx"]]
            q_row = qs_df.loc[pair["qianshou_idx"]]
            matched_pairs.append(MatchPair(
                receipt_id=rid,
                settlement_id=sid,
                match_type=pair.get("match_type", ""),
                confidence=float(pair.get("confidence", 0.0) or 0.0),
                diff_amount=self._diff(q_row.get("签收金额"), s_row.get("含税金额")),
                diff_quantity=self._diff(q_row.get("签收数量"), s_row.get("数量"), absolute=True),
                detail={"新方舟销售单号": self._safe_str(q_row.get("新方舟销售单号")),
                        "采购凭证": self._clean_voucher(s_row.get("采购凭证"))},
            ))
            matched_settlement_ids.add(sid)
            matched_receipt_ids.add(rid)

        unmatched_settlements = [s.id for s in customer_settlements if s.id not in matched_settlement_ids]
        unmatched_receipts = [r.id for r in our_receipts if r.id not in matched_receipt_ids]

        return MatchResult(
            matched_pairs=matched_pairs,
            unmatched_receipts=unmatched_receipts,
            unmatched_settlements=unmatched_settlements,
            excluded_settlements=[],
            engine_version=self.engine_version,
            summary={
                "total_receipts": len(our_receipts),
                "total_settlements": len(customer_settlements),
                "matched": len(matched_pairs),
                "unmatched_receipts": len(unmatched_receipts),
                "unmatched_settlements": len(unmatched_settlements),
                "target_period": f"{target_year}{target_month:02d}" if target_year else "",
            },
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _empty_result(self, our_receipts, customer_settlements) -> MatchResult:
        return MatchResult(
            matched_pairs=[],
            unmatched_receipts=[r.id for r in our_receipts],
            unmatched_settlements=[s.id for s in customer_settlements],
            excluded_settlements=[],
            engine_version=self.engine_version,
            summary={"total_receipts": len(our_receipts), "total_settlements": len(customer_settlements), "matched": 0},
        )

    def _infer_target_period(self, ruku_df):
        """从入库过账日期推导目标年月（取众数月份，入库明细为单月数据）"""
        if "过账日期" not in ruku_df.columns:
            return None, None
        dates = pd.to_datetime(ruku_df["过账日期"], errors="coerce").dropna()
        if dates.empty:
            return None, None
        ym = dates.dt.strftime("%Y-%m")
        top = ym.value_counts().idxmax()
        y, m = top.split("-")
        return int(y), int(m)

    @staticmethod
    def _clean_voucher(value):
        """采购凭证标准化：去掉浮点小数点（4534996557.0 → '4534996557'）"""
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return ""
        try:
            return str(int(float(value)))
        except (ValueError, TypeError):
            return str(value).strip()

    @staticmethod
    def _safe_str(value, default=""):
        if value is None:
            return default
        if isinstance(value, float) and value != value:  # NaN
            return default
        return str(value).strip()

    @staticmethod
    def _safe_float(value):
        if value is None or (isinstance(value, float) and value != value):
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _diff(a, b, absolute=False):
        try:
            av = abs(float(a)) if absolute else float(a)
            bv = abs(float(b)) if absolute else float(b)
            return round(av - bv, 2)
        except (ValueError, TypeError):
            return 0.0
