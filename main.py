"""
IntentRadar - 公开社区竞品替换信号核验与销售赋能引擎 主程序 (v3.1)
Resolves Audit Round-2 Finding #1:
- Live mode (without `--demo`) NEVER mixes `get_mock_signals()` historical benchmark samples into production runs.
- When live collection returns 0 signals or fails, generates an honest zero-result production status report
  and never dispatches historical benchmark samples to webhooks.
"""

import argparse
import json
import logging
import os
import sys
import tempfile
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


def run_pipeline(config: Dict, demo_mode: bool = False, output_html_path: str = "report.html", internal_bd_path: str = "") -> Dict:
    """
    Executes the collection -> qualification -> dispatch pipeline with strict dataset separation.
    In non-demo (live production) mode, historical benchmark samples are NEVER mixed in.
    """
    if demo_mode:
        logger.info("Running in HISTORICAL BENCHMARK mode (--demo): loading 10 API-verified HN benchmark samples...")
        config = dict(config)
        config["use_llm_api"] = False
        config["run_mode"] = "historical_benchmark"
        raw_signals = get_mock_signals()
    else:
        logger.info("Running in LIVE PRODUCTION mode: querying active collectors (HN, GitHub Issues, Dev.to, Google News RSS, V2EX)...")
        config = dict(config)
        config["run_mode"] = "live_production"
        collector_hub = CollectorHub(config)
        raw_signals = collector_hub.run()
        # CRITICAL (Audit Finding #1): Never mix get_mock_signals() into live production mode!
        if not raw_signals:
            logger.warning("Live collection returned 0 signals. Generating honest empty production report (zero historical padding).")

    logger.info(f"Step 1 Complete: Collected {len(raw_signals)} candidate signals (mode={config['run_mode']}).")

    logger.info("Step 2: Performing 4-Stage Sequential Qualification & Provenance Extraction...")
    analyzer = IntentAnalyzer(config)
    enriched_signals = analyzer.analyze_signals(raw_signals)
    logger.info(f"Step 2 Complete: Qualified {len(enriched_signals)} signals (Score >= {config.get('min_intent_score', 50)}).")

    logger.info("Step 3: Generating Client Verification Workbench & Isolated Internal BD Manual...")
    dispatcher = Dispatcher(config)
    if not internal_bd_path:
        internal_dir = os.path.join(tempfile.gettempdir(), "intent_radar_internal")
        os.makedirs(internal_dir, exist_ok=True)
        internal_bd_path = os.path.join(internal_dir, "internal_bd_ops.html")

    report_summary = dispatcher.dispatch(
        enriched_signals,
        output_html_path=output_html_path,
        internal_bd_path=internal_bd_path,
    )
    report_summary["run_mode"] = config["run_mode"]
    report_summary["raw_collected_count"] = len(raw_signals)
    report_summary["qualified_count"] = len(enriched_signals)
    return report_summary


def main():
    parser = argparse.ArgumentParser(description="IntentRadar - 公开社区竞品替换信号核验工作台")
    parser.add_argument("--config", default=os.path.join(CURRENT_DIR, "config.json"), help="配置文件路径")
    parser.add_argument("--demo", action="store_true", help="使用历史基准样本集 (historical_benchmark) 生成研究与核验工作台")
    parser.add_argument("--score", type=int, default=None, help="覆盖最低意向评分阈值 (0-100)")
    parser.add_argument("--html", default=os.path.join(CURRENT_DIR, "report.html"), help="输出客户端核验工作台HTML路径")
    parser.add_argument(
        "--internal-html",
        default=os.path.join(tempfile.gettempdir(), "intent_radar_internal", "internal_bd_ops.html"),
        help="内部 BD 运营手册输出路径（默认隔离在系统临时目录，不写入公开部署目录）",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if args.score is not None:
        config["min_intent_score"] = args.score

    print("""
==============================================================================
   🎯 IntentRadar · 公开社区竞品替换信号核验引擎 (v3.1 Production Pilot Edition)
   定位: 帮助具备企业版与迁移承接能力的挑战者团队发现并核验公开替换机会
==============================================================================
    """)

    report_summary = run_pipeline(
        config=config,
        demo_mode=args.demo,
        output_html_path=args.html,
        internal_bd_path=args.internal_html,
    )

    logger.info("All pipeline stages executed successfully!")
    print(f"\n✅ 客户交付核验工作台已生成至: file://{os.path.abspath(args.html)}")
    print(f"🔒 内部 BD 运营手册已物理隔离生成至: file://{os.path.abspath(report_summary.get('internal_bd_path', args.internal_html))}")
    if report_summary.get("feishu_status") == "SUCCESS":
        print("✅ 飞书群机器人通知推送成功！")
    if report_summary.get("wechat_status") == "SUCCESS":
        print("✅ 企业微信群机器人通知推送成功！")


if __name__ == "__main__":
    main()
