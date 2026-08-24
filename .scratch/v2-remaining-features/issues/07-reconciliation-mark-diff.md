# 07 — 核对桌：标记差异（时间差/真差异）

**What to build:** 实现标记差异功能，财务专员可以标记未匹配的记录为时间差或真差异（价格差/数量差），填写差异说明，系统更新 `receipts.diff_type/diff_note`，并将该记录挂入未决池。

**Blocked by:** 05 — 核对桌：运行匹配 + 左右对照 UI

**Status:** ready-for-agent

- [ ] 实现 `POST /api/reconciliation/mark-diff`：接收 receipt_id, diff_type, diff_note
- [ ] 更新 `receipts.diff_type/diff_note`
- [ ] 前端：标记差异按钮 + 弹窗（选择差异类型 + 填写说明）
- [ ] 标记后的记录出现在未决池中
