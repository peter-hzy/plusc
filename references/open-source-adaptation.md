# 开源项目借鉴与取舍

## 2026-09-19 统一公司池

保持一个完整本地项目和一个Skill入口，不安装重复框架。吸收客户研究的真实场景/现有安排、产品营销的适配/排除与合作阻力、合作营销的互补价值；新研究不再按旅游销售身份或三路径划分准入。代码检查证据绑定与状态，业务判断仍需逐家公司阅读原文。以下是历史取舍记录，不恢复旧客户范围。

## 2026-09-17 实际整合决定

已比较16个不同获客/研究仓库，并核对coreyhaines31/marketingskills（MIT，检查提交5b2c0007766c6a1cf1d53fd8fc73e979e0821022）及本机安装来源。详细业务评估留在本地私有记录，不随公开仓库发布；本文件保留可复用的方法取舍，运行时无需加载整份报告。

本轮独立编写旅游化规则，不复制第三方实现或安装重复Skill：

- product-marketing：实际产品→目标公司与排除条件，融入business-context；不用软件README推断旅游产品，不另建冲突的全局产品文档。
- prospecting：查询矩阵、多来源、证据化筛选，融入research-protocol；拒绝默认25家、热度比例配额、强制决策人和邮箱才入选。
- cold-email：相关观察→已确认能力→单一请求，融入outreach-protocol；不借模板案例或默认3—5封跟进。
- OpenOutFind：借鉴重复/空结果/失败分离和不足时继续发现原则，不引入人员采购和概率模型。
- landermixer：认可公司/部门公开入口和按缺口研究，不移植融资/流量等无关字段。
- 内容、社媒、视频、竞争分析和客户反馈按任务启用现有能力，不成为找20家的固定十步，也不建立多Agent销售团队。

代码负责数据与验收；Skills不是搜索引擎/API授权。Crawl4AI/Firecrawl仍是可选读取组件，尚未证明现有工具不足，所以不增加依赖。采用第三方代码必须另核许可证与NOTICE；高Stars不是直接采用标准。以下旧记录说明历史取舍，不改变最新20家公司与公司入口优先的约束。

复核日期：2026-09-04。以下链接与结构用于设计对照，不代表对第三方项目质量或数据合规作背书。

本项目只借鉴公开项目中可验证的流程思想，不复制代码、品牌、私有数据或宣传结果；每次采用前应检查许可证、当前版本和本地测试结果。

| 项目 | 借鉴 | 不直接采用 |
|---|---|---|
| [LeadMagic/gtm-skills](https://github.com/LeadMagic/gtm-skills) | GTM 任务分层、联系人核验、社交意图、输出检查器 | 不照搬其数据源、发送逻辑或结论 |
| [ai-sales-team-claude](https://github.com/zubair-trabzada/ai-sales-team-claude) | 公司研究、联系人、外联、回复、提案的职责拆分 | 不把 BANT/MEDDIC 变成前期硬门槛 |
| [linkedin_skills](https://github.com/xx254/linkedin_skills) | 语气校准、线索登记、回复分类、复盘 | 不自动加人、私信或模拟登录 |
| [KeeLead](https://github.com/Atum246/keelead) | 自托管研究、联系方式核验、来源适配、MCP 边界 | 不默认其数据质量、合规或可直接生产 |
| [profilespider-agent-skills](https://github.com/spiralcrew-ou/profilespider-agent-skills) | 输入/输出合同、清洗和结构化思路 | 不将公开简介等同于采购意愿 |
| [trycompai/crm](https://github.com/trycompai/crm) | Evidence、任务队列、研究和复查理念 | 第一阶段不引入 CRM 或复杂系统 |

适配原则：入境游的关键不是“多发”，而是目的地、团组/定制能力、采购负责人、旅行季节、RFP 和履约边界。任何通用销售模板都必须经过这些业务事实过滤。

## 仓库结构对照后的决定

- `trycompai/crm` 的 `apps/packages/docs/adrs/.github` 适合多服务CRM；本项目只有本地CLI，因此保留 `src/docs/tests/.github`，不复制Monorepo。
- `LeadMagic/gtm-skills` 强调每个Skill有明确产物和质量检查；本项目采用一个主Skill、按需references、确定性测试和发布锁，避免205个入口带来的选择负担。
- `ai-sales-team-claude` 用多个Skill和Agent覆盖销售全链；本项目只采用职责分离，不采用固定BANT/MEDDIC和连续触达。
- `KeeLead` 展示了UI、MCP和大量来源插件的扩展方向；V1只保留来源合同和注册表，避免“目录存在但实现是占位符”的假完整。
- 成熟公开仓库常见的 README、LICENSE、CHANGELOG、CONTRIBUTING、SECURITY、环境变量示例、CI和测试均应具备；真实数据和运行数据库不进入仓库。

## 源码级复核后的采用与拒绝

- `LeadMagic/gtm-skills`：采用来源计划、查询词族、独有贡献、重叠和覆盖缺口的思路；不把文档型检查器当成真实数据质量验证。
- `profilespider-agent-skills`：采用“每条输入有明确去向”和研究缺口合同；其主体是方法文档，不能替代真实来源执行。
- `linkedin_skills`：采用持久线索登记、去重、触达历史和基于真实回复的复盘；它依赖外部 CSV，不承担广泛找名单，因此只能放在发现之后。
- `ai-sales-team-claude`：拒绝关闭 TLS 校验、估算邮箱和默认多封连续触达；保留公司研究、联系人研究和渠道话术分工。
- `KeeLead`：只采用适配器注册、任务状态和 MCP 外壳。其部分 lead、research 和 source 实现会随机生成公司资料、联系人、邮箱、电话或验证状态，严禁进入本项目的数据层。
- `trycompai/crm`：采用“候选不是证明”、弱证据进入人工判断、任务可重试及 `WAITING_FOR_APPROVAL` 的设计；不引入完整 CRM、Postgres、前后端 Monorepo 和持续运行 Agent。

本项目因此保留轻量 CLI + SQLite，但新增完整 CandidatePool、SourcePlan、CandidateSources 和覆盖诊断。发现能力可以继续增加真实适配器，任何来源在没有真实执行和负向测试前不得宣传为“已支持”。

## 任何新增来源的准入条件

1. 有清楚的授权方式、限制和费用；
2. 返回来源URL、观察时间和明确运行结果；
3. 受限、失败与无结果分开；
4. 不生成或猜测身份信息；
5. 没有该来源时核心流程仍能运行；
6. 有合同测试、负向测试和日志脱敏检查。
