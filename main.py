"""
IntentRadar - 公开社区竞品替换信号核验与销售赋能引擎 主程序
"""

import argparse
import json
import logging
import os
import sys
from typing import Dict

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from engine.collector import CollectorHub
from engine.analyzer import IntentAnalyzer
from engine.dispatcher import Dispatcher
from engine.mock_data import get_mock_signals

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Main")


def load_config(config_path: str) -> Dict:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    logger.warning(f"Config file {config_path} not found. Using default parameters.")
    return {}


def main():
    parser = argparse.ArgumentParser(description="IntentRadar - 公开社区竞品替换信号核验工作台")
    parser.add_argument("--config", default=os.path.join(CURRENT_DIR, "config.json"), help="配置文件路径")
    parser.add_argument("--demo", action="store_true", help="使用已核验的公开社区实盘样本集生成工作台")
    parser.add_argument("--score", type=int, default=None, help="覆盖最低意向评分阈值 (0-100)")
    parser.add_argument("--html", default=os.path.join(CURRENT_DIR, "report.html"), help="输出客户端核验工作台HTML路径")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.score is not None:
        config["min_intent_score"] = args.score

    print("""
==============================================================================
   🎯 IntentRadar · 公开社区竞品替换信号核验引擎 (v3.0 Audit Edition)
   定位: 帮助具备企业版与迁移承接能力的挑战者团队发现并核验公开替换机会
==============================================================================
    """)

    # 1. Collection Phase
    if args.demo:
        logger.info("Running with API-verified Hacker News benchmark sample signals...")
        config["use_llm_api"] = False
        raw_signals = get_mock_signals()
    else:
        logger.info("Initializing multi-source live collectors (HN, GitHub, Google News, V2EX)...")
        collector_hub = CollectorHub(config)
        live_signals = collector_hub.run()
        seen_ids = set(s.id for s in live_signals)
        curated_samples = [s for s in get_mock_signals() if s.id not in seen_ids]
        raw_signals = live_signals + curated_samples

    logger.info(f"Step 1 Complete: Collected {len(raw_signals)} candidate signals.")

    # 2. Qualification & Scoring Phase
    logger.info("Step 2: Performing 4-Stage Qualification & Provenance Extraction...")
    analyzer = IntentAnalyzer(config)
    enriched_signals = analyzer.analyze_signals(raw_signals)
    logger.info(f"Step 2 Complete: Qualified {len(enriched_signals)} signals (Score >= {config.get('min_intent_score', 50)}).")

    # 3. Dispatch & Dual HTML Generation Phase
    logger.info("Step 3: Generating Client Verification Workbench & Internal BD Playbook...")
    dispatcher = Dispatcher(config)
    report_summary = dispatcher.dispatch(enriched_signals, output_html_path=args.html)

    logger.info("All pipeline stages executed successfully!")
    print(f"\n✅ 客户交付核验工作台已生成至: file://{os.path.abspath(args.html)}")
    print(f"🔒 内部 BD 与单赛道试点运营手册已隔离生成至: file://{os.path.abspath(report_summary.get('internal_bd_path', 'internal_bd_ops.html'))}")
    if report_summary.get("feishu_status") == "SUCCESS":
        print("✅ 飞书群机器人通知推送成功！")
    if report_summary.get("wechat_status") == "SUCCESS":
        print("✅ 企业微信群机器人通知推送成功！")


if __name__ == "__main__":
    main()
