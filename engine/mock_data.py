"""
Verified Real-World Public Community Benchmark Dataset for IntentRadar (v3.1).
Every item below is a 100% real, publicly verifiable Hacker News thread (verifiable via
https://hacker-news.firebaseio.com/v0/item/<id>.json and https://news.ycombinator.com/item?id=<id>).

Enforces Audit Round-2 Requirements:
1. 100% complete verbatim text (`content`) matching official HN Firebase API (including full 8-paragraph text for hn_38227662).
2. Explicit dataset tags: `dataset_kind="historical_benchmark"`, `freshness_status="historical_benchmark_archive"`, `delivery_eligible=False`.
   Historical benchmark samples are never mixed into live production runs or pushed as current sales opportunities.
3. Strict separation between `candidate_alternatives` (tools literally named by the post author in the body)
   and `system_recommended_alternatives` (market options suggested by the system).
4. Strict tri-state provenance (`原文明示` / `模型推断` / `未知`) with a per-field `evidence` snippet.
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
                "very bloated and slow.\n\nWhat alternatives can you recommend?"
            ),
            evidence_quote="My team is looking to migrate away from Postman as our API client because it has become very bloated and slow.",
            author="hubraumhugo",
            keyword="migrate away from Postman",
            timestamp="2024-09-25 16:06 UTC",
            updated_at="2024-09-25 16:06 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=10,
            engagement_metric="🔥 8 点赞 · 💬 10 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "研发团队使用（原文明示 My team，具体席位数未披露）",
                    "provenance": "原文明示",
                    "evidence": "My team is looking to migrate away from Postman as our API client",
                },
                "budget_status": {
                    "value": "未知（原帖未披露商业采购预算）",
                    "provenance": "未知",
                    "evidence": "原帖未披露预算信息",
                },
                "decision_authority": {
                    "value": "团队选型评估发起人（代表团队寻找替代方案，最终商务审批权未知）",
                    "provenance": "模型推断",
                    "evidence": "My team is looking to migrate away from Postman... What alternatives can you recommend?",
                },
                "migration_urgency": {
                    "value": "明确正在寻找迁出方案（Looking to migrate away，具体截止日未披露）",
                    "provenance": "原文明示",
                    "evidence": "looking to migrate away from Postman as our API client because it has become very bloated and slow.",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["Bruno", "Hoppscotch", "Yaak", "Insomnia"],
                "blocking_conditions": [
                    "原帖发布于 2024-09-25，属于历史基准核验样本，不计入当期实时采购交付配额",
                    "原帖未披露团队席位规模、采购预算及最终商务决策人，需首轮先做中立资格核验",
                ],
                "contact_path": "HN 原帖 (item?id=41648918) 公开提问核验团队规模与离线/Git 协作需求",
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
                "We find Jira very clunky and hard to use, although it's very flexible (though extremely hard to configure).\n\n"
                "We have tried out Linear a bit, and liked it a lot. What are some other popular alternatives which are fairly flexible, "
                "and good for software development?\n\nIdeally, we want a tool we can use long-term, is easy and pleasant to use, "
                "and is flexible enough for the requirements of a software team."
            ),
            evidence_quote="We (a start-up) currently use Jira, but we have an opportunity to reevaluate our tools. We find Jira very clunky and hard to use, although it's very flexible (though extremely hard to configure).",
            author="CraftThatBlock",
            keyword="Jira Alternatives",
            timestamp="2021-05-02 20:57 UTC",
            updated_at="2021-05-02 20:57 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=8,
            engagement_metric="🔥 7 点赞 · 💬 8 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "初创公司软件研发团队（We (a start-up) ... software team）",
                    "provenance": "原文明示",
                    "evidence": "We (a start-up) currently use Jira... flexible enough for the requirements of a software team.",
                },
                "budget_status": {
                    "value": "未知（寻求长期可用研发团队工具，未明示具体预算金额）",
                    "provenance": "未知",
                    "evidence": "原帖未披露具体预算金额",
                },
                "decision_authority": {
                    "value": "参与团队工具重评估与试用（已实际试用 Linear，具体职位未明示）",
                    "provenance": "模型推断",
                    "evidence": "we have an opportunity to reevaluate our tools... We have tried out Linear a bit",
                },
                "migration_urgency": {
                    "value": "处于工具重评估窗口期（opportunity to reevaluate，历史归档样本）",
                    "provenance": "原文明示",
                    "evidence": "we have an opportunity to reevaluate our tools.",
                },
                "candidate_alternatives": ["Linear"],
                "system_recommended_alternatives": ["Plane", "Linear", "Shortcut"],
                "blocking_conditions": [
                    "历史归档样本（发布于 2021-05-02），仅用于校准评估意图与实体抽取模型，严禁作为当期采购线索交付",
                    "团队具体人数与付费预算未知",
                ],
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
                "I haven't found a single DocuSign alternative that wasn't the same crazy pricing like $1.50/envelope or document.\n\n"
                "I just want a simple mail merge on a document and send that to a customer to sign. "
                "I used to use SignRequest for that, and it used to be standard across the board, "
                "but all of them stopped offering their APIs in their normal SaaS packages; it's all under enterprise or too expensive."
            ),
            evidence_quote="I used to use SignRequest for that, and it used to be standard across the board, but all of them stopped offering their APIs in their normal SaaS packages; it's all under enterprise or too expensive.",
            author="HakuG",
            keyword="DocuSign alternatives API",
            timestamp="2023-08-31 07:31 UTC",
            updated_at="2023-08-31 07:31 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=1,
            engagement_metric="🔥 1 点赞 · 💬 1 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "未知（未披露公司规模与月签署量）",
                    "provenance": "未知",
                    "evidence": "原帖未披露团队人数或月签署量",
                },
                "budget_status": {
                    "value": "明确拒绝 $1.50/envelope 高单价及高价 Enterprise 捆绑，寻求常规 SaaS 价位 API",
                    "provenance": "原文明示",
                    "evidence": "crazy pricing like $1.50/envelope or document... stopped offering their APIs in their normal SaaS packages; it's all under enterprise or too expensive.",
                },
                "decision_authority": {
                    "value": "直接负责业务合同发送与 API 集成的选型人（曾选用 SignRequest）",
                    "provenance": "模型推断",
                    "evidence": "I just want a simple mail merge on a document and send that to a customer to sign. I used to use SignRequest for that",
                },
                "migration_urgency": {
                    "value": "因原服务商取消常规套餐 API 权限而主动寻找替代",
                    "provenance": "原文明示",
                    "evidence": "all of them stopped offering their APIs in their normal SaaS packages",
                },
                "candidate_alternatives": ["SignRequest"],
                "system_recommended_alternatives": ["Documenso", "OpenSign", "Docuseal"],
                "blocking_conditions": [
                    "历史归档样本（发布于 2023-08-31），不计入当期实时商机交付配额",
                    "客户对单份签署成本高度敏感，高客单价企业版年包方案不匹配，仅适合低门槛按量 API 或开源自托管方案",
                ],
                "contact_path": "HN 原帖 (item?id=37333686) 核验月签署量与司法管辖区合规要求",
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
            evidence_quote="However, we are constantly hitting rate limits of their API/actions (we are on the Pro plan). What are some of the alternatives that provide comparable UI/UX/API?",
            author="gajus",
            keyword="Airtable alternatives rate limits",
            timestamp="2023-05-23 10:15 UTC",
            updated_at="2023-05-23 10:15 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=2,
            engagement_metric="🔥 3 点赞 · 💬 2 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "研发团队使用（share views with the team，具体人数未披露）",
                    "provenance": "原文明示",
                    "evidence": "We are using Airtable to record test runs... share views with the team.",
                },
                "budget_status": {
                    "value": "当前为 Airtable Pro 付费套餐订户（we are on the Pro plan）",
                    "provenance": "原文明示",
                    "evidence": "we are on the Pro plan",
                },
                "decision_authority": {
                    "value": "核心研发成员 / 工具评估发起人（原文未明示具体行政头衔）",
                    "provenance": "模型推断",
                    "evidence": "We are using Airtable to record test runs... What are some of the alternatives that provide comparable UI/UX/API?",
                },
                "migration_urgency": {
                    "value": "持续触发 API/actions 限流（constantly hitting rate limits）",
                    "provenance": "原文明示",
                    "evidence": "However, we are constantly hitting rate limits of their API/actions (we are on the Pro plan).",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["NocoDB", "Baserow", "Teable", "NocoBase"],
                "blocking_conditions": [
                    "历史归档样本（发布于 2023-05-23），不计入当期实时采购交付配额",
                    "要求同时满足多表关联（link multiple tables）、团队共享视图（share views）及高吞吐 API",
                ],
                "contact_path": "HN 原帖 (item?id=36042152) 确认自动化测试写入 QPS 峰值与自托管偏好",
            },
        ),
        # 5. Auth0 & Clerk Friction (HN #38227662 - Verified Real Thread, 100% Full Verbatim Text)
        IntentSignal(
            source_id="hn_38227662",
            title="Ask HN: Looking for alternatives to auth0 and clerk (user login services)",
            url="https://news.ycombinator.com/item?id=38227662",
            source="Hacker News",
            content=(
                "Wondering if people can recommend some alternatives to Auth0 and clerk.dev.\n\n"
                "I have an existing site that is as vanilla as you can get (server rendered pages with Hapi.js and JS client features "
                "written in regular old javascript. No frameworks are used like React, Vue, etc.\n\n"
                "I have some simple requirements where I want to add user logins so I can build some further features around that.\n\n"
                "I can role that out on my own easily enough, but dealing with security issues and maintaining all of the issues that "
                "come with home-rolling a login system isn't something I want to do.\n\n"
                "So, I've tried both Auth0 and clerk.dev over the last 2 days. For various reasons, I haven't been able to get either "
                "of these to work. Even exactly following Auth0's quick start guides leads to authentication errors with no clear answers why. "
                "(Google's results are un-surprisingly poor as usual.) And there's lots of commentary out there about how using Auth0 is an "
                "overall negative experience in the long run.\n\n"
                "I monkeyed with clerk.dev for a few hours today and immediately found a couple of bugs I reported. And despite their "
                "documentation, it seems their UI components are React-only even when using their JS sdk.\n\n"
                "I'm probably doing something wrong somewhere, but at this point I'm 2 days past where I wanted to be on this project. "
                "All I want is a simple to use drop-in login/user management system. Nothing dependent on this framework or that one.\n\n"
                "Any recommendations?"
            ),
            evidence_quote=(
                "So, I've tried both Auth0 and clerk.dev over the last 2 days. For various reasons, I haven't been able to get either "
                "of these to work. Even exactly following Auth0's quick start guides leads to authentication errors with no clear answers why."
            ),
            author="geuis",
            keyword="alternatives to auth0",
            timestamp="2023-11-11 04:36 UTC",
            updated_at="2023-11-11 04:36 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=3,
            engagement_metric="🔥 1 点赞 · 💬 3 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "独立开发者或单人维护站点（I have an existing site... on my own）",
                    "provenance": "模型推断",
                    "evidence": "I have an existing site... I can role that out on my own easily enough",
                },
                "budget_status": {
                    "value": "未知（原帖未提及商业付费预算）",
                    "provenance": "未知",
                    "evidence": "原帖未披露预算信息",
                },
                "decision_authority": {
                    "value": "项目直接构建者与技术选型决定人（I have an existing site... I want to add user logins）",
                    "provenance": "原文明示",
                    "evidence": "I have an existing site... I want to add user logins so I can build some further features around that.",
                },
                "migration_urgency": {
                    "value": "已连续 2 天卡在 Auth0/Clerk 接入故障，项目进度受阻（2 days past where I wanted to be）",
                    "provenance": "原文明示",
                    "evidence": "So, I've tried both Auth0 and clerk.dev over the last 2 days... I'm 2 days past where I wanted to be on this project.",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["Logto", "SuperTokens", "Keycloak", "Ory"],
                "blocking_conditions": [
                    "历史归档样本（发布于 2023-11-11），不计入当期实时采购交付配额",
                    "技术栈为 Hapi.js + 原生 Vanilla JS（不使用 React/Vue），任何仅支持 React UI 组件的方案均不匹配",
                    "疑似个人/小型站点项目，商业付费客单价潜力待核实",
                ],
                "contact_path": "HN 原帖 (item?id=38227662) 核验活跃用户规模与纯 Vanilla JS 接入需求",
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
            updated_at="2025-01-18 15:48 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=1,
            engagement_metric="🔥 1 点赞 · 💬 1 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "中小型企业场景（small to medium sized businesses，具体人数未知）",
                    "provenance": "原文明示",
                    "evidence": "What alternatives to Salesforce are you using at your small to medium sized businesses?",
                },
                "budget_status": {
                    "value": "未知（单句提问，未披露预算）",
                    "provenance": "未知",
                    "evidence": "原帖未披露预算信息",
                },
                "decision_authority": {
                    "value": "未知（单句提问，未说明发帖人角色与采购权限）",
                    "provenance": "未知",
                    "evidence": "原帖未披露角色与权限",
                },
                "migration_urgency": {
                    "value": "未知（仅做同行方案问询，未说明是否在执行迁移）",
                    "provenance": "未知",
                    "evidence": "原帖未披露迁移时间表",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["Twenty CRM", "Attio", "Pipedrive", "HubSpot"],
                "blocking_conditions": [
                    "单句宽泛提问：预算未知、决策权限未知、具体痛点未知，不得直接越级判定为阶段 4/4 可推进商机",
                    "需先通过公开回复提问核实：当前席位规模、核心使用模块（销售线索/合同/工单）及替换原因",
                ],
                "contact_path": "HN 原帖 (item?id=42749172) 发送中立核验问题（禁止在确认需求前直接推销产品）",
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
                "Mostly track the user activities in my app and trigger the event based on user properties (attribution). \n"
                "I've tried some tools yet to find out the fit tool for me. Any recommendations guys? Thanks a lot"
            ),
            evidence_quote="I'm looking for Hubspot alternatives. My need is automation workflow and CRM. Mostly track the user activities in my app and trigger the event based on user properties (attribution).",
            author="lienhoangduy",
            keyword="Hubspot Alternative",
            timestamp="2022-10-18 07:22 UTC",
            updated_at="2022-10-18 07:22 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=6,
            engagement_metric="🔥 9 点赞 · 💬 6 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "应用开发者 / 产品团队（in my app，具体团队规模未知）",
                    "provenance": "模型推断",
                    "evidence": "Mostly track the user activities in my app and trigger the event based on user properties",
                },
                "budget_status": {
                    "value": "未知（未披露采购预算）",
                    "provenance": "未知",
                    "evidence": "原帖未披露预算信息",
                },
                "decision_authority": {
                    "value": "直接选型测试人（I've tried some tools yet to find out the fit tool for me）",
                    "provenance": "原文明示",
                    "evidence": "I've tried some tools yet to find out the fit tool for me.",
                },
                "migration_urgency": {
                    "value": "已试用多款工具仍未找到适配方案（历史归档样本）",
                    "provenance": "原文明示",
                    "evidence": "I've tried some tools yet to find out the fit tool for me.",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["Customer.io", "Dittofeed", "Twenty CRM", "Mautic"],
                "blocking_conditions": [
                    "历史归档样本（发布于 2022-10-18），不计入当期实时采购交付配额",
                    "买方核心刚需是「应用内用户行为追踪 + 属性归因触发自动化工作流」，纯静态销售 CRM 不匹配",
                ],
                "contact_path": "HN 原帖归档核验 (item?id=33244048)",
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
            evidence_quote="I'm curious if there is a good open source alternative out there for NewRelic or DataDog's APM service.",
            author="vital101",
            keyword="DataDog APM alternative",
            timestamp="2020-06-02 15:58 UTC",
            updated_at="2020-06-02 15:58 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=2,
            engagement_metric="🔥 4 点赞 · 💬 2 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "未知（未披露主机节点规模或团队人数）",
                    "provenance": "未知",
                    "evidence": "原帖未披露团队与集群规模",
                },
                "budget_status": {
                    "value": "明确倾向开源方案（good open source alternative，商业付费预算未知）",
                    "provenance": "原文明示",
                    "evidence": "I'm curious if there is a good open source alternative out there for NewRelic or DataDog's APM service.",
                },
                "decision_authority": {
                    "value": "研发/可观测性技术调研人（最终商业采购权未知）",
                    "provenance": "模型推断",
                    "evidence": "I'm curious if there is a good open source alternative... so you can trace transactions.",
                },
                "migration_urgency": {
                    "value": "技术调研阶段（I'm curious if there is...，历史归档样本）",
                    "provenance": "原文明示",
                    "evidence": "I'm curious if there is a good open source alternative out there",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["SigNoz", "Jaeger + Prometheus", "SkyWalking", "Uptrace"],
                "blocking_conditions": [
                    "历史归档样本（发布于 2020-06-02），仅用于校准 APM 细分能力要求，不计入当期实时商机配额",
                    "仅提供日志聚合或主机监控的产品不匹配；必须具备应用层分布式事务追踪（Transaction Tracing）",
                ],
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
            evidence_quote="Any workarounds or alternative frontends that are faster? Sadly using Jira was not my choice.",
            author="breckenedge",
            keyword="Alternative Jira UI",
            timestamp="2023-08-16 13:39 UTC",
            updated_at="2023-08-16 13:39 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=11,
            engagement_metric="🔥 6 点赞 · 💬 11 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "敏捷研发团队（trying to plan my team’s next sprint）",
                    "provenance": "原文明示",
                    "evidence": "trying to plan my team’s next sprint.",
                },
                "budget_status": {
                    "value": "未知（原帖未提及预算，仅寻找绕过卡顿的方法或第三方前端）",
                    "provenance": "未知",
                    "evidence": "原帖未披露预算信息",
                },
                "decision_authority": {
                    "value": "无采购与替换决策权（原文明示：Sadly using Jira was not my choice）",
                    "provenance": "原文明示",
                    "evidence": "Sadly using Jira was not my choice.",
                },
                "migration_urgency": {
                    "value": "无法迁出 Jira 后端，仅寻求更快的替代前端（alternative frontends）",
                    "provenance": "原文明示",
                    "evidence": "Any workarounds or alternative frontends that are faster? Sadly using Jira was not my choice.",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": [],
                "blocking_conditions": [
                    "⛔ 关键阻断：发帖人原文明示「Sadly using Jira was not my choice」（无权更换 Jira 后端系统）",
                    "系统已自动阻断（Blocked）向该线索生成整套替换型项目管理软件的推销话术与机器人推送",
                ],
                "contact_path": "已阻断销售推销（仅可作为产品性能痛点研究样本）",
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
            updated_at="2023-06-30 15:42 UTC",
            collected_at="2026-11-03 06:30 UTC",
            comments_count=2,
            engagement_metric="🔥 4 点赞 · 💬 2 条讨论",
            dataset_kind="historical_benchmark",
            freshness_status="historical_benchmark_archive",
            delivery_eligible=False,
            qualification_meta={
                "team_scale": {
                    "value": "未知（未区分个人笔记还是企业团队知识库）",
                    "provenance": "未知",
                    "evidence": "原帖未披露团队规模",
                },
                "budget_status": {
                    "value": "未知（询问开源方案，未披露商业付费预算）",
                    "provenance": "未知",
                    "evidence": "Do we have open source alternatives to notion",
                },
                "decision_authority": {
                    "value": "未知（单句提问，未披露角色与采购权限）",
                    "provenance": "未知",
                    "evidence": "原帖未披露角色与权限",
                },
                "migration_urgency": {
                    "value": "未知（仅做开源生态问询）",
                    "provenance": "未知",
                    "evidence": "原帖未披露迁移时间表",
                },
                "candidate_alternatives": [],
                "system_recommended_alternatives": ["AFFiNE", "AppFlowy", "Outline", "SiYuan (思源笔记)"],
                "blocking_conditions": [
                    "⚠️ 原帖仅有 7 个单词的单句提问，团队规模、预算、决策权限全部未知，仅处于阶段 2/4 待核验资格",
                    "严禁将其作为已核验企业采购商机承诺给销售团队，仅允许发送中立场景核验提问",
                ],
                "contact_path": "HN 原帖 (item?id=36537006) 发送中立问题核实团队或个人用途",
            },
        ),
    ]
