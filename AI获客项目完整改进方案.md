# 入境游 AI 获客项目完整改进方案

版本：1.0 方案版  
状态：核心工程已实施；真实五家公司前向测试与20—25家公司业务UAT待完成  
适用仓库：`inbound-ai-acquisition`  
目标发布版本：`v1.0.0`  
最后更新：2026-09-04

> 本文档定义如何把当前 Skill 原型改造成一个可以从 GitHub 克隆、安装、初始化、运行、检查、导出和升级的完整项目。本文是实施和验收基线；未通过第 22 节全部验收项前，不得宣称项目已经达到正式可用状态。

> 2026-09-04 实施记录：Python包、统一CLI、SQLite、旧数据迁移、Evidence/Claim、事件账本、幂等、草稿审批、回复停止规则、openpyxl导出、公开仓库审计、Skill同步、CI与冷启动文档已经落地。代码工程验收不等于真实获客效果验收；尚未完成的真实UAT继续按第21—22节执行。

## 1. 最终结论

项目继续保持一个主 Skill，不拆成大量用户需要记忆的子 Skill，也暂不建设完整 CRM。

正式 V1 采用以下技术路线：

```text
Codex 主 Skill
  ↓ 调用
Python CLI / 应用服务
  ↓ 读写
本地 SQLite 唯一事实库
  ↓ 导出
Excel 人工审阅工作簿
```

系统必须形成以下闭环：

```text
业务上下文
→ 创建获客批次
→ 多来源发现公司
→ 保存来源运行结果
→ 保存原始证据
→ 提出待确认事实
→ 规则或人工接受事实
→ 核验负责人
→ 生成外联简报
→ 生成邮件和 LinkedIn 草稿
→ 三层门禁检查
→ 人工批准和发送
→ 回复回灌
→ 停止联系或转人工
→ 批次复盘
→ 更新下一批规则
```

完整项目不是“能生成几段文字”，而是满足以下条件：

- GitHub 克隆后能按 README 独立完成安装和初始化；
- 没有付费 API 也能完成导入、整理、核验、人工研究回填、草稿、回复、审计和 Excel 导出；
- 使用 Codex 时，可以通过一个主 Skill 驱动完整工作流；
- 每次运行可恢复、可重试、可检查，不会因重复执行产生重复客户或重复回复；
- 证据、事实提议、正式字段和人工决策相互分离；
- 任何发送、报价、承诺和外部写入都不会被默认自动执行；
- 真实数据不进入公开仓库；
- 一批 20—25 家真实公司 UAT 通过后才发布 `v1.0.0`。

## 2. 当前项目判断

### 2.1 已经具备

- 一个主 `SKILL.md` 和按任务加载的参考文档；
- 入境游 B2B 市场、客户类型、渠道和人工边界；
- 公司、联系人、证据、缺口、草稿、回复、停止名单和重复审查合同；
- JSON 规范化、去重、回复回写、Excel 导出和校验脚本；
- 虚构数据和基础自动测试；
- 发布文件哈希清单工具。

### 2.2 尚未达到“克隆即可完整使用”的原因

1. JSON 和 Excel 同时承担数据存储，缺少唯一事实源。
2. 脚本彼此独立，没有统一 CLI、运行控制器和事务。
3. 当前 Excel 依赖 Codex 内置 Node 表格运行库，普通 GitHub 用户无法稳定复现。
4. `Evidence` 同时表达来源、事实和采纳状态，来源观察与正式结论没有彻底分开。
5. 没有持久事件账本，失败后无法准确知道执行到哪一步。
6. 写操作缺少完整幂等语义，重复回灌可能报错或产生重复结果。
7. 未知字段可能在规范化或导出时被忽略，存在静默丢数据风险。
8. 没有统一来源适配器、来源运行状态、费用和贡献统计。
9. 没有事实及联系人时效复查机制。
10. 当前测试能证明部分结构正确，不能证明整个业务工作流可靠。
11. 仓库工作区、GitHub 已提交版本和本地已安装 Skill 尚未形成一致发布链。

## 3. V1 设计原则

### 3.1 一个主 Skill

用户只需要知道 `inbound-ai-acquisition`。研究公司、核验联系人、写草稿、处理回复等是内部模式，不做成一堆独立入口。

### 3.2 SQLite 是唯一事实库

正式数据写入工作区内的 `acquisition.db`。JSON、CSV 和 Excel 都是导入或导出格式，不再作为多次运行之间的权威状态。

选择 SQLite 的原因：

- Python 自带驱动，不需要数据库服务器；
- 支持事务、唯一约束、迁移和并发保护；
- 可以安全实现幂等、事件序列和跨表关联；
- 单文件便于本地备份；
- 后续迁移 Postgres 时模型清晰。

SQLite 不等于建设 CRM。V1 仍然是本地获客工作区，没有用户体系、销售看板、复杂权限或后台常驻服务。

### 3.3 Excel 是审阅界面

Excel 只承担：

- 人工查看公司、联系人、证据和缺口；
- 查看邮件及 LinkedIn 草稿；
- 查看回复、询盘和停止名单；
- 导出给业务人员使用。

不能直接把修改过的 Excel 当成已批准事实重新覆盖数据库。需要回写时，使用明确的 `import-review` 命令生成变更预览，再由人工确认。

### 3.4 原始观察、事实提议和正式字段分离

```text
SourceRun：这次去哪里查、结果是什么
Evidence：页面实际观察到什么
Claim：根据一条或多条证据提出什么事实
Decision：事实是否被接受、暂缓或拒绝
Company/Contact：只保存已经接受的运营字段
```

模型不能用自己的“置信度”直接覆盖正式字段。置信等级由可检查规则根据证据类型、独立来源和冲突计算，人工保留最终决定权。

### 3.5 写操作默认幂等

所有会改变数据库的命令必须接收或生成 `idempotency_key`。同一请求重复执行时：

- 输入完全相同：返回 `already_applied`；
- 同一键但输入不同：返回 `idempotency_conflict`；
- 不得创建第二条重复记录。

### 3.6 失败必须显式

来源和任务结果至少区分：

```text
succeeded
no_results
restricted
failed_retryable
failed_terminal
cancelled
```

禁止捕获异常后静默返回空数组，因为“确实没有结果”和“程序失败”不是同一件事。

### 3.7 外部写入仍由人工控制

V1 可以生成草稿、复制内容和记录人工发送结果，但不自动发送邮件、不自动操作 LinkedIn、不自动报价或承诺。

## 4. 用户最终使用体验

### 4.1 Windows 安装

```powershell
git clone https://github.com/peter-hzy/inbound-ai-acquisition.git
Set-Location inbound-ai-acquisition
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[excel]"
.\.venv\Scripts\inbound-leads.exe doctor
```

### 4.2 macOS / Linux 安装

```bash
git clone https://github.com/peter-hzy/inbound-ai-acquisition.git
cd inbound-ai-acquisition
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[excel]'
.venv/bin/inbound-leads doctor
```

### 4.3 初始化私有工作区

```powershell
inbound-leads init --workspace D:\inbound-leads-data
```

生成：

```text
D:\inbound-leads-data\
├── acquisition.db
├── config.toml
├── product-profile.md
├── voice-profile.md
├── imports\
├── exports\
├── logs\
└── backups\
```

工作区默认在仓库外。README 必须明确提醒：真实客户数据不得放进公开仓库。

### 4.4 安装或同步 Codex Skill

```powershell
inbound-leads skill install --target codex
inbound-leads skill status
```

`skill install` 只复制运行 Skill 所需的 `SKILL.md`、`agents/` 和 `references/`，不复制 `.git`、测试、虚构输出或真实工作区。若目标存在不同版本，默认只显示差异；只有显式 `--replace` 才覆盖。

### 4.5 创建首批任务

```powershell
inbound-leads context validate --workspace D:\inbound-leads-data
inbound-leads run create `
  --workspace D:\inbound-leads-data `
  --market AU,NZ `
  --segments travel_agency,dmc,tour_operator `
  --target 20
```

命令返回 `run_id` 和下一步建议。

### 4.6 无 API 的最低可用模式

用户可以导入自己找到的公司或 URL：

```powershell
inbound-leads import companies `
  --workspace D:\inbound-leads-data `
  --run <run_id> `
  --file companies.csv
```

然后在 Codex 中调用主 Skill，逐家公司研究并写入证据。即使没有任何付费服务，规范化、去重、审核、草稿、回复、复盘和 Excel 导出仍然可用。

### 4.7 导出人工审阅工作簿

```powershell
inbound-leads export workbook `
  --workspace D:\inbound-leads-data `
  --run <run_id> `
  --output D:\inbound-leads-data\exports\batch.xlsx
```

### 4.8 回复回灌

```powershell
inbound-leads reply ingest `
  --workspace D:\inbound-leads-data `
  --file reply.json `
  --idempotency-key reply-20260904-001
```

回复涉及退订或投诉时，命令必须在同一数据库事务中：写回复、写停止规则、停止待发草稿、更新联系人状态和写事件。

## 5. 支持范围说明

| 使用方式 | 克隆后可用 | 额外条件 |
|---|---:|---|
| 初始化、导入、规范化、去重 | 是 | Python 3.11+ |
| SQLite 状态、审计、备份 | 是 | 无 |
| Excel 导出和校验 | 是 | 安装 `[excel]` 依赖 |
| 人工 URL/资料研究回填 | 是 | 无 |
| Codex AI 研究和草稿 | 是 | 安装 Skill，并具备相应浏览能力 |
| 搜索 API 批量发现 | 可选 | 用户自行配置允许的数据源密钥 |
| 邮箱验证服务 | 可选 | 用户明确启用并承担费用 |
| 邮件或 LinkedIn 自动发送 | 否 | V1 明确不做 |
| CRM 同步 | 否 | 真实 UAT 后另行评估 |

不得在 README 中写“完全无需外部工具自动找到所有负责人”。公开网页可访问性、LinkedIn 权限和邮箱可验证性始终存在客观限制。

## 6. 目标仓库结构

```text
inbound-ai-acquisition/
├── SKILL.md
├── README.md
├── ARCHITECTURE.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── uv.lock
├── .env.example
├── .gitignore
├── agents/
│   └── openai.yaml
├── src/inbound_ai_acquisition/
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── errors.py
│   ├── domain/
│   │   ├── enums.py
│   │   ├── models.py
│   │   ├── transitions.py
│   │   └── policies.py
│   ├── application/
│   │   ├── run_service.py
│   │   ├── research_service.py
│   │   ├── claim_service.py
│   │   ├── identity_service.py
│   │   ├── outreach_service.py
│   │   ├── reply_service.py
│   │   └── export_service.py
│   ├── storage/
│   │   ├── database.py
│   │   ├── migrations.py
│   │   └── repositories.py
│   ├── adapters/
│   │   ├── base.py
│   │   ├── manual.py
│   │   ├── public_web.py
│   │   └── registry.py
│   ├── exporters/
│   │   ├── workbook.py
│   │   └── json_export.py
│   └── audit/
│       ├── events.py
│       ├── public_repo.py
│       └── release.py
├── migrations/
│   ├── 001_initial.sql
│   └── 002_claims_and_events.sql
├── references/
├── templates/
├── scripts/
│   ├── bootstrap.ps1
│   ├── bootstrap.sh
│   └── release_check.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   ├── security/
│   └── fixtures/
├── docs/
│   ├── quickstart.md
│   ├── cli.md
│   ├── data-model.md
│   ├── source-adapters.md
│   ├── privacy.md
│   ├── troubleshooting.md
│   └── uat.md
└── .github/workflows/ci.yml
```

现有脚本在迁移完成前保留为兼容入口，最终只调用正式 Python 包，不继续维护两套业务逻辑。

## 7. 模块职责

### 7.1 `domain`

只包含稳定业务模型、枚举、状态迁移和规则，不读取文件、不访问网络、不依赖 Excel。

### 7.2 `application`

编排一个完整用例。例如回复回灌服务负责验证输入、检查幂等、写回复、写停止规则、停止草稿和记录事件。所有相关修改必须处于同一事务。

### 7.3 `storage`

统一管理 SQLite 连接、事务、迁移和仓储。其他模块不能在不同位置自行拼 SQL。

### 7.4 `adapters`

封装外部来源。适配器只负责查询和返回观察结果，不决定客户是否值得联系，也不能直接修改公司正式字段。

### 7.5 `exporters`

从数据库创建 Excel 和 JSON 快照。导出过程只读，不改变业务状态。

### 7.6 `audit`

负责事件记录、敏感文件扫描、发布文件锁和仓库/安装版本一致性检查。

### 7.7 `SKILL.md`

只保留：模式路由、核心业务上下文、权限边界、何时读取哪个 reference，以及调用哪些 CLI 命令。数据库字段和大段操作说明放到 references 或 docs，避免每次调用加载无关内容。

## 8. SQLite 数据模型

### 8.1 `workspace_meta`

- `schema_version`
- `project_version`
- `created_at`
- `last_migrated_at`
- `workspace_id`

### 8.2 `runs`

- `run_id`
- 市场、客户类型、目标数量
- 产品资料版本、语气版本
- `status`
- 创建人、创建时间、关闭时间
- `next_action`

### 8.3 `companies`

- 内部不可变 `company_id`
- 原始名称、规范名称、国家、城市、类型
- 官网、根域名、LinkedIn 公司页
- 当前正式匹配结论
- 候选状态、研究阶段、风险备注
- 创建及更新时间

`company_id` 不再根据可变化字段重新生成。域名和名称作为身份键保存到 `entity_keys`。

### 8.4 `contacts`

- 内部不可变 `contact_id`
- `company_id`
- 正式姓名、职位、职责范围
- 主要、备用或转交角色
- LinkedIn、公开业务邮箱及各自状态
- 身份状态、联系状态
- 创建及更新时间

### 8.5 `entity_keys`

统一保存实体身份键：

- `entity_type`
- `entity_id`
- `key_type`：`root_domain/name_country/linkedin/email/external_id`
- `normalized_value`
- `status`：`active/conflicting/retired`
- 来源和观察时间

对 `key_type + normalized_value + status=active` 建唯一约束，防止同一个 LinkedIn 或邮箱关联多个活动联系人。

### 8.6 `source_runs`

- `source_run_id`
- `run_id`、`adapter_id`
- 查询摘要和查询指纹
- 开始、结束时间和尝试次数
- `outcome`
- 结果数量、费用和耗时
- 错误码、可否重试

### 8.7 `evidence`

一条记录代表一个独立来源观察：

- `evidence_id`
- `source_run_id`
- 实体类型和 ID
- 来源 URL、来源等级和用途
- 页面实际摘要或有限摘录
- 发布时间、观察时间、内容哈希
- 访问状态
- 是否与已有资料冲突

同一页面中的多个字段可以由一条 Evidence 支持，不能拆成多个“独立来源”。

### 8.8 `claims`

一条记录代表一个待决定事实：

- `claim_id`
- 实体、字段、提议值
- `status`：`proposed/accepted/held/rejected/superseded`
- 规则计算出的证据等级
- 冲突原因
- 决策人、决策时间和决策理由
- `supersedes_claim_id`

### 8.9 `claim_evidence`

Claims 与 Evidence 的多对多关系。接受事实前必须至少有一条允许支持该字段的 Evidence；身份字段使用更严格规则。

### 8.10 `research_gaps`

- 缺失字段、业务影响、建议来源
- 是否阻止外联
- 状态、负责人、复查时间

### 8.11 `drafts`

- 联系人、渠道、主题、正文、CTA
- 使用的 Claim 和 Evidence
- 事实检查、语气检查、停止检查
- 草稿及人工审核状态
- 产品和语气版本
- 手工发送时间及外部引用

### 8.12 `approvals`

每次批准或拒绝单独记录，不能只覆盖 Draft 的一个字段：

- `approval_id`
- 对象类型和 ID
- 决定、决定人、时间、理由
- 被批准内容的哈希

草稿批准后若正文发生变化，原批准立即失效。

### 8.13 `replies`

保留原文或私有来源引用、回复类别、明确需求、未知需求、下一步、人工接管和停止联系状态。

### 8.14 `stop_rules`

- 作用域：公司、域名、联系人、邮箱、LinkedIn
- 规范值、渠道、原因、来源
- 永久或到期时间
- 建立人和解除人

停止命中发生在草稿创建之前、批准之前和标记发送之前，共检查三次。

### 8.15 `duplicate_candidates`

保存确定或疑似重复组、匹配字段、冲突字段、建议保留记录和人工决定。程序不得自动合并模糊重复。

### 8.16 `events`

追加式事件账本：

- `event_id`
- `run_id`
- 单调递增 `sequence`
- `event_type`
- `entity_type/entity_id`
- `idempotency_key`
- 输入和输出哈希
- 状态、错误码、操作者、工具版本
- 创建时间

事件正文只存业务摘要，不能记录密钥、完整私人邮件或不必要个人数据。

## 9. 事实决策规则

### 9.1 证据等级与事实状态是两件事

- Evidence 等级说明来源性质；
- Claim 状态说明该事实是否进入正式记录；
- 不能用 `confidence=0.9` 替代来源检查；
- 搜索摘要只能发现页面，不能直接让 Claim 变为 accepted；
- 发生 contradiction 时 Claim 必须进入 held，直到人工解决。

### 9.2 身份事实

联系人姓名、现任公司和职责至少满足以下一种：

1. 本人公开职业资料直接支持；
2. 公司团队页直接支持；
3. 对方从该业务邮箱回复并在签名中明确身份；
4. 姓名与当前雇主由两个相互独立的可靠来源共同支持。

只有姓名、只有公司或仅由邮箱格式推测，均不得 accepted。

### 9.3 正式字段更新

接受 Claim 时由 `claim_service` 在事务中：

1. 检查证据和冲突；
2. 将旧 Claim 标为 superseded；
3. 写入正式字段；
4. 写 Decision 和 Event；
5. 保留完整历史。

## 10. 状态机

### 10.1 批次

```text
created → researching → review_ready → approved → active → closed
                  ↘ held                    ↘ aborted
```

### 10.2 公司

```text
discovered → researching → formal
                     ↘ held
                     ↘ excluded
```

`formal` 必须满足公司主体、业务联系依据和联系人处理结果均有明确状态。

### 10.3 联系人

```text
candidate → verifying → verified/supported
                    ↘ not_found
                    ↘ contradicted
任何活动状态 → stopped
```

### 10.4 Claim

```text
proposed → accepted
         → held → accepted/rejected
         → rejected
accepted → superseded
```

### 10.5 草稿

```text
draft → review_ready → approved → manually_sent
   ↘ rejected
任何未发送状态 → stopped
```

禁止跳过事实、语气、停止名单和人工批准直接进入 `manually_sent`。

### 10.6 来源运行

```text
queued → running → succeeded/no_results/restricted
                 → failed_retryable → running
                 → failed_terminal
                 → cancelled
```

每个状态迁移必须由集中式 transition policy 检查并写 Event。

## 11. 来源适配器合同

每个适配器实现统一接口：

```python
class SourceAdapter(Protocol):
    adapter_id: str
    capabilities: set[str]

    def discover(self, request: DiscoveryRequest) -> SourceResult: ...
    def inspect_company(self, request: CompanyRequest) -> SourceResult: ...
    def inspect_contact(self, request: ContactRequest) -> SourceResult: ...
```

`SourceResult` 必须包含：

- adapter 和查询指纹；
- 明确 outcome；
- 观察记录及来源 URL；
- 开始/结束时间；
- 错误码和是否可重试；
- 费用和限速信息（如有）；
- 不包含业务判断和自动正式写入。

### 11.1 V1 内置适配器

- `manual`：导入用户提供的公司、URL、目录或联系人；
- `public_web`：处理用户或 Codex 已打开的公开页面结果；
- `directory_csv`：导入旅游协会、展会和供应商目录导出；
- `codex_bridge`：接收主 Skill 研究后的结构化观察。

### 11.2 V1 可选适配器

- 合法授权的搜索 API；
- 邮箱验证服务；
- Apollo 等联系人数据库；
- 官方旅游协会或展会接口。

可选适配器不得成为核心功能的硬依赖。每个适配器单独配置、单独限速、单独记录来源，不允许把多个失败混成“没有找到”。

### 11.3 明确禁止

- 随机生成姓名、公司、邮箱、电话或 verified；
- 根据姓名和域名拼接邮箱后冒充有效邮箱；
- 关闭 TLS 证书校验；
- 捕获全部异常后返回空成功结果；
- 使用 Cookie、密码、会话令牌模拟 LinkedIn 登录；
- 绕过验证码、robots、平台访问限制或授权边界。

## 12. 去重和身份键

### 12.1 公司确定键

- 相同规范根域名；
- 相同可靠外部注册 ID；
- 人工确认的历史别名。

### 12.2 联系人确定键

- 相同规范 LinkedIn URL；
- 相同已验证业务邮箱；
- 相同可靠外部人员 ID。

### 12.3 模糊匹配

名称相似、同国同名、同公司同名只进入 `duplicate_candidates`。合并必须人工批准，并保留旧 ID 到新 ID 的 alias，避免历史草稿和回复失联。

## 13. 外联门禁

创建 `review_ready` 草稿前必须全部满足：

- 公司处于 formal 或人工允许的 chat candidate；
- 联系人身份为 verified 或 supported；
- 没有阻止外联的研究缺口；
- 联系理由对应 accepted Claim；
- 个性化内容引用有效 Evidence；
- 产品能力来自当前产品资料版本；
- 未命中任何 StopRule；
- 邮件和 LinkedIn 分别写作；
- 只有一个轻量 CTA；
- 没有虚构价格、资质、案例、需求或合作关系。

批准后保存正文哈希。发送前再次计算哈希；若内容被修改，必须重新批准。

## 14. 回复和停止机制

回复自然语言分类由 Skill 辅助，最终结构化输入必须可供人工查看。确定性服务只负责验证和写入，不自行理解回复含义。

以下类别强制人工接管：

- `request_quote`
- `meeting_requested`
- `unsubscribe`
- `complaint`
- 涉及合同、付款、佣金、法律、游客个人信息或复杂会展执行

`unsubscribe` 和 `complaint` 必须在同一事务中创建跨渠道 StopRule。`declined` 只有在原文明示不再联系时才永久停止。

同一回复重复回灌必须安全返回 `already_applied`，不能再次累计回复数或创建第二条停止规则。

## 15. 运行控制和恢复

### 15.1 每个命令的标准结果

```json
{
  "request_id": "...",
  "status": "succeeded|already_applied|needs_review|failed",
  "run_id": "...",
  "changed_records": 0,
  "next_action": "...",
  "errors": []
}
```

### 15.2 重试

- 读取类网络失败最多自动重试 2 次；
- 429/临时服务错误按适配器返回建议等待时间；
- 身份冲突、权限限制、无结果和输入错误不自动重试；
- 每次重试写 attempt 和 Event；
- 达到上限后标为 failed_terminal，不能无限循环。

### 15.3 恢复

`inbound-leads run status --run <id>` 必须显示：

- 当前阶段；
- 已完成和未完成公司数；
- 待人工处理 Claims、重复、联系人和草稿；
- 失败、受限和可重试来源；
- 下一步可执行命令。

## 16. CLI 命令范围

```text
inbound-leads doctor
inbound-leads init
inbound-leads migrate
inbound-leads backup
inbound-leads context validate
inbound-leads run create|status|close
inbound-leads import companies|contacts|evidence|review
inbound-leads source list|status
inbound-leads company list|show
inbound-leads contact list|show
inbound-leads claim list|accept|hold|reject
inbound-leads dedupe scan|review
inbound-leads draft create|check|approve|mark-sent|stop
inbound-leads reply ingest
inbound-leads stop add|list|release
inbound-leads export workbook|json
inbound-leads audit workspace|public-repo|release
inbound-leads skill install|status
```

高风险命令必须要求明确对象和理由。`mark-sent` 只记录人工已经发送，不执行发送。`stop release` 必须记录解除人和理由。

## 17. 配置和密钥

### 17.1 `config.toml`

只保存非敏感配置：市场、客户类型、批次大小、来源开关、重试限制、数据保留期和导出设置。

### 17.2 环境变量

可选 API 密钥只通过环境变量或系统密钥管理提供。`.env.example` 只列变量名和用途，不放真实值。

### 17.3 `doctor`

必须检查：

- Python 和包版本；
- 工作区是否可写；
- 数据库版本和迁移状态；
- Excel 依赖是否可用；
- 可选适配器是否配置；
- Skill 仓库版与安装版是否一致；
- 不输出密钥，只显示 configured/not configured。

## 18. Excel 输出

V1 使用 Python `openpyxl` 生成工作簿，移除对 Codex 私有 Node 运行环境和本地 `node_modules` junction 的依赖。

工作簿至少包含：

- RunSummary
- Companies
- Contacts
- Evidence
- Claims
- ResearchGaps
- Drafts
- Approvals
- Replies
- StopRules
- DuplicateReview
- SourcePerformance

要求：

- 冻结表头、筛选、合理列宽、换行和日期格式；
- 状态字段有下拉验证；
- held、contradicted、stopped 和 failed 使用醒目颜色；
- URL 可点击；
- 导出后重新读取，验证工作表、字段、主外键和公式；
- Excel 修改不能直接覆盖数据库，必须经过差异导入流程。

## 19. 测试方案

### 19.1 单元测试

- URL、域名、邮箱和名称规范化；
- 状态迁移允许和拒绝路径；
- Claim 证据等级和冲突规则；
- StopRule 匹配；
- 幂等键和输入哈希；
- 草稿正文哈希及批准失效；
- 适配器错误映射。

### 19.2 数据库测试

- 所有迁移从空库成功；
- 从上一 schema 逐版本升级；
- 唯一约束和外键生效；
- 事务中途失败时完整回滚；
- 重复回复不会重复累计；
- 模糊重复不会自动合并；
- Event sequence 单调且同一 run 不重复。

### 19.3 合同测试

- 每个来源适配器返回统一 SourceResult；
- 每条输入必须得到成功、无结果、受限或失败状态；
- 未知字段默认报错，不静默丢弃；
- 兼容导入使用显式映射并保存原始文件哈希；
- CLI JSON 输出保持兼容。

### 19.4 安全测试

- `.env`、密钥模式、真实邮箱样本和私人回复不会进入发布包；
- StopRule 在草稿、批准和发送记录前均生效；
- 未批准草稿不能 mark-sent；
- 修改获批正文会撤销批准；
- 外部文本不能改变权限配置；
- TLS 校验不能被关闭；
- 日志不能包含密钥和完整私人消息。

### 19.5 端到端虚构测试

至少覆盖：

1. 正常公司 → 已核验联系人 → 草稿 → 批准 → 人工发送记录；
2. 公司匹配但负责人未找到 → 转交入口；
3. 身份冲突 → held，禁止草稿升级；
4. 同域名重复 → 人工审查，不自动合并；
5. 退订回复 → 回复、停止规则和草稿停止原子写入；
6. 相同回复重试 → already_applied；
7. 来源 403 → restricted，不得写成 no_results；
8. 输入多出字段 → 明确失败或进入 RawImport，不得消失；
9. 批准后改正文 → 批准失效；
10. Excel 导出后回读验证通过。

### 19.6 前向测试

使用没有预先写出答案的真实请求，让独立执行过程只根据 Skill、产品资料和公开来源完成五家公司研究。检查结果而不是关键词。

## 20. GitHub CI 和发布链

### 20.1 每次提交检查

CI 在 Windows 和 Linux 上运行：

```text
格式检查
静态类型检查
单元测试
数据库迁移测试
合同测试
安全测试
Skill quick_validate
虚构端到端测试
Excel 生成和回读验证
公开仓库敏感数据扫描
manifest/lock 一致性检查
```

### 20.2 发布锁

生成 `skills.lock.json`，记录正式 Skill 文件、references、模板、Python 包版本和 SHA-256。`audit release` 必须验证锁文件没有过期。

```powershell
inbound-leads audit release --workspace D:\inbound-leads-data
```

### 20.3 本地安装一致性

发布前运行：

```powershell
inbound-leads skill install --target codex --replace
inbound-leads skill status
```

`skill status` 必须返回仓库版本、安装版本、manifest 哈希和 `in_sync=true`。

### 20.4 Git 发布顺序

```text
工作区检查
→ 全量测试
→ 公开仓库审计
→ 生成并验证 lock
→ 同步本地 Skill
→ 再次验证
→ 提交
→ 推送分支
→ 创建 v1.0.0 tag/release
→ 从全新目录重新克隆
→ 按 README 冷启动验收
```

未经用户明确要求，不自动推送、打标签或发布 Release。

## 21. 实施阶段

### 阶段 0：保护当前成果

交付：

- 保存当前 Git 状态和测试结果；
- 不覆盖现有 JSON/Excel 示例；
- 建立迁移夹具；
- 明确旧脚本兼容期限。

完成条件：当前 12 项测试继续通过，现有示例可以被新版迁移器读取。

### 阶段 1：可安装 Python 项目

交付：

- `pyproject.toml`、`src/` 和 `inbound-leads` CLI；
- `doctor`、`init`、`config`；
- Windows/Linux 安装说明；
- 移除 Excel 对 Codex Node 运行库的硬依赖。

完成条件：全新机器按 README 命令能够初始化工作区并导出空工作簿。

### 阶段 2：SQLite 和迁移

交付：

- 初始 schema 和迁移器；
- repositories 和事务；
- 当前 JSON → SQLite 导入器；
- 备份和恢复命令。

完成条件：现有虚构工作簿数据完整迁移，行数、关联和状态一致。

### 阶段 3：Claims、事件和幂等

交付：

- Evidence/Claim/Decision 分层；
- Event Ledger；
- 所有写命令幂等；
- 状态迁移策略；
- 严格输入验证。

完成条件：重试、冲突、回滚、未知字段和状态跳跃测试全部通过。

### 阶段 4：研究和身份闭环

交付：

- 来源适配器接口及四个本地适配器；
- SourceRun 状态；
- EntityKeys 和重复审查；
- 联系人身份核验及复查时间；
- 来源贡献报告。

完成条件：五家虚构公司能显示每个来源做了什么、失败在哪、哪些 Claim 被接受以及为何选该联系人。

### 阶段 5：外联、批准和回复

交付：

- 外联简报服务；
- 邮件和 LinkedIn 草稿门禁；
- 内容哈希审批；
- 幂等回复回灌；
- StopRule 三次检查。

完成条件：所有第 19.5 节场景通过，无未经批准发送路径。

### 阶段 6：Excel、审计和发布工具

交付：

- openpyxl 多表导出；
- 差异式 review 导入；
- public-repo audit；
- release lock；
- Skill install/status。

完成条件：普通 GitHub 克隆环境不依赖 Codex 私有运行库即可生成并验证工作簿。

### 阶段 7：文档和 CI

交付：

- README 五分钟快速开始；
- ARCHITECTURE、CLI、数据模型、隐私和故障排查文档；
- Windows/Linux CI；
- 发布前冷启动脚本。

完成条件：未参与开发的人可以只看 README 完成安装、初始化、导入示例、导出 Excel 和运行测试。

### 阶段 8：真实 UAT

先完成五家公司只读试运行，再扩展到 20—25 家：

1. 澳大利亚、新西兰优先；
2. 每家公司至少有主体和业务依据；
3. 联系人必须 verified/supported/not_found/contradicted 四选一；
4. 每条草稿可追溯到 accepted Claim 和 Evidence；
5. 人工记录改稿原因；
6. 不自动发送；
7. 使用真实回复时保存在仓库外私有工作区；
8. 完成来源、联系人、话术和流程复盘。

完成条件：第 22 节全部通过，用户确认输出可以用于日常开发客户。

### 阶段 9：发布 `v1.0.0`

只有真实 UAT 通过后执行。发布后再讨论邮箱验证、邮件草稿 API、Apollo、MCP 或 CRM，不在 V1 实施中顺带扩张。

## 22. 正式 V1 验收清单

### 安装

- [ ] Windows 和 Linux 全新目录克隆成功；
- [ ] README 命令无缺失步骤；
- [ ] 核心功能不要求付费 API；
- [ ] `doctor` 能准确显示可用与缺失能力。

### 数据

- [ ] SQLite 是唯一事实库；
- [ ] 旧 JSON 可无损迁移；
- [ ] 未知字段不会静默丢失；
- [ ] 所有主外键、唯一键和迁移通过；
- [ ] Excel 可以生成并回读验证。

### 研究

- [ ] 搜索摘要不能直接成为正式事实；
- [ ] Evidence、Claim、Decision 和正式字段分离；
- [ ] 来源失败、无结果和受限状态分开；
- [ ] 联系人身份不靠猜测；
- [ ] 事实冲突会阻止升级；
- [ ] 来源贡献和时效可查看。

### 外联

- [ ] 每条草稿有真实联系依据；
- [ ] 邮件和 LinkedIn 分别写作；
- [ ] 产品未知项不会变成承诺；
- [ ] 修改已批准正文会撤销批准；
- [ ] 系统没有自动发送路径。

### 回复和停止

- [ ] 回复回灌幂等；
- [ ] 报价、会议和风险回复转人工；
- [ ] 退订和投诉原子建立停止规则；
- [ ] StopRule 在三个关键节点生效；
- [ ] 解除停止必须有人工理由。

### 审计和发布

- [ ] 每个写操作都有 Event；
- [ ] 重试次数和失败原因可见；
- [ ] 公开仓库不含真实客户数据和密钥；
- [ ] manifest/lock 与文件一致；
- [ ] 仓库 Skill 与本地安装版一致；
- [ ] 全量 CI 通过；
- [ ] 20—25 家真实公司 UAT 通过；
- [ ] 用户确认可以投入日常获客。

## 23. 开源项目采用矩阵

以下结论基于 2026-09-04 审查的仓库快照。只借鉴理念和经过重新实现的通用模式，不直接混入不兼容或许可不明确的代码。

| 项目 | 审查快照 | 采用 | 拒绝或暂缓 |
|---|---|---|---|
| [LeadMagic/gtm-skills](https://github.com/LeadMagic/gtm-skills) | `130b433`，MIT | 文件锁、来源贡献、安装和公开仓库审计 | 关键词式 checker、SaaS 固定门槛、付费工具硬依赖 |
| [ai-sales-team-claude](https://github.com/zubair-trabzada/ai-sales-team-claude) | `efef8b8`，MIT | 研究/联系人/外联/回复职责边界 | 关闭 TLS、正则抓取即确认、固定 BANT/MEDDIC、默认连续触达 |
| [linkedin_skills](https://github.com/xx254/linkedin_skills) | `168bcd7`，未发现明确根许可证 | 语气校准、稳定登记、结果复盘 | 不复制源码、不混合退订与普通拒绝、不采用自动发送方向 |
| [KeeLead](https://github.com/Atum246/keelead) | `a846e2b`，MIT | 适配器接口、CLI/MCP 分层、来源能力声明 | 随机生成 Lead、猜邮箱、虚假 verified、静默空数组 |
| [profilespider-agent-skills](https://github.com/spiralcrew-ou/profilespider-agent-skills) | `6c65d05`，MIT | 原值/规范值、研究缺口、人工去重、外联简报 | 把提示词合同当成真实执行保证 |
| [trycompai/crm](https://github.com/trycompai/crm) | `6d4793d`，MIT | Claim 提议、Evidence Ledger、运行锁、重试上限、复查理由、数据出境边界 | V1 部署其完整 CRM、Postgres、持久 Agent 和多服务架构 |

许可证允许不代表应直接复制。任何实际复制都必须保存版权声明、检查依赖许可并进行安全测试；本方案优先重新实现适合本项目的最小功能。

## 24. 风险及控制

| 风险 | 控制 |
|---|---|
| 为了“完整”过度建设 | V1 只使用本地 SQLite 和 CLI，不建设 CRM/UI/后台服务 |
| 公开网页变化 | 保存 URL、时间、摘要、哈希和复查时间 |
| 联系人身份错误 | Claim 门禁、独立证据、冲突 held、人工审查 |
| 重复运行重复写入 | 幂等键、唯一约束和事务 |
| Excel 与数据库分叉 | 数据库单一事实源，Excel 差异导入 |
| API 不可用 | 可选适配器、显式失败、本地手工模式 |
| 真实数据泄漏 | 工作区在仓库外、public-repo audit、日志脱敏 |
| 误发或平台风险 | 无自动发送工具、批准哈希、StopRule 三次检查 |
| 测试只会匹配关键词 | 真实状态、数据库副作用和负向场景测试 |
| 仓库与安装 Skill 不一致 | skill manifest、status diff 和发布前同步门禁 |

## 25. V1 后再考虑

以下功能不进入当前完成范围：

- Web CRM 或团队协作界面；
- Postgres、多租户和角色权限；
- 无人值守任务调度；
- 自动邮件发送和 LinkedIn 自动化；
- 自动报价、合同和付款；
- 大规模邮件序列；
- 复杂机器学习评分；
- 多 Agent 自主销售团队。

只有当真实 UAT 证明 Excel 审阅、单机 SQLite 或人工发送成为明确瓶颈时，才讨论这些功能。

## 26. 实施中不再反复讨论的决定

- 一个主 Skill；
- 优先澳大利亚、新西兰，同步美国、加拿大；
- 首要客户为旅行社、DMC 和旅游批发商；
- 后续覆盖企业差旅、MICE 和活动策划；
- 每批默认 20—25 家；
- 邮件和 LinkedIn 同批准备、分别写作；
- 首轮无回复默认停止；
- 不猜邮箱；
- 不自动发送；
- SQLite 为事实库，Excel 为审阅出口；
- 先完成真实 UAT，再评估 CRM 和付费连接器。

## 27. 下一步执行顺序

下一次正式开发从阶段 0—3 开始，不先做真实 20—25 家名单：

1. 建立 `pyproject.toml`、正式包和 CLI；
2. 建立 SQLite schema、迁移、事务和备份；
3. 将现有 JSON 示例无损迁移；
4. 实现 Claims、Events、幂等和状态迁移；
5. 替换 Excel 导出依赖；
6. 完成负向和端到端测试；
7. 再进入来源适配器、真实五家公司试运行和完整 UAT。

这一顺序能先解决数据真实性、重复执行和可恢复性，再验证获客效果；否则真实 UAT 中出现的问题无法可靠定位和复现。

## 28. 方案自检记录

本文完成后必须执行三遍检查：

### 第一遍：范围和事实一致性

- 与此前确认的市场、客户、产品、渠道和人工边界一致；
- 没有把虚构测试写成真实验证；
- 没有声称 LinkedIn、邮箱或付费 API 克隆后必然可用；
- 开源采用和拒绝项与已检查源码一致。

### 第二遍：工程可执行性

- 克隆、安装、初始化、运行、导出和发布路径完整；
- 每个模块、数据表、状态和 CLI 命令有明确职责；
- 数据迁移、幂等、事务、错误、恢复、测试和 CI 均有交付及完成条件；
- 不依赖当前机器的 Codex 私有 Node 路径。

### 第三遍：简化和风险

- 未引入 CRM、Web UI、Postgres 或多 Agent；
- 没有重复建设两套业务逻辑；
- 高风险动作仍由人工确认；
- 真实数据与公开仓库分离；
- 每一阶段均有停止条件，不会无限扩张。

若任一遍发现冲突，应先修改本文，再开始代码实施。

实际检查结果（2026-09-04）：

- 第一遍范围和事实一致性：通过；
- 第二遍工程可执行性：首次发现缺少完整 `inbound-leads audit release` 命令，补充后通过；
- 第三遍简化和风险：首次发现自动发送拒绝项表述不够明确，修正后通过；
- 额外一致性检查：发现旧方案仍自称唯一基线，已将旧方案降级为历史记录并由 README 指向本文。
