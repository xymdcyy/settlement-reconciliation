# 对账单上传服务

import io
from datetime import datetime

import pandas as pd
from sqlalchemy.orm import Session

from app.engines import get_engine
from app.models import CustomerStatement


class ReconciliationUploadService:
    """对账单上传服务"""

    @staticmethod
    def upload_statement(
        customer_id: int,
        period: str,
        file_content: bytes,
        db: Session,
    ) -> dict:
        """
        上传客户对账单

        1. 解析 Excel 文件
        2. 调用引擎的 parse_customer_data 方法解析
        3. 删除该客户+期间的旧记录
        4. 存入 customer_statements 表
        5. 返回解析成功的记录数

        Args:
            customer_id: 客户 ID
            period: 对账期间 YYYYMM
            file_content: Excel 文件内容（字节）
            db: 数据库会话

        Returns:
            {"status": "success", "parsed_count": int, "message": str}

        Raises:
            ValueError: 客户未配置引擎或 Excel 解析失败
        """
        # 获取引擎
        engine = get_engine(customer_id)
        if engine is None:
            raise ValueError(f"客户 {customer_id} 未找到匹配引擎")

        # 解析 Excel 文件
        try:
            df = pd.read_excel(io.BytesIO(file_content))
        except Exception as e:
            raise ValueError(f"Excel 解析失败: {str(e)}")

        # 如果 Excel 为空，直接返回
        if df.empty:
            return {
                "status": "success",
                "parsed_count": 0,
                "message": "Excel 文件为空，解析 0 条记录",
            }

        # 调用引擎解析
        try:
            engine_settlements = engine.parse_customer_data(df)
        except Exception as e:
            raise ValueError(f"引擎解析失败: {str(e)}")

        # 删除该客户+期间的旧记录
        db.query(CustomerStatement).filter(
            CustomerStatement.customer_id == customer_id,
            CustomerStatement.period == period,
        ).delete()

        # 生成批次 ID
        batch_id = f"upload-{period}-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # 存入数据库
        count = 0
        for es in engine_settlements:
            statement = CustomerStatement(
                customer_id=customer_id,
                period=period,
                batch_id=batch_id,
                match_key=es.match_key,
                model=es.model,
                quantity=es.quantity,
                amount=es.amount,
                unit_price=es.unit_price,
                settlement_date=es.settlement_date,
                status="pending",
                raw_data=es.raw_data,
            )
            db.add(statement)
            count += 1

        db.commit()

        return {
            "status": "success",
            "parsed_count": count,
            "message": f"成功解析 {count} 条记录",
        }
