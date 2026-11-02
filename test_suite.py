"""
Automated Verification & Audit Test Suite for IntentRadar (v3.0).
Verifies:
1. Evidence Provenance & Tri-state Qualification Meta ([原文明示] / [模型推断] / [未知])
2. 4-Stage Qualification Calibration (Active Replacement vs. Pending Inquiry vs. No Authority)
3. Incumbent vs. Candidate Alternative Entity Separation
4. Honest Outreach Templates (Transparent Builder Disclosure, Zero Sockpuppets)
5. Physical Separation of Client Workbench (`report.html`) and Internal BD Playbook (`internal_bd_ops.html`)
6. Precompiled Tailwind CSS (Zero runtime Play CDN dependency)
"""

import os
import unittest
from engine.collector import IntentSignal, normalize_url
from engine.analyzer import IntentAnalyzer
from engine.dispatcher import Dispatcher
from engine.mock_data import get_mock_signals
from engine.growth_playbook import (
    get_brand_presets,
    get_launch_campaigns,
    get_pilot_offers,
    get_seed_clients,
)


class TestIntentRadarAudit(unittest.TestCase):
    def setUp(self):
        self.mock_config = {
            "min_intent_score": 50,
            "limit_per_query": 2,
            "hacker_news_queries": ["alternative to"],
            "github_queries": ["alternative to"],
            "news_queries": [],
            "enable_v2ex": False,
            "use_llm_api": False,
        }

    def test_url_normalization_and_signal_provenance(self):
        norm = normalize_url("https://News.YCombinator.com/item?id=41648918&utm_source=twitter#comment")
        self.assertEqual(norm, "https://news.ycombinator.com/item?id=41648918")

        mocks = get_mock_signals()
        self.assertEqual(len(mocks), 10)
        allowed_sources = {"原文明示", "模型推断", "未知"}
        for sig in mocks:
            self.assertTrue(sig.source_id.startswith("hn_"), f"Expected hn_ prefix, got {sig.source_id}")
            item_num = sig.source_id.split("_", 1)[1]
            self.assertTrue(item_num.isdigit(), f"Expected numeric HN item ID, got {sig.source_id}")
            self.assertEqual(sig.url, f"https://news.ycombinator.com/item?id={item_num}")
            self.assertTrue(len(sig.evidence_quote) >= 20)
            self.assertIn(sig.evidence_quote[:25], sig.content)
            self.assertTrue(sig.collected_at)
            qm = sig.qualification_meta
            for field in ("team_scale", "budget_status", "decision_authority", "migration_urgency"):
                self.assertIn(field, qm)
                self.assertIn(qm[field]["source"], allowed_sources)
                self.assertTrue(qm[field]["value"])
            self.assertTrue(isinstance(qm.get("blocking_conditions"), list) and len(qm["blocking_conditions"]) >= 1)
            self.assertTrue(qm.get("contact_path"))

    def test_four_stage_qualification_and_entity_separation(self):
        analyzer = IntentAnalyzer(self.mock_config)
        signals = get_mock_signals()
        enriched_list = analyzer.analyze_signals(signals)
        self.assertEqual(len(enriched_list), 10)

        by_id = {e.signal.id: e for e in enriched_list}

        # 1. Active team replacement with candidate alternatives (hn_41648918)
        postman_sig = by_id["hn_41648918"]
        self.assertEqual(postman_sig.target_competitor, "Postman")
        self.assertIn("Hoppscotch", postman_sig.candidate_alternatives)
        self.assertIn("Bruno", postman_sig.candidate_alternatives)
        self.assertGreaterEqual(postman_sig.intent_score, 85)
        self.assertIn("阶段 4/4", postman_sig.qualification_stage)

        # 2. Negative authority calibration sample (hn_37146814: "Sadly using Jira was not my choice")
        no_auth_sig = by_id["hn_37146814"]
        self.assertLess(no_auth_sig.intent_score, 68)
        self.assertIn("无替换决策权", no_auth_sig.intent_level)
        self.assertIn("阶段 1/4", no_auth_sig.qualification_stage)

        # 3. Minimal info inquiry sample requiring qualification (hn_36537006)
        minimal_sig = by_id["hn_36537006"]
        self.assertLess(minimal_sig.intent_score, 78)
        self.assertIn("待核验资格", minimal_sig.intent_level)
        self.assertIn("阶段 2/4", minimal_sig.qualification_stage)

    def test_honest_outreach_zero_sockpuppet(self):
        analyzer = IntentAnalyzer(self.mock_config)
        enriched_list = analyzer.analyze_signals(get_mock_signals())
        for item in enriched_list:
            self.assertTrue(
                item.public_reply.startswith("利益相关披露："),
                f"Public reply must start with transparent disclosure, got: {item.public_reply[:40]}",
            )
            self.assertNotIn("上季度刚从", item.public_reply)
            self.assertNotIn("省 55%", item.pitch_exec)
            self.assertNotIn("省 60%", item.pitch_exec)

    def test_two_tier_prefilter_without_literal_alternative_word(self):
        analyzer = IntentAnalyzer(self.mock_config)
        # Post complaining about Datadog billing spike & self-hosting without using the word "alternative"
        sig = IntentSignal(
            title="Our Datadog custom metrics bill jumped 3x this quarter",
            url="https://news.ycombinator.com/item?id=99999999",
            source="Hacker News",
            content="We are evaluating self-host observability stacks to keep APM costs predictable.",
        )
        self.assertTrue(analyzer._passes_prefilter(sig))

    def test_dual_html_generation_and_separation(self):
        analyzer = IntentAnalyzer(self.mock_config)
        enriched = analyzer.analyze_signals(get_mock_signals())

        test_client_html = "/tmp/test_client_report.html"
        dispatcher = Dispatcher(self.mock_config)
        summary = dispatcher.dispatch(enriched, output_html_path=test_client_html)
        internal_html = summary["internal_bd_path"]

        self.assertTrue(os.path.exists(test_client_html))
        self.assertTrue(os.path.exists(internal_html))

        with open(test_client_html, "r", encoding="utf-8") as f:
            client_content = f.read()

        # Verify client report has zero internal BD playbook data and zero Play CDN script
        self.assertNotIn("SEED_CLIENTS_DATA", client_content)
        self.assertNotIn("100% 真实买家", client_content)
        self.assertNotIn("cdn.tailwindcss.com", client_content)
        self.assertIn("公开社区实盘核验样本库", client_content)
        self.assertIn("createZipStoreArchive", client_content)
        self.assertIn("sanitizeSpreadsheetCell", client_content)

        with open(internal_html, "r", encoding="utf-8") as f:
            bd_content = f.read()

        self.assertIn("¥999 / 7 天", bd_content)
        self.assertIn("¥1,999 / 14 天", bd_content)
        self.assertIn("¥2,999 / 14 天", bd_content)
        self.assertIn("399.80", bd_content)

        os.remove(test_client_html)
        os.remove(internal_html)

    def test_pilot_offers_and_brand_presets(self):
        offers = get_pilot_offers()
        self.assertEqual(len(offers), 3)
        presets = get_brand_presets()
        self.assertGreaterEqual(len(presets), 7)
        for p in presets:
            self.assertIn("target_competitors", p)
            self.assertIn("approved_capabilities", p)
            self.assertIn("known_limitations", p)
        self.assertGreaterEqual(len(get_seed_clients()), 6)
        self.assertEqual(len(get_launch_campaigns()), 3)


if __name__ == "__main__":
    unittest.main()
