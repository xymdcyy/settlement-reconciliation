# 数据库模型定义 v2.0

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


class User(Base, TimestampMixin):
    """用户表"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, unique=True, comment="用户名")
    password_hash = Column(Text, nullable=False, comment="密码哈希")
    real_name = Column(Text, nullable=True, comment="真实姓名")
    role = Column(Text, nullable=False, default="staff", comment="角色：admin(管理员)/manager(主管)/staff(财务专员)")
    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Customer(Base, TimestampMixin):
    """客户表"""

    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False, comment="客户名称")
    slug = Column(Text, nullable=False, unique=True, comment="客户标识（英文小写）")
    description = Column(Text, nullable=True, comment="客户描述")

    # 对账相关
    has_statement = Column(Boolean, default=False, nullable=False, comment="是否有对账单")
    engine_name = Column(Text, nullable=True, comment="对账引擎名称（如有）")

    # 扩展列配置（JSONB）
    extra_fields_config = Column(
        JsonType,
        nullable=True,
        comment="扩展列配置 [{name, type, required, comment}]",
    )

    is_active = Column(Boolean, default=True, nullable=False, comment="是否启用")

    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class UserCustomerAssignment(Base, TimestampMixin):
    """用户-客户归属表"""

    __tablename__ = "user_customer_assignments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, comment="客户ID")
    role = Column(Text, default="owner", nullable=False, comment="角色：owner(负责)/viewer(查看)")

    # 关系
    user = relationship("User", backref="customer_assignments")
    customer = relationship("Customer", backref="user_assignments")

    def __repr__(self):
        return f"<UserCustomerAssignment(user_id={self.user_id}, customer_id={self.customer_id})>"


class Receipt(Base, TimestampMixin):
    """台账行（核心表）⭐"""

    __tablename__ = "receipts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="关联客户")
    period = Column(Text, nullable=False, index=True, comment="对账期间 YYYYMM")
    batch_id = Column(Text, nullable=True, comment="导入批次")

    # ========== 系统字段（从新方舟94列提取）==========
    receipt_no = Column(Text, nullable=False, index=True, comment="新方舟销售单号")
    model = Column(Text, nullable=True, comment="产品型号")
    quantity = Column(Numeric(12, 2), nullable=True, comment="签收数量")
    amount = Column(Numeric(14, 2), nullable=True, comment="签收金额")
    unit_price = Column(Numeric(14, 4), nullable=True, comment="单价")
    receipt_date = Column(Text, nullable=True, comment="签收日期")
    doc_type = Column(Text, nullable=True, comment="单据类型")
    customer_name = Column(Text, nullable=True, comment="结算客户名称")
    nc_order_no = Column(Text, nullable=True, index=True, comment="NC订单号")
    product_line = Column(Text, nullable=True, comment="产品线")
    raw_data = Column(JsonType, nullable=True, comment="原始94列数据")

    # ========== 开票状态（核心集）==========
    billing_status = Column(
        Text,
        nullable=False,
        default="unbilled",
        index=True,
        comment="开票状态：unbilled(未开)/billed(已开)/split(已拆分)/partial(部分开票)",
    )
    invoice_no = Column(Text, nullable=True, comment="发票号")
    invoice_date = Column(Text, nullable=True, comment="开票日期")
    remark = Column(Text, nullable=True, comment="备注")

    # ========== 拆分相关 ==========
    split_parent_id = Column(Integer, ForeignKey("receipts.id"), nullable=True, index=True, comment="拆分父行ID")
    split_note = Column(Text, nullable=True, comment="拆分说明")

    # ========== 扩展字段（客户级配置）==========
    extra_fields = Column(JsonType, nullable=True, comment="扩展列值（JSONB）")

    # ========== 差异判断 ==========
    diff_type = Column(
        Text,
        nullable=True,
        index=True,
        comment="差异类型：none/time_diff/price_diff/qty_diff/customer_not_received/our_not_received",
    )
    diff_note = Column(Text, nullable=True, comment="差异说明")
    resolved_period = Column(Text, nullable=True, comment="解决期间 YYYYMM")

    # ========== 审计 ==========
    created_by = Column(Integer, nullable=True, comment="创建人")
    updated_by = Column(Integer, nullable=True, comment="更新人")

    # 关系
    customer = relationship("Customer", backref="receipts")
    split_parent = relationship("Receipt", remote_side=[id], backref="split_children")

    def __repr__(self):
        return f"<Receipt(id={self.id}, receipt_no='{self.receipt_no}', status='{self.billing_status}')>"


class CustomerStatement(Base, TimestampMixin):
    """客户对账单（核对桌专用）"""

    __tablename__ = "customer_statements"

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

    customer = relationship("Customer", backref="statements")

    def __repr__(self):
        return f"<CustomerStatement(id={self.id}, match_key='{self.match_key}')>"


class MatchResult(Base, TimestampMixin):
    """匹配结果（核对桌专用）"""

    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="关联客户")
    period = Column(Text, nullable=False, index=True, comment="对账期间 YYYYMM")
    batch_id = Column(Text, nullable=True, comment="导入批次")

    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True, comment="我方记录ID")
    statement_id = Column(Integer, ForeignKey("customer_statements.id"), nullable=True, comment="客户方记录ID")

    match_type = Column(Text, nullable=True, comment="匹配类型")
    confidence = Column(Numeric(5, 2), nullable=True, comment="置信度 0.00-1.00")
    status = Column(Text, default="matched", nullable=False, comment="matched/unmatched/manual/ignored")
    source = Column(Text, default="auto", nullable=False, comment="auto/manual")

    diff_amount = Column(Numeric(14, 2), nullable=True, comment="金额差异")
    diff_quantity = Column(Numeric(12, 2), nullable=True, comment="数量差异")
    remark = Column(Text, nullable=True, comment="备注")

    operator_id = Column(Integer, nullable=True, comment="人工操作人")

    customer = relationship("Customer", backref="match_results")
    receipt = relationship("Receipt", backref="match_results")
    statement = relationship("CustomerStatement", backref="match_results")

    def __repr__(self):
        return f"<MatchResult(id={self.id}, status='{self.status}', type='{self.match_type}')>"


class Invoice(Base, TimestampMixin):
    """发票记录"""

    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=False, index=True, comment="台账行ID")

    invoice_no = Column(Text, nullable=False, comment="发票号")
    invoice_date = Column(Text, nullable=False, comment="开票日期")
    amount = Column(Numeric(14, 2), nullable=False, comment="开票金额")
    quantity = Column(Numeric(12, 2), nullable=False, comment="开票数量")

    invoice_type = Column(Text, nullable=False, default="blue", comment="blue(蓝票)/red(红票)")
    red_notice_no = Column(Text, nullable=True, comment="红字通知单号（红票）")
    original_invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True, comment="原蓝票ID（红票）")

    created_by = Column(Integer, nullable=True, comment="创建人")

    # 关系
    receipt = relationship("Receipt", backref="invoices")
    original_invoice = relationship("Invoice", remote_side=[id], backref="red_invoices")

    def __repr__(self):
        return f"<Invoice(id={self.id}, invoice_no='{self.invoice_no}', type='{self.invoice_type}')>"


class Adjustment(Base, TimestampMixin):
    """调账/红冲记录"""

    __tablename__ = "adjustments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False, index=True, comment="关联客户")
    receipt_id = Column(Integer, ForeignKey("receipts.id"), nullable=True, comment="关联台账行")

    adjustment_type = Column(Text, nullable=False, comment="类型：return(退货)/price_adjust(调价)/qty_adjust(数量调整)")
    original_receipt_no = Column(Text, nullable=True, comment="原单号")
    adjustment_receipt_no = Column(Text, nullable=True, comment="调账单号")
    red_notice_no = Column(Text, nullable=True, comment="红字通知单号")

    status = Column(Text, default="pending", nullable=False, comment="pending/confirmed/completed")
    note = Column(Text, nullable=True, comment="说明")

    created_by = Column(Integer, nullable=True, comment="创建人")

    # 关系
    customer = relationship("Customer", backref="adjustments")
    receipt = relationship("Receipt", backref="adjustments")

    def __repr__(self):
        return f"<Adjustment(id={self.id}, type='{self.adjustment_type}', status='{self.status}')>"


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
