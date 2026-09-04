# Inbound AI Acquisition

面向中国入境游 B2B 业务的证据驱动型 AI 获客项目。一个主 Codex Skill 配合本地命令行，把“找公司、找负责人、核验证据、写邮件和 LinkedIn 草稿、人工联系、记录回复”串成可追溯流程。

它不是 CRM，也不会自动发送邮件、自动操作 LinkedIn、猜邮箱或替业务人员报价。

## 当前能力

- 澳大利亚、新西兰优先，同时支持美国、加拿大；
- 旅行社、DMC、旅游批发商优先，预留企业差旅与 MICE；
- 每批默认 20—25 家公司；
- SQLite 保存唯一正式数据，Excel 只用于人工审阅；
- 公司、联系人、来源运行、Evidence、Claim、研究缺口分别保存；
- 公司域名、LinkedIn、公开邮箱的确定性去重；
- 邮件与 LinkedIn 分别起草，每条只保留一个轻量 CTA；
- 草稿批准后若正文改变，批准自动失效；
- 回复幂等回灌，退订和投诉会停止相关待发草稿；
- 所有关键写操作进入事件账本；
- 无付费 API 也能完成导入、审核、草稿、回复和 Excel 导出。

## 五分钟开始

需要 Python 3.11 或更高版本。

### Windows

```powershell
git clone https://github.com/peter-hzy/inbound-ai-acquisition.git
Set-Location inbound-ai-acquisition
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[excel]"
.\.venv\Scripts\inbound-leads.exe doctor
.\.venv\Scripts\inbound-leads.exe init --workspace D:\inbound-leads-data
```

也可以运行：

```powershell
.\scripts\bootstrap.ps1 -Workspace D:\inbound-leads-data
```

### macOS / Linux

```bash
git clone https://github.com/peter-hzy/inbound-ai-acquisition.git
cd inbound-ai-acquisition
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[excel]'
.venv/bin/inbound-leads doctor
.venv/bin/inbound-leads init --workspace "$HOME/inbound-leads-data"
```

## 创建第一批任务

先填写工作区里的 `product-profile.md` 和 `voice-profile.md`，再运行：

```powershell
inbound-leads context validate --workspace D:\inbound-leads-data
inbound-leads run create `
  --workspace D:\inbound-leads-data `
  --market AU,NZ `
  --segments travel_agency,dmc,tour_operator `
  --target 20 `
  --idempotency-key first-au-nz-batch
```

把已有公司保存成 UTF-8 CSV 或 JSON。JSON 示例：

```json
[
  {
    "name": "Example Travel",
    "country": "AU",
    "segment": "travel_agency",
    "website": "https://example.test",
    "fit_reason": "公开经营亚洲定制线路"
  }
]
```

导入并导出审阅表：

```powershell
inbound-leads import companies --workspace D:\inbound-leads-data --run <run_id> --file companies.json
inbound-leads run status --workspace D:\inbound-leads-data --run <run_id>
inbound-leads export workbook --workspace D:\inbound-leads-data --run <run_id> --output D:\inbound-leads-data\exports\batch.xlsx
```

Codex 中可以直接说：

```text
使用 inbound-ai-acquisition，研究这一批公司的业务匹配度、负责人、LinkedIn 和公开业务邮箱；保存来源和日期，分别生成邮件与 LinkedIn 草稿，不要发送。
```

## 一个主 Skill

仓库只提供一个用户入口 `inbound-ai-acquisition`。公司研究、负责人核验、外联、回复和复盘只是内部模式，不需要记忆多个子 Skill。

安装或同步：

```powershell
inbound-leads skill status
inbound-leads skill install --target codex --replace
```

## 安全边界

- 不自动发送邮件或 LinkedIn 消息；`mark-sent` 只记录人工已发送。
- 不使用密码、Cookie、会话令牌或模拟登录。
- 不猜联系人、职位、邮箱、需求、价格、资质、案例或佣金。
- 搜索摘要只用于发现；正式事实必须有原始页面 Evidence 支持。
- 退订、投诉和明确停止要求进入 StopRule。
- 真实客户数据、回复、密钥和内部价格只能放仓库外的私有工作区。

## 项目结构

```text
SKILL.md                 Codex 主入口
src/                     可安装 Python 包和 inbound-leads CLI
migrations/              数据库迁移标记
references/              业务研究、身份、外联和安全规则
templates/               产品、语气和导入模板
docs/                    使用与架构文档
scripts/                 启动、兼容和发布检查脚本
tests/                   单元、集成、安全和端到端测试
examples/                纯虚构示例
```

详细设计见 [ARCHITECTURE.md](ARCHITECTURE.md)，全部命令见 [docs/cli.md](docs/cli.md)，正式验收见 [docs/uat.md](docs/uat.md)。

## 开发和验证

```powershell
py -3.11 -m pip install -e ".[dev]"
ruff check src tests
py -3.11 -m unittest discover -s tests -p "test_*.py" -v
python -X utf8 scripts/validate_skill.py .
python -X utf8 scripts/three_pass_check.py
inbound-leads audit public-repo
inbound-leads audit build-lock
inbound-leads audit release
```

## 当前验证边界

自动化测试证明本地工作流、事务、幂等、停止规则、Excel回读和敏感文件检查可以按合同工作。它不能替代对真实公司和负责人的人工核验，也不代表真实获客转化率。项目通过五家公司只读前向测试和20—25家公司真实UAT后，才算业务验收完成。

## 开源与许可证

本项目使用 MIT License。开源借鉴记录见 [references/open-source-adaptation.md](references/open-source-adaptation.md)。只采用适合本项目的通用设计，不复制许可证不清晰的源码，也不引入随机生成Lead、猜邮箱、关闭TLS或静默吞错等做法。
