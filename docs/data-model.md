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
# v1.2 / schema v4 增量

新增draft_contracts(draft_id, contract_json)，不破坏旧contacts与drafts。联系人记录仍描述人或handoff入口；每份草稿单独保存联系地址归属、可用性、职责、触达依据及复核信息。旧草稿缺合同不能批准或记录发送，需要按新合同重建，不自动推断迁移。

approvals.body_hash保留兼容列名，v4保存完整发送快照哈希；drafts.body_hash仍是正文哈希。任何关键内容变化导致记录发送时校验失败。schema升级前用SQLite backup建立同目录before-v4备份；真实数据库未在本次开发中迁移。

source_runs旧cost_amount列保留兼容存储，未知金额不解释为免费。source.recorded事件显式保存cost_known/cost_amount，JSON导出未知成本为null；旧记录没有该标记也按未知处理。
