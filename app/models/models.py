# 数据库模型定义

import json
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    TypeDecorator,
    func,
)
from sqlalchemy.orm import relationship

from app.database import Base, IS_SQLITE


class JsonType(TypeDecorator):
    """
    跨数据库 JSON 类型

    - SQLite: 存储为 TEXT，自动序列化/反序列化
    - PostgreSQL: 使用原生 JSONB
    """
    impl = Text if IS_SQLITE else None

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Text)
        else:
            from sqlalchemy.dialects.postgresql import JSONB
            return dialect.type_descriptor(JSONB)

    def process_bind_param(self, value: Optional[Any], dialect) -> Optional[str]:
        if value is None:
            return None
        if dialect.name == "sqlite":
            return json.dumps(value, ensure_ascii=False, default=str)
        return value

    def process_result_value(self, value: Optional[Any], dialect) -> Optional[Any]:
        if value is None:
            return None
        if dialect.name == "sqlite":
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
        return value


class TimestampMixin:
    """自动添加 created_at 和 updated_at 字段"""

    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=True)


class Customer(Base, TimestampMixin):
    """客户注册表"""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, comment="客户名称")
    slug = Column(Text, nullable=False, unique=True, comment="客户标识（英文小写）")
    description = Column(Text, nullable=True, comment="客户描述")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class OurReceipt(Base, TimestampMixin):
    """我方签收记录（新方舟系统导出）"""

    __tablename__ = "our_receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_no = Column(Text, nullable=False, index=True, comment="新方舟销售单号")
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="关联客户")
    period = Column(Text, nullable=False, index=True, comment="对账期间 YYYYMM")
    model = Column(Text, nullable=True, comment="产品型号")
    quantity = Column(Numeric(12, 2), nullable=True, comment="签收数量")
    amount = Column(Numeric(14, 2), nullable=True, comment="签收金额")
    unit_price = Column(Numeric(14, 4), nullable=True, comment="单价")
    receipt_date = Column(Text, nullable=True, comment="签收日期")
    doc_type = Column(Text, nullable=True, comment="单据类型")
    customer_name = Column(Text, nullable=True, comment="结算客户名称")
    nc_order_no = Column(Text, nullable=True, index=True, comment="NC订单号")
    product_line = Column(Text, nullable=True, comment="产品线")
    batch_id = Column(Text, nullable=True, comment="导入批次")
    raw_data = Column(JsonType, nullable=True, comment="原始98列数据")

    customer = relationship("Customer", backref="receipts")

    def __repr__(self):
        return f"<OurReceipt(id={self.id}, receipt_no='{self.receipt_no}', model='{self.model}')>"


class CustomerSettlement(Base, TimestampMixin):
    """客户方结算单"""

    __tablename__ = "customer_settlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="关联客户")
    period = Column(Text, nullable=False, index=True, comment="对账期间 YYYYMM")
    batch_id = Column(Text, nullable=True, comment="导入批次")

    # 引擎提取的标准化字段
    match_key = Column(Text, nullable=True, index=True, comment="引擎提取的匹配键")
    model = Column(Text, nullable=True, comment="引擎提取的型号")
    quantity = Column(Numeric(12, 2), nullable=True, comment="数量")
    amount = Column(Numeric(14, 2), nullable=True, comment="金额")
    unit_price = Column(Numeric(14, 4), nullable=True, comment="单价")
    settlement_date = Column(Text, nullable=True, comment="业务日期")
    doc_type = Column(Text, nullable=True, comment="客户单据类型")
    status = Column(Text, default="pending", nullable=False, comment="pending/matched/unmatched/ignored")

    # 客户原始数据
    raw_data = Column(JsonType, nullable=True)

    customer = relationship("Customer", backref="settlements")

    def __repr__(self):
        return f"<CustomerSettlement(id={self.id}, match_key='{self.match_key}')>"


class MatchResult(Base, TimestampMixin):
    """匹配结果"""

    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="关联客户")
    period = Column(Text, nullable=False, index=True, comment="对账期间 YYYYMM")
    batch_id = Column(Text, nullable=True, comment="导入批次")

    receipt_id = Column(Integer, ForeignKey("our_receipts.id"), nullable=True, comment="我方记录ID")
    settlement_id = Column(Integer, ForeignKey("customer_settlements.id"), nullable=True, comment="客户方记录ID")

    match_type = Column(Text, nullable=True, comment="匹配类型")
    confidence = Column(Numeric(5, 2), nullable=True, comment="置信度 0.00-1.00")
    status = Column(Text, default="matched", nullable=False, comment="matched/unmatched/manual/ignored")
    source = Column(Text, default="auto", nullable=False, comment="auto/manual")

    diff_amount = Column(Numeric(14, 2), nullable=True, comment="金额差异")
    diff_quantity = Column(Numeric(12, 2), nullable=True, comment="数量差异")
    remark = Column(Text, nullable=True, comment="备注")

    operator_id = Column(Integer, nullable=True, comment="人工操作人")

    customer = relationship("Customer", backref="match_results")
    receipt = relationship("OurReceipt", backref="match_results")
    settlement = relationship("CustomerSettlement", backref="match_results")

    def __repr__(self):
        return f"<MatchResult(id={self.id}, status='{self.status}', type='{self.match_type}')>"


class CorrectionLog(Base, TimestampMixin):
    """人工纠正日志"""

    __tablename__ = "correction_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, nullable=True, comment="关联客户")
    period = Column(Text, nullable=True, comment="对账期间")
    result_id = Column(Integer, ForeignKey("match_results.id"), nullable=True, comment="关联匹配结果")

    operation_type = Column(Text, nullable=True, comment="manual_match/unmatch/ignore/add_note")
    before_data = Column(JsonType, nullable=True)
    after_data = Column(JsonType, nullable=True)
    reason = Column(Text, nullable=True, comment="操作原因")
    operator_id = Column(Integer, nullable=True, comment="操作人")

    def __repr__(self):
        return f"<CorrectionLog(id={self.id}, type='{self.operation_type}')>"


class EngineConfig(Base, TimestampMixin):
    """引擎配置"""

    __tablename__ = "engine_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, unique=True, comment="关联客户")
    engine_name = Column(Text, nullable=True, comment="引擎类名")
    engine_version = Column(Text, nullable=True, comment="版本号")
    config_params = Column(JsonType, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    customer = relationship("Customer", backref="engine_config")

    def __repr__(self):
        return f"<EngineConfig(id={self.id}, engine='{self.engine_name}')>"