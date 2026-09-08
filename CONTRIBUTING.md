# 参与共创

感谢你愿意一起改进 PlusC。这是一个面向中国入境游 B2B 的实用项目，当前优先把“找对公司、找对人、保存证据、生成可审核话术”做稳，不追求无人值守群发。

## 从哪里开始

1. 先阅读 [README](README.md)、[路线图](ROADMAP.md) 和 [架构](ARCHITECTURE.md)。
2. 从 Issue 中选择一个边界清楚的任务，或先提交提案。
3. 小步提交 PR；一个 PR 只解决一个主要问题。

适合共创的方向：海外买家研究方法、公开来源适配器、联系人身份核验、Excel 审阅体验、话术评审、回复复盘、测试和中英文文档。

## 本地开发

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
.\.venv\Scripts\python.exe -X utf8 scripts\validate_skill.py .
.\.venv\Scripts\inbound-leads.exe audit public-repo
.\.venv\Scripts\inbound-leads.exe audit release
```

## 必须遵守的边界

- 不提交真实客户名单、联系方式、回复、内部价格、Cookie、密钥或会话信息。
- 不引入自动群发、猜邮箱、模拟登录、绕过平台限制或伪造 Evidence。
- 新增适配器必须区分“无结果”、“受限”和“失败”，并覆盖成功与失败测试。
- 新规则必须说明真实业务风险，不把单次特例写成永久硬限制。

## PR 验收

PR 说明应包含：解决的问题、主要改动、验证结果、数据/权限风险和未完成项。功能改动要有可观察测试，不接受只检查文案关键字的“测试”。

维护者会检查业务价值、数据真实性、权限边界、向后兼容和维护成本。评审不是对人的否定，所有参与者请保持尊重、具体和可验证的沟通。
