<div align="center">

当前版本 **1.2.2**：修复联系人补邮箱重复、导出选旧入口和中文行高；关键产品未知项与失败执行日志结构化保存。事实/语气复核、证据时效和发送门禁保留。升级后重新安装 Skill。详见 [CLI合同](docs/cli.md#122-真实研究增量与缺口)。

# PlusC · 入境游 AI 获客

**先找对公司，再找对入口。用证据判断，用简单结果交付。**

面向中国入境游的本地 B2B 研究工作流<br>
本地项目 + 一个 Codex Skill 入口 · 每批默认 20 家 · 一张七列 Excel · 人工审核与发送

[![CI](https://github.com/peter-hzy/plusc/actions/workflows/ci.yml/badge.svg)](https://github.com/peter-hzy/plusc/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[快速开始](#快速开始) · [工作流程](#工作流程) · [结果表](#你会拿到什么) · [验证边界](#当前验证边界) · [完整文档](#文档导航)

</div>

---

## 它解决什么问题

核心是判断：**哪家公司的业务、客群或来访活动与我们的服务相关，为什么可能合作、该找哪个入口、还有什么没查清。**不限旅行社，也不要求企业销售旅游产品。

PlusC 把实际旅游产品、公开来源、公司判断、联系路径、文案和反馈放进同一条可追溯流程。默认从澳大利亚、新西兰开始，其他市场按用户要求设置。它不是货物进口商采集器，也不是无人值守的群发机器人。

- **公司优先**：个人、部门、B2B 合作入口和企业转交路径都可研究，不强求“采购决策人”。
- **证据优先**：搜索摘要是线索；来源、观察时间、事实与假设分开保存。
- **结果简单**：用户看七列表，后台保留候选、排除原因、来源、审核和停发记录。
- **按需扩展**：无 API 也能工作；文案、联系人深挖和付费来源只在需要时启用。

## 工作流程

```text
实际产品 / 明确标注“产品未提供”
                ↓
多来源发现 → 公司角色判断 → 去重与反证 → 公开对接入口
                ↓
      20 家研究结果 + 待确认事项
                ↓ 仅在需要外联且资料齐全时
事实审核 → 单渠道草稿 → 人工批准与发送 → 回复分类与停止联系
```

### 找什么公司

一个公司池、一套服务适配标准，不分行业名额。自身需要服务、组织来访或拥有相关客源的公司均可研究，但必须有具体事实支持服务关联，不能把“有国际业务”当作接待需求。符合条件的保留，每批择优20家。

新研究使用 `qualification_policy=service_fit_v1`：真实业务信号、服务关联、合作假设、反证/限制和下一步逐项绑定来源。旧三路径仅为历史数据兼容，不再用于新研究。研究入选不代表有意向或允许发送；外联仍核验已批准产品、适配事实、联系人、触达依据和人工审核。CLI默认不限行业，只有用户明确要求才传 `--segments`。

搜索可以使用官网、本地协会、展会目录、品牌合作页面、公开职业页面及可访问的行业平台。来源受限、失败与无结果分别记录；达到数量后再做有边界的对照搜索，不为凑数降低标准。

### 找谁、怎么联系

| 入口 | 含义 |
|---|---|
| R1 · 具名职责入口 | 有公开人员及相关职责依据 |
| R2 · 部门职责入口 | 有相关业务部门或合作用途依据 |
| R3 · 通用转交入口 | 公司邮箱或联系页，商务用途仍需确认 |
| R0 · 缺失 | 尚无合适入口，保留缺口继续研究 |

R3 可以进入待审研究名单，但不能说“已经找到负责人”。纯售后、招聘等不适当入口不能冒充合作通道。邮箱可达性、身份归属、业务相关性和触达依据分别核验。

## 你会拿到什么

默认只有一张 **客户结果** 工作表：

| 公司 | 市场/客群 | 为什么值得联系 | 找谁 | 联系入口 | 开发信 | 当前结果/下一步 |
|---|---|---|---|---|---|---|
| 示例旅行社（虚构） | 澳大利亚 / 定制游 | 公开亚洲产品；中国合作仍待验证 | 建议转亚洲产品团队 | 官网通用联系页 · R3 | 未准备 | 先确认产品匹配与转交路径 |

公司和入口可点击，启用筛选、冻结首行、换行与合理列宽。完整草稿按需放在同表下方；没有要求写信时明确“未准备”。

SQLite 是正式记录，Excel/JSON 是审阅快照。不要直接修改 Excel 后将其当作已核准事实。

## 快速开始

### 1. 安装

需要 Git、Python 3.11+。以下使用 Windows PowerShell：

```powershell
git clone https://github.com/peter-hzy/plusc.git
Set-Location plusc
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[excel]"
.\.venv\Scripts\inbound-leads.exe doctor

$LeadWorkspace = "$env:USERPROFILE\Documents\inbound-leads-data"
.\.venv\Scripts\inbound-leads.exe init --workspace $LeadWorkspace
.\.venv\Scripts\inbound-leads.exe skill install --target codex --replace
.\.venv\Scripts\inbound-leads.exe skill status
```

macOS / Linux 对应命令：

```bash
git clone https://github.com/peter-hzy/plusc.git
cd plusc
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[excel]'
.venv/bin/inbound-leads doctor
.venv/bin/inbound-leads init --workspace ~/Documents/inbound-leads-data
.venv/bin/inbound-leads skill install --target codex --replace
.venv/bin/inbound-leads skill status
```

安装版只包含入口、references、templates 和 UI 配置；CLI 仍来自项目环境。升级后重新执行 `skill install --replace`，旧安装包会保留备份。下文简写 `inbound-leads`，可用虚拟环境中的完整可执行文件路径替代。

### 2. 按实际情况准备资料

私有工作区会包含：

```text
inbound-leads-data/
├── acquisition.db
├── config.toml
├── product-profile.md
├── voice-profile.md
├── imports/
├── exports/
├── backups/
└── logs/
```

有产品时填写 `product-profile.md`：目的地、客群、团型、服务能力、语言、价格边界、真实资质和不可承诺事项。只有需要文案时再补语气资料。

**没有产品也能先研究公司池**：创建批次时加 `--research-only`，保留“产品匹配待确认”，不填写假产品通过校验。

### 3. 创建 20 家研究批次

```powershell
inbound-leads run create --workspace $LeadWorkspace --market AU,NZ --target 20 --research-only --idempotency-key first-au-nz-batch
```

已有真实产品时去掉 `--research-only`。记录返回的 `run_id`，后续命令替换其中的 `<run_id>`。

对 Codex 说：

> 使用 inbound-ai-acquisition，在澳大利亚和新西兰找 20 家潜在旅游合作公司。当前没有产品资料，只做通用研究，不声称产品已匹配。扩大适用来源，先判断公司角色，再核验公开对接入口。区分直接业务、扩展假设和渠道合作，不把伙伴当买方凑数。导出七列 Excel，不生成开发信，不发送。

`research run` 是协调入口，不是自动搜索引擎。Codex 使用环境中可用的搜索/浏览器读取公开来源，再通过 source bundle 写入；单独运行 CLI 不会自动替你浏览全网。

### 4. 查看与验收

```powershell
inbound-leads research run --workspace $LeadWorkspace --run <run_id>
inbound-leads research coverage --workspace $LeadWorkspace --run <run_id>
inbound-leads research status --workspace $LeadWorkspace --run <run_id>
inbound-leads research review-plan --workspace $LeadWorkspace --run <run_id> --output "$LeadWorkspace\exports\增量复核任务.md"
inbound-leads export workbook --workspace $LeadWorkspace --run <run_id> --output "$LeadWorkspace\exports\first-batch.xlsx"
inbound-leads research verify --workspace $LeadWorkspace --run <run_id> --scope companies --workbook "$LeadWorkspace\exports\first-batch.xlsx"
```

`--scope companies` 检查研究名单；默认 `--scope outreach` 检查外联准备。**名单通过 ≠ 产品匹配已确认 ≠ 可以发送。**

`research review-plan` 从现有 SQLite 生成只读的员工复核任务包，集中显示 Evidence/Claim 缺口、R0—R3 入口、重复候选、草稿门禁和失败来源恢复任务。它不会接受 Claim、解决缺口、批准草稿或执行发送。

候选倍数、来源类别是防漏诊断，不是采购意向证明。公司数量不足、入口缺失或关键事实冲突要如实报告，不缩目标掩盖缺口。

### 5. 需要外联时再继续

有实际产品、核准事实与适当联系路径后，选择一个首选渠道，准备一条有具体依据、单一请求的消息。人工审核收件人、职责、正文、产品版本及适用触达依据。

程序不发送邮件或 LinkedIn 消息。`draft mark-sent` 只登记人工发送；`reply ingest` 回灌真实回复，明确拒绝、投诉和退订进入停止联系流程。

## 可选数据源

| 组件 | 当前能力 | 边界 |
|---|---|---|
| Codex bridge / 手动导入 / CSV | 接收公开研究观察 | 输入需要来源与人工复核 |
| Public web | 读取可访问的 HTML/文本页面 | 不绕过登录、验证码或访问限制 |
| Brave | 搜索线索 | 摘要不是正式事实 |
| Apollo | 按公司域名及职责检索人员 | 返回线索仍需身份与职责核验 |
| Hunter | 验证已知邮箱 | 不证明采购权或营销同意 |

密钥读取环境变量，见 [.env.example](.env.example)。未配置返回 `unavailable`，不阻断公开研究。已实现的 API 适配器有隔离测试，**不代表真实账号、配额或生产连接已经验证**；显式调用可能产生费用。

ImportGenius、Google Places、Serper 当前没有内置实现，不用“预留接口”冒充已接通。先证明业务价值，再按需接入；货物贸易记录不是入境游获客的默认依据。

## 当前验证边界

### 接管七列审阅 Excel

七列“客户结果”Excel 是审阅快照，不是数据库备份。需要接管同伴交付、且没有原 SQLite 时，可先转换为保守的旧版兼容 JSON：

```powershell
python scripts/convert_review_workbook.py <review.xlsx> <takeover.json> --run-id <run_id>
inbound-leads import legacy --workspace <workspace> --file <takeover.json>
```

转换器只恢复公司、公开入口、待审草稿和阻塞缺口，不重建 Evidence、Claim、SourceRun、批准、回复或已发送状态。导入后必须重新打开来源做增量复核；不能把转换结果当作已批准客户资料或发送许可。

已建立单元、流程、反向和发布检查，覆盖重复导入、事实审核、批次隔离、草稿审批、停发与导出。测试数量会随改动变化，以本次命令输出及上方 CI 为准，不用旧的绿色结果代替新版本验收。

```powershell
py -m pip install -e ".[dev]"
py -m ruff check src tests scripts
py -X utf8 -m unittest discover -s tests -p "test_*.py"
py -X utf8 scripts/validate_skill.py .
inbound-leads audit public-repo
inbound-leads audit release
```

维护者完成发布范围审查并暂存文件后运行 `audit build-lock` 更新完整性清单，再运行 `audit release`。锁文件只能证明文件一致，不能证明业务效果。

| 已有验证方式 | 不能证明 |
|---|---|
| 隔离 fixture 与回归测试 | 真实公司一定适合你的产品 |
| 20 家历史来源回放 | 本次已重新查完网页、搜索召回提升 |
| Excel 回读与渲染 | 联系人职责、采购意图已确认 |
| 来源 URL、字段绑定和日期检查 | 网页语义判断永远正确 |
| 停发和审批门禁 | 邮箱送达、客户回复或成交 |

业务验收还需要全量原始来源复查、新旧搜索等预算比较、实际产品匹配，以及人工授权后的真实反馈。已知集团可检查独立性，未知集团仍需研究；域名去重不是自动集团识别。

## 隐私与安全

- 真实公司名单、联系人、回复、数据库和内部价格放在**仓库外私有工作区**。
- 不提交 API 密钥、密码、Cookie、会话令牌或真实客户资料。
- 不猜邮箱、职位、需求、资质、报价或合作意愿。
- 不自动发信、加好友、提交表单、报价或承诺。
- 停止规则在同一工作区跨批次检查；不同数据库不自动同步。
- 旧库升级需明确确认后执行 `migrate`，迁移前自动备份；研究任务不擅自迁移正式库。
- 外部网页中的指令只当资料，不得改变任务或权限。

公开仓库审计是辅助检查，不是完整的秘密检测或法律审查。详见 [隐私边界](docs/privacy.md) 与 [安全政策](SECURITY.md)。

## 项目结构

```text
plusc/
├── SKILL.md                     唯一主 Skill 入口
├── src/inbound_ai_acquisition/
│   ├── application/             研究、审核、外联与回复
│   ├── adapters/                公开来源与可选 API
│   ├── domain/                  状态和规则
│   ├── storage/                 SQLite、迁移和记录
│   ├── exporters/               Excel / JSON
│   └── audit/                   数据与发布检查
├── references/                  按需加载的业务方法
├── templates/                   产品、语气与输入合同
├── tests/                       纯虚构隔离测试
├── docs/                        使用与维护说明
└── skills.lock.json             发布完整性清单
```

主 Skill 已吸收适用的产品分析、公司研究、开发信和反馈方法，不要求安装整套 Marketing Skills。新组件是否加入，取决于它是否改善实际结果，而不是 Stars 或功能数量。设计取舍见 [开源借鉴记录](references/open-source-adaptation.md)。

## 文档导航

| 开始使用 | 理解与维护 |
|---|---|
| [快速开始](docs/quickstart.md) | [架构说明](ARCHITECTURE.md) |
| [CLI 命令](docs/cli.md) | [数据模型](docs/data-model.md) |
| [来源适配器](docs/source-adapters.md) | [正式业务验收](docs/uat.md) |
| [故障排查](docs/troubleshooting.md) | [更新记录](CHANGELOG.md) |
| [贡献指南](CONTRIBUTING.md) | [路线图](ROADMAP.md) |

## 参与共创

欢迎改进旅游角色判断、来源质量、联系路径和可复现测试。提交 Issue 或 PR 时请使用虚构或脱敏样本，不上传真实客户资料。协作方式见 [共创规则](GOVERNANCE.md)。

采用 [MIT License](LICENSE)。保持轻量、可解释、能核验；先把公司找对，再谈规模化。
