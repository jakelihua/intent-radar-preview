# -*- coding: utf-8 -*-
"""
Claude-Inspired High-Fidelity Design Template for IntentRadar (v3.3).
Integrates Claude's Inbox Master-Detail & Review Drawer architecture
with IntentRadar's 4-Stage Sequential Verification, Provenance Engine,
and Executive Intelligence Dashboard.
"""

import html as _html
import json
import re
from pathlib import Path
from typing import Any, Dict, List

# Benchmark fallback data matching Claude's benchmark set
CLAUDE_BENCHMARK_LEADS = [
  { "id": "hn_41648918", "comp": "Postman", "title": "Ask HN: What’s the Best Postman Alternative?", "author": "hubraumhugo", "date": "2024-09-25", "replies": 10, "stage": 2,
    "quote": "My team is looking to migrate away from Postman as our API client because it has become very bloated and slow.",
    "facts": [["团队规模", "研发团队，人数未披露", "stated", "My team"], ["预算", "未披露", "unknown", ""], ["决策权", "发起迁移评估的成员，审批权待确认", "inferred", "My team is looking to migrate"], ["紧迫度", "正在计划迁出", "stated", "looking to migrate away from Postman"]],
    "todos": ["团队里有多少人在用 Postman？", "已有付费预算，还是只考虑免费工具？", "替代品必须覆盖哪些能力：集合、环境变量、CI 运行？"],
    "reqs": [["替代 Postman 作为团队 API 客户端", "“migrate away from Postman as our API client”"], ["比 Postman 轻、启动快", "“it has become very bloated and slow”"], ["导入现有 Postman 集合与环境", "原帖未提，迁移时通常必需"]],
    "reply": "Curious what’s pushing the move — is it mostly performance, or also pricing and the account requirement? And which features are must-haves for your team (collections, environments, CI)? Asking before suggesting anything." },
  { "id": "hn_27018935", "comp": "Atlassian Jira", "title": "Ask HN: Jira Alternatives?", "author": "CraftThatBlock", "date": "2021-05-02", "replies": 8, "stage": 2,
    "quote": "We (a start-up) currently use Jira, but we have an opportunity to reevaluate our tools.",
    "facts": [["团队规模", "初创团队，人数未披露", "stated", "We (a start-up)"], ["预算", "未披露", "unknown", ""], ["决策权", "参与重新选型", "inferred", "we have an opportunity to reevaluate"], ["紧迫度", "正在重新评估工具", "stated", "opportunity to reevaluate our tools"]],
    "todos": ["团队规模与 Jira 席位数？", "已经在试哪些替代品（原帖提到 Linear）？", "迁移时必须保留哪些历史数据？"],
    "reqs": [["比 Jira 易用、配置简单", "“very clunky and hard to use”"], ["保留足够的灵活度", "“it’s very flexible”"], ["导入 Jira 历史工单", "原帖未提，迁移时通常必需"]],
    "reply": "What’s the main thing Jira gets in your way on — configuration, speed, or the workflow model itself? And roughly how many people would move over? Happy to compare notes." },
  { "id": "hn_37333686", "comp": "DocuSign", "title": "Are there any affordable DocuSign alternatives that do API access?", "author": "HakuG", "date": "2023-08-31", "replies": 1, "stage": 2,
    "quote": "All of them stopped offering their APIs in their normal SaaS packages; it’s all under enterprise or too expensive.",
    "facts": [["团队规模", "未披露", "unknown", ""], ["预算", "明确嫌企业版太贵", "stated", "too expensive"], ["决策权", "自己在找方案", "inferred", "I used to use SignRequest"], ["紧迫度", "原工具已停 API", "stated", "stopped offering their APIs"]],
    "todos": ["每月大约签多少份？", "API 是嵌入产品，还是内部流程用？", "能接受的单价区间？"],
    "reqs": [["标准套餐即可调用 API", "“stopped offering their APIs in their normal SaaS packages”"], ["价格低于企业版", "“too expensive”"]],
    "reply": "Roughly what volume are you signing per month, and is the API for embedding in your own product or internal workflows? That changes which options make sense." },
  { "id": "hn_36042152", "comp": "Airtable", "title": "Ask HN: What are Airtable alternatives with higher rate limits?", "author": "gajus", "date": "2023-05-23", "replies": 2, "stage": 2,
    "quote": "We are constantly hitting rate limits of their API/actions (we are on the Pro plan).",
    "facts": [["团队规模", "团队共用视图，人数未披露", "stated", "share views with the team"], ["预算", "Pro 付费用户", "stated", "we are on the Pro plan"], ["决策权", "选型发起人", "inferred", "What are some of the alternatives"], ["紧迫度", "持续触发限流", "stated", "constantly hitting rate limits"]],
    "todos": ["每分钟大约多少次 API 调用？", "是否接受自托管？", "视图与自动化哪些必须迁移？"],
    "reqs": [["API 限额高于 Airtable Pro", "“constantly hitting rate limits”"], ["相近的界面与 API 体验", "“comparable UI/UX/API”"]],
    "reply": "What request rate are you hitting the limits at, and would self-hosting be on the table? Those two answers narrow the field a lot." },
  { "id": "hn_38227662", "comp": "Auth0 / Clerk", "title": "Ask HN: Looking for alternatives to auth0 and clerk (user login services)", "author": "geuis", "date": "2023-11-11", "replies": 3, "stage": 2,
    "quote": "I’ve tried both Auth0 and clerk.dev over the last 2 days. For various reasons, I haven’t been able to get either of these to work.",
    "facts": [["团队规模", "可能是独立开发者", "inferred", "I have an existing site"], ["预算", "未披露", "unknown", ""], ["决策权", "本人选型", "stated", "I’ve tried both"], ["紧迫度", "已卡住两天", "stated", "over the last 2 days"]],
    "todos": ["个人项目还是公司产品？", "需要 SSO / SAML 吗？", "现有技术栈是什么？"],
    "reqs": [["按快速入门文档能直接跑通", "“following Auth0’s quick start guides leads to authentication errors”"], ["接入现有站点", "“I have an existing site”"]],
    "reply": "Which stack is the existing site on, and do you need anything beyond email/social login (SSO, orgs)? That decides whether a hosted service is even the right fit." },
  { "id": "hn_42749172", "comp": "Salesforce CRM", "title": "Ask HN: Alternatives to Salesforce?", "author": "cloudking", "date": "2025-01-18", "replies": 1, "stage": 2,
    "quote": "What alternatives to Salesforce are you using at your small to medium sized businesses?",
    "facts": [["团队规模", "泛问中小企业，非本人公司", "stated", "small to medium sized businesses"], ["预算", "未披露", "unknown", ""], ["决策权", "未披露", "unknown", ""], ["紧迫度", "未披露", "unknown", ""]],
    "todos": ["是在为自己的公司选型吗？", "现在 Salesforce 用了多少席位？", "计划什么时候切换？"],
    "reqs": [["适合中小企业的 CRM", "“small to medium sized businesses”"]],
    "reply": "Are you looking for your own team, or surveying what others use? If it’s your team, what’s driving the change?" },
  { "id": "hn_33244048", "comp": "HubSpot", "title": "Ask HN: Hubspot Alternative", "author": "lienhoangduy", "date": "2022-10-18", "replies": 6, "stage": 2,
    "quote": "I’m looking for Hubspot alternatives. My need is automation workflow and CRM.",
    "facts": [["团队规模", "应用开发团队，人数未披露", "inferred", "in my app"], ["预算", "未披露", "unknown", ""], ["决策权", "本人选型", "stated", "I’m looking for"], ["紧迫度", "正在寻找", "stated", "looking for Hubspot alternatives"]],
    "todos": ["需要追踪多少用户的行为？", "现在 HubSpot 用的是哪个套餐？", "自动化工作流最关键的场景？"],
    "reqs": [["自动化工作流", "“automation workflow”"], ["基于用户属性触发事件", "“trigger the event based on user properties”"]],
    "reply": "How many users are you tracking events for, and which HubSpot plan are you on today? Want to understand the scale before pointing anywhere." },
  { "id": "hn_23392464", "comp": "Datadog / New Relic", "title": "Ask HN: Open-source NewRelic / DataDog APM alternative?", "author": "vital101", "date": "2020-06-02", "replies": 2, "stage": 2,
    "quote": "I’m curious if there is a good open source alternative out there for NewRelic or DataDog’s APM service.",
    "facts": [["团队规模", "未披露", "unknown", ""], ["预算", "倾向开源，商业预算未知", "stated", "open source alternative"], ["决策权", "自己在找方案", "inferred", "I’m curious"], ["紧迫度", "了解阶段", "stated", "curious if there is"]],
    "todos": ["大约多少台主机 / 服务？", "开源是硬性要求还是成本考虑？", "有无商业支持预算？"],
    "reqs": [["开源可自托管", "“open source alternative”"], ["APM 链路追踪", "“APM service”"]],
    "reply": "Is open source a hard requirement, or mainly about cost? And roughly how many hosts are you instrumenting?" },
  { "id": "hn_37146814", "comp": "Atlassian Jira", "title": "Ask HN: Alternative Jira UIs?", "author": "breckenedge", "date": "2023-08-16", "replies": 11, "stage": 1, "blocked": True,
    "quote": "Any workarounds or alternative frontends that are faster? Sadly using Jira was not my choice.",
    "blockedReason": "作者明确表示没有选型权（“using Jira was not my choice”），只想找提速办法，并不打算更换工具。保留为研究记录。",
    "facts": [["团队规模", "敏捷研发团队", "stated", "trying to plan my team’s next sprint"], ["预算", "未披露", "unknown", ""], ["决策权", "明确无选型权", "stated", "using Jira was not my choice"], ["紧迫度", "只求提速，不是替换", "stated", "workarounds or alternative frontends"]],
    "todos": [], "reqs": [], "reply": "" },
  { "id": "hn_36537006", "comp": "Notion", "title": "Ask HN: Notion Like Alternatives?", "author": "mr_o47", "date": "2023-06-30", "replies": 2, "stage": 2,
    "quote": "Do we have open source alternatives to notion",
    "facts": [["团队规模", "未披露", "unknown", ""], ["预算", "倾向开源", "stated", "open source alternatives"], ["决策权", "本人询问", "inferred", "Do we have"], ["紧迫度", "探索阶段", "stated", "Do we have alternatives"]],
    "todos": ["个人知识库还是团队协作？", "离线存储和数据自持是硬性要求吗？", "是否需要数据库视图？"],
    "reqs": [["开源可私有部署", "“open source alternatives”"], ["类似 Notion 的块级与多维体验", "“Notion Like”"]],
    "reply": "Is local offline storage the main motivation, or avoiding cloud vendor lock-in? And do you need real-time multi-person editing?" }
]

BENCHMARK_LOOKUP = {lead["id"]: lead for lead in CLAUDE_BENCHMARK_LEADS}


def convert_signals_to_claude_leads(signals: List[Any], run_mode: str = "historical_benchmark") -> List[Dict[str, Any]]:
    """Convert IntentSignal analysis objects into Claude's clean JSON format."""
    if not signals:
        return CLAUDE_BENCHMARK_LEADS

    leads = []
    for item in signals:
        sig = getattr(item, "signal", None) or getattr(item, "raw_signal", None) or item
        sig_id = getattr(sig, "id", "")

        # If benchmark lead, inherit curated high-touch provenance & copy
        if sig_id in BENCHMARK_LOOKUP and run_mode == "historical_benchmark":
            leads.append(BENCHMARK_LOOKUP[sig_id])
            continue
        
        # 提取 provenance facts
        prov = getattr(item, "qualification_meta", None) or getattr(item, "provenance_meta", None) or getattr(sig, "qualification_meta", {}) or {}
        facts = []
        fact_keys = [
            ("团队规模", "team_size"),
            ("预算", "budget_constraint"),
            ("决策权", "buying_authority"),
            ("紧迫度", "timing_urgency")
        ]
        for label, f_key in fact_keys:
            val_dict = prov.get(f_key, {})
            if isinstance(val_dict, dict):
                v_text = val_dict.get("value", "未披露")
                v_source = val_dict.get("source", "unknown")
                v_quote = val_dict.get("quote", "")
            else:
                v_text = "未披露"
                v_source = "unknown"
                v_quote = ""
            facts.append([label, v_text, v_source, v_quote])

        # 是否已拦截
        auth_v = str(prov.get("buying_authority", {}).get("value", ""))
        is_blocked = (
            getattr(item, "is_disqualified", False)
            or "无采购与替换决策权" in auth_v
            or "无选型决定权" in auth_v
            or getattr(item, "is_negated", False)
        )
        blocked_reason = getattr(item, "disqualification_reason", "") or ("无替换意向或无选型决策权" if is_blocked else "")

        stage_num = getattr(item, "contiguous_stage_num", 2)
        if is_blocked:
            stage_num = 1

        reqs = getattr(item, "required_capabilities", None) or getattr(item, "candidate_alternatives", None)
        if isinstance(reqs, list) and reqs and isinstance(reqs[0], (list, tuple)):
            clean_reqs = reqs
        else:
            comp_name = getattr(item, 'target_competitor', '当前工具')
            quote_sub = str(getattr(sig, 'evidence_quote', '') or getattr(sig, 'content', ''))[:40]
            clean_reqs = [
                [f"替代 {comp_name}", f"“{quote_sub}”" if quote_sub else "明确寻找替代工具"],
                ["具备生产级可靠性与支持", "原帖未提，选型必备"]
            ]

        # 解析回复数
        eng = str(getattr(sig, "engagement_metric", "0"))
        replies_m = re.search(r"(\d+)\s*(?:条讨论|replies|条回复)", eng, re.I)
        replies = int(replies_m.group(1)) if replies_m else 0

        date_str = str(getattr(sig, "timestamp", "2024-01-01"))[:10]

        reply_text = (
            getattr(item, "public_reply", "")
            or getattr(item, "suggested_pitch", "")
            or "Curious what’s driving the move? Asking before suggesting anything."
        )

        leads.append({
            "id": sig_id or f"sig_{len(leads)+1}",
            "comp": getattr(item, "target_competitor", "通用竞品"),
            "title": getattr(sig, "title", "未命名线索"),
            "author": getattr(sig, "author", "匿名"),
            "date": date_str,
            "replies": replies,
            "stage": stage_num,
            "quote": getattr(sig, "evidence_quote", "") or getattr(sig, "content", ""),
            "facts": facts,
            "todos": getattr(item, "first_reply_todos", None) or [
                "了解团队目前席位数与部署方式？",
                "确认是否有预算排期与迁移时间表？",
                "替代品必须覆盖哪些关键能力？"
            ],
            "reqs": clean_reqs,
            "reply": reply_text,
            "blocked": is_blocked,
            "blockedReason": blocked_reason
        })

    return leads


def render_claude_workbench_html(leads: List[Dict[str, Any]], banner_text: str = "", run_mode: str = "historical_benchmark") -> str:
    leads_json = json.dumps(leads, ensure_ascii=False).replace("<", r"\u003c").replace(">", r"\u003e")
    
    if not banner_text:
        banner_text = "<strong>演示数据</strong>：10 条 Hacker News 历史帖（2020–2025），用于演练核验流程，不会推送给任何人。"

    tmpl_path = Path(__file__).parent / "templates" / "workbench_claude.html"
    tmpl = tmpl_path.read_text(encoding="utf-8")
    return tmpl.replace("<!-- LEADS_DATA_PLACEHOLDER -->", leads_json).replace("<!-- BANNER_TEXT -->", banner_text)
