# Contributing

提交前请确保改动符合入境游 B2B 范围，不引入自动群发、猜邮箱、模拟登录或真实客户数据。

```powershell
py -3.11 -m pip install -e ".[dev]"
ruff check src tests
py -3.11 -m unittest discover -s tests -p "test_*.py" -v
python -X utf8 scripts/validate_skill.py .
python -X utf8 scripts/three_pass_check.py
inbound-leads audit public-repo
```

新增来源适配器必须返回统一结果，区分无结果、受限和失败，并覆盖至少一个成功与一个失败测试。新增业务规则应说明它解决的真实风险，避免把一次特例变成所有任务的永久限制。
