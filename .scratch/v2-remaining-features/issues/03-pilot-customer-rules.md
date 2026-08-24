# 03 — 试点客户迁移规则配置

**What to build:** 为四个试点客户（潍坊百货、全福元、河北劲草、天猫优品）创建 YAML 规则文件，包含各自的列名映射、状态值映射、特殊处理规则。

**Blocked by:** 02 — 迁移规则引擎

**Status:** ready-for-agent

- [ ] 创建 `scripts/migration/rules/weifangbaihuo.yaml`（潍坊百货）
- [ ] 创建 `scripts/migration/rules/quanfuyuan.yaml`（全福元）
- [ ] 创建 `scripts/migration/rules/hebeijincao.yaml`（河北劲草）
- [ ] 创建 `scripts/migration/rules/tmall.yaml`（天猫优品）
- [ ] 每个规则文件包含：列名映射、状态值映射、特殊处理规则
- [ ] 单元测试：每个试点客户的规则文件可以加载并应用
