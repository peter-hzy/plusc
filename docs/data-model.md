# 数据模型

- `runs`：一批目标市场、客户类型和数量。
- `companies` / `contacts`：正式运营字段。
- `entity_keys`：域名、LinkedIn、邮箱等身份键。
- `source_runs`：每次来源查询及明确结果。
- `source_plan_entries`：计划搜索的来源、用途、目标信号、覆盖范围和执行状态。
- `candidates`：完整候选池；未入选公司也保留状态与原因。
- `candidate_sources`：候选与一个或多个发现来源的关系，用于计算独有贡献与重叠。
- `evidence`：来源URL、观察内容、时间与哈希。
- `claims` / `claim_evidence`：待判断事实及支持证据。
- `research_gaps`：未知项和是否阻止外联。
- `duplicate_candidates`：只供人工处理的模糊重复。
- `drafts` / `approvals`：渠道草稿、正文哈希和人工批准。
- `replies` / `stop_rules`：回复、询盘和跨渠道停止规则。
- `events`：关键写操作的追加式账本。
- `idempotency`：重复请求保护。

SQLite 是唯一事实库。Excel和JSON均为快照，不应绕过导入检查直接覆盖数据库。
