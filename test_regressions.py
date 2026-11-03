"""Regression tests for audit round 3. No network or real webhook calls."""
import copy
import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from engine.analyzer import IntentAnalyzer
from engine.collector import CollectorHub, IntentSignal, SourceRateLimiter, evaluate_freshness, DevToCollector
from engine.dispatcher import Dispatcher
from engine.frontend_assets import get_full_client_js
from engine.policy import evaluate_facts, seller_snapshot
from engine.state_store import IntentStateStore


def signal(body=None, title="Looking for a Jira alternative", **kw):
    return IntentSignal(title, "https://example.org/post", "Test",
        content=body or "My team is looking to migrate away from Jira. We are on a paid plan and evaluating issue trackers.",
        source_id="test_1", timestamp=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(), **kw)


def profile():
    return {"brand_name": "TaskLite", "actor_role": "销售顾问", "target_competitors": ["Atlassian Jira"],
            "approved_capabilities": "CSV 导出", "known_limitations": "无私有化、SAML、附件导入"}


def reviewed(sig, fit="supported", actionable=True):
    p = profile()
    p["reviews"] = {sig.source_id: {"source": sig.source, "content_hash": sig.content_hash,
        "seller_snapshot": seller_snapshot(p), "reviewer": "审核人", "evidence": "已逐项核对原帖必选工作流与产品文档",
        "reviewed_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), "fit": fit,
        "authority_confirmed": actionable, "contact_url": "https://example.org/contact",
        "contact_evidence": "原帖与作者公开联系路径已核对" if actionable else ""}}
    return p


class ProductionRegressions(unittest.TestCase):
    def analyze(self, sig, seller=None):
        a = IntentAnalyzer({"use_llm_api": False, "seller_profile": seller})
        try:
            return a._heuristic_analyze(sig)
        finally:
            a.session.close()

    def test_pain_is_not_evaluation(self):
        s = IntentSignal("Jira is slow", "https://example.org", "Test", content=
            "Our team uses Jira on the Pro plan. The board is slow on Mondays. "
            "We have not discussed changing any tools; this is an internal performance observation.", source_id="pain")
        e = self.analyze(s, reviewed(s))
        self.assertEqual(e.intent_type, "pain_only")
        self.assertEqual(e.contiguous_stage_num, 1)
        self.assertLessEqual(e.intent_score, 55)
        self.assertEqual(e.outreach_policy["policy_status"], "blocked")

    def test_fit_requires_evidence_not_brand_keywords(self):
        s = signal("We are looking for a Jira alternative. Mandatory: private hosting, SAML SSO and full attachment import.")
        e = self.analyze(s, profile())
        self.assertEqual(e.contiguous_stage_num, 2)
        rejected = self.analyze(s, reviewed(s, fit="unsupported"))
        self.assertEqual(rejected.outreach_policy["policy_status"], "blocked")
        fit_only = self.analyze(s, reviewed(s, actionable=False))
        self.assertEqual(fit_only.contiguous_stage_num, 3)
        self.assertEqual(fit_only.outreach_policy["policy_status"], "neutral_inquiry_only")

    def test_review_is_bound_to_revision_and_seller(self):
        s = signal()
        p = reviewed(s)
        self.assertEqual(self.analyze(s, p).contiguous_stage_num, 4)
        p["approved_capabilities"] = "能力已修改"
        self.assertEqual(self.analyze(s, p).contiguous_stage_num, 2)
        p = reviewed(s)
        s.content_hash = "new-revision"
        self.assertEqual(self.analyze(s, p).contiguous_stage_num, 2)

    def test_unknown_future_expired_and_partial_are_not_deliverable(self):
        for value in (None, "garbage", "2099-01-01 00:00 UTC", "2020-01-01 00:00 UTC"):
            self.assertFalse(evaluate_freshness(value)[1])
        self.assertFalse(IntentSignal("a", "https://example.org", "Test").delivery_eligible)
        s = signal(content_complete=False)
        self.assertFalse(self.analyze(s, reviewed(s)).outreach_policy["allow_webhook_push"])

    def test_history_never_passes_stage4_even_after_manual_review(self):
        s = signal(dataset_kind="historical_benchmark")
        e = self.analyze(s, reviewed(s))
        self.assertEqual(e.contiguous_stage_num, 3)
        self.assertFalse(e.outreach_policy["allow_webhook_push"])

    def test_llm_cannot_add_claims_or_rescue_pain(self):
        s = signal()
        p = reviewed(s)
        a = IntentAnalyzer({"use_llm_api": False, "seller_profile": p})
        reply = {"is_software_or_saas": True, "has_decision_authority": "yes", "intent_type": "buyer_evaluation",
                 "intent_score": 99, "target_competitor": "Jira", "candidate_alternatives": [],
                 "public_reply": "利益相关披露：我们已通过 SOC 2 Type II 认证，并免费全量迁移。"}
        a.session.post = Mock(return_value=Mock(status_code=200, json=lambda: {"choices": [{"message": {"content": json.dumps(reply)}}]}))
        try:
            e = a._analyze_with_llm(s)
            self.assertEqual(e.public_reply, e.outreach_policy["public_reply"])
            self.assertNotIn("SOC 2", e.public_reply)
            self.assertNotIn("免费", e.public_reply)
            for bad in ({}, {**reply, "intent_score": 101}, {**reply, "intent_type": "anything"}):
                with self.assertRaises(ValueError):
                    a._validate_llm_schema(bad)
        finally:
            a.session.close()

    def test_concurrent_webhooks_claim_once_across_connections(self):
        s = signal(); p = reviewed(s); e = self.analyze(s, p)
        with tempfile.TemporaryDirectory() as directory:
            stores = [IntentStateStore(str(Path(directory) / "state.db")) for _ in range(2)]
            dispatchers = [Dispatcher({"client_id": "same", "seller_profile": p}, st) for st in stores]
            entered = threading.Event(); release = threading.Event()
            def post(*args, **kw):
                entered.set(); release.wait(2)
                return Mock(status_code=200, json=lambda: {"code": 0})
            try:
                with patch("engine.dispatcher.requests.post", side_effect=post) as http, ThreadPoolExecutor(2) as pool:
                    first = pool.submit(dispatchers[0].send_feishu_card, [e])
                    self.assertTrue(entered.wait(2))
                    second = pool.submit(dispatchers[1].send_feishu_card, [e])
                    self.assertFalse(second.result(2))
                    release.set()
                    self.assertTrue(first.result(2))
                    self.assertEqual(http.call_count, 1)
                stores[0].record_delivery(s.source, s.source_id, "same:feishu", 2)
                stores[1].record_delivery(s.source, s.source_id, "same:feishu", 1)
                self.assertFalse(stores[0].should_deliver(s.source, s.source_id, "same:feishu", 2))
            finally:
                release.set()
                for st in stores: st.close()

    def test_ambiguous_webhook_timeout_does_not_auto_resend(self):
        import requests
        s = signal(); p = reviewed(s); e = self.analyze(s, p)
        st = IntentStateStore(":memory:")
        try:
            d = Dispatcher({"client_id": "same", "seller_profile": p}, st)
            with patch("engine.dispatcher.requests.post", side_effect=requests.Timeout) as http:
                self.assertFalse(d.send_feishu_card([e]))
                self.assertFalse(d.send_feishu_card([e]))
                self.assertEqual(http.call_count, 1)
        finally: st.close()

    def test_cooldown_changes_while_a_caller_waits(self):
        limiter = SourceRateLimiter(.15)
        limiter.check_or_wait("https://same.test")
        sleeping = threading.Event(); original_sleep = time.sleep
        def wait(seconds):
            sleeping.set(); original_sleep(seconds)
        with patch("engine.collector.time.sleep", side_effect=wait), ThreadPoolExecutor(1) as pool:
            result = pool.submit(limiter.check_or_wait, "https://same.test")
            self.assertTrue(sleeping.wait(1))
            limiter.set_cooldown("https://same.test", 60)
            self.assertFalse(result.result(1)[0])

    def test_cli_has_no_lingering_collector_threads(self):
        code = """
import sys
from unittest.mock import patch
from engine.collector import CollectorHub
hub=CollectorHub({'state_db_path':':memory:', 'hacker_news_queries':['x'], 'github_queries':[],
'enable_devto':False,'enable_google_news':False,'enable_v2ex':False})
with patch.object(hub, '_worker_command', return_value=[sys.executable,'-c','import time; time.sleep(30)']):
    hub.run(global_timeout=.05)
hub.close()
"""
        started = time.monotonic()
        subprocess.run([sys.executable, "-c", code], check=True, capture_output=True, timeout=3)
        self.assertLess(time.monotonic() - started, 2)

    def test_real_worker_serialization_and_cross_run_state(self):
        code = """
import json,sys
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch,Mock
from engine.collector_worker import collect
payload={'hits':[{'objectID':'101','title':'Ask HN: Jira alternatives?',
'story_text':'<p>My team is looking for a Jira alternative.</p>', 'author':'buyer',
'created_at':datetime.now(timezone.utc).isoformat()}]}
with patch('engine.collector.requests.get',return_value=Mock(status_code=200,json=lambda:payload)):
    result=collect('hn',json.load(sys.stdin))
Path(sys.argv[1]).write_text(json.dumps(result))
"""
        with tempfile.TemporaryDirectory() as directory:
            config = {"state_db_path": str(Path(directory) / "state.db"), "hacker_news_queries": ["Jira"],
                      "github_queries": [], "enable_devto": False, "enable_google_news": False, "enable_v2ex": False}
            hub = CollectorHub(config)
            try:
                with patch.object(hub, "_worker_command", side_effect=lambda source, path: [sys.executable, "-c", code, str(path)]):
                    first = hub.run(global_timeout=3)
                    self.assertEqual(len(first), 1)
                    self.assertEqual(first[0].source_id, "hn_101")
                    self.assertEqual(first[0].content, "My team is looking for a Jira alternative.")
                    self.assertEqual(first[0].version_num, 1)
                    self.assertEqual(hub.run(global_timeout=3, only_new_or_updated=True), [])
            finally: hub.close()

    def test_devto_detail_is_required_for_complete_content(self):
        listing = Mock(status_code=200, json=lambda: [{"id": 1, "title": "Jira alternative", "url": "https://dev.to/a", "description": "short"}])
        detail = Mock(status_code=200, json=lambda: {"body_markdown": "Full body " * 200})
        with patch("engine.collector.request_with_retry", side_effect=[listing, detail]):
            sig = DevToCollector().fetch()[0]
            self.assertTrue(sig.content_complete)
            self.assertGreater(len(sig.content), 1000)
        with patch("engine.collector.request_with_retry", side_effect=[listing, None]):
            sig = DevToCollector().fetch()[0]
            self.assertFalse(sig.content_complete)
            self.assertFalse(sig.delivery_eligible)

    def test_uncertain_delivery_is_resolved_only_after_operator_confirmation(self):
        store = IntentStateStore(":memory:")
        try:
            token = store.claim_delivery("Test", "id", "customer:feishu", 1)
            store.finish_delivery("Test", "id", "customer:feishu", 1, token, "uncertain", "feishu")
            self.assertIsNone(store.claim_delivery("Test", "id", "customer:feishu", 1))
            store.resolve_delivery(token, received=False)
            self.assertIsNotNone(store.claim_delivery("Test", "id", "customer:feishu", 1))
        finally: store.close()

    def test_python_browser_contract(self):
        s = signal(); p = reviewed(s); e = self.analyze(s, p)
        facts = e.qualification_meta["policy_facts"]
        cases = []
        for kind in ("live_production", "historical_benchmark"):
            for fit in ("supported", "unsupported", "pending"):
                for actionable in (True, False):
                    f = {**facts, "dataset_kind": kind}
                    prof = reviewed(s, fit, actionable)
                    cases.append({"facts": f, "profile": prof})
        cases += [{"facts": facts, "profile": None}, {"facts": {**facts, "evaluation_verified": False}, "profile": p},
                  {"facts": {**facts, "published_at": "2099-01-01T00:00:00+00:00"}, "profile": p}]
        now = datetime.now(timezone.utc)
        expected = [evaluate_facts(c["facts"], c["profile"], now) for c in cases]
        script = """const fs=require('fs'),vm=require('vm');const c={URL};vm.createContext(c);
vm.runInContext(fs.readFileSync('engine/policy_client.js','utf8'),c);
const input=JSON.parse(fs.readFileSync(0,'utf8'));console.log(JSON.stringify(input.cases.map(v=>{
c.f=v.facts;c.p=v.profile;c.n=input.now;return vm.runInContext('evaluatePolicyFacts(f,p,n)',c)})));"""
        result = subprocess.run(["node", "-e", script], input=json.dumps({"cases": cases, "now": now.timestamp()*1000}),
                                capture_output=True, text=True, check=True)
        self.assertEqual(expected, json.loads(result.stdout))

    def test_xlsx_and_memory_fallback_execute_real_js(self):
        import openpyxl
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "client.js"; bundle.write_text(get_full_client_js())
            dest = Path(directory) / "report.xlsx"
            code = r"""const fs=require('fs'),vm=require('vm');const ctx={URL,Blob,TextEncoder,setTimeout,console,
document:{addEventListener(){},getElementById(){return null}},window:{addEventListener(){}},LEADS_DATA:[],
localStorage:{getItem(){return '未处理'},setItem(){throw Error('quota')}}};vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),ctx);
vm.runInContext('applyRender=()=>{};showToast=()=>{};setLeadStatus("a","已触达")',ctx);
if(vm.runInContext('getLeadStatus("a")',ctx)!=='已触达')process.exit(2);
if(vm.runInContext('sanitizeCsvCell("=1+1")',ctx)!=="'=1+1")process.exit(3);
(async()=>{const b=vm.runInContext('buildRealXlsxBlob(["名称","内容"],[["中文😀","=1+1"]],[20,40])',ctx);
fs.writeFileSync(process.argv[2],Buffer.from(await b.arrayBuffer()))})();"""
            subprocess.run(["node", "-e", code, str(bundle), str(dest)], check=True, capture_output=True)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                workbook = openpyxl.load_workbook(dest)
                sheet = workbook.active
                self.assertEqual(sheet["B2"].value, "=1+1")
                self.assertEqual(sheet["B2"].data_type, "s")
                self.assertEqual(sheet.freeze_panes, "A2")
                self.assertTrue(sheet["A2"].alignment.wrap_text)
                workbook.close()
                self.assertEqual(caught, [])

    def test_bounded_worker_pool_and_atomic_worker_write(self):
        from engine.collector_worker import atomic_write_json
        with tempfile.TemporaryDirectory() as directory:
            out_file = Path(directory) / "atomic.json"
            atomic_write_json(out_file, {"ok": True})
            self.assertEqual(json.loads(out_file.read_text(encoding="utf-8")), {"ok": True})
            self.assertFalse(out_file.with_suffix(".json.tmp").exists())

            config = {
                "state_db_path": str(Path(directory) / "state.db"),
                "collector_max_workers": 2,
                "hacker_news_queries": ["Jira"],
                "github_queries": ["Jira"],
                "enable_devto": True,
                "enable_google_news": False,
                "enable_v2ex": False,
            }
            hub = CollectorHub(config)
            code = """
import json, sys
from pathlib import Path
from engine.collector_worker import atomic_write_json
atomic_write_json(Path(sys.argv[1]), {"signals": [], "outcomes": {}, "deferred": {}, "cooldowns": {}})
"""
            try:
                with patch.object(hub, "_worker_command", side_effect=lambda source, path: [sys.executable, "-c", code, str(path)]):
                    hub.run(global_timeout=3)
                    self.assertEqual(hub.last_run_status, {"hn": "complete", "github": "complete", "devto": "complete"})
            finally:
                hub.close()

    def test_claude_adversarial_probes_a_to_j(self):
        ts = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d %H:%M UTC")
        def run_probe(title, body):
            s = IntentSignal(title=title, url="https://news.ycombinator.com/item?id=1", source="Hacker News",
                             content=body, timestamp=ts, source_id="hn_1")
            return self.analyze(s)

        # Probe A: Completed past migration / retrospective recommendation -> pain_only, Stage 1, blocked
        res_a = run_probe("We migrated to Linear last year",
            "We finished switching from Jira to Linear in 2025 and honestly it's great. Highly recommend Linear to everyone.")
        self.assertEqual(res_a.intent_type, "pain_only")
        self.assertEqual(res_a.contiguous_stage_num, 1)
        self.assertEqual(res_a.outreach_policy["policy_status"], "blocked")

        # Probe B: Stealth vendor self-promotion -> vendor_self_promotion, Stage 0, blocked
        res_b = run_probe("Jira alternatives that actually work",
            "I've been building Acme, an alternative to Jira for small teams. Feedback welcome, link in profile.")
        self.assertEqual(res_b.intent_type, "vendor_self_promotion")
        self.assertEqual(res_b.contiguous_stage_num, 0)
        self.assertEqual(res_b.outreach_policy["policy_status"], "blocked")

        # Probe C: Common English words ('twenty engineers', 'control plane', 'wiki 替代 + twenty engineers')
        res_c1 = run_probe("Our control plane keeps crashing",
            "We have twenty engineers and the control plane is too expensive to run, looking for alternatives for k8s.")
        self.assertEqual(res_c1.target_competitor, "未知")
        self.assertEqual(res_c1.contiguous_stage_num, 0)
        self.assertLessEqual(res_c1.intent_score, 35)
        self.assertEqual(res_c1.outreach_policy["policy_status"], "blocked")

        res_c2 = run_probe("Looking for a wiki alternative",
            "We have twenty engineers and our internal wiki is too slow, looking for alternatives.")
        self.assertEqual(res_c2.target_competitor, "未知")
        self.assertNotEqual(res_c2.target_competitor, "Twenty CRM")

        # Probe D: Chinese team scale ('50人团队')
        res_d = run_probe("求推荐 Jira 替代方案", "我们50人团队在用 Jira，续费太贵，寻找替代方案，预算有限。")
        self.assertEqual(res_d.qualification_meta["team_scale"]["source"], "原文明示")
        self.assertIn("50人团队", res_d.qualification_meta["team_scale"]["value"])
        self.assertEqual(res_d.qualification_meta["budget_status"]["source"], "原文明示")

        # Probe E: '学生作业，没有预算' -> lack_of_authority, Stage 1, blocked, zero-budget provenance
        res_e = run_probe("求推荐 Notion 替代", "学生作业，没有预算，寻找 Notion 的免费替代方案。")
        self.assertEqual(res_e.intent_type, "lack_of_authority")
        self.assertEqual(res_e.contiguous_stage_num, 1)
        self.assertEqual(res_e.outreach_policy["policy_status"], "blocked")
        self.assertIn("无商业采购预算", res_e.qualification_meta["budget_status"]["value"])

        # Probe F: Blogger / market survey ('Not for my company, just research') -> pain_only, Stage 1, blocked
        res_f = run_probe("Survey: what Jira alternatives do you use?",
            "I'm writing a blog post comparing Jira alternatives, what do you all use? Not for my company, just research.")
        self.assertEqual(res_f.intent_type, "pain_only")
        self.assertEqual(res_f.contiguous_stage_num, 1)
        self.assertEqual(res_f.outreach_policy["policy_status"], "blocked")

        # Probe G: '$5M seed' funding noise must NOT be marked as SaaS budget constraint
        res_g = run_probe("Looking for alternative to Datadog",
            "We just raised $5M seed and are looking for an alternative to Datadog.")
        self.assertEqual(res_g.qualification_meta["budget_status"]["source"], "未知")

        # Probe H, I, J: Canonical competitor aliases, empty competitor string, and malformed review in both Python & JS
        now = datetime.now(timezone.utc)
        base_facts = dict(source="Hacker News", source_id="hn_1", content_hash="h", pain_verified=True, evaluation_verified=True,
                          dataset_kind="live_production", delivery_eligible=True, content_complete=True,
                          published_at=(now - timedelta(days=1)).isoformat())
        prof_jira = {"brand_name": "Plane", "actor_role": "创始人", "approved_capabilities": ["Jira 导入"], "target_competitors": ["Jira"]}
        self.assertEqual(evaluate_facts({**base_facts, "competitor": "Atlassian Jira"}, prof_jira, now)["policy_status"], "neutral_inquiry_only")
        self.assertTrue(evaluate_facts({**base_facts, "competitor": "Atlassian Jira"}, prof_jira, now)["compatible"])
        prof_empty = {**prof_jira, "target_competitors": ["Atlassian Jira", " "]}
        self.assertFalse(evaluate_facts({**base_facts, "competitor": ""}, prof_empty, now)["compatible"])
        malformed_res = evaluate_facts({**base_facts, "competitor": "Atlassian Jira"}, {**prof_jira, "reviews": {"hn_1": ["x"]}}, now)
        self.assertFalse(malformed_res["review_current"])

    def test_webhook_markdown_injection_escaped_and_ledger_rehydration(self):
        from main import run_pipeline
        with tempfile.TemporaryDirectory() as directory:
            db_path = str(Path(directory) / "state.db")
            store = IntentStateStore(db_path)
            malicious_sig = signal(
                body="My team is looking to migrate away from Jira. <at id=all></at> [点击领取](https://evil.example/phish)",
                title="Ask HN: [钓鱼标题](https://evil.example) <at id=all></at> Jira alternative?",
            )
            store.upsert_signal(malicious_sig)
            store.close()

            prof = reviewed(malicious_sig, fit="supported", actionable=True)
            cfg = {
                "state_db_path": db_path,
                "client_id": "tenant_alpha",
                "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
                "wechat_webhook": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
                "seller_profile": prof,
                "use_llm_api": False,
            }
            captured_payloads = []
            def fake_post(url, json=None, timeout=10):
                captured_payloads.append(json)
                return Mock(status_code=200, json=lambda: {"code": 0, "errcode": 0})

            with patch.object(CollectorHub, "run", return_value=[]), patch("engine.dispatcher.requests.post", side_effect=fake_post):
                summary = run_pipeline(
                    config=cfg,
                    demo_mode=False,
                    output_html_path=str(Path(directory) / "report.html"),
                    internal_bd_path=str(Path(directory) / "bd.html"),
                )
            self.assertEqual(summary["feishu_status"], "SUCCESS")
            self.assertEqual(summary["wechat_status"], "SUCCESS")
            self.assertEqual(summary["delivered_count"], 2)
            serialized = json.dumps(captured_payloads, ensure_ascii=False)
            self.assertNotIn("<at id=all>", serialized)
            self.assertNotIn("](https://evil.example", serialized)

    def test_resolve_delivery_guards_active_sending_and_resets_attempts_and_privacy_ops(self):
        store = IntentStateStore(":memory:")
        try:
            token = store.claim_delivery("Hacker News", "hn_1", "client:feishu", 1)
            # Active 'sending' claim (<60s old) cannot be prematurely resolved by operator
            with self.assertRaises(ValueError):
                store.resolve_delivery(token, received=False, min_sending_age_seconds=60.0)
            # Simulate 3 failed attempts then uncertain timeout
            for _ in range(2):
                store.finish_delivery("Hacker News", "hn_1", "client:feishu", 1, token, "failed", "feishu")
                token = store.claim_delivery("Hacker News", "hn_1", "client:feishu", 1)
            store.finish_delivery("Hacker News", "hn_1", "client:feishu", 1, token, "uncertain", "feishu")
            # Operator confirms 'not-sent' -> attempts reset to 0 so it can be re-claimed
            store.resolve_delivery(token, received=False)
            self.assertTrue(store.should_deliver("Hacker News", "hn_1", "client:feishu", 1))
            self.assertIsNotNone(store.claim_delivery("Hacker News", "hn_1", "client:feishu", 1))

            # Privacy & retention compliance operations
            s = signal()
            s.author = "privacy_user"
            store.upsert_signal(s)
            self.assertEqual(store.erase_author("privacy_user"), 1)
            self.assertIsNone(store.get_signal_record(s.source, s.source_id))
        finally:
            store.close()


if __name__ == "__main__": unittest.main()
