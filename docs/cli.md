# CLI 命令

## 旅游公司研究与外联分开验收

- 每批默认20家公司。无真实产品且用户要求通用研究时，`run create --research-only` 保留空产品版本；不得伪造产品资料。
- 普通`run create`需要产品卡，不要求语气卡；语气卡在准备文案时补齐。
- `research verify --scope companies --workbook ...`检查公司数量、证据、公开对接入口和单表7列输出；不要求具名联系人、个人邮箱或草稿。缺入口保留公司，但交付验收不通过。
- 默认`--scope outreach`继续使用事实批准、草稿与渠道门禁。名单检查通过不代表产品匹配已核准或可发送。
- schema v5将联系人邮箱/LinkedIn唯一约束限定于同一公司快照，允许跨批次重新研究；同一工作区的停止联系检查仍跨批次生效。正式旧库需用户确认后运行`migrate --workspace ...`，迁移自动备份；不同工作区不共享停发记录。

所有处理真实数据的命令都要求 `--workspace` 指向仓库外私有目录。

```text
doctor [--workspace]
init --workspace
migrate --workspace
backup --workspace [--output]
context validate --workspace
run create|status|close
research run|status|coverage|verify
import companies|contacts|evidence|legacy|review
source list|status|record
company list|show
contact list|show
claim propose|list|accept|hold|reject
dedupe scan|review
draft create|check|approve|mark-sent|stop
reply ingest
stop add|list|release
export workbook|json
audit workspace|public-repo|build-lock|release
skill install|status
```

`run create` 的发现基线可按批次调整：

- `--candidate-pool-multiplier`：候选池相对正式目标的倍数，默认 3。
- `--min-source-categories`：互补来源类别基线，默认 3。
- `--production-min-target`：可称为正式批次的最小公司数，默认 20。

这些是防漏和验收参数，不是客户类型配额。`research run` 可在同一 run 中多次传入新的 source bundle，已发现候选会按根域名优先去重并追加来源。

写命令返回 JSON，包含 `request_id`、`status`、`changed_records`、`next_action` 和 `errors`。回复回灌和批次创建支持幂等键；相同键加相同输入返回 `already_applied`，不同输入会明确失败。

`import review` 当前只输出变更预览，不自动覆盖数据库。`draft mark-sent` 不发送消息，只登记人工已经完成的发送。
# v1.2 新增与变更

`source list --workspace <path>` 显示配置是否存在和能力，绝不打印密钥；configured不代表实际连接通过。

`source execute --workspace <path> --adapter brave --operation discover --file query.json` 显式联网执行。Brave输入为{"query":"Australia China tailor made tour operators"}。Apollo inspect_contact输入为{"domain":"company.example","titles":["Product Manager"]}；Hunter inspect_contact输入为{"email":"verified-public-business-address"}。这些示意值不能当作真实客户。

密钥来自BRAVE_SEARCH_API_KEY、APOLLO_API_KEY、HUNTER_API_KEY环境变量。无Key返回unavailable；限额返回rate_limited；不自动重复收费查询。来源输出仍是待核验观察，不自动写成客户事实。先检查已有source_runs/候选和查询指纹，在同一run补搜；有配置不等于授权任何收费调用。

`draft create`的JSON可带outreach_contract，字段见references/outreach-protocol.md；`draft approve`要求完整合同。consent记录basis（express/inferred/deemed）、market、source_reference、reason、reviewed_by、带时区的valid_until。开发信还必须提供product_version及产品和事实复核人，不能用假审核人填满字段。

`export workbook`默认单表7列；`export json --run`只导出关联该批次实体，原始混批导入不随批次输出。完整工作区备份仍可另行执行。

`skill install --replace`会保留旧安装包至同级.inbound-acquisition-backups目录；status同时检查非发布清单的残留文件。旧tests/scripts不再混进新的轻量Skill包，运行测试使用源项目tests。
