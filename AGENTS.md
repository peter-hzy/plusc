# AI获客项目

- Python 3.11+、SQLite、标准库；Excel可选openpyxl。CLI入口：`python -m inbound_ai_acquisition.cli`。
- 安装与升级按README；运行数据放workspace/outputs，不加入Git。
- src存实现，tests存隔离测试，references/templates存安装Skill合同。项目根SKILL.md是源，安装版通过CLI同步。
- 新研究统一公司池service_fit_v1，不设行业配额；旧合同仅历史兼容。假设、来源事实、人工决定分开记录。
- 事实/语气复核、产品绑定、证据时效、身份、触达依据、停发和审批快照不可绕过；不自动发送或报价。
- 验证：`python -m unittest discover -s tests -p "test_*.py"`、`python -m ruff check src tests`、`python scripts/validate_skill.py .`。
- 发布先暂存明确范围，重建audit build-lock，通过audit public-repo和audit release，再同步安装版、提交和推送原分支。
- 1.2.2修复说明在CHANGELOG和references/data-contract.md；真实20家已研究及导出，产品能力、采购需求和转化仍待核准，不能把来源回放解释为新搜索或真实外联。
