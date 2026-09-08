# CLI 命令

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
