# Excel 解析工具

import pandas as pd
from typing import Optional


class ExcelParser:
    """Excel 解析器"""

    @staticmethod
    def find_main_sheet(file_path: str, keyword: str = "全品类") -> str:
        """
        自动识别主 sheet

        优先选择包含关键词的 sheet，否则选择第一个 sheet
        """
        xl = pd.ExcelFile(file_path)

        # 优先选择包含关键词的 sheet
        for name in xl.sheet_names:
            if keyword in name:
                return name

        # 否则选择第一个 sheet
        return xl.sheet_names[0]

    @staticmethod
    def find_column_index(df: pd.DataFrame, column_name: str) -> int:
        """
        查找列索引

        如果找不到，返回 -1
        """
        try:
            return df.columns.tolist().index(column_name)
        except ValueError:
            return -1

    @staticmethod
    def split_manual_system_columns(df: pd.DataFrame, marker_column: str = "新方舟销售单号") -> tuple:
        """
        分割手工区列和系统区列

        返回: (manual_cols, system_cols)
        """
        marker_idx = ExcelParser.find_column_index(df, marker_column)

        if marker_idx == -1:
            raise ValueError(f"Excel 中未找到标记列: {marker_column}")

        manual_cols = df.columns[:marker_idx].tolist()
        system_cols = df.columns[marker_idx:].tolist()

        return manual_cols, system_cols

    @staticmethod
    def read_excel_with_header_detection(
        file_path: str,
        sheet_name: Optional[str] = None,
        header_keyword: str = "新方舟销售单号",
    ) -> pd.DataFrame:
        """
        读取 Excel 并自动检测表头行

        有些 Excel 的前几行是说明文字，真正的表头在第 N 行
        """
        if not sheet_name:
            sheet_name = ExcelParser.find_main_sheet(file_path)

        # 先读取前 10 行，查找表头
        df_preview = pd.read_excel(file_path, sheet_name=sheet_name, header=None, nrows=10)

        header_row = 0
        for idx in range(len(df_preview)):
            row_values = df_preview.iloc[idx].astype(str).tolist()
            if any(header_keyword in str(v) for v in row_values):
                header_row = idx
                break

        # 用检测到的表头行重新读取
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)

        return df
