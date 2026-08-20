# 重百智屏 —— 采购凭证 / 门店 / 样转销 提取器
#
# 从原脚本 reconcile_all.py 逐字迁移（VoucherExtractor / StoreExtractor /
# SampleSaleExtractor），仅调整 import，正则与策略保持完全一致以保证保真。

import re


class VoucherExtractor:
    """采购凭证提取器"""

    VALID_PREFIXES = ["45", "47", "48"]

    @classmethod
    def extract(cls, remark, remark_type="其他", line_remark=""):
        """从订单备注中提取采购凭证（返回单个主凭证或 None）"""
        if remark is None or str(remark).strip() == "":
            remark = ""
        else:
            remark = str(remark).strip()

        line_remark = str(line_remark).strip() if line_remark else ""

        # 价格调整和冲销类：备注中的数字是引用号/原单号，非采购凭证，不提取
        if remark_type in ("补差价差", "冲销"):
            return None

        extractors = {
            "纯数字": cls._extract_pure_digital,
            "标准格式": cls._extract_standard,
            "收货码": cls._extract_shouhuoma,
            "厂送": cls._extract_changsong,
            "一退一进": cls._extract_yituiyijin,
        }

        extractor = extractors.get(remark_type, cls._extract_generic)
        voucher = extractor(remark)

        # 主备注未提取到时，尝试从订单行备注中提取
        if not voucher and line_remark:
            voucher = extractor(line_remark)

        if voucher and cls.validate(voucher):
            return voucher

        return None

    @classmethod
    def _extract_pure_digital(cls, remark):
        """纯数字格式"""
        if remark.isdigit() and len(remark) == 10:
            return remark
        return None

    @classmethod
    def _find_10digit(cls, text):
        """安全查找10位数字（前后不能是数字，防止匹配11位数字的前10位）"""
        return re.findall(r"(?<!\d)(\d{10})(?!\d)", text)

    @classmethod
    def _extract_standard(cls, remark):
        """标准格式：店-人 凭证/单号"""
        match = re.search(r"(?<!\d)(\d{10})(?=/)", remark)
        if match:
            return match.group(1)
        return None

    @classmethod
    def _extract_shouhuoma(cls, remark):
        """收货码格式：提取末尾店名+数字"""
        match = re.search(r"[一-龥]+(?:店|商社|重百)\s*(?<!\d)(\d{10})(?!\d)", remark)
        if match:
            return match.group(1)
        matches = cls._find_10digit(remark)
        if matches:
            valid = [m for m in matches if any(m.startswith(p) for p in cls.VALID_PREFIXES)]
            if valid:
                return valid[-1]  # 末尾的有效凭证
            return matches[-1]
        # 兜底：从长数字中提取有效前缀的10位子串
        long_nums = re.findall(r"\d{11,}", remark)
        for ln in long_nums:
            for i in range(len(ln) - 9):
                sub = ln[i:i + 10]
                if any(sub.startswith(p) for p in cls.VALID_PREFIXES):
                    return sub
        return None

    @classmethod
    def _extract_changsong(cls, remark):
        """厂送格式：凭证通常在地址末尾，优先取最后的有效数字"""
        matches = cls._find_10digit(remark)
        if not matches:
            return None
        valid_prefix = [m for m in matches if any(m.startswith(p) for p in cls.VALID_PREFIXES)]
        if valid_prefix:
            return valid_prefix[-1]
        return matches[-1]

    @classmethod
    def _extract_yituiyijin(cls, remark):
        """一退一进格式：取第一个有效凭证"""
        matches = cls._find_10digit(remark)
        if not matches:
            return None
        for m in matches:
            if any(m.startswith(p) for p in cls.VALID_PREFIXES):
                return m
        return matches[0]

    @classmethod
    def _extract_generic(cls, remark):
        """通用提取策略：凭证通常在备注末尾，优先取末尾数字避免假阳性"""
        candidates = cls._find_10digit(remark)
        if not candidates:
            long_nums = re.findall(r"\d{11,}", remark)
            for ln in long_nums:
                for i in range(len(ln) - 9):
                    sub = ln[i:i + 10]
                    if any(sub.startswith(p) for p in cls.VALID_PREFIXES):
                        return sub
            return None

        valid = [c for c in candidates if any(c.startswith(p) for p in cls.VALID_PREFIXES)]
        if not valid:
            valid = [c for c in candidates if not c.startswith("8800")]
        if not valid:
            return None

        # 策略1: 店名/商社+数字 模式（最高置信度）
        match = re.search(r"[一-龥]{1,4}(?:店|商社|重百|商都|仓库|凯瑞)\s*(\d{10})", remark)
        if match and match.group(1) in valid:
            return match.group(1)

        # 策略2: 凭证在末尾
        for c in reversed(valid):
            idx = remark.rfind(c)
            after = remark[idx + 10:].strip()
            if len(after) <= 5:
                return c

        # 策略3: 独立数字（前后有分隔符）
        for c in reversed(valid):
            idx = remark.find(c)
            before_ok = idx == 0 or remark[idx - 1] in " \t\r\n，,。.（(）)"
            after_ok = idx + 10 >= len(remark) or remark[idx + 10] in " \t\r\n，,。.）)/"
            if before_ok and after_ok:
                return c

        # 策略4: 回退 - 返回最后一个有效凭证
        return valid[-1]

    @classmethod
    def validate(cls, voucher):
        """验证采购凭证格式"""
        if not voucher or len(voucher) != 10:
            return False
        if not voucher.isdigit():
            return False
        if not any(voucher.startswith(p) for p in cls.VALID_PREFIXES):
            return False
        return True

    @classmethod
    def extract_all(cls, remark, remark_type="其他", line_remark=""):
        """提取备注中所有可能的采购凭证号（支持 / 分隔的多凭证格式），返回去重列表"""
        if remark is None or str(remark).strip() == "":
            remark = ""
        else:
            remark = str(remark).strip()

        line_remark = str(line_remark).strip() if line_remark else ""

        if remark_type in ("补差价差", "冲销"):
            return []

        text = remark if remark else line_remark
        if not text:
            return []

        all_nums = re.findall(r"(?<!\d)(\d{10})(?!\d)", text)

        valid = [n for n in all_nums if any(n.startswith(p) for p in cls.VALID_PREFIXES)]

        if not valid:
            valid = [n for n in all_nums if not n.startswith("8800")]

        if not valid:
            long_nums = re.findall(r"\d{11,}", text)
            for ln in long_nums:
                for i in range(len(ln) - 9):
                    sub = ln[i:i + 10]
                    if any(sub.startswith(p) for p in cls.VALID_PREFIXES):
                        valid.append(sub)

        seen = set()
        result = []
        for v in valid:
            if v not in seen:
                seen.add(v)
                result.append(v)
        return result


class StoreExtractor:
    """门店提取器"""

    STORE_ALIAS = {
        "江北店": ["江北店", "江北重百", "江重百", "世纪新都"],
        "北碚店": ["北碚店", "北碚二店", "北碚重百"],
        "解放碑店": ["解放碑店", "解放碑重百", "解放碑商社", "解商社"],
        "万州店": ["万州店", "万州商都", "万州重百", "万州新世纪"],
        "合川店": ["合川店", "合川重百"],
        "永川店": ["永川店", "永川华茂", "永川重百"],
        "渝北店": ["渝北店", "渝北重百"],
        "南坪店": ["南坪店", "南坪商社", "南岸店"],
        "杨家坪店": ["杨家坪", "杨家坪商社", "杨商社", "瑞成商都"],
        "沙坪坝店": ["沙坪坝", "沙重百", "沙坪坝重百"],
        "涪陵店": ["涪陵店", "涪陵重百", "涪陵商都"],
        "江津店": ["江津店", "江津紫金", "江津重百"],
        "璧山店": ["璧山店", "璧山重百"],
        "潼南店": ["潼南店", "潼南重百"],
        "长寿店": ["长寿店", "长寿重百"],
        "大渡口店": ["大渡口", "大渡口商都"],
        "江南商都": ["江南商都", "南岸商都"],
        "九龙坡店": ["九龙坡", "西城"],
        "巴南店": ["巴南", "巴南店"],
        "丰都店": ["丰都", "丰都店"],
        "黔江店": ["黔江", "黔江店"],
        "铜梁店": ["铜梁店", "铜梁重百", "铜梁"],
        "大坪店": ["大坪店", "大坪商社"],
        "凯瑞商都": ["凯瑞商都", "凯瑞"],
        "弹子石店": ["弹子石店", "弹子石商社"],
        "綦江店": ["綦江店", "綦江重百"],
        "万盛店": ["万盛店", "万盛重百"],
        "云阳店": ["云阳店", "云阳重百"],
        "园博园店": ["园博园店", "园博园"],
        "奉节店": ["奉节店", "奉节重百"],
        "忠县店": ["忠县店", "忠县重百"],
        "垫江店": ["垫江店", "垫江重百"],
        "南川店": ["南川店", "南川重百"],
        "荣昌店": ["荣昌店", "荣昌重百"],
        "梁平店": ["梁平店", "梁平重百"],
        "开州店": ["开州店", "开州重百"],
        "电器物流仓库": ["电器物流仓库", "大库", "物流仓库"],
    }

    @classmethod
    def extract(cls, remark):
        """从订单备注中提取门店信息，返回标准化门店名称或 None"""
        if remark is None or str(remark).strip() == "":
            return None

        remark = str(remark).strip()

        # 规则1: 开头"门店-"或"门店 "格式
        match = re.match(r"^([一-龥]+(?:店|商社|重百))[-\s]", remark)
        if match:
            return cls._normalize_store(match.group(1))

        # 规则2: 末尾"店名+凭证"格式
        match = re.search(r"([一-龥]+(?:店|商社))\s*4[578]\d{8}", remark)
        if match:
            return cls._normalize_store(match.group(1))

        # 规则3: 包含"厂送"时，提取厂送前的门店
        if "厂送" in remark:
            match = re.search(r"([一-龥]+(?:店|商社))\s*厂送", remark)
            if match:
                return cls._normalize_store(match.group(1))

        # 规则4: 样转销格式
        if "样转销" in remark or "样机" in remark:
            match = re.search(r"(?:重百电器|重百)\s*([一-龥]{2,10}(?:店|商社|中心|仓储))[，,]", remark)
            if match:
                return cls._normalize_store(match.group(1))
            match = re.search(r"样转销\s+[一-龥]{2,4}\s+([一-龥]{2,8}(?:店|商社|重百))", remark)
            if match:
                return cls._normalize_store(match.group(1))

        # 规则5: 遍历所有别名查找
        for standard_name, aliases in cls.STORE_ALIAS.items():
            for alias in aliases:
                if alias in remark:
                    return standard_name

        return None

    @classmethod
    def _normalize_store(cls, store_raw):
        """标准化门店名称"""
        for standard_name, aliases in cls.STORE_ALIAS.items():
            if store_raw in aliases or store_raw == standard_name:
                return standard_name

        for standard_name, aliases in cls.STORE_ALIAS.items():
            for alias in aliases:
                if alias in store_raw or store_raw in alias:
                    return standard_name

        return store_raw

    @classmethod
    def match_stores(cls, ruku_store, qianshou_store_from_remark):
        """匹配两个门店名称"""
        if not ruku_store or not qianshou_store_from_remark:
            return False

        ruku_store = str(ruku_store).strip()
        qianshou_store = str(qianshou_store_from_remark).strip()

        if ruku_store == qianshou_store:
            return True

        ruku_normalized = cls._normalize_store(ruku_store)
        qianshou_normalized = cls._normalize_store(qianshou_store)

        if ruku_normalized == qianshou_normalized:
            return True

        if ruku_normalized in qianshou_store or qianshou_normalized in ruku_store:
            return True

        return False


class SampleSaleExtractor:
    """样转销信息提取器"""

    @classmethod
    def extract(cls, remark):
        """从订单备注中提取样转销信息，返回 {型号, 机身码} 或 None"""
        if remark is None or str(remark).strip() == "":
            return None

        remark = str(remark).strip()

        if "样转销" not in remark and "样机" not in remark:
            return None

        result = {}

        # 提取型号
        # 格式1: "型号，机身码"
        match = re.search(
            r"([A-Z]?\d{2}[A-Z0-9]{1,8}(?:\s*(?:Pro|Plus|Mini|H|K|L|G|S|R|Q|X|Z|A|B|C|JN|H-JN|P-JN)?))\s*[，,，]\s*机身码",
            remark,
        )
        if match:
            result["型号"] = match.group(1).strip()

        # 格式2: "样机XXX转销售"
        if "型号" not in result:
            match = re.search(
                r"样机\s*([A-Z]?\d{2}[A-Z0-9]{1,8}(?:\s*(?:Pro|Plus|Mini|H|K|L|G|S|R|Q|X|Z|A|B|C|JN|H-JN|P-JN)?))\s*转",
                remark,
            )
            if match:
                result["型号"] = match.group(1).strip()

        # 格式3: "XXX转销售"
        if "型号" not in result:
            match = re.search(
                r"([A-Z]?\d{2}[A-Z0-9]{1,8}(?:\s*(?:Pro|Plus|Mini|H|K|L|G|S|R|Q|X|Z|A|B|C|-JN|H-JN|P-JN)?))\s*转",
                remark,
            )
            if match:
                result["型号"] = match.group(1).strip()

        # 格式4: 备选 - 排除机身码前缀
        if "型号" not in result:
            match = re.search(
                r"(?<!\d)([A-Z]?\d{2}[A-Z0-9]{1,8}(?:\s*(?:Pro|Plus|Mini|H|K|L|G|S|R|Q|X|Z|A|B|C|JN|H-JN|P-JN)?))",
                remark,
            )
            if match:
                model = match.group(1).strip()
                if len(model) <= 15 and not re.match(r"\d{8,}", model):
                    result["型号"] = model

        # 提取机身码
        match = re.search(r"机身码[：:]\s*([A-Za-z0-9]+)", remark)
        if match:
            sn = match.group(1).strip()
            if len(sn) >= 6:
                result["机身码"] = sn

        if result:
            return result

        return None

    @classmethod
    def match_sample_sale(cls, ruku_row, qianshou_row):
        """匹配样转销记录，返回匹配分数 (0-1)"""
        score = 0.0

        ruku_store = str(ruku_row.get("门店名称", "")).strip()
        ruku_model = str(ruku_row.get("规格型号", "")).strip()

        sample_info = cls.extract(qianshou_row.get("订单备注", ""))
        if not sample_info:
            return 0.0

        # 门店匹配
        if "门店" in sample_info:
            if StoreExtractor.match_stores(ruku_store, sample_info["门店"]):
                score += 0.4

        # 型号匹配
        if "型号" in sample_info:
            qs_model = sample_info["型号"]
            ruku_model_norm = re.sub(r"\s+", "", ruku_model.upper())
            qs_model_norm = re.sub(r"\s+", "", qs_model.upper())
            if (
                ruku_model_norm == qs_model_norm
                or ruku_model_norm in qs_model_norm
                or qs_model_norm in ruku_model_norm
            ):
                score += 0.4

        # 机身码匹配
        if "机身码" in sample_info:
            ruku_sn = str(ruku_row.get("机身码", "")).strip()
            if ruku_sn and ruku_sn in sample_info["机身码"]:
                score += 0.2

        return score
