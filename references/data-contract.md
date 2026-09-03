# 数据合同

## Account（公司）字段

| 字段 | 必填 | 说明 |
|---|---:|---|
| account_id | 是 | 本地稳定 ID |
| company_name | 是 | 官方名称 |
| country | 是 | 国家/地区 |
| city | 否 | 城市 |
| company_type | 是 | agency、DMC、wholesaler、corporate_travel、MICE、event 等 |
| website | 是 | 官网 |
| linkedin_company | 否 | 公开公司页 |
| fit_reason | 是 | 为什么基本匹配 |
| fit_status | 是 | 见研究协议 |
| evidence_urls | 是 | 一个或多个来源 |
| evidence_date | 是 | 观察日期 |
| facts | 是 | 明确事实 |
| inferences | 否 | 推断，必须单独标记 |
| unknowns | 否 | 未知项 |
| risk_note | 否 | 风险或冲突 |

## Contact（联系人）字段

`contact_id`、`account_id`、`name`、`title`、`department_or_scope`、`linkedin_url`、`business_email`、`email_status`、`responsibility_evidence`、`source_url`、`observed_at`、`contact_confidence`、`handoff_message`。

邮箱没有可靠来源时留空；不要根据姓名格式猜邮箱。私人邮箱、私人电话和非公开个人信息不作为默认字段。

## Touchpoint（触达）字段

`touchpoint_id`、`account_id`、`contact_id`、`channel`、`draft_status`、`subject`、`message`、`cta`、`personalization_basis`、`fact_check_status`、`human_review_status`、`sent_at`、`reply_status`、`stop_reason`。

`channel` 只能是 `email`、`linkedin`、`website_form`、`other`。第一版只生成草稿，不记录为已发送，除非人工明确回填 `sent_at`。

## Reply / Opportunity 字段

记录 `source`、`received_at`、`reply_category`、`confirmed_requirements`、`unknown_requirements`、`next_action`、`owner`、`needs_human_takeover`、`do_not_contact`、`opportunity_stage`。

需求字段建议：目的地、日期、人数、客群、服务范围、语言、预算、佣金、采购流程、截止日期、下一步。没有出现的信息写 `unknown`。

