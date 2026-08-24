# 试点客户迁移规则测试

import pandas as pd
import pytest

from app.services.migration_rule_engine import MigrationRuleEngine


class TestPilotCustomerRules:
    """测试试点客户的规则文件"""

    def test_weifangbaihuo_rules_load(self):
        """测试潍坊百货规则文件可以加载"""
        rules = MigrationRuleEngine.load_rules_by_customer("weifangbaihuo")

        assert rules["customer"] == "潍坊百货"
        assert rules["slug"] == "weifangbaihuo"
        assert "column_mapping" in rules
        assert "status_mapping" in rules
        assert "special_rules" in rules

        # 验证列名映射
        assert rules["column_mapping"]["是否开票"] == "billing_status"
        assert rules["column_mapping"]["红通号"] == "extra_fields.红通号"
        assert rules["column_mapping"]["红票勾选台数"] == "extra_fields.红票勾选台数"

    def test_quanfuyuan_rules_load(self):
        """测试全福元规则文件可以加载"""
        rules = MigrationRuleEngine.load_rules_by_customer("quanfuyuan")

        assert rules["customer"] == "全福元"
        assert rules["slug"] == "quanfuyuan"
        assert "column_mapping" in rules
        assert "status_mapping" in rules

    def test_hebeijincao_rules_load(self):
        """测试河北劲草规则文件可以加载"""
        rules = MigrationRuleEngine.load_rules_by_customer("hebeijincao")

        assert rules["customer"] == "河北劲草"
        assert rules["slug"] == "hebeijincao"
        assert "column_mapping" in rules
        assert "status_mapping" in rules

        # 验证列名映射
        assert rules["column_mapping"]["开票编号"] == "extra_fields.开票编号"

    def test_tmall_rules_load(self):
        """测试天猫优品规则文件可以加载"""
        rules = MigrationRuleEngine.load_rules_by_customer("tmall")

        assert rules["customer"] == "天猫优品"
        assert rules["slug"] == "tmall"
        assert "column_mapping" in rules
        assert "status_mapping" in rules

    def test_weifangbaihuo_rules_apply(self):
        """测试潍坊百货规则可以应用"""
        rules = MigrationRuleEngine.load_rules_by_customer("weifangbaihuo")

        df = pd.DataFrame({
            "新方舟销售单号": ["S1010000000001", "S1010000000002", "S1010000000003"],
            "产品型号": ["75V69H", "75V69H", "85X11K"],
            "签收数量": [5, 3, 2],
            "签收金额": [34650.00, 20790.00, 17000.00],
            "是否开票": ["已开", "111", "未开"],
            "发票号": ["24932000000078813068", "24932000000078813069", None],
            "开票日期": ["2026-08-15", "2026-08-16", None],
            "红通号": [None, "RED123456", None],
            "红票勾选台数": [None, 3, None],
        })

        result = MigrationRuleEngine.apply_rules(df, rules)

        # 验证状态值映射
        assert result.iloc[0]["billing_status"] == "billed"
        assert result.iloc[1]["billing_status"] == "billed"
        assert result.iloc[2]["billing_status"] == "unbilled"

        # 验证扩展字段
        assert result.iloc[1]["extra_fields"]["红通号"] == "RED123456"
        assert result.iloc[1]["extra_fields"]["红票勾选台数"] == 3

    def test_hebeijincao_rules_apply(self):
        """测试河北劲草规则可以应用"""
        rules = MigrationRuleEngine.load_rules_by_customer("hebeijincao")

        df = pd.DataFrame({
            "新方舟销售单号": ["S1010000000001", "S1010000000002"],
            "产品型号": ["75V69H", "75V69H"],
            "签收数量": [5, 3],
            "签收金额": [34650.00, 20790.00],
            "是否开票": ["已开", "未开"],
            "发票号": ["24932000000078813068", None],
            "开票日期": ["2026-08-15", None],
            "开票编号": ["BILL001", None],
        })

        result = MigrationRuleEngine.apply_rules(df, rules)

        # 验证状态值映射
        assert result.iloc[0]["billing_status"] == "billed"
        assert result.iloc[1]["billing_status"] == "unbilled"

        # 验证扩展字段
        assert result.iloc[0]["extra_fields"]["开票编号"] == "BILL001"

    def test_special_rules_apply(self):
        """测试特殊处理规则可以应用"""
        rules = MigrationRuleEngine.load_rules_by_customer("weifangbaihuo")

        df = pd.DataFrame({
            "新方舟销售单号": ["S1010000000001"],
            "产品型号": ["75V69H"],
            "签收数量": [5],
            "签收金额": [34650.00],
            "是否开票": ["重复开具：24932000000078813069"],
            "发票号": ["24932000000078813068"],
            "开票日期": ["2026-08-15"],
        })

        result = MigrationRuleEngine.apply_rules(df, rules)

        # 验证特殊处理规则
        assert result.iloc[0]["billing_status"] == "billed"
        assert "重复开具" in str(result.iloc[0]["remark"])
