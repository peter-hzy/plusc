# 入境游 AI 获客 Skill

这是面向入境游 B2B 获客的 Codex Skill，不是 CRM，也不是自动群发工具。

它支持：

- 研究澳大利亚、新西兰、美国、加拿大的海外旅行社、DMC、旅游批发商；
- 后续扩展企业差旅、MICE、会展和活动策划公司；
- 记录公司、负责人、LinkedIn、公开业务邮箱和证据；
- 生成渠道原生的英文邮件和 LinkedIn 草稿；
- 解析回复、提取询盘、判断人工下一步并复盘。

## 原则

AI 负责研究、整理、起草和分类；人工负责审核、发送、聊天、报价、承诺和最终判断。默认不自动发送、不自动私信、不使用 Cookie 或密码，不把公开社交信号直接当成购买意愿。

## 目录

- `SKILL.md`：主 Skill 入口和闭环规则
- `references/`：业务、研究、数据、话术、回复、安全和 API/MCP 规则
- `templates/`：产品资料、语气、状态、名单和复盘模板
- `scripts/`：本地初始化与校验脚本
- `examples/`：虚构样本，仅用于理解格式
- `tests/`：标准库测试
- `AI获客项目方案.md`：本项目的方案基线

## 本地验证

在仓库根目录运行：

```powershell
python -X utf8 scripts/validate_skill.py .
python -X utf8 scripts/three_pass_check.py
python -m unittest discover -s tests -p "test_*.py"
python -X utf8 C:\Users\Lenovo\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

## 使用建议

先填 `templates/product-profile.template.md` 和 `templates/voice-profile.template.md`，再让 Skill 以 20—25 家为一批做真实研究。名单、联系人和回复数据不要直接提交到公开仓库。

