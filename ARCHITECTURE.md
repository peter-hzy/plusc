# 架构

## 主链路

```text
Codex 主 Skill
  → inbound-leads CLI
  → application 用例
  → domain 业务门禁
  → SQLite 唯一事实库
  → Excel / JSON 只读导出
```

## 为什么这样分

- `SKILL.md` 决定何时研究、核验、起草或处理回复，不存正式客户数据。
- `domain/` 保存不会因为界面变化而改变的规则，例如“不猜邮箱”和草稿状态迁移。
- `application/` 把一个动作需要的多次数据库修改放进同一事务。
- `storage/` 负责连接、迁移、幂等和事件，不让业务模块各自管理数据库。
- `adapters/` 只返回来源观察和明确结果，不直接决定客户是否合适。
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

