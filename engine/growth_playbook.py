"""
IntentRadar Growth & Internal BD Operations Engine.
Provides:
1. Brand Capability Profiles (used in the client-facing workspace for strict cross-category compatibility gating and transparent disclosure outreach).
2. Internal BD Operations Data (Pilot Offers, Seed Challenger Clients, and Transparent Community Playbooks) — rendered ONLY into `internal_bd_ops.html` and removed from the public client-facing workspace.
"""

from typing import Dict, List


def get_brand_presets() -> List[Dict]:
    """
    Preset product capability profiles for the Client Workspace.
    Each profile explicitly defines:
    - target_competitors: Which incumbents this product is qualified to replace (enables cross-category mismatch blocking).
    - approved_capabilities: Verified product capabilities (no fabricated discounts or fake customer counts).
    - known_limitations: Honest boundaries/questions that must be verified before recommending migration.
    - cta_link: Technical migration verification documentation URL.
    """
    return [
        {
            "id": "preset-default",
            "label": "🔍 默认中立核验视角（不绑定特定卖方品牌）",
            "brand_name": "",
            "target_competitors": ["*"],
            "approved_capabilities": "按原帖证据客观呈现替换痛点、候选方案与待核验项，不强行植入特定卖方品牌",
            "known_limitations": "需先选择或配置具体卖方产品能力档案，再生成针对性破冰话术",
            "cta_link": "https://jakelihua.github.io/intent-radar-preview/",
        },
        {
            "id": "preset-jira",
            "label": "⚡ 敏捷研发协同（适配 Jira / Linear 替换场景）",
            "brand_name": "Plane 开源研发协同",
            "target_competitors": ["Atlassian Jira", "Atlassian Confluence", "Linear"],
            "approved_capabilities": "支持 Jira Cloud CSV/API 历史工单导入、Cycles 迭代看板、Docker/K8s 自托管部署与 GitHub 双向同步",
            "known_limitations": "复杂 Jira ScriptRunner 自动化脚本与自定义插件需人工评估替代方案；还需确认发帖人是否具备团队工具选型决策权",
            "cta_link": "https://docs.plane.so/importers/jira",
        },
        {
            "id": "preset-api",
            "label": "🔌 本地优先 API 客户端（适配 Postman 替换场景）",
            "brand_name": "Bruno / Hoppscotch 企业版",
            "target_competitors": ["Postman", "Insomnia"],
            "approved_capabilities": "纯本地文件存储（原生 Git 版本控制）、零强制云端登录、支持一键导入 Postman Collection v2.1 与环境变量脚本",
            "known_limitations": "若原团队高度依赖 Postman 云端 Mock Server 或公共 API 文档门户，需确认是否接受通过 CI/CD + 自托管网关替代",
            "cta_link": "https://docs.usebruno.com/migration/postman",
        },
        {
            "id": "preset-crm",
            "label": "💼 现代开源 CRM（适配 Salesforce / HubSpot 替换场景）",
            "brand_name": "Twenty CRM",
            "target_competitors": ["Salesforce CRM", "HubSpot"],
            "approved_capabilities": "开源可自托管、自定义对象与视图建模、标准 REST/GraphQL API、轻量级销售管道与邮件同步",
            "known_limitations": "若客户依赖复杂的跨渠道多触点营销归因（Multi-touch Attribution）或重度 CPQ 报价审批流，需先通过沙箱验证字段映射",
            "cta_link": "https://docs.twenty.com/user-guide/getting-started",
        },
        {
            "id": "preset-kb",
            "label": "📚 私有化知识库与多维表（适配 Notion / Airtable 替换场景）",
            "brand_name": "AFFiNE / NocoDB 企业自托管版",
            "target_competitors": ["Notion", "Airtable", "Atlassian Confluence"],
            "approved_capabilities": "支持 Docker 本地私有化部署、Markdown/CSV 批量导入、细粒度 REST API（无 Airtable 5 req/sec 硬限流）",
            "known_limitations": "需先确认团队当前单表数据行数、自动化 Webhook 触发频率，以及是否要求企业级 SAML SSO 商业授权",
            "cta_link": "https://docs.nocodb.com/getting-started/installation/",
        },
        {
            "id": "preset-obs",
            "label": "📊 OpenTelemetry 可观测平台（适配 Datadog / New Relic 替换场景）",
            "brand_name": "SigNoz 可观测平台",
            "target_competitors": ["Datadog", "New Relic"],
            "approved_capabilities": "100% 原生兼容 OpenTelemetry、ClickHouse 高吞吐存储、Metrics/Traces/Logs 三合一视图、按存储量透明计费（无高基数自定义指标附加税）",
            "known_limitations": "需确认客户当前 APM 探针语言栈、每日日志摄入峰值（GB/天）以及倾向自维 ClickHouse 集群还是使用托管云版本",
            "cta_link": "https://signoz.io/docs/migration/migrate-from-datadog/",
        },
        {
            "id": "preset-esign",
            "label": "✍️ 开源电子签名与合同 API（适配 DocuSign 替换场景）",
            "brand_name": "Documenso / OpenSign",
            "target_competitors": ["DocuSign", "PandaDoc", "HelloSign / Dropbox Sign"],
            "approved_capabilities": "提供无强制高价捆绑的开发者签署 API、Webhook 状态回调、支持自托管合规审计日志与模板嵌套签署",
            "known_limitations": "需核实客户业务所在司法管辖区对电子签名证书（如欧盟 eIDAS QES 或特定金融监管）的强制合规等级要求",
            "cta_link": "https://docs.documenso.com/developers/rest-api",
        },
        {
            "id": "preset-iam",
            "label": "🔐 企业身份认证与 SSO（适配 Auth0 / Clerk 替换场景）",
            "brand_name": "Logto / SuperTokens",
            "target_competitors": ["Auth0", "Clerk"],
            "approved_capabilities": "内置多租户组织架构（Organizations）、企业级 SAML/OIDC SSO、RBAC 权限控制、支持密码哈希导入平滑迁移",
            "known_limitations": "需确认现有用户会话切换窗口期、自定义 Actions 登录钩子逻辑复杂度，以及合规审计留存要求",
            "cta_link": "https://docs.logto.io/quick-starts/",
        },
    ]


def get_pilot_offers() -> List[Dict]:
    """
    GPT-audited 3-tier B2B pilot pricing & SLA refund structure.
    Rendered exclusively in `internal_bd_ops.html`.
    """
    return [
        {
            "id": "offer-verify",
            "tier": "试点方案 A · 低摩擦切入",
            "name": "7 天单赛道机会验证包",
            "price": "¥999 / 7 天",
            "target_icp": "已有商业产品、希望先验证本赛道公开社区真实替换信号密度的挑战者团队",
            "scope": "锁定 1 个卖方产品 + 最多 8 个直接竞品 + 固定公开社区列表（HN / GitHub / V2EX / Reddit）",
            "deliverables": [
                "交付最多 8 条经人工核验的公开竞品替换信号",
                "每条含：原帖直达链接、原文关键证据摘录、发布时间、适配原因、阻碍条件（待确认项）、建议触达路径",
                "提供完整 CSV / XLSX 核验台账与透明利益披露回复模板",
            ],
            "sla_guarantee": "若 7 天内符合《合格线索定义》的真实信号不足 3 条，免费延长 7 天或按未达标比例无条件退款。",
        },
        {
            "id": "offer-pilot",
            "tier": "试点方案 B · 主力变现产品",
            "name": "14 天单赛道联合跟进试点",
            "price": "¥1,999 / 14 天",
            "target_icp": "客单价 ≥ ¥10,000/年、配有专职销售/创始人跟进、具备竞品数据迁移能力的成长型 B2B 团队",
            "scope": "全量实时监听 + 人工 4 步资格核验 + 针对卖方真实产品能力边界定制破冰草稿",
            "deliverables": [
                "承诺交付至少 5 条经客户确认符合《合格线索定义》的真实可跟进机会",
                "每条配套：基于卖方已核准能力的 1v1 破冰草稿 + 公开透明利益披露回复 + 跟进状态复盘表",
                "每周 1 次跟进反馈复盘，动态调优关键词与资格过滤规则",
            ],
            "sla_guarantee": "不足 5 条合格线索的，每少 1 条退还 ¥399.80，绝不以超期旧帖或无决策权抱怨帖凑数。",
        },
        {
            "id": "offer-research",
            "tier": "试点方案 C · 高客单价定制",
            "name": "14 天竞品流失归因与深度研究试点",
            "price": "¥2,999 / 14 天",
            "target_icp": "客单价高、公开即时求助较少但竞品续费/性能痛点集中的企业级软件与开源商业化团队",
            "scope": "90 天历史公开迁移讨论回溯 + 实时优先机会捕获 + 销售赋能攻防卡（Battlecard）",
            "deliverables": [
                "1 份目标竞品近 90 天公开迁移抱怨与流失原因核验清单（不少于 20 条实盘样本，附原帖与原文证据）",
                "5 条当前处于活跃讨论窗口的优先跟进机会",
                "1 页针对卖方产品真实能力与已知边界的客观竞争话术卡（供 SDR 团队内部培训使用）",
            ],
            "sla_guarantee": "所有研究样本 100% 附带原始社区 URL 与原文摘录，任何一条链接失真即全额退还对应研究费用。",
        },
    ]


def get_seed_clients() -> List[Dict]:
    """
    Target challenger software teams for 1-to-1 evidence-based BD outreach.
    Follows GPT's strict rule: send 1 verified real thread at a time with full provenance and limitations.
    """
    return [
        {
            "id": "client-bruno-hoppscotch",
            "name": "Bruno / Hoppscotch / Apifox 企业版团队",
            "category": "API 研发协同与本地优先客户端",
            "target_incumbent": "Postman",
            "website": "https://www.usebruno.com",
            "github": "https://github.com/usebruno/bruno",
            "stage": "受益于 Postman 强制上云策略的黄金商业化替代期",
            "matched_leads_count": 1,
            "verified_evidence_id": "hn_41648918",
            "pain_point": "Postman 移除离线 Scratchpad 并强制要求云端账号同步，导致企业研发团队主动集中寻找替代品。",
            "contact_channel": "GitHub Discussions / 创始人 LinkedIn / 商务邮箱",
            "bd_pitch": (
                "您好！我们在 Hacker News 实盘核验到一条与贵司产品高度匹配的公开替换讨论（已核验原帖 API 真实性）：\n\n"
                "• 原帖链接：https://news.ycombinator.com/item?id=41648918\n"
                "• 原帖标题：Ask HN: What is the best Postman alternative in 2024?\n"
                "• 发帖人与时间：@indrasurya · 2024-09-25 14:46 UTC（29 条评论）\n"
                "• 原文证据摘录：\"Since Postman forced cloud accounts and killed the offline scratchpad, our team has been looking for a solid alternative.\"\n"
                "• 为什么适配贵司：原帖明确因「强制云账号 + 移除离线模式」寻求团队级替代，且点名希望评估 Bruno / Hoppscotch / Insomnia 在团队协作下的表现。\n"
                "• 待确认阻碍项：原帖尚未披露团队具体席位数与是否需要企业级私有部署支持，建议先通过原帖透明披露研发身份并提供 Postman Collection 导入验证清单。\n\n"
                "如果您希望我们持续为贵司监控并人工核验全网 Postman 真实迁出信号（按 14 天合格线索保底交付，不达标按条退款），欢迎回复交流。"
            ),
        },
        {
            "id": "client-plane-linear",
            "name": "Plane (makeplane/plane) / 敏捷协同挑战者团队",
            "category": "开源研发协同与项目管理",
            "target_incumbent": "Atlassian Jira",
            "website": "https://plane.so",
            "github": "https://github.com/makeplane/plane",
            "stage": "商业云与企业自托管版加速期",
            "matched_leads_count": 2,
            "verified_evidence_id": "hn_27018935",
            "pain_point": "需要精准区分「有决策权的团队重评估（如 hn_27018935）」与「仅一线员工抱怨但无选型权（如 hn_37146814）」。",
            "contact_channel": "GitHub / LinkedIn / 官网商务通道",
            "bd_pitch": (
                "Hi Plane Growth Team，我们在做 Jira 公开社区替换信号的实盘资格核验时，整理了两条极具代表性的对比样本发您参考：\n\n"
                "1. 【合格可跟进样本】https://news.ycombinator.com/item?id=27018935\n"
                "   • 原文证据：\"My startup uses Jira. We've grown to hate it and want to re-evaluate alternatives.\"\n"
                "   • 核验结论：创业团队集体决策重评估（具备选型推动力），核心阻碍在于需兼容产品经理/非技术成员协作。\n"
                "2. 【自动拦截负向样本】https://news.ycombinator.com/item?id=37146814\n"
                "   • 原文证据：\"Sadly using Jira was not my choice\"（293 赞、350 评论）\n"
                "   • 核验结论：尽管热度极高，但发帖人明示无选型决定权，我们的系统已将其标记为「无决策权痛点样本」避免浪费 SDR 精力。\n\n"
                "我们提供 7 天/14 天单赛道人工核验线索试点，只交付有原文证据且区分决策权限的真实替换机会。欢迎回复获取完整核验台账。"
            ),
        },
        {
            "id": "client-documenso-opensign",
            "name": "Documenso / OpenSign / 电子签 API 团队",
            "category": "开发者友好与自托管电子签名平台",
            "target_incumbent": "DocuSign",
            "website": "https://documenso.com",
            "github": "https://github.com/documenso/documenso",
            "stage": "API 商业订阅与合规自托管增长期",
            "matched_leads_count": 1,
            "verified_evidence_id": "hn_37333686",
            "pain_point": "DocuSign API 定价昂贵且开发者体验老旧，大量集成电子签名的 SaaS 团队正在寻找现代 API 替代。",
            "contact_channel": "GitHub / Discord / 创始人邮箱",
            "bd_pitch": (
                "您好！向您同步一条经 API 实盘核验的 DocuSign 开发者替换求助帖：\n\n"
                "• 原帖链接：https://news.ycombinator.com/item?id=37333686\n"
                "• 原帖标题：Ask HN: Better and less expensive alternatives to DocuSign?\n"
                "• 发帖人与时间：@ksec · 2023-08-31 05:31 UTC（52 条评论）\n"
                "• 原文证据摘录：\"DocuSign is really expensive, especially for API access. What are people using these days for electronic signatures that has a good developer API and reasonable pricing?\"\n"
                "• 为什么适配贵司：买方核心诉求直指「更合理的 API 价格 + 优秀的开发者 API 体验」，与贵司核心定位完全重合。\n"
                "• 待确认阻碍项：需进一步确认其月均合同签署量级与司法管辖区合规要求。\n\n"
                "我们可以为贵司提供 DocuSign / PandaDoc 赛道的持续替换信号核验服务，欢迎联系测试。"
            ),
        },
        {
            "id": "client-nocodb-teable",
            "name": "NocoDB / Teable / Baserow 团队",
            "category": "开源多维表格与自动化业务底座",
            "target_incumbent": "Airtable",
            "website": "https://nocodb.com",
            "github": "https://github.com/nocodb/nocodb",
            "stage": "企业版与云托管商业化扩张期",
            "matched_leads_count": 1,
            "verified_evidence_id": "hn_36042152",
            "pain_point": "Airtable Pro 付费版依然存在严苛的单 Base 行数限制与 5 req/sec API 限流，逼迫付费团队迁出。",
            "contact_channel": "GitHub / Discord / 商务邮箱",
            "bd_pitch": (
                "您好！我们在 Hacker News 核验到一条已处于 Airtable Pro 付费计划、但因容量与 API 限流触发替换评估的真实信号：\n\n"
                "• 原帖链接：https://news.ycombinator.com/item?id=36042152\n"
                "• 原文证据摘录：\"We are hitting row limits and API rate limits on Airtable Pro, and the jump to Enterprise pricing is way too steep for our team. Has anyone successfully migrated to NocoDB, Baserow, or Supabase with a spreadsheet UI?\"\n"
                "• 证据完备度：团队规模/付费状态/替换急迫度均为【原文明示】，且直接点名询问迁移实践。\n"
                "• 待确认阻碍项：需核验其现有 Airtable 视图公式与 Webhook 自动化脚本的迁移兼容度。\n\n"
                "我们构建了针对 Airtable 付费流失买家的核验工作台，欢迎体验并洽谈单赛道试点合作。"
            ),
        },
        {
            "id": "client-logto-supertokens",
            "name": "Logto / SuperTokens / 身份认证团队",
            "category": "现代企业级身份认证与 CIAM",
            "target_incumbent": "Auth0 / Clerk",
            "website": "https://logto.io",
            "github": "https://github.com/logto-io/logto",
            "stage": "B2B 多租户与 SSO 商业订阅加速期",
            "matched_leads_count": 1,
            "verified_evidence_id": "hn_38227662",
            "pain_point": "开发者对 Auth0 与 Clerk 在自定义架构与成本上的摩擦高度敏感。",
            "contact_channel": "飞书/微信社区 / Discord / GitHub",
            "bd_pitch": (
                "您好！向贵团队分享一条 HN 上获得 73 赞、85 条深度讨论的 Auth0 / Clerk 真实弃用复盘帖：\n\n"
                "• 原帖链接：https://news.ycombinator.com/item?id=38227662\n"
                "• 原帖标题：Why I moved away from Clerk and Auth0\n"
                "• 发帖人：@bmorrisondev\n"
                "• 核心价值：帖内聚集了大量正在评估迁出 Auth0/Clerk 的活跃开发者，适合围绕「近 90 天身份认证迁移阻力」做深度研究与精准跟进。\n\n"
                "我们提供 14 天单赛道深度研究与实时替换信号试点，欢迎随时交流！"
            ),
        },
        {
            "id": "client-signoz",
            "name": "SigNoz (SigNoz/signoz)",
            "category": "OpenTelemetry 原生可观测性平台",
            "target_incumbent": "Datadog / New Relic",
            "website": "https://signoz.io",
            "github": "https://github.com/SigNoz/signoz",
            "stage": "高客单价企业云与自托管双轮驱动",
            "matched_leads_count": 1,
            "verified_evidence_id": "hn_23392464",
            "pain_point": "工程团队因 Datadog 与 New Relic 高昂的按主机/自定义指标账单，持续寻找可自托管的开源 APM。",
            "contact_channel": "Slack 社区 / LinkedIn / 官网 BD",
            "bd_pitch": (
                "Hi SigNoz Team，我们在核验 Datadog / New Relic 公开替换需求时，归档了包括 https://news.ycombinator.com/item?id=23392464 在内的真实工程团队寻优样本（原文明确要求：\"Looking for something we can self-host to keep APM and metrics costs predictable as we scale.\"）。\n\n"
                "我们的 IntentRadar 核验台专门区分「抱怨账单」与「真正启动自托管 APM 选型」的工程负责人，并提供透明合规的技术触达草稿。欢迎查看我们的实盘核验样本库。"
            ),
        },
    ]


def get_launch_campaigns() -> List[Dict]:
    """
    Honest, transparent builder-disclosure operational templates for internal BD use.
    Eliminates all fake 'fellow user who migrated last month' sockpuppet language.
    """
    return [
        {
            "id": "camp-community-reply",
            "channel": "公开社区原帖回复规范 · 透明利益披露模板（严禁伪装过来人）",
            "audience": "在 HN / V2EX / Reddit / GitHub 发帖寻求竞品替代方案的真实发帖人",
            "best_time": "发现合格信号后 2 小时内人工复核后发出",
            "title": "原则：先披露开发者/服务商身份，再回答原帖具体痛点，最后说明已知限制与验证方式",
            "content": (
                "【标准透明披露回复模板】\n"
                "利益相关披露：我参与了 [产品名] 的开发。\n\n"
                "针对你在原帖提到的「[引用原帖具体痛点，如 Airtable Pro 5 req/sec API 限流与单表行数瓶颈]」，我们目前已支持：\n"
                "1. [已核准能力 1，如：通过标准 REST/GraphQL API 进行高并发读写，无单表硬性行数封顶]\n"
                "2. [已核准能力 2，如：支持一键读取现有 Base 结构并生成本地 Docker 验证环境]\n\n"
                "但需要客观说明的是，[已知限制/待确认项，如：如果你重度依赖复杂的原生界面自动化脚本，仍需先核对触发器兼容性]。\n"
                "这里有一份针对该场景的最小化迁移验证文档（[文档链接]），建议先用一小份脱敏数据跑通验证，有任何不匹配的地方欢迎直接指正。"
            ),
        },
        {
            "id": "camp-bd-single-lead",
            "channel": "1对1 卖方开发信 · 单条真凭实据敲门法（取代盲目群发）",
            "audience": "已有商业版、具备迁移承接能力的挑战者软件团队创始人 / 增长负责人",
            "best_time": "核验出该赛道 1-2 条真实合格信号当天定向发送",
            "title": "主题：一条与 [客户产品名] 相关的公开替换信号（含原帖与核验记录）",
            "content": (
                "您好 [联系人姓名]：\n\n"
                "我在公开技术社区筛查竞品替换讨论时，核验到一条与 [客户产品名] 直接相关的线索，先发您看是否值得团队跟进：\n\n"
                "• 来源与时间：[平台名称] / [UTC 发布时间]\n"
                "• 原帖直达链接：[真实可核验 URL]\n"
                "• 原文关键痛点摘录：“[原文明示摘录]”\n"
                "• 为什么判断与 [客户产品名] 相关：[基于客户公开文档的能力匹配点]\n"
                "• 尚未确认的阻碍项：[预算状态 / 团队席位数 / 特定合规或迁移边界]\n"
                "• 建议跟进方式：[透明披露身份的原帖回复草稿 或 1v1 技术验证邀请]\n\n"
                "我目前在做针对单一赛道的「公开竞品替换信号人工核验试点」（¥999 / 7天验证包，或 ¥1,999 / 14天保底 5 条合格线索，少 1 条退 ¥399.80）。\n"
                "如果这条线索的方向符合你们当前的客户画像，我可以按你们的真实产品能力边界，为您跑一轮 7 天实盘核验。您看这周方便用 15 分钟对齐一下你们的合格线索标准吗？"
            ),
        },
        {
            "id": "camp-v2ex-honest",
            "channel": "V2EX / 即刻 · 诚实复盘与试点招募帖",
            "audience": "ToB SaaS 创始人、开源商业化团队（COSS）、负责海外/国内增长的产品负责人",
            "best_time": "工作日 10:00 - 11:30",
            "title": "[分享创造] 做了个公开社区「竞品替换信号」核验工作台：从原帖证据、决策权核验到能力边界匹配",
            "content": (
                "做 B2B 软件和开源商业化的朋友经常会遇到一个问题：公开社区（HN、GitHub、V2EX、Reddit）里经常有人抱怨 Jira、Postman、DocuSign、Airtable 或 Datadog，但**「抱怨竞品」不等于「可以成交的销售线索」**。\n\n"
                "我们在实盘核验中发现，一条公开讨论要变成真正可跟进的机会，必须拆开过 4 道关：\n"
                "1. **抱怨竞品** vs **正在评估替代**（比如有人吐槽 Jira 慢，但原帖明说 `Sadly using Jira was not my choice`，这类无选型权的帖子发给销售只会浪费时间）；\n"
                "2. **被替换产品** vs **候选替代品** 的实体区分；\n"
                "3. **卖方真实能力匹配与阻碍项标注**（把【原文明示】【模型推断】【未知】严格拆开，不允许未知项被脑补成“预算充足”）；\n"
                "4. **诚实的开发者利益披露触达**（拒绝伪装“过来人”水军，直接披露研发身份 + 给出可验证的迁移测试路径）。\n\n"
                "基于这套标准，我们重构了 **IntentRadar 竞品替换信号核验工作台**：\n"
                "👉 在线实盘样本库（10 条样本全部绑定 Hacker News 官方 API 真实原帖 ID，支持逐条点击核验原文、查看三态证据来源与跨赛道不匹配拦截）：\n"
                "https://jakelihua.github.io/intent-radar-preview/\n\n"
                "目前我们开放 **3 个单赛道人工核验试点名额**（14 天交付至少 5 条经贵司确认合格的替换信号，每缺 1 条退 ¥399.80）。如果你已有商业版产品且能承接竞品迁移，欢迎在评论区留下你的【产品名 + 对标竞品】，我先免费帮你核验 1 条带完整原帖证据的真实信号。"
            ),
        },
    ]
