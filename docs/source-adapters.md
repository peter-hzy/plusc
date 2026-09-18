# 来源适配器

内置来源：`manual`、`directory_csv`、`public_web`、`codex_bridge`，以及显式调用的`brave`、`apollo`、`hunter`。公开网页适配器读取HTML/文本，不负责搜索发现；bridge接收Codex研究结果，不自动启动浏览器。它们不绕过网站权限。

每次来源运行必须明确区分：成功、无结果、受限、可重试失败、终止失败和取消。不得把403、验证码、超时或解析失败写成“没有找到”。

Brave按query发现线索，Apollo按公司域名及职责找人员，Hunter验证已知邮箱；没有密钥时返回unavailable，核心流程仍可运行。密钥仅从环境变量读取，详见.env.example和CLI文档。已做无密钥及模拟响应测试，不等于生产连接或数据准确性验证。适配器不能猜邮箱，不能把搜索摘要直接升级为正式事实。

ImportGenius、Google Places、Serper尚未内置。新增源须证明旅游业务价值，并完成费用、失败降级、原始来源、数据授权和脱敏检查。
