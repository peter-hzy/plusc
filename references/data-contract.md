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
8. 目录或展会来源的域名不是公司域名；发现记录只有明确 `website` 时才用该官网做域名去重。部门邮箱不映射到个人；官网联系页可展示为研究入口，但不自动成为可发送渠道。

## 2. 后台审计结构与Excel结果视图

下表是后台数据库/审计视图，不是默认Excel工作表。用户Excel只有“客户结果”一张表、7列；证据来源可由单元格批注或后台记录追溯，不恢复旧版多工作表输出。

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
- `formal_list`：进入研究名单，具备主体和业务依据；事实核准、实际产品匹配及外联许可单独判断，不代表可发送；
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
- `unverified`：只有候选线索；
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

Evidence 是观察，Claim 是待决定事实，正式公司/联系人字段只接受真实人工批准的 Claim。规则检查不能代替人工批准。没有 Evidence 的 Claim 不能接受；存在冲突证据时必须 held 或 rejected。

选择实际可用的首选渠道；如确需准备两个渠道，必须分别记录，不要求每家公司具备两个渠道。每条草稿必须关联联系人和个性化证据：

- 草稿的 `evidence_ids` 必须指向当前公司或联系人的存在且非冲突证据；
- `fact_check_status` 和 `voice_check_status` 未通过时不能批准；
- 人工批准保存完整发送快照哈希；收件目标、渠道、主题、正文、附件、证据、产品版本或联系合同改变后，原批准不可用于记录发送；
- `sent` 必须有 `sent_at`，且只表示人工回填发送事实；
- `do_not_contact` 公司、联系人或邮箱不得存在可发送状态的草稿；
- 第一轮无回复不自动生成下一条追信。

## 10. 回复与询盘合同

回复只提取文字中明确出现的信息。目的地、日期、人数、客群、服务、语言、预算、佣金和截止日期没有出现时留空，并写入 `unknown_needs`。

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

## 13. 研究扩展合同（无需改变schema）

新研究统一提交qualification_policy=service_fit_v1，以及fit_basis(supported/hypothesis)、business_signal、service_fit、cooperation_hypothesis、counter_evidence、next_action。这些和原有fit_reason/fit_status一起保存为待审Claim，复用既有数据库，不新增表。新合同必须提供field_sources逐字段绑定；绑定有效不证明原文语义，需实际复核。hypothesis不得升priority_chat；supported不等于有采购意向。外联仍要求已批准的产品、事实、身份、适用触达依据和人工审核。新合同不使用下述旧行业/路径字段作为门槛；历史数据没有版本标记则保持旧合同，不能无证据自动升级。新CLI批次默认segments=*，明确指定其他值表示用户要求的行业限制。

source bundle公司可新增qualification_path（direct/expansion/channel）、audience_fit、cooperation_hypothesis、counter_evidence、next_action、group_key、independent_unit_reason。均保存为待审Claim，不直接写成正式事实；预览按accepted再proposed覆盖。扩展和渠道的适用门槛见research-protocol。同一group_key多个公司需要各自独立合作依据，否则验收失败；此检查不能自动发现未提供的集团关系。

contact新增route_grade（R0/R1/R2/R3）、route_purpose（business/general/unknown/unsuitable），也保存为Claim。旧数据保守默认R3/unknown。R1具名相关人员、R2相关部门均要求business及职责说明；R1还需姓名。R3为通用转交，R0缺失；unsuitable、contradicted不能计有效入口。business_route_count与handoff_route_count分开，不把普通页面算职责已确认。

公司/联系人可提供field_sources：字段名到已成功读取的本实体来源URL数组。提供此映射后，每个提交字段都必须有绑定；未知URL或缺字段报错回滚。旧bundle未提供时仍兼容，但宽泛证据关联不证明逐字段语义正确，必须人工复核。新研究应提供绑定，包括route_grade/route_purpose；hypothesis字段是有依据的分析而非对方采购事实。

名单验收检查正式及待审身份上的停发、关键公司阻塞缺口、入口与集团计数。R3可交待审名单，但不是外联批准。research_delivery_status表示名单准备，旧stage仅为工作流兼容，不强制准备文案。

## 1.2.1 审核与回复门槛

新研究统一使用 `service_fit_v1`；`research run` 返回的执行请求和 `research verify --scope outreach` 均使用同一合同，历史无标记数据保留旧合同。

草稿 `outreach_contract` 必须显式记录 `fact_check_status`、`voice_check_status`（`needs_review` / `pending` / `passed` / `failed`），及 `fact_checked_by`、`voice_checked_by`。未通过的草稿保存为 `draft`；只有两个状态均为 `passed` 才进入 `review_ready`，批准仍检查复核人、产品、身份、证据和触达依据。顶层状态可兼容输入，但与合同冲突时拒绝，不再忽略 `failed`。已保存的 `draft` 可重交同一 draft bundle，只更新这四个复核字段；正文、引用、收件目标或已批准草稿的变更仍需重建。状态是人工复核记录，不能由系统替人声称完成检查。

批准和发送登记均要求联系人最近30天核验、引用的公司证据最近90天/联系人证据最近30天，适配字段也须有近90天已接受且可访问、无冲突的来源。日期缺失、无时区、未来或超期均阻止外联。过期时实际重新打开来源，提交带真实 `observed_at` 的增量 source bundle，人工接受新 Claim 后重建草稿；不能只改日期冒充复核。接受身份 Claim 时以其来源观察日期更新 `last_verified_at`。

回复至少提供可定位的 `source_reference` 或 `raw_text`。原文保存在已有 `raw_imports`，仅原文输入会生成内部引用；全量备份及所属批次 JSON 可回读该回复原文，不导出其他批次原文。重复导入仍幂等。Excel 七列结构保持，结果列优先显示各联系人的最新回复、确认/未知需求、下一步与接管/停发状态。

`wrong_person`、`not_fit` 停止当前联系人及等价身份的后续触达，不将整家公司标记不可联系；需人工核实新角色或按既有 stop release 流程解除。报价、价格、合同、投诉等继续转人工。系统没有自动发送、报价、CRM或成交跟踪闭环。

## 1.2.2 实跑缺口与失败执行记录

公司或contact可提交research_gaps数组，每项必须包含field_name、business_impact及JSON布尔blocking。只保存open缺口；重复提交同一实体/字段更新说明，不重复新增，也不通过省略或blocking=false解除已有阻塞。产品语言、人数、研学保障、季节库存和合作条件不明时明确写待确认；影响批准的条件blocking=true。缺口不是事实Claim或人工批准。沿用research_gaps表及已有草稿/批准门禁，不修改数据库结构。

source bundle可附source_attempts数组，记录未取得有效观察的真实执行：source_url、带时区的实际observed_at、outcome（SOURCE_OUTCOMES中除succeeded）、error_code和布尔retryable；可附原始摘要/响应哈希供审计。成功观察仍进入公司/contact sources。相同批次、相同完整attempt重放只保留一条历史执行记录；正常研究执行日志仍逐次增加。错误记录缺时间时先保留原始ledger，不补造时间；实际重试另记真实时间。HTTP成功、安全检查页、空正文与取得有效业务观察必须分开；不得按文本长度替代语义判断。research status返回source_outcomes分类计数，JSON包含完整source_runs。

转交入口增量匹配要求相同实体、无身份冲突并有共同公开入口；不同部门或不唯一匹配不自动合并。已有正式草稿按其原收件目标导出；没有草稿时优先合适用途、已支持身份和可用邮箱/LinkedIn。历史重复联系人保留，不能无授权删除或迁移。内部文案提案仍放私有工作区，proposed Claim不会自动成为正式草稿、人工批准或发送许可。
