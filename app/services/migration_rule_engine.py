# 迁移规则引擎

import re
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml


class MigrationRuleEngine:
    """迁移规则引擎

    从 YAML 文件加载客户的清洗规则，并应用到 Excel 清洗过程中。
    """

    @staticmethod
    def load_rules(rules_file_path: str) -> dict:
        """
        从 YAML 文件加载规则

        Args:
            rules_file_path: 规则文件路径（如 scripts/migration/rules/weifangbaihuo.yaml）

        Returns:
            规则字典，包含 column_mapping/status_mapping/special_rules

        Raises:
            FileNotFoundError: 规则文件不存在
        """
        path = Path(rules_file_path)
        if not path.exists():
            raise FileNotFoundError(f"规则文件不存在: {rules_file_path}")

        with open(path, "r", encoding="utf-8") as f:
            rules = yaml.safe_load(f)

        return rules

    @staticmethod
    def load_rules_by_customer(customer_slug: str, rules_dir: str = "scripts/migration/rules") -> dict:
        """
        按客户 slug 加载规则

        Args:
            customer_slug: 客户标识（如 weifangbaihuo）
            rules_dir: 规则文件目录

        Returns:
            规则字典

        Raises:
            FileNotFoundError: 规则文件不存在
        """
        rules_file = Path(rules_dir) / f"{customer_slug}.yaml"
        return MigrationRuleEngine.load_rules(str(rules_file))

    @staticmethod
    def apply_rules(df: pd.DataFrame, rules: dict) -> pd.DataFrame:
        """
        应用规则到 DataFrame

        Args:
            df: 原始 DataFrame（从 Excel 读取）
            rules: 规则字典（从 YAML 加载）

        Returns:
            清洗后的 DataFrame
        """
        if df.empty:
            return df

        result = df.copy()

        # 1. 应用列名映射
        column_mapping = rules.get("column_mapping", {})
        for old_col, new_col in column_mapping.items():
            if old_col in result.columns:
                # 处理扩展字段（extra_fields.红通号 -> extra_fields 字典）
                if new_col.startswith("extra_fields."):
                    field_name = new_col.split(".", 1)[1]
                    if "extra_fields" not in result.columns:
                        result["extra_fields"] = None
                    result["extra_fields"] = result.apply(
                        lambda row: MigrationRuleEngine._add_extra_field(
                            row.get("extra_fields"), field_name, row[old_col]
                        ),
                        axis=1,
                    )
                else:
                    result[new_col] = result[old_col]

        # 2. 应用特殊处理规则（在状态值映射之前）
        # 因为特殊处理规则可能会修改 billing_status 的原始值
        special_rules = rules.get("special_rules", [])
        for rule in special_rules:
            pattern = rule.get("pattern", "")
            action = rule.get("action", "")
            if pattern and action and "billing_status" in result.columns:
                result = MigrationRuleEngine._apply_special_rule(result, pattern, action)

        # 3. 应用状态值映射
        status_mapping = rules.get("status_mapping", {})
        if "billing_status" in result.columns:
            result["billing_status"] = result["billing_status"].apply(
                lambda x: MigrationRuleEngine._map_status(x, status_mapping)
            )

        return result

    @staticmethod
    def _add_extra_field(extra_fields: Optional[dict], field_name: str, value) -> dict:
        """添加扩展字段到 extra_fields 字典"""
        if pd.isna(value):
            return extra_fields

        if extra_fields is None:
            extra_fields = {}

        extra_fields[field_name] = value
        return extra_fields

    @staticmethod
    def _map_status(value, status_mapping: dict) -> str:
        """映射状态值"""
        if pd.isna(value):
            return "unbilled"

        # 如果值已经是标准枚举值（billed/unbilled/split），保留不变
        # 这是为了保留特殊处理规则设置的值
        value_str = str(value).strip()
        if value_str in ["billed", "unbilled", "split", "partial"]:
            return value_str

        # 尝试多种匹配方式：
        # 1. 直接用原始值匹配（处理数字类型的 key）
        if value in status_mapping:
            return status_mapping[value]

        # 2. 用字符串匹配（处理字符串类型的 key）
        if value_str in status_mapping:
            return status_mapping[value_str]

        # 3. 如果值是数字字符串，尝试转换为数字匹配（处理 YAML 中的数字 key）
        try:
            value_num = int(value_str)
            if value_num in status_mapping:
                return status_mapping[value_num]
        except (ValueError, TypeError):
            pass

        # 4. 如果值是数字，尝试转换为字符串匹配（处理 YAML 中的字符串 key）
        if isinstance(value, (int, float)):
            value_str_from_num = str(int(value))
            if value_str_from_num in status_mapping:
                return status_mapping[value_str_from_num]

        # 默认返回 unbilled
        return "unbilled"

    @staticmethod
    def _apply_special_rule(df: pd.DataFrame, pattern: str, action: str) -> pd.DataFrame:
        """
        应用特殊处理规则

        Args:
            df: DataFrame
            pattern: 正则表达式（如 "重复开具：(.+)"）
            action: 动作（如 "billing_status=billed, remark=重复开具：\\1"）

        Returns:
            处理后的 DataFrame
        """
        result = df.copy()

        # 解析 action
        # 格式: "field1=value1, field2=value2"
        actions = {}
        for part in action.split(","):
            part = part.strip()
            if "=" in part:
                key, value = part.split("=", 1)
                actions[key.strip()] = value.strip()

        # 应用规则到每一行
        for idx, row in result.iterrows():
            billing_status_raw = str(row.get("billing_status", ""))

            # 检查是否匹配 pattern
            match = re.search(pattern, billing_status_raw)
            if match:
                # 应用 action
                for key, value in actions.items():
                    # 替换 \1, \2 等捕获组
                    for i, group in enumerate(match.groups(), start=1):
                        value = value.replace(f"\\{i}", group)

                    # 设置值
                    if key == "billing_status":
                        result.at[idx, "billing_status"] = value
                    elif key == "remark":
                        # 如果 remark 已有值，追加；否则直接设置
                        existing_remark = result.at[idx, "remark"] if "remark" in result.columns else None
                        if pd.notna(existing_remark) and existing_remark:
                            result.at[idx, "remark"] = f"{existing_remark} {value}"
                        else:
                            result.at[idx, "remark"] = value
                    else:
                        result.at[idx, key] = value

        return result
