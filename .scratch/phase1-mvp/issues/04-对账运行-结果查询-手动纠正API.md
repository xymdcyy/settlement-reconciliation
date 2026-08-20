# 04 — 对账运行 + 结果查询 + 手动纠正 API

**What to build:** 运行自动匹配的 API、查询匹配结果的 API、手动纠正操作的 API，所有操作记录审计日志。

**Blocked by:** #03（需要上传的数据）

**Status:** done ✅ — 已实现；端到端验证中修复匹配率口径 + 纠正响应 result_id（2026-08-20）

**交付内容：**

1. **`POST /api/reconciliation/run`** — 运行自动匹配：
   - 参数：客户 ID + 对账期间
   - 从数据库加载双方数据，调用对应客户的 `MatchEngine.match()`
   - 匹配结果存入 `match_results` 表
   - 返回匹配摘要（匹配率、匹配数、未匹配数、金额差异）

2. **`GET /api/reconciliation/results`** — 查询匹配结果：
   - 参数：客户 ID + 对账期间 + 筛选条件（status/match_type 等）
   - 返回分页的匹配结果列表，含双方数据完整信息
   - 支持按状态（matched/unmatched/manual/ignored）筛选
   - 支持按型号/订单号搜索

3. **`GET /api/reconciliation/status`** — 查询对账状态：
   - 返回当前对账的统计摘要（匹配率、已匹配金额、未匹配金额、差异金额）

4. **手动纠正 API：**
   - `POST /api/corrections/manual-match` — 手动匹配一对记录
   - `POST /api/corrections/unmatch` — 解除匹配
   - `POST /api/corrections/ignore` — 标记忽略（含原因）
   - `POST /api/corrections/note` — 添加备注

5. **审计日志** — 所有手动纠正操作记录到 `correction_logs` 表：
   - 操作类型、操作人、操作前数据、操作后数据、原因、时间戳

- [ ] 运行匹配 → 调用引擎，结果正确存入数据库
- [ ] 查询结果 → 支持分页、按状态筛选、按型号搜索
- [ ] 手动匹配/解除匹配/忽略/备注 → 数据库状态正确更新
- [ ] 所有手动操作在 `correction_logs` 表中可查询