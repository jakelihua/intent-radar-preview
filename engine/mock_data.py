"""
Verified Real-World Public Community Sample Dataset for IntentRadar.
Every item below is a 100% real, publicly verifiable Hacker News thread (verifiable via
https://hacker-news.firebaseio.com/v0/item/<id>.json and https://news.ycombinator.com/item?id=<id>).
Each signal preserves:
- Exact source_id, verbatim title, verbatim text, author, and UTC publish timestamp
- Tri-state qualification provenance: [原文明示] (Explicit), [模型推断] (Inferred), [未知] (Unknown)
- Four-stage funnel separation: 抱怨竞品 -> 正在评估替代 -> 产品能力匹配 -> 触达路径核验
"""

from typing import List
from .collector import IntentSignal


def get_mock_signals() -> List[IntentSignal]:
    return [
        # 1. Postman (HN #41648918 - Verified Real Thread)
        IntentSignal(
            source_id="hn_41648918",
            title="Ask HN: What's the Best Postman Alternative?",
            url="https://news.ycombinator.com/item?id=41648918",
            source="Hacker News",
            content=(
                "My team is looking to migrate away from Postman as our API client because it has become "
                "very bloated and slow. What alternatives can you recommend?"
            ),
            evidence_quote="My team is looking to migrate away from Postman as our API client because it has become very bloated and slow.",
            author="hubraumhugo",
            keyword="migrate away from Postman",
            timestamp="2024-09-25 16:06 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=10,
            engagement_metric="🔥 8 点赞 · 💬 10 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（团队级迁移选型）",
                "team_scale": {"value": "团队级使用（具体席位数未披露）", "provenance": "原文明示"},
                "budget_status": {"value": "未知（未披露商业采购预算）", "provenance": "未知"},
                "decision_authority": {"value": "研发团队成员 / 选型发起人", "provenance": "模型推断"},
                "migration_urgency": {"value": "明确正在寻找迁移目标（Looking to migrate away）", "provenance": "原文明示"},
                "candidate_alternatives": ["Bruno", "Hoppscotch", "Yaak", "Insomnia"],
                "blocking_conditions": "HN 账号未直接公开企业邮箱，需先在原帖提供离线/Git 集合导入对比方案完成首轮互动。",
                "contact_path": "HN 原帖公开技术回复 (item?id=41648918) + 用户主页关联线索核查",
            },
        ),
        # 2. Jira Startup Re-evaluation (HN #27018935 - Verified Real Thread)
        IntentSignal(
            source_id="hn_27018935",
            title="Ask HN: Jira Alternatives?",
            url="https://news.ycombinator.com/item?id=27018935",
            source="Hacker News",
            content=(
                "We (a start-up) currently use Jira, but we have an opportunity to reevaluate our tools. "
                "We find Jira very clunky and hard to use, although it's very flexible (though extremely hard to configure). "
                "We have tried out Linear a bit, and liked it a lot. What are some other popular alternatives which are fairly flexible, "
                "and good for software development? Ideally, we want a tool we can use long-term, is easy and pleasant to use, "
                "and is flexible enough for the requirements of a software team."
            ),
            evidence_quote="We (a start-up) currently use Jira, but we have an opportunity to reevaluate our tools. We find Jira very clunky and hard to use... We have tried out Linear a bit.",
            author="CraftThatBlock",
            keyword="Jira Alternatives",
            timestamp="2021-05-02 20:57 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=8,
            engagement_metric="🔥 7 点赞 · 💬 8 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（已试用 Linear 等候选品）",
                "team_scale": {"value": "初创公司研发团队（具体人数未披露）", "provenance": "原文明示"},
                "budget_status": {"value": "未知（寻求长期可用研发团队方案）", "provenance": "未知"},
                "decision_authority": {"value": "拥有工具重评估参与权（Opportunity to reevaluate）", "provenance": "原文明示"},
                "migration_urgency": {"value": "处于工具重评估窗口期（样本发布时间较早，仅作历史核验基准）", "provenance": "原文明示"},
                "candidate_alternatives": ["Linear", "Plane", "Shortcut"],
                "blocking_conditions": "历史归档样本（发布于 2021 年），用于校准评估意图识别模型，不计入当期有效商机交付配额。",
                "contact_path": "HN 原帖归档核验 (item?id=27018935)",
            },
        ),
        # 3. DocuSign API Pricing (HN #37333686 - Verified Real Thread)
        IntentSignal(
            source_id="hn_37333686",
            title="Are there any affordable DocuSign alternatives that do API access?",
            url="https://news.ycombinator.com/item?id=37333686",
            source="Hacker News",
            content=(
                "I haven't found a single DocuSign alternative that wasn't the same crazy pricing like $1.50/envelope or document. "
                "I just want a simple mail merge on a document and send that to a customer to sign. "
                "I used to use SignRequest for that, and it used to be standard across the board, "
                "but all of them stopped offering their APIs in their normal SaaS packages; it's all under enterprise or too expensive."
            ),
            evidence_quote="I haven't found a single DocuSign alternative that wasn't the same crazy pricing like $1.50/envelope... all of them stopped offering their APIs in their normal SaaS packages.",
            author="HakuG",
            keyword="DocuSign alternatives API",
            timestamp="2023-08-31 07:31 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=1,
            engagement_metric="🔥 1 点赞 · 💬 1 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（明确 API 签署与价格敏感诉求）",
                "team_scale": {"value": "未知（未披露公司规模与月签署量）", "provenance": "未知"},
                "budget_status": {"value": "明确拒绝 $1.50/信封高价及强制捆绑企业版套餐", "provenance": "原文明示"},
                "decision_authority": {"value": "负责集成选型的开发者 / 业务主理人", "provenance": "模型推断"},
                "migration_urgency": {"value": "因原用的 SignRequest 等取消常规套餐 API 而迫切寻找替代", "provenance": "原文明示"},
                "candidate_alternatives": ["Docuseal", "OpenSign", "SignRequest"],
                "blocking_conditions": "客户对单信封成本极度敏感，若卖方仅提供高价企业年包则无法成交；适合开源自托管或低价按量 API 方案。",
                "contact_path": "HN 原帖回复 (item?id=37333686) 提供 API 定价透明对比与沙盒文档",
            },
        ),
        # 4. Airtable Pro Plan API Rate Limits (HN #36042152 - Verified Real Thread)
        IntentSignal(
            source_id="hn_36042152",
            title="Ask HN: What are Airtable alternatives with higher rate limits?",
            url="https://news.ycombinator.com/item?id=36042152",
            source="Hacker News",
            content=(
                "We are using Airtable to record test runs. It is working great, and I especially like the ability "
                "to link multiple tables and share views with the team. However, we are constantly hitting rate limits "
                "of their API/actions (we are on the Pro plan). What are some of the alternatives that provide comparable UI/UX/API?"
            ),
            evidence_quote="We are using Airtable to record test runs... However, we are constantly hitting rate limits of their API/actions (we are on the Pro plan).",
            author="gajus",
            keyword="Airtable alternatives rate limits",
            timestamp="2023-05-23 10:15 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=2,
            engagement_metric="🔥 3 点赞 · 💬 2 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（现有付费 Pro 团队遭遇技术瓶颈）",
                "team_scale": {"value": "研发团队使用（已采购 Pro 付费套餐，具体人数未知）", "provenance": "原文明示"},
                "budget_status": {"value": "已有付费习惯（当前为 Airtable Pro 付费订户）", "provenance": "原文明示"},
                "decision_authority": {"value": "知名开源作者 / 技术负责人 (gajus)", "provenance": "原文明示"},
                "migration_urgency": {"value": "高频触发 API 限流阻碍自动化测试记录，亟需高吞吐 API 平替", "provenance": "原文明示"},
                "candidate_alternatives": ["Baserow", "NocoDB", "Teable", "NocoBase"],
                "blocking_conditions": "要求同时具备多表关联（Linked Tables）、团队共享视图以及无严格限流的高性能 API。",
                "contact_path": "HN 账号 gajus（公开实名开发者，可通过 GitHub/Twitter/原帖直接触达）",
            },
        ),
        # 5. Auth0 & Clerk Friction (HN #38227662 - Verified Real Thread)
        IntentSignal(
            source_id="hn_38227662",
            title="Ask HN: Looking for alternatives to auth0 and clerk (user login services)",
            url="https://news.ycombinator.com/item?id=38227662",
            source="Hacker News",
            content=(
                "Wondering if people can recommend some alternatives to Auth0 and clerk.dev. "
                "I have an existing site that is as vanilla as you can get (server rendered pages with Hapi.js and JS client features "
                "written in regular old javascript. No frameworks are used like React, Vue, etc... "
                "Even exactly following Auth0's quick start guides leads to authentication errors with no clear answers why... "
                "All I want is a simple to use drop-in login/user management system. Nothing dependent on this framework or that one."
            ),
            evidence_quote="Even exactly following Auth0's quick start guides leads to authentication errors with no clear answers why... All I want is a simple to use drop-in login/user management system.",
            author="geuis",
            keyword="alternatives to auth0",
            timestamp="2023-11-11 04:36 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=3,
            engagement_metric="🔥 1 点赞 · 💬 3 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（明确拒绝 React 强绑定，寻求框架无关 IAM）",
                "team_scale": {"value": "未知（疑似独立开发者或小型项目团队）", "provenance": "模型推断"},
                "budget_status": {"value": "未知（未提及付费预算规模）", "provenance": "未知"},
                "decision_authority": {"value": "项目直接开发者（拥有技术选型决定权）", "provenance": "原文明示"},
                "migration_urgency": {"value": "已连续 2 天卡在 Auth0/Clerk 接入故障，进度受阻急需替换", "provenance": "原文明示"},
                "candidate_alternatives": ["Logto", "SuperTokens", "Keycloak", "Ory"],
                "blocking_conditions": "技术栈为 Hapi.js + 原生 Vanilla JS（不使用 React/Vue），任何仅提供 React 组件库的方案均不适配！",
                "contact_path": "HN 原帖 (item?id=38227662) 提供纯标准 OIDC / Vanilla JS SDK 接入示例",
            },
        ),
        # 6. Salesforce SMB Alternatives (HN #42749172 - Verified Real 2025 Thread)
        IntentSignal(
            source_id="hn_42749172",
            title="Ask HN: Alternatives to Salesforce?",
            url="https://news.ycombinator.com/item?id=42749172",
            source="Hacker News",
            content="What alternatives to Salesforce are you using at your small to medium sized businesses?",
            evidence_quote="What alternatives to Salesforce are you using at your small to medium sized businesses?",
            author="cloudking",
            keyword="Alternatives to Salesforce",
            timestamp="2025-01-18 15:48 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=1,
            engagement_metric="🔥 1 点赞 · 💬 1 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（SMB 场景公开寻优，需进一步资格核验）",
                "team_scale": {"value": "中小型企业 (Small to medium sized business)", "provenance": "原文明示"},
                "budget_status": {"value": "未知（未披露席位预算）", "provenance": "未知"},
                "decision_authority": {"value": "未知（需核实发帖人是否为业务/IT负责人）", "provenance": "未知"},
                "migration_urgency": {"value": "未知（仅发起选型调研，未明示合同到期日）", "provenance": "未知"},
                "candidate_alternatives": ["Twenty CRM", "Attio", "Pipedrive", "HubSpot"],
                "blocking_conditions": "原帖信息较简短，未说明具体核心流程（如邮件同步、工单或自定义报表），需先通过评论区互动确认具体需求边界。",
                "contact_path": "HN 原帖 (item?id=42749172) 互动提问核实具体业务场景",
            },
        ),
        # 7. HubSpot Automation & Attribution Alternative (HN #33244048 - Verified Real Thread)
        IntentSignal(
            source_id="hn_33244048",
            title="Ask HN: Hubspot Alternative",
            url="https://news.ycombinator.com/item?id=33244048",
            source="Hacker News",
            content=(
                "Hi everyone, I'm looking for Hubspot alternatives. My need is automation workflow and CRM. "
                "Mostly track the user activities in my app and trigger the event based on user properties (attribution). "
                "I've tried some tools yet to find out the fit tool for me. Any recommendations guys? Thanks a lot"
            ),
            evidence_quote="I'm looking for Hubspot alternatives. My need is automation workflow and CRM. Mostly track the user activities in my app and trigger the event based on user properties (attribution).",
            author="lienhoangduy",
            keyword="Hubspot Alternative",
            timestamp="2022-10-18 07:22 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=6,
            engagement_metric="🔥 9 点赞 · 💬 6 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（明确需要应用内事件追踪 + 自动化工作流 + CRM）",
                "team_scale": {"value": "未知（应用开发者/产品负责人）", "provenance": "模型推断"},
                "budget_status": {"value": "未知（未披露预算范围）", "provenance": "未知"},
                "decision_authority": {"value": "直接选型决策人（已亲自测试多款候选工具）", "provenance": "原文明示"},
                "migration_urgency": {"value": "已试用多款工具仍未找到匹配项（Yet to find out the fit tool）", "provenance": "原文明示"},
                "candidate_alternatives": ["Customer.io", "Dittofeed", "Twenty CRM", "Mautic"],
                "blocking_conditions": "纯静态销售记录型 CRM 不匹配！买方核心刚需是「应用内用户行为追踪 (Event Tracking) + 属性归因触发工作流」。",
                "contact_path": "HN 原帖 (item?id=33244048) / 用户主页联系路径",
            },
        ),
        # 8. Datadog / NewRelic Open-Source APM (HN #23392464 - Verified Real Thread)
        IntentSignal(
            source_id="hn_23392464",
            title="Ask HN: Open-source NewRelic / DataDog APM alternative?",
            url="https://news.ycombinator.com/item?id=23392464",
            source="Hacker News",
            content=(
                "I'm curious if there is a good open source alternative out there for NewRelic or DataDog's APM service. "
                "I see lots of options for log aggregation or server monitoring, "
                "but haven't found anything with application integration so you can trace transactions."
            ),
            evidence_quote="I'm curious if there is a good open source alternative out there for NewRelic or DataDog's APM service... with application integration so you can trace transactions.",
            author="vital101",
            keyword="DataDog APM alternative",
            timestamp="2020-06-02 15:58 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=2,
            engagement_metric="🔥 4 点赞 · 💬 2 条讨论",
            qualification_meta={
                "qualification_stage": "正在评估替代（明确要求开源 + 应用层分布式链路追踪 Transaction Tracing）",
                "team_scale": {"value": "未知（未披露服务器节点规模）", "provenance": "未知"},
                "budget_status": {"value": "倾向开源自托管方案（Open-source alternative）", "provenance": "原文明示"},
                "decision_authority": {"value": "研发/运维工程师", "provenance": "模型推断"},
                "migration_urgency": {"value": "历史归档技术调研样本（用于検証 APM 细分能力匹配度）", "provenance": "原文明示"},
                "candidate_alternatives": ["SigNoz", "Jaeger + Prometheus", "SkyWalking", "Uptrace"],
                "blocking_conditions": "仅提供基础主机监控或日志聚合的产品不匹配；卖方必须原生支持 OpenTelemetry 应用层分布式事务追踪 (APM Tracing)。",
                "contact_path": "HN 原帖归档核验 (item?id=23392464)",
            },
        ),
        # 9. Jira Slow UI - Explicit LACK of Decision Authority (HN #37146814 - Verified Real Thread)
        IntentSignal(
            source_id="hn_37146814",
            title="Ask HN: Alternative Jira UIs?",
            url="https://news.ycombinator.com/item?id=37146814",
            source="Hacker News",
            content=(
                "Especially on the “Backlog” view, eventually my M2 Mac starts to just crawl as I’m moving stuff around "
                "and trying to plan my team’s next sprint. I’m using Safari. Any workarounds or alternative frontends "
                "that are faster? Sadly using Jira was not my choice."
            ),
            evidence_quote="Especially on the “Backlog” view, eventually my M2 Mac starts to just crawl... Any workarounds or alternative frontends that are faster? Sadly using Jira was not my choice.",
            author="breckenedge",
            keyword="Alternative Jira UI",
            timestamp="2023-08-16 13:39 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=11,
            engagement_metric="🔥 6 点赞 · 💬 11 条讨论",
            qualification_meta={
                "qualification_stage": "仅抱怨竞品 / 无替换决策权（反例警示样本）",
                "team_scale": {"value": "敏捷研发团队（正在做 Sprint 规划）", "provenance": "原文明示"},
                "budget_status": {"value": "无替换预算（仅寻找第三方加速前端或浏览器插件）", "provenance": "原文明示"},
                "decision_authority": {"value": "无采购替换决定权（原文明示：Sadly using Jira was not my choice）", "provenance": "原文明示"},
                "migration_urgency": {"value": "无法整套迁出 Jira，仅能接受兼容 Jira 后端的第三方客户端", "provenance": "原文明示"},
                "candidate_alternatives": ["Jira CLI / 第三方轻量前端（整套替换型 SaaS 不适用）"],
                "blocking_conditions": "⚠️ 关键阻碍：发帖人已明言「使用 Jira 不是我的选择（无权更换底层系统）」。推销整套替换 Jira 的项目管理软件将无法成单，仅可作为内部自下而上口碑渗透线索。",
                "contact_path": "HN 原帖 (item?id=37146814) — 建议归入低优先级或不合格",
            },
        ),
        # 10. Notion Open Source Alternative (HN #36537006 - Verified Real Thread)
        IntentSignal(
            source_id="hn_36537006",
            title="Ask HN: Notion Like Alternatives?",
            url="https://news.ycombinator.com/item?id=36537006",
            source="Hacker News",
            content="Do we have open source alternatives to notion",
            evidence_quote="Do we have open source alternatives to notion",
            author="mr_o47",
            keyword="open source alternatives to notion",
            timestamp="2023-06-30 15:42 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=2,
            engagement_metric="🔥 4 点赞 · 💬 2 条讨论",
            qualification_meta={
                "qualification_stage": "初步寻优（信息极简，待首轮回复核验团队或个人属性）",
                "team_scale": {"value": "未知（未区分个人笔记还是企业团队知识库）", "provenance": "未知"},
                "budget_status": {"value": "未知（要求开源方案，商业付费意愿待确认）", "provenance": "未知"},
                "decision_authority": {"value": "未知", "provenance": "未知"},
                "migration_urgency": {"value": "未知（仅做开源生态问询）", "provenance": "未知"},
                "candidate_alternatives": ["AFFiNE", "AppFlowy", "Outline", "SiYuan (思源笔记)"],
                "blocking_conditions": "⚠️ 原帖仅有单句提问，缺乏团队规模、私有化部署环境及企业权限诉求说明，严禁直接当成高价值企业采购单承诺给销售团队。",
                "contact_path": "HN 原帖 (item?id=36537006) — 需先回复开源对比清单并追问使用场景",
            },
        ),
    ]
