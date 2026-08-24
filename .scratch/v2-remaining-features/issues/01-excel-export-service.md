# 01 — Excel 导出服务（基础功能）

**What to build:** 实现三个 Excel 导出功能（台账导出、开票清单导出、确认单导出），财务专员可以点击导出按钮，下载包含筛选后数据的 Excel 文件，列名与原始台账一致。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 台账导出：支持筛选（期间/状态/搜索），列名与原始台账一致
- [ ] 开票清单导出：导出勾选的可开票记录，包含单号/型号/数量/金额
- [ ] 确认单导出：导出退货记录和匹配的蓝票信息
- [ ] 导出速度 < 5 秒（1 万行）
- [ ] 导出文件自动下载（Content-Disposition: attachment）
