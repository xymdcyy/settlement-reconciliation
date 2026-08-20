# 重百智屏 —— 订单备注分类 + 项目分类
#
# 从原脚本 reconcile_all.py 逐字迁移（RemarkClassifier / ProjectClassifier），
# 仅调整 import，逻辑与阈值保持完全一致以保证匹配保真。

import re

import pandas as pd


class RemarkClassifier:
    """订单备注分类器"""

    @classmethod
    def classify(cls, remark, doc_type=""):
        """分类订单备注，返回分类名称"""
        if remark is None or str(remark).strip() == "":
            return "空备注"

        remark = str(remark).strip()
        doc_type = str(doc_type) if doc_type else ""

        # 1. 借机转销售单（费用类）
        if doc_type == "借机转销售单":
            return "借机转销售"

        # 2. 费用兑现
        if "费用兑现" in remark:
            return "费用兑现"

        # 3. 补差/价差调整
        if any(kw in remark for kw in ["价差", "补差", "调整"]):
            return "补差价差"

        # 4. CB编号（售后退厂编号）
        if re.search(r"CB\d{10}", remark):
            return "CB编号"

        # 5. 残次退厂
        if "残次退厂" in remark or ("退厂" in remark and "售后" in remark):
            return "残次退厂"

        # 6. 冲销
        if "冲销" in remark:
            return "冲销"

        # 7. 一退一进
        if any(kw in remark for kw in ["一退一进", "一进一退"]):
            return "一退一进"

        # 8. 样转销
        if any(kw in remark for kw in ["样转销", "样机"]):
            return "样转销"

        # 9. 厂送
        if "厂送" in remark:
            return "厂送"

        # 10. 收货码
        if any(kw in remark for kw in ["收货码", "提货码"]):
            return "收货码"

        # 11. 售后
        if "售后" in remark:
            return "售后"

        # 12. 大库
        if "大库" in remark:
            return "大库"

        # 13. 邮件
        if "邮件" in remark:
            return "邮件"

        # 14. 纯数字10位
        if remark.isdigit() and len(remark) == 10:
            return "纯数字"

        # 15. 标准格式：店-人 凭证/单号
        if re.search(r".+?-[一-龥]+\s+\d{10}/\d+", remark):
            return "标准格式"

        # 默认：其他
        return "其他"

    @classmethod
    def should_exclude(cls, remark, doc_type="", qty=0):
        """判断是否应排除不参与匹配，返回 (是否排除, 排除原因)"""
        category = cls.classify(remark, doc_type)

        # 明确排除的类别
        exclude_categories = {
            "借机转销售": "借机转销售单（费用类）",
            "费用兑现": "费用兑现单据",
            "CB编号": "售后CB编号记录",
            "残次退厂": "残次退厂记录",
            "厂送": "厂送订单（厂家直送，不经过重百仓库）",
            "邮件": "邮件通知类记录（无采购凭证）",
        }
        # 冲销不排除：部分冲销记录备注中仍有采购凭证可提取

        if category in exclude_categories:
            return True, exclude_categories[category]

        # 补差/价差（仅数量>100的排除，小额可能含实物流转）
        if category == "补差价差":
            if abs(qty) > 100:
                return True, "补差/价差调整（大额，非实物流转）"
            # 小额补差价差可能仍有实物对应，不排除但标记
            return False, None

        return False, None


class ProjectClassifier:
    """根据台账"项目"列的手工标注，指导匹配策略"""

    # 项目分类 → 匹配策略：(匹配模式, 策略, 原因)
    PROJECT_RULES = [
        (r"费用|兑现|场地费", "排除", "费用类虚拟单据"),
        (r"虚进|虚退|虚入|虚出", "排除-虚拟", "虚拟调账，无实物对应"),
        (r"价格错误|价格调整", "排除-价格错误", "价格错误记录"),
        (r"商品退|商品-退", "退货", "退货单，仅匹配退货"),
        (r"商品进|商品-进", "正常匹配", "正常商品进货"),
        (r"一退一进|一进一退|对冲", "对冲", "对冲记录，特殊处理"),
        (r"样转销|样机", "样转销", "样机转销售"),
    ]

    @classmethod
    def classify(cls, project_label):
        """根据项目分类标签返回匹配策略 dict"""
        if project_label is None or pd.isna(project_label):
            return {"strategy": "未标注", "reason": "", "is_return": False}

        label = str(project_label).strip()

        for pattern, strategy, reason in cls.PROJECT_RULES:
            if re.search(pattern, label):
                is_return = strategy == "退货"
                return {
                    "strategy": strategy,
                    "reason": reason,
                    "is_return": is_return,
                    "label": label,
                }

        return {"strategy": "其他", "reason": f"未识别: {label[:30]}", "is_return": False, "label": label}

    @classmethod
    def should_exclude(cls, project_label):
        """判断项目分类是否建议排除"""
        result = cls.classify(project_label)
        return result["strategy"] in ("排除", "排除-虚拟", "排除-价格错误"), result["reason"]

    @classmethod
    def is_virtual(cls, project_label):
        """判断是否为虚拟调账（虚进/虚退）"""
        result = cls.classify(project_label)
        return result["strategy"] == "排除-虚拟"
