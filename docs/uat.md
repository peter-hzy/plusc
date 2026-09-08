# 正式验收

## 五家公司只读前向测试

- 从全新仓库外 workspace 发起，不使用示例、fixture 或预写公司名单；
- 先主动发现超过五家候选，再按证据和匹配度保留五家；
- 使用未预先写答案的真实请求；
- 每家公司有归属当前 run 的 SourceRun、打开真实网页后形成的 Evidence、fit_reason 和 fit_status；
- 联系人标为 verified、supported、not_found 或 contradicted；
- 整批 proposed Claim 只暂停一次由真人审核，禁止用虚构 actor 绕过；
- 草稿可追溯到 Evidence 和已接受 Claim；
- 每家公司分别有 Email 和 LinkedIn 原生草稿，每条恰好一个 CTA；
- `LeadReview` 首页可直接查看联系理由、负责人、渠道、证据、缺口、两种草稿和下一步；
- `research verify`、自动测试和 `PRAGMA integrity_check` 全部通过；
- 不发送消息，不把真实数据提交到仓库。

## 20—25家公司真实UAT

- 澳大利亚、新西兰优先；
- 核对去重、来源失败、联系人身份和话术自然度；
- 人工记录改稿原因；
- 由人工发送和回灌真实回复；
- 验证退订、投诉、重复回复和审批失效；
- 完成来源、联系人、话术和流程复盘。

只有全新目录克隆安装、全部自动测试、公开仓库审计、Skill同步和本节真实UAT都通过后，才可以宣称达到正式生产验收。
