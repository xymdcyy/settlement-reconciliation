# 天猫优品引擎配置

# 结算单列映射
SETTLEMENT_COLS = {
    "order_id": "业务主单据编码",
    "amount": "含税金额",
    "product_name": "后端商品名称",
    "quantity": "商品数量",
    "unit_price": "含税单价",
    "date": "业务时间",
}

# 签收单列映射
RECEIPT_COLS = {
    "approval_no": "审批单号",
    "nc_order_no": "NC订单号",
    "platform_no": "平台订单号",
    "model": "产品型号",
    "amount": "签收金额",
    "quantity": "签收数量",
    "date": "签收日期/完成日期",
    "doc_type": "单据类型",
    "customer_name": "结算客户名称",
    "receipt_no": "新方舟销售单号",
    "product_name": "产品名称",
    "product_code": "产品编码",
}

# 引擎版本
ENGINE_VERSION = "v1.0.0"