# CLI 命令

所有处理真实数据的命令都要求 `--workspace` 指向仓库外私有目录。

```text
doctor [--workspace]
init --workspace
migrate --workspace
backup --workspace [--output]
context validate --workspace
run create|status|close
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

写命令返回 JSON，包含 `request_id`、`status`、`changed_records`、`next_action` 和 `errors`。回复回灌和批次创建支持幂等键；相同键加相同输入返回 `already_applied`，不同输入会明确失败。

`import review` 当前只输出变更预览，不自动覆盖数据库。`draft mark-sent` 不发送消息，只登记人工已经完成的发送。
