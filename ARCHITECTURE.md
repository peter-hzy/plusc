# 架构

## 主链路

```text
Codex / Research Orchestrator
  → Source Execution（discover / inspect_company / inspect_contact）
  → inbound-leads CLI / application 用例
  → domain 业务门禁
  → SQLite 唯一事实库
  → Excel / JSON 只读导出
```

## 为什么这样分

- `SKILL.md` 负责任务编排和研究判断，不存正式客户数据。
- `adapters/` 负责来源执行并返回明确的成功、无结果、受限或失败状态。V1 中 `codex_bridge` 接收 Codex 已打开公开页面后形成的观察；`public_web` 没有配置执行器时返回 `not_configured`，不制造结果；`directory_csv` 只读取明确提供的目录文件。
- `source_plan_entries`、`candidates` 和 `candidate_sources` 保存发现计划、完整候选池及多来源关系。未入选候选不会再只藏在事件 JSON 中。
- `application.discovery` 专门计算候选池、来源独有/重叠贡献和补搜提醒。候选池倍数、最少来源类别和正式批次基线保存在 run 中，不再写死在验收代码里。
- 同一 run 允许多轮增量发现；候选优先按根域名去重并保留多来源。不同 run 可以重新研究同一公司，因为当前是批次研究工具，不是 CRM 主档。
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

草稿进入 `review_ready` 前必须有已核验联系人、至少一个已接受 Claim、没有阻塞缺口且未命中停止规则。批准保存正文哈希；正文变化后必须重新批准。系统没有发送实现，`mark-sent` 只是人工发送后的记录。

## 明确不做

V1 不建设 CRM、Web UI、Postgres、多租户、无人值守调度、自动邮件发送、LinkedIn 自动化、自动报价或多 Agent 销售团队。
