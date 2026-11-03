"""
IntentRadar Growth & Internal BD Operations Engine (v3.1).
Resolves Audit Round-2 Finding #2 & Finding #6:
1. All internal BD scripts in `get_seed_clients()` are dynamically generated from the canonical verified `IntentSignal`
   records in `mock_data.py` (never hardcoded separately).
2. Explicitly separates `verbatim_evidence_record` (exact title, author, timestamp, verbatim quote),
   `analysis_summary` (qualification & provenance summary), and `recommended_next_step` (verification action).
3. Brand capability presets include explicit `actor_role` ('产品研发团队' | '官方销售顾问' | '外部选型顾问') and remove wildcard '*' defaults.
"""

from typing import Dict, List
from .mock_data import get_mock_signals


def get_brand_presets() -> List[Dict]:
    """
    Preset product capability profiles for the Client Workspace.
    Each profile explicitly defines:
    - brand_name: Seller product name
    - actor_role: Sender's true identity ('产品研发团队' | '官方销售顾问' | '外部选型顾问')
    - target_competitors: Explicit list of incumbents this product can replace (no '*' wildcard)
    - approved_capabilities: Verified product capabilities (zero fabricated ROI/discounts)
    - known_limitations: Honest boundaries that must be verified before migration
    - cta_link: Technical migration verification documentation URL
    """
    return [
        {
            "id": "preset-default",
            "label": "🔍 默认中立核验视角（不绑定特定卖方品牌·仅生成中立核验问题）",
            "brand_name": "",
            "actor_role": "",
            "target_competitors": [],
            "approved_capabilities": "",
            "known_limitations": "未配置卖方产品能力档案时，阶段 3 保持「待核验」，系统仅生成中立资格核验提问，不承诺任何产品能力",
            "cta_link": "",
        },
        {
            "id": "preset-jira",
            "label": "⚡ 敏捷研发协同（适配 Jira / Linear 替换场景）",
            "brand_name": "Plane 开源研发协同",
            "actor_role": "产品研发团队",
            "target_competitors": ["Atlassian Jira", "Atlassian Confluence", "Linear"],
            "approved_capabilities": "支持 Jira Cloud CSV/API 历史工单导入、Cycles 迭代看板、Docker/K8s 自托管部署与 GitHub 双向同步",
            "known_limitations": "复杂 Jira ScriptRunner 自动化脚本与自定义插件需人工评估替代方案；还需确认发帖人是否具备团队工具选型决策权",
            "cta_link": "https://docs.plane.so/importers/jira",
        },
        {
            "id": "preset-api",
            "label": "🔌 本地优先 API 客户端（适配 Postman 替换场景）",
            "brand_name": "Bruno / Hoppscotch 企业版",
            "actor_role": "产品研发团队",
            "target_competitors": ["Postman", "Insomnia"],
            "approved_capabilities": "纯本地文件存储（原生 Git 版本控制）、零强制云端登录、支持导入 Postman Collection v2.1 与环境变量脚本",
            "known_limitations": "若原团队高度依赖 Postman 云端 Mock Server 或公共 API 文档门户，需确认是否接受通过 CI/CD + 自托管网关替代",
            "cta_link": "https://docs.usebruno.com/migration/postman",
        },
        {
            "id": "preset-crm",
            "label": "💼 现代开源 CRM（适配 Salesforce / HubSpot 替换场景）",
            "brand_name": "Twenty CRM",
            "actor_role": "产品研发团队",
            "target_competitors": ["Salesforce CRM", "HubSpot"],
            "approved_capabilities": "开源可自托管、自定义对象与视图建模、标准 REST/GraphQL API、轻量级销售管道与邮件同步",
            "known_limitations": "若客户依赖跨渠道多触点营销归因（Attribution）或重度 CPQ 报价审批流，需先通过沙箱验证字段映射",
            "cta_link": "https://docs.twenty.com/user-guide/getting-started",
        },
        {
            "id": "preset-kb",
            "label": "📚 私有化知识库与多维表（适配 Notion / Airtable 替换场景）",
            "brand_name": "AFFiNE / NocoDB 企业自托管版",
            "actor_role": "产品研发团队",
            "target_competitors": ["Notion", "Airtable", "Atlassian Confluence"],
            "approved_capabilities": "支持 Docker 本地私有化部署、多表关联视图（Linked Tables）、细粒度 REST API（无 Airtable Pro 严格 API 限流）",
            "known_limitations": "需先确认团队自动化测试写入并发峰值（QPS）、现有视图公式复杂度以及是否要求企业级 SAML SSO",
            "cta_link": "https://docs.nocodb.com/getting-started/installation/",
        },
        {
            "id": "preset-obs",
            "label": "📊 OpenTelemetry 可观测平台（适配 Datadog / New Relic 替换场景）",
            "brand_name": "SigNoz 可观测平台",
            "actor_role": "产品研发团队",
            "target_competitors": ["Datadog", "New Relic", "Datadog / New Relic"],
            "approved_capabilities": "原生兼容 OpenTelemetry 应用层分布式链路追踪（Transaction Tracing）、Metrics/Traces/Logs 三合一视图、支持开源自托管",
            "known_limitations": "需确认客户当前应用语言栈探针兼容性、每日 Trace/Log 摄入量（GB/天）以及自维 ClickHouse 还是使用云托管版",
            "cta_link": "https://signoz.io/docs/migration/migrate-from-datadog/",
        },
        {
            "id": "preset-esign",
            "label": "✍️ 开源电子签名与合同 API（适配 DocuSign 替换场景）",
            "brand_name": "Documenso / OpenSign",
            "actor_role": "产品研发团队",
            "target_competitors": ["DocuSign", "SignRequest", "PandaDoc", "HelloSign / Dropbox Sign"],
            "approved_capabilities": "提供常规套餐可用的开发者签署 API、模板邮件合并（Mail Merge）发送签署、Webhook 状态回调与自托管部署",
            "known_limitations": "需核实客户业务所在司法管辖区对电子签名证书（如欧盟 eIDAS QES 或特定行业监管）的强制合规等级要求",
            "cta_link": "https://docs.documenso.com/developers/rest-api",
        },
        {
            "id": "preset-iam",
            "label": "🔐 企业身份认证与 SSO（适配 Auth0 / Clerk 替换场景）",
            "brand_name": "Logto / SuperTokens",
            "actor_role": "产品研发团队",
            "target_competitors": ["Auth0", "Clerk", "Auth0 / Clerk"],
            "approved_capabilities": "支持标准 OIDC/OAuth2 协议、框架无关（支持 Hapi.js + 原生 Vanilla JS，不强制绑定 React）、内置多租户与用户管理",
            "known_limitations": "需确认现有站点会话管理方式、是否需要迁移存量密码哈希以及自托管或云服务偏好",
            "cta_link": "https://docs.logto.io/quick-starts/",
        },
    ]


def get_pilot_offers() -> List[Dict]:
    """
    3-tier B2B pilot pricing & SLA refund structure.
    Rendered exclusively in the non-public internal operations manual.
    """
    return [
        {
            "id": "offer-verify",
            "tier": "试点方案 A · 低摩擦切入",
            "name": "14 天单赛道 Stage 3 机会验证包",
            "price": "¥999 / 14 天",
            "target_icp": "已有商业产品、希望先验证本赛道公开社区真实替换信号密度的挑战者团队",
            "scope": "锁定 1 个卖方产品 + 最多 8 个直接竞品 + 5 大已实现公开源（Hacker News / GitHub Issues / Dev.to / Google News RSS / V2EX）+ 赛道排他保护",
            "deliverables": [
                "按实测漏斗交付经 Stage 3（卖方产品能力已人工核验）确认的当期公开竞品替换信号（绝不混入历史基准样本）",
                "每条含：原帖直达链接、原文关键证据摘录、发布时间、三态证据来源、阻碍条件、建议触达路径",
                "单帖排他锁：同一原帖在活跃窗口内仅交付给同赛道唯一签约客户，防止多厂商同时回复引发社区反感",
            ],
            "sla_guarantee": "仅以通过 Stage 3（卖方能力人工核验匹配）的当期真实信号计入交付配额（Stage 2 未核验线索不计入）；若 14 天内不足 3 条 Stage 3 合格信号，按未达标比例无条件退还差额。",
        },
        {
            "id": "offer-pilot",
            "tier": "试点方案 B · 主力变现产品",
            "name": "14 天多竞品联合核验试点",
            "price": "¥1,999 / 14 天",
            "target_icp": "客单价 ≥ ¥10,000/年、配有专职销售/创始人跟进、具备竞品数据迁移能力的成长型 B2B 团队",
            "scope": "全量实时监听 + 人工 Stage 3 能力匹配 & Stage 4 联系路径核验 + 针对卖方真实产品能力边界定制破冰草稿 + 赛道排他锁",
            "deliverables": [
                "承诺交付至少 5 条通过 Stage 3+（卖方能力匹配且核实选型上下文）的当期真实可跟进机会",
                "每条配套：基于卖方已核准能力的 1v1 破冰草稿 + 公开透明利益披露回复（严格遵守社区频控 ≤ 2 条/社区/天）",
                "每周 1 次跟进反馈复盘，动态调优关键词与资格过滤规则",
            ],
            "sla_guarantee": "不足 5 条 Stage 3+ 合格线索的，每少 1 条退还 ¥399.80（封顶全额退款，不做无限期顺延敞口），绝不以历史归档旧帖或仅 Stage 2 初筛帖凑数。",
        },
        {
            "id": "offer-research",
            "tier": "试点方案 C · 高客单价定制",
            "name": "14 天竞品流失归因与深度研究试点",
            "price": "¥2,999 / 14 天",
            "target_icp": "客单价高、公开即时求助较少但竞品续费/性能痛点集中的企业级软件与开源商业化团队",
            "scope": "历史公开迁移讨论归因回溯 + 实时优先机会捕获 + 销售赋能攻防卡（Battlecard）",
            "deliverables": [
                "1 份目标竞品公开迁移抱怨与流失原因核验清单（不少于 20 条实盘样本，附原帖与原文证据）",
                "5 条当前处于活跃讨论窗口的优先跟进机会",
                "1 页针对卖方产品真实能力与已知边界的客观竞争话术卡（供 SDR 团队内部培训使用）",
            ],
            "sla_guarantee": "所有研究样本 100% 附带原始社区 URL 与逐字原文摘录，任何一条链接或引述失真即全额退还对应研究费用。",
        },
    ]


def get_seed_clients() -> List[Dict]:
    """
    Target challenger software teams for 1-to-1 evidence-based BD outreach.
    CRITICAL INVARIANT (Audit Finding #2):
    Every BD script is dynamically constructed from the canonical verified `IntentSignal` record in `get_mock_signals()`.
    Zero separate/hardcoded quotes, authors, or timestamps.
    Explicitly separates:
    - `verbatim_evidence_record`: Exact source_id, url, title, author, timestamp, verbatim_quote, full_content
    - `analysis_summary`: Structured qualification & provenance summary
    - `recommended_next_step`: Actionable verification recommendation
    """
    signals_by_id = {s.source_id: s for s in get_mock_signals()}

    def _build_client_entry(
        client_id: str,
        name: str,
        category: str,
        target_incumbent: str,
        website: str,
        github: str,
        stage: str,
        evidence_id: str,
        analysis_summary: str,
        recommended_next_step: str,
        contact_channel: str,
        negative_comparison_id: str = "",
    ) -> Dict:
        sig = signals_by_id[evidence_id]
        qm = sig.qualification_meta or {}
        blockers_str = "；".join(qm.get("blocking_conditions") or ["需核实具体业务场景"])

        verbatim_record = {
            "source_id": sig.source_id,
            "url": sig.url,
            "title": sig.title,
            "author": sig.author,
            "timestamp": sig.timestamp,
            "published_at": sig.timestamp,
            "verbatim_quote": sig.evidence_quote,
            "evidence_quote": sig.evidence_quote,
            "full_content": sig.content,
            "dataset_kind": sig.dataset_kind,
        }

        neg_section = ""
        if negative_comparison_id and negative_comparison_id in signals_by_id:
            neg_sig = signals_by_id[negative_comparison_id]
            neg_section = (
                f"\n【附：系统自动拦截的无决策权反例校准样本 ({neg_sig.source_id})】\n"
                f"• 原帖链接：{neg_sig.url}\n"
                f"• 原帖标题：{neg_sig.title}\n"
                f"• 发帖人与发布时间：@{neg_sig.author} · {neg_sig.timestamp}\n"
                f"• 逐字原文摘录：\"{neg_sig.evidence_quote}\"\n"
                f"• 拦截说明：因作者原文明示 \"Sadly using Jira was not my choice\"（无替换决策权），系统将其锁定在阶段 1/4 并自动阻断销售外呼。\n"
            )

        bd_pitch = (
            f"您好！我们在 Hacker News 实盘基准库中核验并归档了与贵司对标竞品（{target_incumbent}）直接相关的公开替换讨论（数据直接源自官方 Firebase API 核验记录 {sig.source_id}）：\n\n"
            f"【一、已核验原帖证据（Verbatim Evidence）】\n"
            f"• 原帖直达链接：{sig.url}\n"
            f"• 原帖标题：{sig.title}\n"
            f"• 发帖人与发布时间：@{sig.author} · {sig.timestamp}（数据集属性：{sig.dataset_kind}）\n"
            f"• 逐字原文证据摘录：\"{sig.evidence_quote}\"\n\n"
            f"【二、资格核验与归因摘要（Analysis Summary）】\n"
            f"• 适配与痛点归纳：{analysis_summary}\n"
            f"• 证据来源标识：规模[{qm.get('team_scale', {}).get('source', '未知')}] / "
            f"预算[{qm.get('budget_status', {}).get('source', '未知')}] / "
            f"决策权[{qm.get('decision_authority', {}).get('source', '未知')}]\n"
            f"• 已知阻碍条件：{blockers_str}\n"
            f"{neg_section}\n"
            f"【三、建议验证动作（Recommended Next Step）】\n"
            f"• {recommended_next_step}\n\n"
            f"（说明：上方样本为历史基准校准集样本，不计入当期实时商机配额。若贵司希望开启 7 天/14 天当期实时替换信号核验试点，欢迎随时交流。）"
        )

        return {
            "id": client_id,
            "name": name,
            "category": category,
            "target_incumbent": target_incumbent,
            "website": website,
            "github": github,
            "stage": stage,
            "matched_leads_count": 2 if negative_comparison_id else 1,
            "verified_evidence_id": sig.source_id,
            "target_signal_id": sig.source_id,
            "verbatim_evidence_record": verbatim_record,
            "analysis_summary": analysis_summary,
            "recommended_next_step": recommended_next_step,
            "pain_point": analysis_summary,
            "contact_channel": contact_channel,
            "bd_pitch": bd_pitch,
            "knock_door_dm": bd_pitch,
        }

    return [
        _build_client_entry(
            client_id="archetype-api-client",
            name="赛道范例 A · API 研发协同与本地优先客户端厂商",
            category="API 研发协同与本地优先客户端",
            target_incumbent="Postman",
            website="https://example.org/api-client-challenger",
            github="https://github.com/topics/api-client",
            stage="企业商业化与团队协同替代期（单赛道排他交付）",
            evidence_id="hn_41648918",
            analysis_summary="发帖人明示团队（My team）因 Postman 变得臃肿缓慢（very bloated and slow）正主动寻找迁出替代方案；原帖正文未点名具体候选工具，团队具体席位数与商业预算属于未知待核实项。",
            recommended_next_step="在监控到当期同类 Postman 团队迁出求助时，先披露研发团队身份，提供 Postman Collection 导入兼容度清单并询问团队席位规模。",
            contact_channel="公开社区合规披露回复 / 官网商务通道",
        ),
        _build_client_entry(
            client_id="archetype-agile-pm",
            name="赛道范例 B · 敏捷研发协同与私有化项目管理厂商",
            category="开源研发协同与项目管理",
            target_incumbent="Atlassian Jira",
            website="https://example.org/agile-pm-challenger",
            github="https://github.com/topics/project-management",
            stage="商业云与企业自托管版加速期（单赛道排他交付）",
            evidence_id="hn_27018935",
            negative_comparison_id="hn_37146814",
            analysis_summary="初创公司研发团队（We a start-up）因 Jira 笨重难配置而启动工具重评估（opportunity to reevaluate），且原文明示已试用过 Linear（We have tried out Linear a bit）；系统将其与无选型权的抱怨帖（hn_37146814）严格区分。",
            recommended_next_step="针对处于工具重评估窗口的研发团队，重点提供 Jira 历史工单导入沙箱与灵活工作流配置对比，先确认团队人数与自托管偏好。",
            contact_channel="公开社区合规披露回复 / 官网商务通道",
        ),
        _build_client_entry(
            client_id="archetype-esign-api",
            name="赛道范例 C · 开发者友好型电子签名 API 平台",
            category="开发者友好与自托管电子签名平台",
            target_incumbent="DocuSign",
            website="https://example.org/esign-api-challenger",
            github="https://github.com/topics/document-signing",
            stage="API 商业订阅与合规自托管增长期（单赛道排他交付）",
            evidence_id="hn_37333686",
            analysis_summary="发帖人原文明示拒绝 DocuSign 等 $1.50/envelope 的高单价，指出需要简单的文档邮件合并（mail merge）并调用 API 发送给客户签署；曾使用 SignRequest，但因常规 SaaS 套餐停止提供 API（强制绑入高价企业版）而寻找替代。",
            recommended_next_step="向此类 API 价格敏感型买方提供透明的常规套餐 API 定价与 Mail Merge 签署接口示例，并核实其月签署量与合规管辖区。",
            contact_channel="公开社区合规披露回复 / 官网商务通道",
        ),
        _build_client_entry(
            client_id="archetype-spreadsheet-db",
            name="赛道范例 D · 企业级多维表格与自动化业务底座厂商",
            category="开源多维表格与自动化业务底座",
            target_incumbent="Airtable",
            website="https://example.org/spreadsheet-db-challenger",
            github="https://github.com/topics/airtable-alternative",
            stage="企业版与云托管商业化扩张期（单赛道排他交付）",
            evidence_id="hn_36042152",
            analysis_summary="发帖人（@gajus）原文明示团队正在使用 Airtable Pro 付费套餐记录测试运行（record test runs），高度认可其多表关联（link multiple tables）与团队共享视图（share views with the team），但因持续触发 API/actions 限流而公开寻找具备同等 UI/UX/API 的替代品（注：原帖未提及单表行数限制或具体候选产品名）。",
            recommended_next_step="围绕「多表关联 + 团队共享视图 + 高吞吐 REST API 无严格限流」三大原文明示诉求提供基准测试对比，并核实其每日测试记录 API 写入峰值。",
            contact_channel="公开社区合规披露回复 / 官网商务通道",
        ),
        _build_client_entry(
            client_id="archetype-ciam-auth",
            name="赛道范例 E · 企业级身份认证与多租户 CIAM 厂商",
            category="现代企业级身份认证与 CIAM",
            target_incumbent="Auth0 / Clerk",
            website="https://example.org/ciam-auth-challenger",
            github="https://github.com/topics/authentication",
            stage="B2B 多租户与 SSO 商业订阅加速期（单赛道排他交付）",
            evidence_id="hn_38227662",
            analysis_summary="发帖人（@geuis）原文明示其站点采用 Hapi.js 服务端渲染 + 原生 Vanilla JS（不使用 React/Vue），连续 2 天尝试接入 Auth0 与 clerk.dev 均受阻（Auth0 快速入门报错无明确原因，clerk.dev 的 UI 组件即使在 JS SDK 下仍强依赖 React），急需框架无关的开箱即用登录与用户管理系统。",
            recommended_next_step="针对非 React/原生 JS 技术栈开发者，直接提供纯标准 OIDC / Vanilla JS 接入示例，并核实其活跃用户规模与商业支持需求。",
            contact_channel="公开社区合规披露回复 / 官网商务通道",
        ),
        _build_client_entry(
            client_id="archetype-otel-apm",
            name="赛道范例 F · OpenTelemetry 原生可观测性平台厂商",
            category="OpenTelemetry 原生可观测性平台",
            target_incumbent="Datadog / New Relic",
            website="https://example.org/otel-apm-challenger",
            github="https://github.com/topics/opentelemetry",
            stage="高客单价企业云与自托管双轮驱动（单赛道排他交付）",
            evidence_id="hn_23392464",
            analysis_summary="发帖人（@vital101）原文明示正在寻找 NewRelic 或 DataDog APM 服务的开源替代方案（open source alternative），指出市面上虽有很多日志聚合或服务器监控工具，但缺乏能够与应用集成并追踪事务（application integration so you can trace transactions）的方案。",
            recommended_next_step="围绕「开源 + 应用层集成与分布式事务追踪（Transaction Tracing）」提供 OpenTelemetry 探针接入演示，并询问其应用语言栈与日均 Trace 量级。",
            contact_channel="公开社区合规披露回复 / 官网商务通道",
        ),
    ]


def get_launch_campaigns() -> List[Dict]:
    """
    Honest, transparent builder-disclosure operational templates for internal BD use.
    """
    return [
        {
            "id": "camp-community-reply",
            "channel": "公开社区原帖回复规范 · 真实身份披露模板（严禁伪装过来人）",
            "audience": "在 HN / GitHub / Dev.to / V2EX 发帖寻求竞品替代方案的真实发帖人",
            "best_time": "发现当期合格信号并完成阶段 1-3 核验后人工复核发出",
            "title": "原则：先按真实角色披露身份（研发/销售/顾问），再引用原帖逐字痛点，仅陈述已核准能力并追问未知项",
            "content": (
                "【标准透明披露回复模板（阶段 3 卖方能力已匹配时启用）】\n"
                "利益相关披露：我是 [产品名] 的 [真实身份：产品研发团队 / 官方销售顾问 / 外部选型顾问]。\n\n"
                "针对你在原帖提到的「[逐字引用原帖具体痛点，严禁篡改或脑补原文未提及的内容]」，我们目前已核准支持：\n"
                "1. [卖方档案中已核准能力 1]\n"
                "2. [卖方档案中已核准能力 2]\n\n"
                "但需要客观说明已知边界：[卖方档案中已知限制]；同时原帖尚未披露 [未知项：如团队规模 / 预算范围 / 并发指标]，建议先基于最小化验证文档（[文档链接]）实测确认。"
            ),
        },
        {
            "id": "camp-bd-single-lead",
            "channel": "1对1 卖方开发信 · 单条已核验记录追溯模板",
            "audience": "已有商业版、具备迁移承接能力的挑战者软件团队创始人 / 增长负责人",
            "best_time": "核验出该赛道当期真实信号当天定向发送",
            "title": "主题：一条与 [客户产品名] 相关的公开替换信号（附原帖链接与原文证据摘录）",
            "content": (
                "您好 [联系人姓名]：\n\n"
                "我们在公开技术社区筛查竞品替换讨论时，核验到一条与 [客户产品名] 相关的记录，先发您审阅：\n\n"
                "• 来源与原帖 ID：[平台名称] / [source_id]\n"
                "• 发布时间与数据集类型：[UTC 发布时间]（[live_production / historical_benchmark]）\n"
                "• 原帖直达链接：[真实可核验 URL]\n"
                "• 逐字原文痛点摘录：“[必须与原帖 100% 一致的原文片段]”\n"
                "• 资格与证据来源：规模[[原文明示/模型推断/未知]]、预算[[原文明示/模型推断/未知]]、权限[[原文明示/模型推断/未知]]\n"
                "• 尚未确认的阻碍项：[具体待核实项]\n\n"
                "我们提供单赛道「当期公开竞品替换信号人工核验试点」（¥999 / 7天验证包，或 ¥1,999 / 14天保底 5 条当期合格线索，少 1 条退 ¥399.80，绝不混入历史样本）。欢迎回复交流。"
            ),
        },
    ]
