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
from .redesign_template import convert_signals_to_claude_leads, render_claude_workbench_html

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
        run_mode = self.config.get("run_mode", "historical_benchmark")
        claude_leads = convert_signals_to_claude_leads(signals, run_mode=run_mode)

        is_historical = (
            run_mode == "historical_benchmark" or
            (bool(signals) and all(getattr(s.signal, "dataset_kind", "") == "historical_benchmark" for s in signals))
        )
        if is_historical:
            banner_text = "<strong>演示数据</strong>：10 条 Hacker News 历史帖（2020–2025），用于演练核验流程，不会推送给任何人。"
        else:
            banner_text = f"<strong>实时采集</strong>：共获取到 {len(signals)} 条公开社区信号，已完成阶段 1–2 准入与四维三态证据核验。"

        html_content = render_claude_workbench_html(
            leads=claude_leads,
            banner_text=banner_text,
            run_mode=run_mode
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"Client-Facing Verification Workbench written to {output_path}")
