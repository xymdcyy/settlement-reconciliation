# 02 — 迁移规则引擎（YAML 加载和应用）

**What to build:** 实现 YAML 规则文件的加载和应用引擎，系统可以从 YAML 文件读取客户的列名映射、状态值映射、特殊处理规则，并应用到 Excel 清洗过程中。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 实现 `load_rules(customer_slug)` 函数，从 YAML 文件加载规则
- [ ] 实现 `apply_rules(df, rules)` 函数，应用列名映射和状态值映射
- [ ] 支持特殊处理规则（如"重复开具：xxx" → billed + remark）
- [ ] 单元测试：加载规则、应用规则、特殊处理
