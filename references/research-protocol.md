# 公司研究与证据协议

## 1. 目标

研究不是“搜到名字就进入名单”，而是把公开线索转成可以人工复核的公司、联系人和联系依据。澳大利亚、新西兰优先，美国、加拿大同步；默认每批 20—25 家。

研究必须做到：

- 多来源发现，不能只依赖 LinkedIn、Google 或单一目录；
- 先确认公司，再寻找联系人；
- 搜索摘要负责指路，打开后的原始页面负责证明；
- 公司有中国/亚洲业务与公司现在有采购意愿必须分开；
- 找不到、没搜索、受限和冲突都要记录，不能静默空白；
- 每条输入最终进入正式名单、待研究、培育、不匹配或停止联系状态。

## 2. 运行前建立来源计划

先根据国家、客户类型和产品场景规划来源，不要直接漫无目的搜索。来源计划至少包含：

- `source_category`：官网、协会、展会、行业目录、LinkedIn、招聘、媒体、社交内容等；
- `source_role`：用于发现还是用于验证；
- `target_signal`：希望从该来源确认什么；
- `query_or_entry_url`：查询词或入口地址；
- `coverage`：国家、细分客户和语言；
- `access_status`：未搜索、已打开、没找到、来源受限；
- `contribution`：新增公司、新增联系人、新增证据、只重复已有内容或无贡献。

旅游行业查询不能只使用 `travel agency`。根据任务组合：

```text
China tours / Asia tours / long-haul / tailor-made / custom tours
group travel / educational travel / special-interest travel
luxury / adventure / family / senior / culture / food travel
corporate travel / incentive travel / MICE / event agency
supplier / contracting / product manager / destination manager
```

还应关注新增中国线路、亚洲产品招聘、展会参展、目的地合作伙伴招募、团组产品上线等时间信号。

客户类型分布是覆盖诊断，不是固定配额。正式目标为 20—25 家时，默认防漏基线是目标 3 倍的独立候选和 3 类互补来源，但应按市场规模在创建 run 时调整。如果某类优质公司很少，记录缺口并调整下一轮搜索，不能用弱公司凑数量。每个来源要统计候选数、独有候选、重叠候选和最终入选数。

未入选候选也必须进入 `CandidatePool`，并标明 `candidate_pool`、`held` 或 `excluded` 及原因。只有保存整个候选池，才能复查是否搜窄、误删或漏掉公司。

## 3. 来源等级

### A：优先正式证据

- 公司官网的产品、团队、合作、目的地和联系页面；
- 协会会员目录和展会官方参展商资料；
- 公司新闻稿、正式业务资料；
- 本人公开职业资料或本人邮件签名。

### B：可靠辅助证据

- LinkedIn 公司页和公开职业资料；
- 公司官方社交账号；
- 招聘页、活动演讲者资料、可靠行业媒体和公开采访；
- 经过核验的专业商业目录。

### C：只用于发现

- 搜索摘要；
- 聚合目录、转载内容；
- YouTube、TikTok、Facebook、Instagram、Reddit 等普通公开内容；
- 点赞、播放、粉丝、泛评论和没有业务上下文的互动。

### X：不能升级

- 页面无法打开或来源已失效；
- 多个来源相互冲突；
- 疑似私人或敏感个人信息；
- 无法确认指向同一家公司或同一个人。

C 级来源可以发现公司或负责人候选，但关键公司结论和联系人身份至少需要 A/B 来源支持。只有 C 级来源时，保持 `candidate_pool` 或 `research_needed`。

## 4. 两层名单

### L1 候选池 `candidate_pool`

满足任一条件即可进入：

- 来源表明它可能属于目标客户类型；
- 经营亚洲、长线、定制、团组、商务或 MICE 产品；
- 出现潜在中国相关信号，但尚未完成核验。

候选池允许资料不完整，但必须保存发现来源和观察日期。

### L2 正式研究名单 `formal_list`

必须同时满足：

1. 公司官网或其他 A/B 来源确认公司主体；
2. 有 A/B 级证据证明它向目标客源市场销售出境旅游产品；
3. 有直接中国产品，或有能够解释中国合作场景的亚洲长线、定制、团组产品；
4. 记录它可能使用外部中国地接、合作路径不明、或已有自营地接，不能把“经营中国游”直接写成采购需求；
5. 记录它是潜在买方、业务混合、竞争者或关系未知；一体化竞争者不能进入优先联系；
6. 有可以解释联系原因的真实业务依据，没有未解决的主体冲突或停止联系信号；
7. 记录至少一名主要联系人，或明确记录已搜索但没找到并保留转交入口。

最终入选公司必须填写四个门禁字段：

- `source_market_role`：`outbound_seller` / `unclear` / `not_source_market`；
- `china_product_signal`：`direct` / `adjacent` / `none`；
- `ground_partner_route`：`external_partner_possible` / `unclear` / `in_house`；
- `competitive_position`：`potential_buyer` / `mixed` / `competitor` / `unknown`。

只有 `outbound_seller` 且中国信号为 `direct` 或 `adjacent` 才能进入正式名单。`priority_chat` 还必须有 `external_partner_possible` 的公开依据；否则最多保留为普通候选或继续研究。

`formal_list` 不是“对方有购买意愿”，只是允许进入人工外联准备。

其他研究阶段：

- `held`：因身份冲突、来源受限或重要缺口暂缓；
- `excluded`：明确不匹配或不得联系。

## 5. 每家公司必须回答

1. 公司主体、官网、国家和客户类型是什么？
2. 它向谁销售什么旅游产品？
3. 是否存在中国、亚洲、长线、定制、团组、企业差旅或 MICE 信号？
4. 哪个信号是事实，哪个只是合作假设？
5. 我们当前已确认的产品能力与哪个业务场景相关？
6. 为什么联系这个人，而不是只找最高职位？
7. 哪些资料未知、没找到、来源受限或存在冲突？
8. 是否命中重复记录或停止联系规则？
9. 它是目标市场的客源方，还是当地入境地接/同行？
10. 它使用外部中国地接的依据是什么；若未知，是否已降级而非写成采购意向？

## 6. 证据记录

每个独立来源观察写入一条 `Evidence`：

- `entity_type`、`entity_id`；
- `supported_field`；
- `evidence_kind`；
- `fact_summary`；
- `source_url`；
- `source_tier`；
- `source_role`；
- `source_access_status`；
- `source_published_at`（如有）；
- `observed_at`；
- `evidence_status`；
- `conflict_note`。

同一页面出现多个字段仍属于一个独立来源。可以让一条证据支持一个主要结论并在摘要中补充其他信息，但不能复制成多条提升可信度。

## 7. 联系人研究

联系人选择依据公司规模和业务：

- 小公司：Owner、Founder、Managing Director；
- 产品型旅行公司：Product、Contracting、Purchasing、Destination；
- 中国/亚洲专线：China Specialist、Asia Product；
- 团组和会展：Groups、MICE、Events、Incentives；
- 合作入口：Partnerships、Business Development；
- 只能转交：公开业务邮箱或一般联系入口。

每家公司默认一名 `primary`，必要时一名 `backup` 或 `handoff`。禁止为了增加触达量同时准备多名同公司联系人发送。

联系人身份核验必须读取 `identity-matching.md`。

## 8. 状态与冲突

来源访问状态：

```text
not_searched
opened
searched_not_found
source_restricted
```

证据状态见 `data-contract.md`。以下情况必须保持 `held` 或 `research_needed`：

- 公司同名但域名或国家无法确认；
- 联系人姓名、现任公司或职位冲突；
- 个性化依据只有搜索摘要；
- 联系理由依赖未确认的产品能力；
- 关键来源无法访问且没有替代来源。

冲突不能靠增加更多弱来源“投票”消除。必须找到更直接的来源或交给人工判断。

## 9. 完成一次研究的输出

一次公司研究必须产生以下之一：

- 正式公司和联系人记录；
- 候选记录及明确的下一步研究缺口；
- 已搜索但没找到的状态；
- 来源受限状态；
- 冲突及人工判断请求；
- 不匹配或停止联系记录。

不得返回只有公司名称、没有来源和状态的“名单”。
