"""
Dispatcher module for IntentRadar (v3.1).
Generates:
1. Public Client-Facing Verification Workbench (`report.html` / `index.html`) — 100% free of internal BD playbooks.
2. Standalone Internal BD & Pilot Operations Playbook — written by default to an isolated non-public directory
   (`/tmp/intent_radar_internal/internal_bd_ops.html`) so deployment workflows uploading the repo never leak internal docs.
3. Policy-Gated & Version-Deduplicated Webhook Dispatch (`send_feishu_card`, `send_wechat_markdown`):
   - Enforces `delivery_eligible == True` (blocks historical benchmark samples from live push)
   - Enforces `outreach_policy.policy_status != 'blocked'` (blocks no-authority / negative / cross-category leads)
   - Enforces `IntentStateStore.should_deliver(...)` & `record_delivery(...)` so unchanged threads are never re-pushed.
"""

import html as _html
import json
import logging
import os
import re
import tempfile
import urllib.parse
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional
import requests
from .analyzer import EnrichedSignal
from .compiled_css import COMPILED_TAILWIND_CSS
from .frontend_assets import get_full_client_js, render_internal_bd_html
from .growth_playbook import (
    get_brand_presets,
    get_launch_campaigns,
    get_pilot_offers,
    get_seed_clients,
)
from .state_store import IntentStateStore
from .policy import evaluate_facts, safe_contact

logger = logging.getLogger("Dispatcher")


def escape_webhook_markdown(raw: str) -> str:
    """
    Neutralizes untrusted community strings before embedding into Feishu `lark_md` or WeChat `markdown`.
    Prevents:
    - `<at id=all></at>` or HTML/XML tag injection
    - `[钓鱼链接](https://evil.example)` markdown link spoofing
    - Formatting breakout via `*`, `_`, `` ` ``, `~`, or newlines
    """
    if not raw:
        return ""
    cleaned = str(raw).replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    cleaned = cleaned.replace("[", "【").replace("]", "】").replace("(", "（").replace(")", "）")
    cleaned = cleaned.replace("`", "＇").replace("*", "＊").replace("~", "～")
    return cleaned.strip()


def _make_brand_svg_data_uri(bg_color: str, label: str) -> str:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<rect width="24" height="24" rx="6" fill="{bg_color}"/>'
        f'<text x="12" y="16.5" text-anchor="middle" fill="#ffffff" '
        f'font-family="Inter, -apple-system, sans-serif" font-weight="800" font-size="11">{label}</text>'
        f'</svg>'
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


COMPETITOR_LOGOS = {
    "jira": _make_brand_svg_data_uri("#0052CC", "J"),
    "atlassian jira": _make_brand_svg_data_uri("#0052CC", "J"),
    "salesforce": _make_brand_svg_data_uri("#00A1E0", "SF"),
    "salesforce crm": _make_brand_svg_data_uri("#00A1E0", "SF"),
    "notion": _make_brand_svg_data_uri("#18181B", "N"),
    "datadog": _make_brand_svg_data_uri("#632CA6", "DD"),
    "datadog / new relic": _make_brand_svg_data_uri("#632CA6", "DD"),
    "docusign": _make_brand_svg_data_uri("#4C00FF", "DS"),
    "postman": _make_brand_svg_data_uri("#FF6C37", "PM"),
    "zendesk": _make_brand_svg_data_uri("#03363D", "ZD"),
    "auth0": _make_brand_svg_data_uri("#EB5424", "A0"),
    "auth0 / clerk": _make_brand_svg_data_uri("#EB5424", "A0"),
    "airtable": _make_brand_svg_data_uri("#18BFFF", "AT"),
    "hubspot": _make_brand_svg_data_uri("#FF7A59", "HS"),
    "slack": _make_brand_svg_data_uri("#4A154B", "SL"),
    "linear": _make_brand_svg_data_uri("#5E6AD2", "LN"),
}


class Dispatcher:
    def __init__(self, config: Dict, state_store: Optional[IntentStateStore] = None):
        self.config = config
        self.feishu_webhook = config.get("feishu_webhook")
        self.wechat_webhook = config.get("wechat_webhook")
        if (self.feishu_webhook or self.wechat_webhook) and not str(config.get("client_id", "")).strip():
            raise ValueError("Webhook delivery requires an explicit client_id")
        self.client_id = config.get("client_id", "default_pilot_client")
        self.state_store = state_store or IntentStateStore(config.get("state_db_path"))
        self._last_sent_count = 0

    def filter_deliverable_signals(self, signals: List[EnrichedSignal], channel: str = "webhook") -> List[EnrichedSignal]:
        """
        Enforces unified delivery & outreach policy gates before any webhook push:
        1. Must be `delivery_eligible == True` and `dataset_kind == 'live_production'` (never push historical benchmark samples).
        2. Must have `outreach_policy['policy_status'] != 'blocked'` and `can_outreach == True` (never push no-authority or negative leads).
        3. Must not have already been delivered at the current `version_num` to `self.client_id`.
        """
        eligible: List[EnrichedSignal] = []
        for item in signals:
            sig = item.signal
            if getattr(sig, "dataset_kind", "live_production") != "live_production":
                continue
            if not getattr(sig, "delivery_eligible", False):
                continue
            policy = evaluate_facts(item.qualification_meta.get("policy_facts", {}), self.config.get("seller_profile"))
            if not policy["allow_webhook_push"]:
                continue
            ver = int(getattr(sig, "version_num", 1))
            if not self.state_store.should_deliver(sig.source, sig.source_id, f"{self.client_id}:{channel}", ver):
                continue
            eligible.append(item)
        return eligible

    def dispatch(
        self,
        signals: List[EnrichedSignal],
        output_html_path: str = "report.html",
        internal_bd_path: Optional[str] = None,
    ) -> Dict:
        if not internal_bd_path:
            isolated_dir = os.path.join(tempfile.gettempdir(), "intent_radar_internal")
            os.makedirs(isolated_dir, exist_ok=True)
            internal_bd_path = os.path.join(isolated_dir, "internal_bd_ops.html")
        else:
            os.makedirs(os.path.dirname(os.path.abspath(internal_bd_path)), exist_ok=True)

        report_summary = {
            "total_signals": len(signals),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "feishu_status": "SKIPPED",
            "wechat_status": "SKIPPED",
            "internal_bd_path": internal_bd_path,
            "delivered_count": 0,
        }

        self.print_console_preview(signals)
        self.generate_html_report(signals, output_html_path)
        self.generate_internal_bd_report(internal_bd_path)

        if self.feishu_webhook:
            feishu_candidates = self.filter_deliverable_signals(signals, channel="feishu")[:5]
            if feishu_candidates:
                res = self.send_feishu_card(feishu_candidates)
                report_summary["feishu_status"] = "SUCCESS" if res else "FAILED"
                if res:
                    report_summary["delivered_count"] += self._last_sent_count

        if self.wechat_webhook:
            wechat_candidates = self.filter_deliverable_signals(signals, channel="wechat")[:5]
            if wechat_candidates:
                res = self.send_wechat_markdown(wechat_candidates)
                report_summary["wechat_status"] = "SUCCESS" if res else "FAILED"
                if res:
                    report_summary["delivered_count"] += self._last_sent_count

        return report_summary

    def print_console_preview(self, signals: List[EnrichedSignal]):
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("\n" + "=" * 78)
        print(f"🎯 【IntentRadar · 公开社区竞品替换信号核验台账】 ({now})")
        print(f"📊 本轮已核验信号: {len(signals)} 条 | 区分 4 步连续资格链路与三态证据来源")
        print("=" * 78 + "\n")

        if not signals:
            print("ℹ️ 本轮实时采集未发现符合条件的采购替换信号（未混入任何历史基准样本）。\n")
            return

        for idx, item in enumerate(signals[:5], 1):
            print(f"📌 【信号 #{idx}】 [{item.intent_level}]  评分: {item.intent_score}/100")
            print(f"🏢 被替换竞品: {item.target_competitor} | 原文提及候选: {', '.join(item.candidate_alternatives) or '无'}")
            print(f"👤 角色与权限: {item.buyer_persona} | 阶段: {item.qualification_stage}")
            print(f"📰 原帖标题: {item.signal.title} (ID: {item.signal.source_id})")
            print(f"🔗 原始链接: {item.signal.url}")
            print(f"💬 关键证据: “{item.signal.evidence_quote}”")
            print("-" * 78 + "\n")

    def send_feishu_card(self, top_signals: List[EnrichedSignal]) -> bool:
        eligible, claims = self._claim_signals(top_signals, "feishu")
        if not eligible:
            logger.info("No deliverable signals passed policy/freshness/version gates for Feishu push.")
            return False

        elements = []
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        elements.append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**本轮已核验 {len(eligible)} 条当期公开社区竞品替换信号（均已通过权限与门控核验）。**",
            },
        })
        elements.append({"tag": "hr"})

        for idx, item in enumerate(eligible, 1):
            policy_status = (item.outreach_policy or {}).get("policy_status", "neutral_inquiry_only")
            safe_title = escape_webhook_markdown(item.signal.title)
            safe_quote = escape_webhook_markdown(item.signal.evidence_quote)
            safe_sid = escape_webhook_markdown(item.signal.source_id)
            safe_url = item.signal.url if safe_contact(item.signal.url) else "#"
            safe_reply = escape_webhook_markdown(item.public_reply)
            card_item_md = (
                f"**#{idx} [{item.intent_level}] · 被替换竞品：{item.target_competitor}**\n"
                f"**资格阶段**：{item.qualification_stage} | **门控策略**：`{policy_status}` | **评分**：`{item.intent_score}分`\n"
                f"**原帖链接**：[{safe_title}]({safe_url}) (ID: `{safe_sid}`)\n"
                f"**原文证据**：“{safe_quote}”\n"
                f"> 💬 **合规沟通草稿**：{safe_reply}"
            )
            elements.append({"tag": "div", "text": {"tag": "lark_md", "content": card_item_md}})
            elements.append({"tag": "hr"})

        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": f"🎯 IntentRadar · 竞品替换信号核验日报 ({now})"},
                    "template": "blue",
                },
                "elements": elements,
            },
        }
        return self._post_claimed(self.feishu_webhook, card_payload, claims, "feishu", "code")

    def send_wechat_markdown(self, top_signals: List[EnrichedSignal]) -> bool:
        eligible, claims = self._claim_signals(top_signals, "wechat")
        if not eligible:
            logger.info("No deliverable signals passed policy/freshness/version gates for WeChat push.")
            return False

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        md_text = f"### 🎯 IntentRadar · 竞品替换信号核验日报 ({now})\n"
        for idx, item in enumerate(eligible, 1):
            safe_title = escape_webhook_markdown(item.signal.title)
            safe_quote = escape_webhook_markdown(item.signal.evidence_quote)
            safe_url = item.signal.url if safe_contact(item.signal.url) else "#"
            safe_reply = escape_webhook_markdown(item.public_reply)
            md_text += f"**#{idx} [{item.intent_level}]** `{item.target_competitor}`\n"
            md_text += f"- **阶段**：{item.qualification_stage} ({item.intent_score}分)\n"
            md_text += f"- **原帖**：[{safe_title}]({safe_url})\n"
            md_text += f"- **证据**：“{safe_quote}”\n"
            md_text += f"- **合规草稿**：{safe_reply}\n\n"
        payload = {"msgtype": "markdown", "markdown": {"content": md_text}}
        return self._post_claimed(self.wechat_webhook, payload, claims, "wechat", "errcode")

    def _claim_signals(self, signals, channel):
        eligible, claims = [], []
        for item in self.filter_deliverable_signals(signals, channel):
            sig = item.signal
            token = self.state_store.claim_delivery(sig.source, sig.source_id,
                f"{self.client_id}:{channel}", sig.version_num)
            if token:
                eligible.append(item)
                claims.append((sig, token))
        return eligible, claims

    def _post_claimed(self, url, payload, claims, channel, code_key):
        outcome = "uncertain"
        try:
            # No automatic HTTP retries: a timeout may mean the receiver accepted
            # the message. Outbox ownership is acquired BEFORE constructing it.
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict) and type(data.get(code_key)) is int:
                    outcome = "sent" if data[code_key] == 0 else "failed"
            elif 400 <= response.status_code < 500:
                outcome = "failed"
        except (requests.RequestException, ValueError, TypeError):
            logger.warning("Webhook result is uncertain; automatic resend disabled (%s)", channel)
        stored = True
        sent_count = 0
        for sig, token in claims:
            try:
                self.state_store.finish_delivery(sig.source, sig.source_id,
                    f"{self.client_id}:{channel}", sig.version_num, token, outcome, channel)
                if outcome == "sent":
                    sent_count += 1
            except Exception:
                stored = False
                logger.exception("Delivery ledger update failed; claim remains reserved")
        self._last_sent_count = sent_count if (outcome == "sent" and stored) else 0
        return outcome == "sent" and stored

    def close(self):
        self.state_store.close()

    def generate_internal_bd_report(self, output_path: Optional[str] = None):
        if not output_path:
            isolated_dir = os.path.join(tempfile.gettempdir(), "intent_radar_internal")
            os.makedirs(isolated_dir, exist_ok=True)
            output_path = os.path.join(isolated_dir, "internal_bd_ops.html")
        html_str = render_internal_bd_html(
            pilot_offers=get_pilot_offers(),
            seed_clients=get_seed_clients(),
            launch_campaigns=get_launch_campaigns(),
            compiled_css=COMPILED_TAILWIND_CSS,
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_str)
        logger.info(f"Internal BD & Pilot Operations Playbook written to isolated path {output_path}")

    def generate_html_report(self, signals: List[EnrichedSignal], output_path: str):
        today_date = datetime.now().strftime("%Y-%m-%d")
        source_names = {"hn": "Hacker News", "github": "GitHub Issues", "devto": "Dev.to", "news": "Google News", "v2ex": "V2EX"}
        status_names = {"complete": "采集完成", "failed": "采集失败", "partial": "部分失败", "deferred": "限流延期", "timeout": "采集超时"}
        collection_status_text = _html.escape(" / ".join(
            f"{source_names.get(k, k)}：{status_names.get(v, v)}" for k, v in self.config.get("collection_status", {}).items()
        ) or ("历史核验演练，不计实时交付" if self.config.get("run_mode") == "historical_benchmark" else "未执行实时采集"))
        comp_counter = Counter(s.target_competitor for s in signals)
        sorted_competitors = comp_counter.most_common()

        def _has_verified_or_inferred_auth(s: EnrichedSignal) -> bool:
            qm = s.qualification_meta or {}
            auth_obj = qm.get("decision_authority", {})
            auth_v = auth_obj.get("value", "")
            auth_s = auth_obj.get("source") or auth_obj.get("provenance") or "未知"
            if "无采购与替换决策权" in auth_v or "无选型决定权" in auth_v or getattr(s, "intent_type", "") != "buyer_evaluation":
                return False
            return auth_s in ("原文明示", "模型推断")

        def _is_pricing(s: EnrichedSignal) -> bool:
            txt = (" ".join(s.churn_drivers) + " " + s.signal.title + " " + (s.signal.evidence_quote or "")).lower()
            return bool(re.search(r"价格|成本|费用|涨价|贵|配额|限流|账单|expensive|pricing|rate limit|pro plan", txt))

        def _is_privacy(s: EnrichedSignal) -> bool:
            txt = (" ".join(s.churn_drivers) + " " + s.signal.title + " " + (s.signal.evidence_quote or "")).lower()
            return bool(re.search(r"隐私|开源|自托管|合规|数据|上云|离线|cloud|offline|scratchpad|self-host|open source", txt))

        high_intent_count = sum(1 for s in signals if s.intent_score >= 80 and _has_verified_or_inferred_auth(s))
        caution_count = len(signals) - high_intent_count
        pricing_count = sum(1 for s in signals if _is_pricing(s))
        privacy_count = sum(1 for s in signals if _is_privacy(s))

        leads_json_data = []
        for idx, s in enumerate(signals, 1):
            comp_key = s.target_competitor.lower().strip()
            first_key = comp_key.split("/")[0].strip()
            logo_url = COMPETITOR_LOGOS.get(
                comp_key,
                COMPETITOR_LOGOS.get(first_key, _make_brand_svg_data_uri("#27272a", s.target_competitor[:2].upper())),
            )
            leads_json_data.append({
                "idx": idx,
                "id": s.signal.id,
                "source_id": getattr(s.signal, "source_id", s.signal.id),
                "title": s.signal.title,
                "url": s.signal.url,
                "source": s.signal.source,
                "content": s.signal.content,
                "raw_content": s.signal.raw_content,
                "content_complete": s.signal.content_complete,
                "evidence_quote": getattr(s.signal, "evidence_quote", "") or s.signal.content,
                "author": s.signal.author,
                "timestamp": s.signal.timestamp,
                "updated_at": getattr(s.signal, "updated_at", s.signal.timestamp),
                "collected_at": getattr(s.signal, "collected_at", today_date),
                "engagement": s.signal.engagement_metric,
                "dataset_kind": getattr(s.signal, "dataset_kind", "historical_benchmark"),
                "freshness_status": getattr(s.signal, "freshness_status", "historical_benchmark_archive"),
                "delivery_eligible": getattr(s.signal, "delivery_eligible", False),
                "intent_score": s.intent_score,
                "intent_level": s.intent_level,
                "intent_type": getattr(s, "intent_type", "buyer_evaluation"),
                "qualification_stage": getattr(s, "qualification_stage", ""),
                "contiguous_stage_num": getattr(s, "contiguous_stage_num", 2),
                "qualification_stages": getattr(s, "qualification_stages", {}),
                "qualification_meta": getattr(s, "qualification_meta", {}),
                "policy_facts": s.qualification_meta.get("policy_facts", {}),
                "outreach_policy": getattr(s, "outreach_policy", {}),
                "competitor": s.target_competitor,
                "candidate_alternatives": getattr(s, "candidate_alternatives", []),
                "system_recommended_alternatives": getattr(s, "system_recommended_alternatives", []),
                "competitor_logo": logo_url,
                "category": s.category,
                "buyer_persona": s.buyer_persona,
                "churn_drivers": s.churn_drivers,
                "core_issue": s.core_issue,
                "executive_summary": s.executive_summary,
                "tactical_action_plan": s.tactical_action_plan,
                "suggested_pitch": s.suggested_pitch,
                "pitch_dev": getattr(s, "pitch_dev", s.suggested_pitch),
                "pitch_exec": getattr(s, "pitch_exec", s.suggested_pitch),
                "public_reply": getattr(s, "public_reply", ""),
                "objection_handling": getattr(s, "objection_handling", ""),
            })

        leads_json_str = json.dumps(leads_json_data, ensure_ascii=False).replace("<", r"\u003c").replace(">", r"\u003e")
        brand_icons_json_str = json.dumps(COMPETITOR_LOGOS, ensure_ascii=False).replace("<", r"\u003c").replace(">", r"\u003e")
        brand_presets = get_brand_presets()
        brand_presets_json_str = json.dumps(brand_presets, ensure_ascii=False).replace("<", r"\u003c").replace(">", r"\u003e")

        comp_pills_html = f"""
        <button type="button" data-action="filter-competitor" data-competitor="ALL" class="comp-pill inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold bg-zinc-900 text-white transition-all shadow-xs flex-shrink-0">
            <span>全部竞品</span>
            <span class="bg-zinc-700 text-zinc-200 text-[10px] px-1.5 py-0.2 rounded-full font-mono">{len(signals)}</span>
        </button>
        """
        for comp, cnt in sorted_competitors:
            comp_key = comp.lower().strip()
            first_key = comp_key.split("/")[0].strip()
            icon_uri = COMPETITOR_LOGOS.get(comp_key, COMPETITOR_LOGOS.get(first_key, _make_brand_svg_data_uri("#3f3f46", comp[:2].upper())))
            esc_comp = _html.escape(comp)
            comp_pills_html += f"""
            <button type="button" data-action="filter-competitor" data-competitor="{esc_comp}" class="comp-pill inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-white text-zinc-700 hover:bg-zinc-100 hover:text-zinc-900 border border-zinc-200 transition-all shadow-xs flex-shrink-0">
                <img src="{_html.escape(icon_uri)}" class="w-3.5 h-3.5 rounded-[3px] object-contain flex-shrink-0" alt="{esc_comp}" />
                <span>{esc_comp}</span>
                <span class="text-zinc-400 text-[11px] font-mono">({cnt})</span>
            </button>
            """

        status_options_html = "".join(
            f'<option value="{st}">{st}</option>'
            for st in ["未处理", "已核验接受", "已触达", "有回复", "已预约", "已成交", "不合格"]
        )
        disq_options_html = "".join(
            f'<option value="{rs}">{rs}</option>'
            for rs in [
                "无替换决策权（如一线员工被动使用）",
                "非目标客群规模（个人/学生项目）",
                "痛点与我方产品能力不匹配",
                "原帖讨论已超期或已完成选型",
                "仅倾诉情绪无迁移预算",
            ]
        )

        style_tag = (
            f"<style>{COMPILED_TAILWIND_CSS}</style>"
            if COMPILED_TAILWIND_CSS
            else '<script src="https://cdn.tailwindcss.com"></script>'
        )
        client_js = get_full_client_js()
        run_mode = self.config.get("run_mode", "historical_benchmark")
        dataset_badge_text = (
            "公开社区历史基准核验集（Hacker News 官方 API 已核验 · 不计当期实时交付配额）"
            if run_mode == "historical_benchmark" or (bool(signals) and all(getattr(s.signal, "dataset_kind", "") == "historical_benchmark" for s in signals))
            else "实时公开源生产采集模式（HN / GitHub Issues / Dev.to / Google News RSS / V2EX）"
        )

        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN" class="h-full bg-zinc-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>IntentRadar · 公开社区竞品替换信号核验工作台</title>
    {style_tag}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;600;700&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        code, pre, .font-mono {{ font-family: 'JetBrains Mono', monospace; }}
        ::-webkit-scrollbar {{ width: 5px; height: 5px; }}
        ::-webkit-scrollbar-track {{ background: transparent; }}
        ::-webkit-scrollbar-thumb {{ background: #d4d4d8; border-radius: 9999px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #a1a1aa; }}
        .drawer-mask {{ background: rgba(9, 9, 11, 0.45); backdrop-filter: blur(3px); }}
    </style>
</head>
<body class="h-full w-full max-w-full font-sans antialiased text-zinc-900 flex overflow-hidden">

    <!-- Left Navigation Sidebar -->
    <aside class="hidden lg:flex lg:flex-shrink-0 w-64 bg-zinc-950 border-r border-zinc-800/80 flex-col">
        <div class="h-14 flex items-center px-5 border-b border-zinc-800/80">
            <div class="w-8 h-8 rounded-lg bg-gradient-to-tr from-emerald-600 to-teal-400 p-[1px] mr-2.5 flex-shrink-0">
                <div class="w-full h-full bg-zinc-950 rounded-[7px] flex items-center justify-center">
                    <svg class="w-4 h-4 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="12" cy="12" r="9" opacity="0.35" />
                        <path d="M12 3a9 9 0 0 1 9 9" />
                        <circle cx="12" cy="12" r="2" fill="currentColor" />
                    </svg>
                </div>
            </div>
            <div class="flex flex-col">
                <div class="flex items-center gap-1.5">
                    <span class="text-xs font-bold text-white tracking-wide">IntentRadar</span>
                    <span class="bg-emerald-500/20 text-emerald-300 text-[10px] font-mono px-1 py-0.2 rounded border border-emerald-500/30">v3.3 Pilot</span>
                </div>
                <span class="text-[10px] text-zinc-400 font-mono">B2B 竞品替换情报大盘与核验台</span>
            </div>
        </div>

        <div class="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            <div class="px-2.5 pb-1.5 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">四步资格核验视图</div>

            <button type="button" data-nav-cat="all" onclick="setFilterCategory('all', this)" class="nav-btn w-full flex items-center px-3 py-2 text-xs font-semibold text-white bg-zinc-800 rounded-lg text-left transition-all">
                <svg class="w-4 h-4 mr-2 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"></path></svg>
                <span>全部核验样本</span>
                <span id="badgeCountAll" class="ml-auto bg-zinc-700 text-zinc-200 py-0.5 px-2 rounded-full text-[10px] font-mono">{len(signals)}</span>
            </button>

            <button type="button" data-nav-cat="high-intent" onclick="setFilterCategory('high-intent', this)" class="nav-btn w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg text-left transition-all">
                <svg class="w-4 h-4 mr-2 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                <span>替换评估证据（Stage 2+）</span>
                <span id="badgeCountHigh" class="ml-auto bg-emerald-500/20 text-emerald-300 py-0.5 px-2 rounded-full text-[10px] font-mono">{high_intent_count}</span>
            </button>

            <button type="button" data-nav-cat="caution" onclick="setFilterCategory('caution', this)" class="nav-btn w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg text-left transition-all">
                <svg class="w-4 h-4 mr-2 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
                <span>替换意图未核实 / 已阻断</span>
                <span id="badgeCountCaution" class="ml-auto bg-amber-500/20 text-amber-300 py-0.5 px-2 rounded-full text-[10px] font-mono">{caution_count}</span>
            </button>

            <div class="pt-3 px-2.5 pb-1 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">核心痛点维度过滤</div>

            <button type="button" data-nav-cat="pricing" onclick="setFilterCategory('pricing', this)" class="nav-btn w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg text-left transition-all">
                <svg class="w-4 h-4 mr-2 text-rose-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                <span>API 限流 / 价格与账单</span>
                <span id="badgeCountPricing" class="ml-auto bg-rose-500/20 text-rose-300 py-0.5 px-2 rounded-full text-[10px] font-mono">{pricing_count}</span>
            </button>

            <button type="button" data-nav-cat="privacy" onclick="setFilterCategory('privacy', this)" class="nav-btn w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-400 hover:text-zinc-200 hover:bg-zinc-900 rounded-lg text-left transition-all">
                <svg class="w-4 h-4 mr-2 text-indigo-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                <span>强制上云 / 开源自托管</span>
                <span id="badgeCountPrivacy" class="ml-auto bg-indigo-500/20 text-indigo-300 py-0.5 px-2 rounded-full text-[10px] font-mono">{privacy_count}</span>
            </button>

            <div class="pt-4 px-2.5 pb-1 text-[10px] font-bold text-zinc-500 uppercase tracking-wider">阶段3卖方门控与导出</div>

            <button type="button" onclick="toggleBrandCustomizer()" class="w-full flex items-center px-3 py-2 text-xs font-medium text-amber-300 hover:text-white hover:bg-zinc-900 rounded-lg transition-all text-left">
                <svg class="w-4 h-4 mr-2 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                <span>配置卖方能力与赛道门控</span>
            </button>

            <button type="button" onclick="triggerExport('filtered', 'xlsx')" class="w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-200 hover:text-white hover:bg-zinc-900 rounded-lg transition-all text-left">
                <svg class="w-4 h-4 mr-2 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                <span>导出当前筛选 (.xlsx)</span>
            </button>

            <button type="button" onclick="triggerExport('all', 'xlsx')" class="w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-300 hover:text-white hover:bg-zinc-900 rounded-lg transition-all text-left">
                <svg class="w-4 h-4 mr-2 text-zinc-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                <span>导出全库样本 ({len(signals)}条 .xlsx)</span>
            </button>

            <button type="button" id="btnCopyFilteredPitches" onclick="copyFilteredPitches(this)" class="w-full flex items-center px-3 py-2 text-xs font-medium text-zinc-300 hover:text-white hover:bg-zinc-900 rounded-lg transition-all text-left">
                <svg class="w-4 h-4 mr-2 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2"></path></svg>
                <span>批量复制当前合规草稿</span>
            </button>

            <!-- Provenance Legend -->
            <div class="pt-3 px-1">
                <div class="p-3 rounded-xl bg-zinc-900/90 border border-zinc-800 text-[11px] text-zinc-400 space-y-1.5">
                    <div class="text-zinc-200 font-semibold">三态证据来源标识说明</div>
                    <div class="flex items-center justify-between"><span><strong class="text-emerald-400">[原文明示]</strong></span><span>原帖字面直接包含</span></div>
                    <div class="flex items-center justify-between"><span><strong class="text-amber-400">[模型推断]</strong></span><span>基于上下文合理推断</span></div>
                    <div class="flex items-center justify-between"><span><strong class="text-zinc-300">[未知]</strong></span><span>原帖未披露·需首轮核实</span></div>
                </div>
            </div>
        </div>
    </aside>

    <!-- Main Workspace -->
    <div class="flex-1 flex flex-col min-w-0 w-full max-w-full overflow-hidden">
        <!-- Top Application Bar -->
        <header class="min-h-14 py-2 px-4 sm:px-5 bg-white border-b border-zinc-200/90 flex flex-col sm:flex-row sm:items-center justify-between gap-2 flex-shrink-0">
            <div class="relative w-full sm:max-w-xs flex-1">
                <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-zinc-400">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
                </div>
                <input type="text"
                       id="searchInput"
                       oninput="handleSearch()"
                       aria-label="搜索竞品、原帖ID、原文证据或发帖人"
                       placeholder="搜索竞品、ID、原文证据... (/)"
                       class="block w-full pl-9 pr-8 py-1.5 border border-zinc-200 rounded-lg text-xs placeholder-zinc-400 focus:outline-none focus:ring-2 focus:ring-zinc-900 bg-zinc-50 focus:bg-white">
                <button type="button" id="searchClearBtn" onclick="clearSearch()" class="hidden absolute inset-y-0 right-0 pr-2.5 flex items-center text-zinc-400 hover:text-zinc-700" title="清空搜索">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>

            <!-- View Switcher & Explicit Export Buttons -->
            <div class="flex items-center justify-between sm:justify-end gap-1.5 w-full sm:w-auto flex-wrap">
                <div class="flex items-center gap-0.5 text-[11px] text-zinc-600 bg-zinc-100 p-0.5 rounded-lg border border-zinc-200">
                    <button type="button" onclick="setViewMode('table')" id="btnViewTable" class="px-2 py-1 rounded-md font-semibold text-zinc-900 bg-white shadow-xs transition-all flex items-center gap-1 whitespace-nowrap">
                        <span>核验宽表</span>
                    </button>
                    <button type="button" onclick="setViewMode('split')" id="btnViewSplit" class="px-2 py-1 rounded-md font-medium text-zinc-600 hover:text-zinc-900 transition-all flex items-center gap-1 whitespace-nowrap">
                        <span>分屏工作台</span>
                    </button>
                    <button type="button" onclick="setViewMode('cards')" id="btnViewCards" class="px-2 py-1 rounded-md font-medium text-zinc-600 hover:text-zinc-900 transition-all flex items-center gap-1 whitespace-nowrap">
                        <span>证据卡片</span>
                    </button>
                </div>

                <div class="flex items-center gap-1 flex-wrap">
                    <button type="button" id="btnToggleDashboard" onclick="toggleDashboardOverview()" class="inline-flex items-center px-2 py-1 rounded-lg text-[11px] font-semibold bg-zinc-100 hover:bg-zinc-200 text-zinc-800 border border-zinc-200 transition-colors whitespace-nowrap">
                        <span>📊 收起大盘</span>
                    </button>
                    <button type="button" id="btnToggleCustomizer" onclick="toggleBrandCustomizer()" class="inline-flex items-center px-2 py-1 rounded-lg text-[11px] font-semibold bg-amber-50 hover:bg-amber-100 text-amber-800 border border-amber-200/90 transition-colors whitespace-nowrap">
                        <span>🎯 阶段3卖方能力门控</span>
                    </button>
                    <button type="button" id="btnExportFilteredXlsx" onclick="triggerExport('filtered', 'xlsx')" class="inline-flex items-center px-2 py-1 rounded-lg text-[11px] font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition-colors whitespace-nowrap">
                        <span>导出当前筛选 ({len(signals)}条 .xlsx)</span>
                    </button>
                    <button type="button" id="btnExportFilteredCsv" onclick="triggerExport('filtered', 'csv')" class="inline-flex items-center px-2 py-1 rounded-lg text-[11px] font-semibold bg-white hover:bg-zinc-100 text-zinc-800 border border-zinc-300 shadow-2xs transition-colors whitespace-nowrap">
                        <span>导出当前 CSV ({len(signals)}条)</span>
                    </button>
                    <button type="button" id="btnExportAllXlsx" onclick="triggerExport('all', 'xlsx')" class="inline-flex items-center px-2 py-1 rounded-lg text-[11px] font-semibold bg-zinc-900 hover:bg-zinc-800 text-white shadow-xs transition-colors whitespace-nowrap">
                        <span>导出全库 ({len(signals)}条 .xlsx)</span>
                    </button>
                    <button type="button" id="btnHowItWorks" onclick="openHowItWorksModal(this)" class="inline-flex items-center px-2 py-1 rounded-lg text-[11px] font-medium bg-zinc-100 hover:bg-zinc-200 text-zinc-700 border border-zinc-200 whitespace-nowrap" title="查看四步资格核验规范">
                        <span>📘 核验标准</span>
                    </button>
                </div>
            </div>
        </header>

        <!-- Cross-Category Brand Capability Customizer Drawer/Bar -->
        <div id="brandCustomizerBar" class="hidden ir-customizer-panel flex-shrink-0">
            <div class="flex flex-col gap-2">
                <div class="flex items-center justify-between flex-wrap gap-2">
                    <div class="flex items-center gap-2 flex-wrap">
                        <span class="text-xs font-bold text-zinc-900">🎯 阶段 3 卖方产品能力档案与真实身份披露配置（Capability & Role Gating）</span>
                        <span class="text-[11px] text-zinc-500">一键体验预设赛道或手动配置（严格校核赛道适配与真实身份，禁止通配符或自动补造能力）：</span>
                    </div>
                    <button type="button" onclick="toggleBrandCustomizer()" class="text-[11px] font-semibold text-zinc-500 hover:text-zinc-800">收起配置 ▲</button>
                </div>
                <div class="flex items-center gap-1.5 flex-wrap" id="brandPresetButtons"></div>
                <div class="ir-form-grid">
                    <div class="ir-field-group">
                        <label for="customBrandName" class="ir-field-label">卖方产品名</label>
                        <input id="customBrandName" type="text" placeholder="如: Plane / Hoppscotch" class="w-full px-2.5 py-1.5 text-xs bg-white border border-zinc-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                    </div>
                    <div class="ir-field-group">
                        <label for="customActorRole" class="ir-field-label">发送人真实身份</label>
                        <select id="customActorRole" aria-label="发送人真实角色" class="w-full px-2 py-1.5 text-xs bg-white border border-zinc-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900">
                            <option value="产品研发团队">身份: 产品研发团队</option>
                            <option value="官方销售顾问">身份: 官方销售顾问</option>
                            <option value="外部选型顾问">身份: 外部选型顾问</option>
                        </select>
                    </div>
                    <div class="ir-field-group">
                        <label for="customTargetCompetitors" class="ir-field-label">适配被替换竞品 (必填)</label>
                        <input id="customTargetCompetitors" type="text" placeholder="如: Atlassian Jira, Linear" class="w-full px-2.5 py-1.5 text-xs bg-white border border-zinc-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                    </div>
                    <div class="ir-field-group">
                        <label for="customApprovedCaps" class="ir-field-label">已核准真实能力 (必填)</label>
                        <input id="customApprovedCaps" type="text" placeholder="如: 原生 Git 同步、离线执行" class="w-full px-2.5 py-1.5 text-xs bg-white border border-zinc-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                    </div>
                    <div class="ir-field-group">
                        <label for="customKnownLimits" class="ir-field-label">已知限制 / 待确认边界</label>
                        <input id="customKnownLimits" type="text" placeholder="如: 暂不支持旧版专有插件" class="w-full px-2.5 py-1.5 text-xs bg-white border border-zinc-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                    </div>
                    <div class="ir-field-group">
                        <label for="customBrandLink" class="ir-field-label">验证文档 URL & 应用</label>
                        <div class="flex items-center gap-1">
                            <input id="customBrandLink" type="text" placeholder="https://docs..." class="w-full px-2 py-1.5 text-xs bg-white border border-zinc-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-zinc-900" />
                            <button type="button" onclick="applyCustomBrandProfile()" class="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-zinc-900 hover:bg-zinc-800 text-white whitespace-nowrap">
                                应用门控
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Main Scrollable Workspace -->
        <main class="flex-1 overflow-y-auto p-3 sm:p-5 min-w-0 max-w-full" id="mainContainer">

            <!-- EXECUTIVE INTELLIGENCE OVERVIEW DASHBOARD (全景情报大盘) -->
            <section id="overviewDashboardSection" class="ir-dashboard-section" aria-label="竞品替换情报全景大盘">
                <!-- Executive Status & Telemetry Banner -->
                <div class="ir-overview-banner">
                    <div class="ir-overview-banner-left">
                        <span class="ir-overview-pulse"></span>
                        <span class="text-xs font-bold tracking-wide text-white">{_html.escape(dataset_badge_text)}</span>
                        <span role="status" class="text-[11px] font-mono text-zinc-300 bg-zinc-800/90 px-2 py-0.5 rounded border border-zinc-700">来源执行状态：{collection_status_text or "历史演练"}</span>
                    </div>
                    <div class="flex items-center gap-2 flex-wrap">
                        <span id="activeBrandIndicator" class="text-[11px] font-medium text-zinc-200 bg-zinc-800 border border-zinc-700 px-2.5 py-0.5 rounded-md">当前视角：默认中立证据核验（阶段3待绑定卖方能力·仅生成中立问题）</span>
                        <span id="liveFilterSummary" class="text-[11px] font-mono font-semibold text-emerald-300 bg-emerald-500/20 border border-emerald-500/30 px-2.5 py-0.5 rounded-md">当前筛选显示 {len(signals)} / {len(signals)} 条样本</span>
                    </div>
                </div>

                <!-- Row 1: 4 Core KPI Metric Cards -->
                <div id="dashboardKpiGrid" class="ir-kpi-grid"></div>

                <!-- Row 2: 3 Visual Analytics & Telemetry Panels -->
                <div class="ir-chart-grid">
                    <!-- Panel 1: 4-Stage Qualification Funnel -->
                    <div class="ir-chart-card">
                        <div class="ir-chart-header">
                            <span class="ir-chart-title">
                                <svg class="w-4 h-4 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z"></path></svg>
                                <span>四步连续资格核验漏斗</span>
                            </span>
                            <span class="ir-chart-subtitle">点击阶段过滤宽表</span>
                        </div>
                        <div id="chartFunnelContainer" class="ir-funnel-list"></div>
                    </div>

                    <!-- Panel 2: Incumbent Competitor Heat Distribution -->
                    <div class="ir-chart-card">
                        <div class="ir-chart-header">
                            <span class="ir-chart-title">
                                <svg class="w-4 h-4 text-emerald-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"></path></svg>
                                <span>被替换竞品信号热度排行</span>
                            </span>
                            <span class="ir-chart-subtitle">点击竞品联动筛选</span>
                        </div>
                        <div id="chartCompetitorContainer" class="ir-bar-list"></div>
                    </div>

                    <!-- Panel 3: Churn Drivers & 4D Provenance Matrix -->
                    <div class="ir-chart-card">
                        <div class="ir-chart-header">
                            <span class="ir-chart-title">
                                <svg class="w-4 h-4 text-indigo-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 3.055A9.001 9.001 0 1020.945 13H11V3.055z"></path></svg>
                                <span>流失驱动归因与证据可信度</span>
                            </span>
                            <span class="ir-chart-subtitle">三态溯源分布</span>
                        </div>
                        <div id="chartDriversAndProvenanceContainer" class="flex flex-col justify-between flex-1 gap-2"></div>
                    </div>
                </div>
            </section>

            <!--Competitor Filter Pills Toolbar -->
            <div class="bg-white rounded-xl border border-zinc-200/90 px-3.5 py-2.5 mb-3 shadow-xs flex flex-wrap items-center justify-between gap-2">
                <div class="flex items-center flex-wrap gap-1.5 max-w-full" id="competitorPillContainer">
                    {comp_pills_html}
                </div>
                <div class="text-[11px] text-zinc-500">
                    严格分离「原文提及候选」与「系统参考候选」· 点击任意行打开右侧核验抽屉
                </div>
            </div>

            <!-- 1. DATA GRID VIEW -->
            <div id="tableViewWrapper" class="ir-workbench-card max-w-full">
                <div class="overflow-x-auto max-w-full">
                    <table class="w-full divide-y divide-zinc-200 text-left text-xs">
                        <thead class="bg-zinc-50/90 font-semibold text-zinc-500 uppercase tracking-wider text-[11px]">
                            <tr>
                                <th onclick="toggleSort('idx')" class="py-2.5 px-1.5 w-9 text-center cursor-pointer hover:bg-zinc-100 select-none">
                                    <span>#<span id="sortIndicatorIdx" class="text-zinc-400 font-mono text-[10px]">↕</span></span>
                                </th>
                                <th onclick="toggleSort('score')" class="py-2.5 px-2 w-32 whitespace-nowrap cursor-pointer hover:bg-zinc-100 select-none">
                                    <span>阶段 / 评分 <span id="sortIndicatorScore" class="text-zinc-400 font-mono text-[10px]">↕</span></span>
                                </th>
                                <th class="py-2.5 px-2 w-36 whitespace-nowrap">被替换竞品 / 候选</th>
                                <th class="py-2.5 px-2.5">原帖完整标题 · 逐字证据摘录 · 四维来源 · 阻碍项</th>
                                <th class="py-2.5 px-2 w-36 whitespace-nowrap">发布时间 / 互动</th>
                                <th class="py-2.5 px-1.5 w-24 whitespace-nowrap">跟进状态</th>
                                <th class="py-2.5 px-2 w-32 whitespace-nowrap text-right">核验操作</th>
                            </tr>
                        </thead>
                        <tbody id="leadTableBody" class="divide-y divide-zinc-100 font-normal text-zinc-700"></tbody>
                    </table>
                </div>
            </div>

            <!-- 2. SPLIT WORKSTATION VIEW -->
            <div id="splitViewWrapper" class="hidden grid grid-cols-1 lg:grid-cols-12 gap-4 max-w-full">
                <!-- Left: Accessible Button Group (aria-pressed on native buttons) -->
                <div class="lg:col-span-5 bg-white rounded-xl border border-zinc-200/90 shadow-xs overflow-hidden flex flex-col h-[720px]">
                    <div class="p-2.5 bg-zinc-50/90 border-b border-zinc-200 flex items-center justify-between text-xs font-semibold text-zinc-700 flex-shrink-0">
                        <span>核验样本列表 (支持 ↑/↓ 键切换)</span>
                        <span id="splitCountBadge" class="text-[11px] font-mono text-zinc-500"></span>
                    </div>
                    <div id="splitLeadList" role="group" aria-label="核验样本列表" class="flex-1 overflow-y-auto divide-y divide-zinc-100"></div>
                </div>

                <!-- Right: Evidence-First Docked Sheet -->
                <div class="lg:col-span-7 bg-white rounded-xl border border-zinc-200/90 shadow-xs overflow-hidden flex flex-col h-[720px]">
                    <div id="splitDockedContainer" class="flex-1 flex flex-col overflow-hidden">
                        <div class="h-12 px-4 border-b border-zinc-200 flex items-center justify-between bg-zinc-50/80 flex-shrink-0">
                            <div class="flex items-center gap-2 truncate">
                                <span id="splitScoreBadge"></span>
                                <span id="splitCompetitorBadge" class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200 truncate"></span>
                            </div>
                            <a id="splitSourceLink" href="#" target="_blank" rel="noopener noreferrer" class="inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold text-blue-700 bg-blue-50 hover:bg-blue-100 border border-blue-200 whitespace-nowrap">
                                <span>打开原帖核验 ↗</span>
                            </a>
                        </div>

                        <div class="flex-1 overflow-y-auto p-4 space-y-3.5">
                            <div>
                                <h2 id="splitTitle" class="text-sm font-bold text-zinc-900 leading-snug mb-1"></h2>
                                <div class="flex flex-wrap items-center gap-3 text-[11px] text-zinc-500 font-mono">
                                    <span id="splitAuthor"></span>
                                    <span id="splitTimestamp"></span>
                                    <span id="splitCollectedAt"></span>
                                    <span id="splitEngagement" class="text-amber-700 font-sans font-medium"></span>
                                </div>
                            </div>

                            <!-- Priority 1: Verbatim Evidence Quote -->
                            <div class="p-3 rounded-xl bg-emerald-50/60 border border-emerald-200/90 space-y-1">
                                <div class="text-[11px] font-bold text-emerald-900 uppercase tracking-wider">📌 1. 支持关键判断的原文证据片段 (Verbatim Evidence)</div>
                                <div id="splitEvidenceQuote" class="text-xs text-zinc-900 font-medium italic leading-relaxed"></div>
                            </div>

                            <!-- Priority 2: Tri-state Qualification Provenance Grid -->
                            <div class="space-y-1.5">
                                <div class="text-[11px] font-bold text-zinc-700 uppercase tracking-wider">🔍 2. 四维资格核验、证据来源与原文依据 ([原文明示] / [模型推断] / [未知])</div>
                                <div id="splitReviewPanel" class="review-panel"></div>
            <div id="splitProvenanceGrid" class="grid grid-cols-1 sm:grid-cols-2 gap-2"></div>
                            </div>

                            <!-- Priority 3: Blocking Conditions & Next Action -->
                            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                                <div class="p-3 rounded-xl bg-rose-50/70 border border-rose-200/80 space-y-1">
                                    <div class="text-[11px] font-bold text-rose-900">🚧 3. 阻碍条件与待核验项 (Blocking Conditions)</div>
                                    <ul id="splitBlockers" class="list-disc pl-4 text-xs text-rose-900 space-y-0.5"></ul>
                                </div>
                                <div class="p-3 rounded-xl bg-blue-50/60 border border-blue-200/80 space-y-1">
                                    <div class="text-[11px] font-bold text-blue-900">🧭 4. 建议触达路径与下一步动作</div>
                                    <div id="splitContactPath" class="text-xs text-blue-900 leading-relaxed"></div>
                                    <div id="splitChurnBadges" class="flex flex-wrap gap-1 pt-1"></div>
                                </div>
                            </div>

                            <!-- Priority 4: Policy-Gated Outreach Drafts -->
                            <div class="space-y-2 pt-1">
                                <div class="flex items-center justify-between">
                                    <span class="text-[11px] font-bold text-zinc-700 uppercase tracking-wider">💬 5. 门控沟通草稿（未配置卖方时仅生成中立问题·配置后按真实身份披露）</span>
                                    <button type="button" onclick="copyToClipboard(document.getElementById('splitPitch').innerText, '已复制当前沟通草稿！', this)" class="inline-flex items-center px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md">
                                        <span>复制当前草稿</span>
                                    </button>
                                </div>
                                <div class="flex items-center gap-1 p-1 bg-zinc-100 rounded-lg border border-zinc-200/80 text-xs">
                                    <button type="button" id="btnSplitPitchReply" onclick="switchSplitPitchTab('reply')" class="flex-1 py-1 px-2 rounded-md font-semibold text-zinc-900 bg-white shadow-2xs transition-all">
                                        <span>💬 原帖公开核验/回复</span>
                                    </button>
                                    <button type="button" id="btnSplitPitchDev" onclick="switchSplitPitchTab('dev')" class="flex-1 py-1 px-2 rounded-md font-medium text-zinc-500 hover:text-zinc-800 transition-all">
                                        <span>💻 1v1 技术边界核验</span>
                                    </button>
                                    <button type="button" id="btnSplitPitchExec" onclick="switchSplitPitchTab('exec')" class="flex-1 py-1 px-2 rounded-md font-medium text-zinc-500 hover:text-zinc-800 transition-all">
                                        <span>💼 商业资格核验清单</span>
                                    </button>
                                </div>
                                <div id="splitPitch" class="bg-zinc-950 text-zinc-100 p-3 rounded-xl text-xs font-mono leading-relaxed select-all whitespace-pre-wrap"></div>
                            </div>

                            <!-- Collapsible Full Post & Extended Analysis -->
                            <details class="group bg-zinc-50 rounded-xl border border-zinc-200/80 p-3">
                                <summary class="text-xs font-bold text-zinc-700 cursor-pointer select-none flex items-center justify-between">
                                    <span>📂 展开原文 / 摘要与扩展分析（摘要会单独标明）</span>
                                    <span class="text-zinc-400 group-open:rotate-180 transition-transform">▼</span>
                                </summary>
                                <div class="mt-3 space-y-3 pt-2 border-t border-zinc-200/60 text-xs">
                                    <div>
                                        <div class="font-bold text-zinc-700 mb-1">原帖完整正文：</div>
                                        <div id="splitContent" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-700 whitespace-pre-wrap"></div>
                                    </div>
                                    <div>
                                        <div class="font-bold text-zinc-700 mb-1">情报摘要：</div>
                                        <div id="splitExecutiveSummary" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-600 whitespace-pre-wrap"></div>
                                    </div>
                                    <div>
                                        <div class="font-bold text-zinc-700 mb-1">核验行动建议：</div>
                                        <div id="splitTactics" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-600 whitespace-pre-wrap"></div>
                                    </div>
                                    <div>
                                        <div class="font-bold text-zinc-700 mb-1">待核验边界说明：</div>
                                        <div id="splitObjection" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-600 whitespace-pre-wrap"></div>
                                    </div>
                                </div>
                            </details>
                        </div>

                        <!-- Docked Footer -->
                        <div class="p-3 border-t border-zinc-200 bg-zinc-50/90 flex flex-wrap items-center justify-between gap-2 text-xs flex-shrink-0">
                            <div class="flex items-center gap-2">
                                <label for="splitStatusSelect" class="font-bold text-zinc-700">跟进状态:</label>
                                <select id="splitStatusSelect" class="px-2.5 py-1 rounded-lg border border-zinc-300 bg-white text-xs font-semibold text-zinc-800 focus:outline-none focus:ring-2 focus:ring-zinc-900">
                                    {status_options_html}
                                </select>
                            </div>
                            <div id="splitDisqualifyWrap" class="hidden flex items-center gap-1.5">
                                <label for="splitDisqualifySelect" class="text-rose-700 font-semibold">不合格原因:</label>
                                <select id="splitDisqualifySelect" class="px-2 py-1 rounded-lg border border-rose-300 bg-rose-50 text-xs text-rose-900 focus:outline-none">
                                    {disq_options_html}
                                </select>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 3. CARD VIEW -->
            <div id="cardViewWrapper" class="hidden space-y-3"></div>

            <!-- Empty State (Honest Zero-Result State for both Filtering and Live Empty Collection) -->
            <div id="empty-state" class="hidden text-center py-14 bg-white rounded-xl border border-zinc-200 shadow-xs">
                <h3 class="text-sm font-semibold text-zinc-900 mb-1">当前无可展示的匹配信号（0 条）</h3>
                <p class="text-xs text-zinc-500 mb-3">系统严格执行不掺水原则：实时采集为空或当前筛选为 0 时如实展示，绝不自动混入历史样本充当今日商机。</p>
                <div class="flex items-center justify-center gap-2">
                    <button type="button" onclick="resetAllFilters()" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-zinc-900 text-white hover:bg-zinc-800">
                        重置所有筛选条件
                    </button>
                </div>
            </div>
        </main>
    </div>

    <!-- RIGHT SLIDE-OVER DRAWER -->
    <div id="detailDrawerMask" onclick="closeDrawer()" class="drawer-mask fixed inset-0 z-40 hidden transition-opacity duration-300"></div>

    <aside id="detailDrawer"
           role="dialog"
           aria-modal="true"
           aria-labelledby="drawerTitle"
           aria-hidden="true"
           hidden
           inert
           class="fixed top-0 right-0 z-50 h-full w-full max-w-xl bg-white shadow-2xl border-l border-zinc-200 transform translate-x-full transition-transform duration-300 ease-in-out flex flex-col">
        <div class="h-14 px-5 border-b border-zinc-200 flex items-center justify-between gap-2 bg-zinc-50/80 flex-shrink-0">
            <div class="flex items-center gap-2 min-w-0 flex-1 overflow-hidden">
                <span id="drawerScoreBadge" class="flex-shrink-0"></span>
                <span id="drawerCompetitorBadge" class="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md text-xs font-semibold bg-zinc-100 text-zinc-800 border border-zinc-200 truncate min-w-0"></span>
            </div>
            <button type="button" id="drawerCloseBtn" onclick="closeDrawer()" aria-label="关闭核验详情抽屉" class="p-1.5 rounded-lg text-zinc-400 hover:text-zinc-700 hover:bg-zinc-200/60 flex-shrink-0">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
            </button>
        </div>

        <div class="flex-1 overflow-y-auto p-5 space-y-4">
            <div>
                <h2 id="drawerTitle" class="text-base font-bold text-zinc-900 leading-snug mb-1.5"></h2>
                <div class="flex flex-wrap items-center gap-3 text-xs text-zinc-500 font-mono">
                    <span id="drawerAuthor"></span>
                    <span id="drawerTimestamp"></span>
                    <span id="drawerCollectedAt"></span>
                    <span id="drawerEngagement" class="text-amber-700 font-sans font-medium"></span>
                </div>
            </div>

            <!-- 1. Verbatim Evidence Quote -->
            <div class="p-3.5 rounded-xl bg-emerald-50/70 border border-emerald-200 space-y-1.5">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-emerald-950">📌 1. 原帖关键证据摘录 (Verbatim Evidence)</span>
                    <a id="drawerSourceLink" href="#" target="_blank" rel="noopener noreferrer" class="text-xs text-blue-600 hover:underline font-semibold">
                        打开原帖核验 ↗
                    </a>
                </div>
                <div id="drawerEvidenceQuote" class="text-xs text-zinc-900 font-medium italic leading-relaxed"></div>
            </div>

            <!-- 2. Tri-state Provenance Grid -->
            <div class="space-y-1.5">
                <span class="text-xs font-bold text-zinc-700">🔍 2. 四维资格核验、证据来源与原文依据 ([原文明示] / [模型推断] / [未知])</span>
                <div id="drawerReviewPanel" class="review-panel"></div>
            <div id="drawerProvenanceGrid" class="grid grid-cols-1 sm:grid-cols-2 gap-2"></div>
            </div>

            <!-- 3. Blockers & Next Action -->
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <div class="p-3 rounded-xl bg-rose-50/70 border border-rose-200 space-y-1">
                    <div class="text-xs font-bold text-rose-900">🚧 3. 阻碍条件 / 待核验项</div>
                    <ul id="drawerBlockers" class="list-disc pl-4 text-xs text-rose-900 space-y-0.5"></ul>
                </div>
                <div class="p-3 rounded-xl bg-blue-50/60 border border-blue-200 space-y-1">
                    <div class="text-xs font-bold text-blue-900">🧭 4. 下一步跟进路径</div>
                    <div id="drawerContactPath" class="text-xs text-blue-900 leading-relaxed"></div>
                    <div id="drawerChurnBadges" class="flex flex-wrap gap-1 pt-1"></div>
                </div>
            </div>

            <!-- 4. Honest Outreach Templates -->
            <div class="space-y-2">
                <div class="flex items-center justify-between">
                    <span class="text-xs font-bold text-zinc-700">💬 5. 门控沟通草稿（未配置卖方时仅生成中立问题）</span>
                    <button type="button" onclick="copyToClipboard(document.getElementById('drawerPitch').innerText, '已复制当前沟通草稿！', this)" class="inline-flex items-center px-2.5 py-1 text-xs font-semibold text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-md">
                        <span>复制当前草稿</span>
                    </button>
                </div>
                <div class="flex items-center gap-1 p-1 bg-zinc-100 rounded-lg border border-zinc-200 text-xs">
                    <button type="button" id="btnPitchReply" onclick="switchPitchTab('reply')" class="flex-1 py-1.5 px-2 rounded-md font-semibold text-zinc-900 bg-white shadow-2xs transition-all">
                        <span>💬 原帖公开核验/回复</span>
                    </button>
                    <button type="button" id="btnPitchDev" onclick="switchPitchTab('dev')" class="flex-1 py-1.5 px-2 rounded-md font-medium text-zinc-500 hover:text-zinc-800 transition-all">
                        <span>💻 1v1 技术边界核验</span>
                    </button>
                    <button type="button" id="btnPitchExec" onclick="switchPitchTab('exec')" class="flex-1 py-1.5 px-2 rounded-md font-medium text-zinc-500 hover:text-zinc-800 transition-all">
                        <span>💼 商业资格核验清单</span>
                    </button>
                </div>
                <div id="drawerPitch" class="bg-zinc-950 text-zinc-100 p-3.5 rounded-xl text-xs font-mono leading-relaxed select-all whitespace-pre-wrap"></div>
            </div>

            <!-- Collapsible Full Post & Extended Analysis -->
            <details class="group bg-zinc-50 rounded-xl border border-zinc-200 p-3.5">
                <summary class="text-xs font-bold text-zinc-700 cursor-pointer select-none flex items-center justify-between">
                    <span>📂 展开原文 / 摘要与扩展分析（摘要会单独标明）</span>
                    <span class="text-zinc-400 group-open:rotate-180 transition-transform">▼</span>
                </summary>
                <div class="mt-3 space-y-3 pt-2 border-t border-zinc-200 text-xs">
                    <div>
                        <div class="font-bold text-zinc-700 mb-1">原帖完整正文：</div>
                        <div id="drawerContent" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-700 whitespace-pre-wrap"></div>
                    </div>
                    <div>
                        <div class="font-bold text-zinc-700 mb-1">商业情报摘要：</div>
                        <div id="drawerExecutiveSummary" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-600 whitespace-pre-wrap"></div>
                    </div>
                    <div>
                        <div class="font-bold text-zinc-700 mb-1">核验行动建议：</div>
                        <div id="drawerTactics" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-600 whitespace-pre-wrap"></div>
                    </div>
                    <div>
                        <div class="font-bold text-zinc-700 mb-1">待核验边界说明：</div>
                        <div id="drawerObjection" class="p-2.5 bg-white rounded border border-zinc-200 text-zinc-600 whitespace-pre-wrap"></div>
                    </div>
                </div>
            </details>
        </div>

        <!-- Drawer Footer -->
        <div class="p-4 border-t border-zinc-200 bg-zinc-50 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div class="flex items-center gap-2">
                <label for="drawerStatusSelect" class="font-bold text-zinc-700">7步跟进状态:</label>
                <select id="drawerStatusSelect" class="px-2.5 py-1 rounded-lg border border-zinc-300 bg-white text-xs font-semibold text-zinc-800">
                    {status_options_html}
                </select>
            </div>
            <div id="drawerDisqualifyWrap" class="hidden flex items-center gap-1.5">
                <label for="drawerDisqualifySelect" class="text-rose-700 font-semibold">不合格原因:</label>
                <select id="drawerDisqualifySelect" class="px-2 py-1 rounded-lg border border-rose-300 bg-rose-50 text-xs text-rose-900">
                    {disq_options_html}
                </select>
            </div>
        </div>
    </aside>

    <!-- Qualification Standards Modal Dialog -->
    <div id="howItWorksMask"
         onclick="closeHowItWorksModal()"
         hidden
         aria-hidden="true"
         class="drawer-mask fixed inset-0 z-50 hidden flex items-center justify-center p-4">
        <div id="howItWorksModal"
             role="dialog"
             aria-modal="true"
             aria-labelledby="howItWorksTitle"
             onclick="event.stopPropagation()"
             class="bg-white rounded-2xl border border-zinc-200 shadow-2xl max-w-2xl w-full p-6 space-y-4">
            <div class="flex items-center justify-between pb-3 border-b border-zinc-100">
                <div>
                    <h3 id="howItWorksTitle" class="text-sm font-bold text-zinc-900">IntentRadar v3.1 · 四步连续资格核验与门控规范</h3>
                    <p class="text-[11px] text-zinc-500 font-mono">严格执行「痛点存在 → 评估替代 → 卖方能力适配 → 可触达推进」连续通过规则</p>
                </div>
                <button type="button" id="howItWorksCloseBtn" onclick="closeHowItWorksModal()" aria-label="关闭弹窗" class="p-1 rounded-lg text-zinc-400 hover:text-zinc-700">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                </button>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs text-zinc-600">
                <div class="p-3 rounded-xl bg-zinc-50 border border-zinc-200 space-y-1">
                    <div class="font-bold text-zinc-900">1. 生产与历史基准隔离</div>
                    <p>实时生产采集绝不混入历史基准样本；每条记录显式标记 <code class="bg-zinc-200 px-1 rounded">dataset_kind</code> 与 <code class="bg-zinc-200 px-1 rounded">delivery_eligible</code>。</p>
                </div>
                <div class="p-3 rounded-xl bg-zinc-50 border border-zinc-200 space-y-1">
                    <div class="font-bold text-zinc-900">2. 四阶段连续晋级（分数不替代资格）</div>
                    <p>卖方能力未知时最高停留在阶段 2/4；单句提问且预算/权限未知时禁止越级；明确不考虑替换或厂商推广帖直接拦截。</p>
                </div>
                <div class="p-3 rounded-xl bg-zinc-50 border border-zinc-200 space-y-1">
                    <div class="font-bold text-zinc-900">3. 统一前后端话术门控</div>
                    <p>未绑定卖方档案或权限未知时仅生成中立核验问题；绑定卖方后按真实身份（研发/销售/顾问）披露并拦截跨赛道套用。</p>
                </div>
                <div class="p-3 rounded-xl bg-zinc-50 border border-zinc-200 space-y-1">
                    <div class="font-bold text-zinc-900">4. 候选区分与逐项证据追溯</div>
                    <p>严格区分作者原文提及候选与系统推荐候选；四维资格字段均附独立原文依据片段。</p>
                </div>
            </div>
            <div class="pt-2 border-t border-zinc-100 flex justify-end">
                <button type="button" onclick="closeHowItWorksModal()" class="px-4 py-1.5 rounded-lg text-xs font-semibold bg-zinc-900 text-white hover:bg-zinc-800">
                    返回核验工作台
                </button>
            </div>
        </div>
    </div>

    <!-- Toast Notification -->
    <div id="toastNotification" role="status" aria-live="polite" class="fixed bottom-6 right-6 z-50 transform translate-y-24 opacity-0 transition-all duration-300 pointer-events-none">
        <div class="bg-zinc-950 text-white px-4 py-3 rounded-xl shadow-2xl border border-zinc-800 flex items-center space-x-3 text-xs">
            <span id="toastIcon" class="text-emerald-400"></span>
            <span id="toastMessage" class="font-medium"></span>
        </div>
    </div>

    <script>
        const LEADS_DATA = {leads_json_str};
        const BRAND_ICONS = {brand_icons_json_str};
        const BRAND_PRESETS_DATA = {brand_presets_json_str};
        {client_js}
    </script>
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Client-Facing Verification Workbench written to {output_path}")
