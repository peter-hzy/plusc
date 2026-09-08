# V1 数据合同

本合同适用于名单研究、联系人核验、外联草稿、回复和复盘。正式数据以工作区 `acquisition.db` 为唯一事实源，机器约束以 `src/inbound_ai_acquisition/storage/migrations.py` 为准；本文解释业务含义和跨表约束。上一版JSON/Excel只能通过 `import legacy` 迁移，不再承担正式状态。

## 1. 基本原则

1. 一个 SQLite 工作区可以承载多个运行批次，每条记录必须有不可变 ID。
2. 公司、联系人、来源运行、证据、Claim、研究缺口、草稿、批准和回复分表保存。
3. 原始值与规范化值并存；规范化不能覆盖原始证据。
4. 空值、未知、没搜索、没找到、来源受限和冲突是不同状态。
5. 每条输入都必须进入明确结果状态，不能因异常而静默消失。
6. 搜索摘要只能用于发现，不能直接标为 `verified`。
7. CLI只规范化、检查和提出重复建议，不替代业务判断或人工合并。

## 2. Excel审阅结构

| 工作表 | 粒度 | 作用 |
|---|---|---|
| `RunSummary` | 每个批次一行 | 保存市场、客户类型、产品/语气版本和进度 |
| `DiscoveryCoverage` | 每个批次一份 | 显示候选池规模、补搜提醒和来源独有/重叠贡献 |
| `CandidatePool` | 每个独立候选一行 | 保存所有发现对象，包括未入选公司和原因 |
| `SourcePlan` | 每个计划入口或查询一行 | 保存来源用途、覆盖范围、执行状态和贡献 |
| `CandidateSources` | 候选与发现来源关系 | 识别各来源的独有贡献、重叠和遗漏 |
| `Companies` | 每家公司一行 | 保存公司主体、匹配理由和研究状态 |
| `Contacts` | 每个联系人一行 | 保存角色、LinkedIn、邮箱和身份状态 |
| `Evidence` | 每个独立来源观察一行 | 支持具体字段、保留来源和冲突 |
| `Claims` | 每个事实提议一行 | 分离模型提议、证据等级和人工决定 |
| `ResearchGaps` | 每个缺口一行 | 说明缺什么、为什么重要、是否阻止触达 |
| `Drafts` | 每条渠道草稿一行 | 邮件与 LinkedIn 分开，保存审核和发送回填 |
| `Approvals` | 每次人工批准一行 | 保存批准人、理由和正文哈希 |
| `Replies` | 每条回复一行 | 保存回复分类和明确询盘字段 |
| `StopRules` | 每个停止规则一行 | 阻止跨渠道或跨批次再次联系 |
| `DuplicateReview` | 每组疑似重复一行 | 供人工决定合并或保留 |
| `SourcePerformance` | 每次来源运行一行 | 区分成功、无结果、受限和失败 |

Excel 是数据库只读快照，首行为字段名并冻结、筛选。Excel修改不能直接覆盖数据库；回写只能通过明确的差异预览和人工确认。

## 3. 主键与关联

- `runs.run_id` → `companies.run_id`
- `Companies.company_id` → `Contacts.company_id`
- `Companies.company_id` 或 `Contacts.contact_id` → `Evidence.entity_id`
- `Companies.company_id` 或 `Contacts.contact_id` → `ResearchGaps.entity_id`
- `Contacts.contact_id` → `Drafts.contact_id`
- `Drafts.message_id` → `Replies.message_id`（允许空，适用于无法定位原消息的回复）
- `Contacts.contact_id` → `Replies.contact_id`

所有主键在数据库表中唯一，外键由 SQLite 强制执行；Excel导出后还需回读验证工作表和关联完整性。

## 4. ID 规则

ID 是本地不可变标识，不是外部平台 ID：

- 公司：`co_` + 随机不可变 ID；
- 联系人：`ct_` + 随机不可变 ID；
- 证据：`ev_`；
- 草稿：`msg_`；
- 回复：`rep_`；
- 缺口：`gap_`；
- 停止项：`stop_`；
- 重复组：`dup_`。

已有 ID 不因显示名称、域名、职位或邮箱变化而重建。域名、LinkedIn、邮箱和外部ID另存为 `entity_keys`，负责去重与冲突检查。

## 5. 公司合同

公司必须保留：

- 原始名称和规范化名称；
- 官网和根域名；
- 国家、客户类型；
- 为什么基本匹配；
- 候选状态；
- 研究阶段；
- 首次发现 URL 和观察日期。

`research_stage`：

- `candidate_pool`：已经发现但尚未完成正式核验；
- `formal_list`：主体、业务依据和联系人处理均达到外联准备要求；
- `held`：冲突、来源受限或重要缺口导致暂缓；
- `excluded`：明确不匹配或不得联系。

`candidate_status`：

- `priority_chat`：证据清楚且值得优先人工联系；
- `chat_candidate`：基本相关，可以进入对话池；
- `research_needed`：相关但关键资料不足；
- `nurture`：不是当前时点，但值得保留；
- `not_fit`：当前业务不匹配；
- `do_not_contact`：明确不得联系。

`priority_chat` 不是购买意愿保证，不能写成“客户有意向”。

## 6. 联系人合同

联系人至少必须关联真实公司，并记录 `contact_role` 和 `identity_status`。

- `primary`：本批首选联系人；
- `backup`：主要联系人不可用时的候选；
- `handoff`：只能帮助确认或转交给正确负责人。

`identity_status`：

- `verified`：公开资料明确支持姓名、公司和当前职责；
- `supported`：资料基本一致，但仍需人工确认；
- `identity_pending`：只有候选线索；
- `contradicted`：来源冲突，不能继续升级；
- `not_found`：已搜索但没有找到具体负责人。

邮箱没有可靠来源时必须留空，并将 `email_status` 标为 `not_found`、`not_checked` 或 `unresolved`。禁止通过姓名和域名拼接邮箱后标为真实。

## 7. 证据合同

一条 `Evidence` 代表一个独立来源观察。一个网页同时显示姓名和职位，仍然是一条来源，不能拆成多条冒充独立证据。

每条证据必须说明：

- 支持哪个公司、联系人、消息或回复；
- 支持哪个字段或结论；
- 页面实际写了什么；
- URL、发布日期（如有）和访问日期；
- 来源等级、发现/验证角色和访问状态；
- 当前证据状态；
- 是否存在冲突。

`evidence_status`：

- `verified`：原始/权威页面直接支持；
- `supporting`：可靠辅助来源支持；
- `hypothesis`：只是一种业务解释，需要确认；
- `contradicted`：来源冲突；
- `not_searched`：尚未查询；
- `searched_not_found`：已查询但没有结果；
- `source_restricted`：来源不可访问或不允许自动读取；
- `identity_pending`：联系人身份尚未闭环。

发生 `contradicted` 时，相关字段不能用于生成“已经确认”的个性化表达。

## 8. 研究缺口合同

缺失资料不得只写“unknown”，必须在重要时说明：

- 缺少什么；
- 为什么影响当前判断；
- 建议从哪里查；
- 是否阻止触达；
- 是继续研究、接受未知还是来源受限。

只有会改变联系人、联系理由、产品承诺或安全边界的缺口才默认 `blocks_outreach=true`。

## 9. Claim与草稿合同

Evidence 是观察，Claim 是待决定事实，正式公司/联系人字段只接受经过规则或人工批准的 Claim。没有 Evidence 的 Claim 不能接受；存在冲突证据时必须 held 或 rejected。

邮件和 LinkedIn 必须是两条独立记录。每条草稿必须关联联系人和个性化证据：

- 草稿的 `evidence_ids` 必须指向当前公司或联系人的存在且非冲突证据；
- `fact_check_status` 和 `voice_check_status` 未通过时不能批准；
- 人工批准保存正文哈希，正文变化后批准立即失效；
- `sent` 必须有 `sent_at`，且只表示人工回填发送事实；
- `do_not_contact` 公司、联系人或邮箱不得存在可发送状态的草稿；
- 第一轮无回复不自动生成下一条追信。

## 10. 回复与询盘合同

回复只提取文字中明确出现的信息。目的地、日期、人数、客群、服务、语言、预算、佣金和截止日期没有出现时留空，并写入 `unknown_requirements`。

报价、会议、佣金、合同、支付、取消、投诉、退订和复杂执行需求必须 `needs_human_takeover=true`。

当回复类别为 `unsubscribe`、`complaint` 或明确拒绝继续联系时：

1. `do_not_contact=true`；
2. 建立 `StopRule` 记录；
3. 相关待发送草稿改为 `stopped`；
4. 后续批次仍需命中该停止规则。

## 11. 重复记录合同

确定重复键：

- 公司根域名完全相同；
- 联系人公开邮箱完全相同；
- 联系人 LinkedIn URL 完全相同。

疑似重复：

- 同国家且规范化公司名称高度相似；
- 同公司且联系人姓名高度相似，但缺少确定键。

脚本只能写入 `DuplicateReview`，不能自动删除或合并。推荐保留资料最完整的一条，但最终决定由人工填写。

## 12. 兼容旧版 CSV

旧版多表JSON使用 `inbound-leads import legacy` 无损封存原始输入并映射到SQLite。旧单表CSV应先整理为当前 `companies`、`contacts` 或 `evidence` 导入字段；未知字段会明确报错，不会静默丢弃。
