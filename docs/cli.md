# CLI 命令

## 公司研究与外联分开验收

- 每批默认20家公司。无真实产品且用户要求通用研究时，`run create --research-only` 保留空产品版本；不得伪造产品资料。
- 普通`run create`需要产品卡，不要求语气卡；语气卡在准备文案时补齐。
- `--segments`默认`*`（不限行业）；仅用户明确限定时填写具体行业。新source bundle公司使用`qualification_policy=service_fit_v1`，必填字段和逐字段来源绑定见references/data-contract.md；无标记历史数据仅按旧规则兼容，不自动重判。
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

## 1.2.1 审核与回复门槛

新研究统一使用 `service_fit_v1`；`research run` 返回的执行请求和 `research verify --scope outreach` 均使用同一合同，历史无标记数据保留旧合同。

草稿 `outreach_contract` 必须显式记录 `fact_check_status`、`voice_check_status`（`needs_review` / `pending` / `passed` / `failed`），及 `fact_checked_by`、`voice_checked_by`。未通过的草稿保存为 `draft`；只有两个状态均为 `passed` 才进入 `review_ready`，批准仍检查复核人、产品、身份、证据和触达依据。顶层状态可兼容输入，但与合同冲突时拒绝，不再忽略 `failed`。已保存的 `draft` 可重交同一 draft bundle，只更新这四个复核字段；正文、引用、收件目标或已批准草稿的变更仍需重建。状态是人工复核记录，不能由系统替人声称完成检查。

批准和发送登记均要求联系人最近30天核验、引用的公司证据最近90天/联系人证据最近30天，适配字段也须有近90天已接受且可访问、无冲突的来源。日期缺失、无时区、未来或超期均阻止外联。过期时实际重新打开来源，提交带真实 `observed_at` 的增量 source bundle，人工接受新 Claim 后重建草稿；不能只改日期冒充复核。接受身份 Claim 时以其来源观察日期更新 `last_verified_at`。

回复至少提供可定位的 `source_reference` 或 `raw_text`。原文保存在已有 `raw_imports`，仅原文输入会生成内部引用；全量备份及所属批次 JSON 可回读该回复原文，不导出其他批次原文。重复导入仍幂等。Excel 七列结构保持，结果列优先显示各联系人的最新回复、确认/未知需求、下一步与接管/停发状态。

`wrong_person`、`not_fit` 停止当前联系人及等价身份的后续触达，不将整家公司标记不可联系；需人工核实新角色或按既有 stop release 流程解除。报价、价格、合同、投诉等继续转人工。系统没有自动发送、报价、CRM或成交跟踪闭环。

## 1.2.2 真实研究增量与缺口

research run --source-bundle支持公司/contact的research_gaps与顶层source_attempts，具体字段见references/data-contract.md。影响批准的产品未知项用open/blocking缺口；不能把其省略或标false来解除阻塞。名单verify会显式提示关键公司缺口，外联门禁保留。

同一公开转交入口补邮箱优先复用已有联系人；匹配明确地址优先于旧空入口，冲突或不同部门不自动合并。原历史记录保留。Excel没有正式草稿时优先展示可用入口，正式草稿仍展示其原目标，中文长限制使用保守行高。

source_attempts只记录未取得有效观察的真实执行，并需要实际带时区时间；失败不能生成Evidence或Claim。research status返回source_outcomes；export json可回读失败记录。重放不重复同一历史失败，正常研究执行日志仍逐次增加。内部文案提案仍与正式草稿分开，proposed事实不会自动获批。
