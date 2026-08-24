# 迁移规则引擎测试

import pandas as pd
import pytest
import yaml

from app.services.migration_rule_engine import MigrationRuleEngine


@pytest.fixture
def sample_rules_file(tmp_path):
    """创建测试规则文件"""
    rules = {
        "customer": "潍坊百货",
        "slug": "weifangbaihuo",
        "column_mapping": {
            "是否开票": "billing_status",
            "发票号": "invoice_no",
            "开票日期": "invoice_date",
            "拆分": "split_note",
            "备注": "remark",
            "红通号": "extra_fields.红通号",
            "红票勾选台数": "extra_fields.红票勾选台数",
        },
        "status_mapping": {
            "已开": "billed",
            "111": "billed",
            "手工标识已开": "billed",
            "25年已开": "billed",
            "26年已开": "billed",
            "前期已开": "billed",
            "未开": "unbilled",
            "未开确定": "unbilled",
            "已拆分": "split",
        },
        "special_rules": [
            {
                "pattern": r"重复开具：(.+)",
                "action": "billing_status=billed, remark=重复开具：\\1",
            }
        ],
    }

    rules_file = tmp_path / "weifangbaihuo.yaml"
    with open(rules_file, "w", encoding="utf-8") as f:
        yaml.dump(rules, f, allow_unicode=True)

    return str(rules_file)


@pytest.fixture
def sample_df():
    """创建测试 DataFrame"""
    return pd.DataFrame({
        "新方舟销售单号": ["S1010000000001", "S1010000000002", "S1010000000003", "S1010000000004"],
        "产品型号": ["75V69H", "75V69H", "85X11K", "85X11K"],
        "签收数量": [5, 3, 2, 1],
        "签收金额": [34650.00, 20790.00, 17000.00, 8500.00],
        "是否开票": ["已开", "111", "未开", "重复开具：24932000000078813069"],
        "发票号": ["24932000000078813068", "24932000000078813069", None, "24932000000078813070"],
        "开票日期": ["2026-08-15", "2026-08-16", None, "2026-08-17"],
        "拆分": [None, None, None, None],
        "备注": [None, None, None, None],
        "红通号": [None, None, None, None],
        "红票勾选台数": [None, None, None, None],
    })


class TestLoadRules:
    """测试加载规则"""

    def test_load_rules_success(self, sample_rules_file):
        """测试成功加载规则文件"""
        rules = MigrationRuleEngine.load_rules(sample_rules_file)

        assert rules["customer"] == "潍坊百货"
        assert rules["slug"] == "weifangbaihuo"
        assert "column_mapping" in rules
        assert "status_mapping" in rules
        assert "special_rules" in rules

    def test_load_rules_file_not_found(self):
        """测试规则文件不存在"""
        with pytest.raises(FileNotFoundError):
            MigrationRuleEngine.load_rules("nonexistent.yaml")

    def test_load_rules_column_mapping(self, sample_rules_file):
        """测试列名映射"""
        rules = MigrationRuleEngine.load_rules(sample_rules_file)

        assert rules["column_mapping"]["是否开票"] == "billing_status"
        assert rules["column_mapping"]["发票号"] == "invoice_no"
        assert rules["column_mapping"]["红通号"] == "extra_fields.红通号"

    def test_load_rules_status_mapping(self, sample_rules_file):
        """测试状态值映射"""
        rules = MigrationRuleEngine.load_rules(sample_rules_file)

        assert rules["status_mapping"]["已开"] == "billed"
        assert rules["status_mapping"]["111"] == "billed"
        assert rules["status_mapping"]["未开"] == "unbilled"
        assert rules["status_mapping"]["已拆分"] == "split"


class TestApplyRules:
    """测试应用规则"""

    def test_apply_rules_column_mapping(self, sample_rules_file, sample_df):
        """测试列名映射"""
        rules = MigrationRuleEngine.load_rules(sample_rules_file)
        result = MigrationRuleEngine.apply_rules(sample_df, rules)

        # 验证列名被正确映射
        assert "billing_status" in result.columns
        assert "invoice_no" in result.columns
        assert "invoice_date" in result.columns
        assert "split_note" in result.columns
        assert "remark" in result.columns

    def test_apply_rules_status_mapping(self, sample_rules_file, sample_df):
        """测试状态值映射"""
        rules = MigrationRuleEngine.load_rules(sample_rules_file)
        result = MigrationRuleEngine.apply_rules(sample_df, rules)

        # 验证状态值被正确映射
        assert result.iloc[0]["billing_status"] == "billed"  # 已开 -> billed
        assert result.iloc[1]["billing_status"] == "billed"  # 111 -> billed
        assert result.iloc[2]["billing_status"] == "unbilled"  # 未开 -> unbilled

    def test_apply_rules_special_rules(self, sample_rules_file, sample_df):
        """测试特殊处理规则"""
        rules = MigrationRuleEngine.load_rules(sample_rules_file)
        result = MigrationRuleEngine.apply_rules(sample_df, rules)

        # 验证特殊处理规则（重复开具：xxx -> billed + remark）
        row = result.iloc[3]
        assert row["billing_status"] == "billed"
        assert "重复开具" in str(row["remark"])

    def test_apply_rules_extra_fields(self, sample_rules_file, sample_df):
        """测试扩展字段"""
        # 添加扩展字段数据
        sample_df.loc[0, "红通号"] = "RED123456"
        sample_df.loc[0, "红票勾选台数"] = 3

        rules = MigrationRuleEngine.load_rules(sample_rules_file)
        result = MigrationRuleEngine.apply_rules(sample_df, rules)

        # 验证扩展字段被正确映射到 extra_fields
        assert "extra_fields" in result.columns
        extra_fields = result.iloc[0]["extra_fields"]
        assert extra_fields is not None
        assert extra_fields.get("红通号") == "RED123456"
        assert extra_fields.get("红票勾选台数") == 3

    def test_apply_rules_empty_df(self, sample_rules_file):
        """测试空 DataFrame"""
        empty_df = pd.DataFrame()
        rules = MigrationRuleEngine.load_rules(sample_rules_file)
        result = MigrationRuleEngine.apply_rules(empty_df, rules)

        assert len(result) == 0

    def test_apply_rules_missing_column(self, sample_rules_file):
        """测试缺少列的情况"""
        df = pd.DataFrame({
            "新方舟销售单号": ["S1010000000001"],
            "产品型号": ["75V69H"],
            # 缺少"是否开票"列
        })

        rules = MigrationRuleEngine.load_rules(sample_rules_file)
        result = MigrationRuleEngine.apply_rules(df, rules)

        # 应该正常处理，不报错
        assert len(result) == 1
