# 03 — 上传 API + Excel 解析

**What to build:** 上传我方签收明细和客户方结算单的 API 端点，解析 Excel 存入数据库，客户自动识别。

**Blocked by:** #01（需要数据库模型），#02（需要引擎解析客户方数据）

**Status:** ready-for-agent

**交付内容：**

1. **`POST /api/upload/our-receipts`** — 上传我方签收明细 Excel：
   - 接收 Excel 文件 + 对账期间（YYYYMM）
   - 用 pandas 解析 98 列，提取标准化字段
   - 根据 `结算客户名称` 自动匹配 `customers` 表
   - 未匹配到客户的记录标记为"未分配客户"
   - 存入 `our_receipts` 表，原始 98 列存入 `raw_data` JSON
   - 返回导入统计（总行数、分配到各客户行数）

2. **`POST /api/upload/settlements`** — 上传客户方结算单：
   - 接收 Excel 文件 + 客户 ID + 对账期间
   - 调用对应客户的 `MatchEngine.parse_customer_data()` 解析
   - 标准化字段 + 原始数据存入 `customer_settlements`
   - 返回导入统计（总行数、提取 match_key 成功数）

3. **文件存储** — 上传的 Excel 文件保存到 `uploads/{customer_id}/{period}/` 目录

4. **错误处理**：
   - 验证必填列是否存在，缺失时给出清晰错误信息
   - Excel 解析失败时返回具体错误行号

- [ ] 上传我方签收明细 → 数据正确解析，按结算客户名称分配到客户，存入数据库
- [ ] 上传客户方结算单 → 调用引擎解析，标准化字段 + 原始数据存入数据库
- [ ] 上传文件保存到本地文件系统
- [ ] 缺失必填列时返回友好错误信息