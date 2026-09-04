# 故障排查

- `工作区未初始化`：先运行 `inbound-leads init --workspace <目录>`。
- `Excel依赖缺失`：运行 `python -m pip install -e ".[excel]"`。
- `idempotency_conflict`：不要复用旧幂等键提交不同内容。
- `联系人身份未核验`：补负责人职责证据，将状态设为 supported 或 verified。
- `缺少已接受的联系依据`：先创建 Claim、绑定 Evidence，再由人工接受。
- `命中停止联系规则`：不要继续触达；只有人工给出理由后才能执行 `stop release`。
- 来源返回 `restricted`：记录限制并换合法来源，不绕过登录、验证码或平台限制。

