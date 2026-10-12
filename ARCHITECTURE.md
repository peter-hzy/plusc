# 架构

## 主链路

```text
Codex / Research Orchestrator
  → Source Execution（discover / inspect_company / inspect_contact）
  → inbound-leads CLI / application 用例
  → domain 业务门禁
  → SQLite 唯一事实库
  → 单表Excel / 按批次实体关联过滤的JSON只读导出
```

## 为什么这样分

- `SKILL.md` 负责任务编排和研究判断，不存正式客户数据。
- `adapters/` 负责来源执行并返回明确的成功、无结果、受限或失败状态。`codex_bridge`接收Codex已读取公开页面后形成的观察；`public_web`可读取HTML/文本，但不提供搜索发现；`directory_csv`只读取明确提供的文件。Brave/Apollo/Hunter为显式调用的可选API，无密钥返回unavailable，不代替身份和事实审核。
- `source_plan_entries`、`candidates` 和 `candidate_sources` 保存发现计划、完整候选池及多来源关系。未入选候选不会再只藏在事件 JSON 中。
- `application.discovery` 专门计算候选池、来源独有/重叠贡献和补搜提醒。候选池倍数、最少来源类别和正式批次基线保存在 run 中，不再写死在验收代码里。
- 同一 run 允许多轮增量发现；候选优先按规范化主机名（移除www，非PSL注册域解析）去重并保留多来源。子域和跨域品牌需另查主体；已知group_key检查独立性，不自动识别全部集团。不同run可重新研究同一公司，因为当前是批次研究工具，不是CRM主档。
- `domain/` 保存不会因为界面变化而改变的规则，例如“不猜邮箱”和草稿状态迁移。
- `application/` 把一个动作需要的多次数据库修改放进同一事务。
- `storage/` 负责连接、迁移、幂等和事件，不让业务模块各自管理数据库。
- Source Adapter 只返回来源观察和明确结果，不直接决定客户是否合适；Evidence、Claim、联系人和草稿门禁仍由 application/domain 负责。
- `exporters/` 只读数据库；Excel 不是事实库。
- `audit/` 检查公开仓库、发布锁和数据完整性。

## 数据真实性

```text
SourceRun：这次查了什么，成功、无结果、受限还是失败
Evidence：网页实际看到什么
Claim：根据证据提出什么事实
Decision：人工接受、暂缓或拒绝
Company / Contact：已接受、可运营的正式字段
```

模型不能把自己的推断直接写成正式事实。公司和联系人使用不可变内部 ID；域名、LinkedIn、邮箱是可冲突、可退休的身份键。

## 外联安全

草稿进入 `review_ready` 前必须有已核验联系人、至少一个已接受 Claim、没有阻塞缺口且未命中停止规则。schema v4的draft_contracts保存收件地址归属、验证、职责、触达依据、附件与产品/文案复核；批准哈希绑定完整发送快照。旧草稿无合同不能批准，升级前自动备份。系统没有发送实现，`mark-sent` 只是人工发送后的记录。

## 明确不做

V1 不建设 CRM、Web UI、Postgres、多租户、无人值守调度、自动邮件发送、LinkedIn 自动化、自动报价或多 Agent 销售团队。
# 项目与Skill边界

这是完整的本地获客项目：Skill是AI操作入口；application/domain负责数据与规则校验，adapters承接真实来源，SQLite保存证据/状态，exporters输出结果。不新增CRM或并行客户库。新公司研究采用统一服务场景合同service_fit_v1，不限行业；旧三路径仅兼容历史记录。行业限制只有用户明确指定时生效。研究结论、事实审核和外联批准仍分开，规则校验不代替原文语义核验。
