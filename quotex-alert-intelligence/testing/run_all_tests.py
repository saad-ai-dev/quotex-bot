#!/usr/bin/env python3
"""
Master Test Runner for Quotex Alert Intelligence System
ALERT-ONLY - No trade execution.

Orchestrates all testing phases:
    1. Pytest unit tests
    2. Integration tests
    3. Detector edge case tests
    4. Scoring profile tests
    5. Historical replay validation
    6. Combined report generation

Usage:
    python -m testing.run_all_tests
    python testing/run_all_tests.py
    python testing/run_all_tests.py --skip-replay
    python testing/run_all_tests.py --quick
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

# Ensure project root is importable
PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("run_all_tests")


# ---------------------------------------------------------------------------
# Test phase runners
# ---------------------------------------------------------------------------


def run_pytest_suite(test_path: str, label: str) -> Dict[str, Any]:
    """Run a pytest suite and return structured results.

    ALERT-ONLY: Tests validate alert system functionality.

    Args:
        test_path: Path to the test file or directory.
        label: Human-readable label for this suite.

    Returns:
        Dict with passed, failed, errors, duration, and output.
    """
    logger.info("Running %s: %s", label, test_path)
    start = time.monotonic()

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short", "-q"],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=PROJECT_ROOT,
        )
        duration = round(time.monotonic() - start, 2)
        output = result.stdout + result.stderr

        # Parse counts from pytest output
        passed = _count_in_output(output, " passed")
        failed = _count_in_output(output, " failed")
        errors = _count_in_output(output, " error")

        return {
            "label": label,
            "path": test_path,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "duration_seconds": duration,
            "exit_code": result.returncode,
            "output_tail": output[-1000:] if len(output) > 1000 else output,
        }
    except subprocess.TimeoutExpired:
        return {
            "label": label,
            "path": test_path,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "duration_seconds": 300,
            "exit_code": -1,
            "output_tail": "TIMEOUT: Test suite exceeded 300 second limit",
        }
    except Exception as exc:
        return {
            "label": label,
            "path": test_path,
            "passed": 0,
            "failed": 0,
            "errors": 1,
            "duration_seconds": round(time.monotonic() - start, 2),
            "exit_code": -1,
            "output_tail": f"ERROR: {exc}",
        }


def _count_in_output(output: str, pattern: str) -> int:
    """Count occurrences of a pattern in pytest output."""
    count = 0
    for line in output.split("\n"):
        if pattern in line:
            # Try to extract the number before the pattern
            parts = line.strip().split()
            for i, part in enumerate(parts):
                if pattern.strip() in parts[min(i + 1, len(parts) - 1):]:
                    try:
                        count = max(count, int(part))
                    except (ValueError, IndexError):
                        pass
    return count


async def run_historical_replay() -> Dict[str, Any]:
    """Run historical replay validation.

    ALERT-ONLY: Validates alert predictions against synthetic candle data.

    Returns:
        Dict with replay metrics.
    """
    logger.info("Running historical replay validation...")
    try:
        from testing.historical_replay import HistoryReplayRunner
        from testing.fixtures.candle_fixtures import (
            generate_uptrend,
            generate_downtrend,
            generate_breakout,
            generate_reversal,
            generate_range,
        )

        runner = HistoryReplayRunner()
        sequences = [
            {"candles": generate_uptrend(30), "actual_direction": "UP"},
            {"candles": generate_downtrend(30), "actual_direction": "DOWN"},
            {"candles": generate_breakout(30), "actual_direction": "UP"},
            {"candles": generate_reversal(30), "actual_direction": "DOWN"},
            {"candles": generate_range(30), "actual_direction": None},
            {"candles": generate_uptrend(30, step=0.0010), "actual_direction": "UP"},
            {"candles": generate_downtrend(30, step=0.0010), "actual_direction": "DOWN"},
        ]

        batch_result = await runner.run_replay(sequences, "LIVE", "1m")
        report = runner.generate_report(batch_result)
        return report
    except Exception as exc:
        logger.error("Historical replay failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------


async def main(args: argparse.Namespace) -> None:
    """Run all test phases and generate a combined report.

    ALERT-ONLY: Complete system validation, no trade execution.
    """
    all_results: Dict[str, Any] = {
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "system": "Quotex Alert Intelligence (ALERT-ONLY)",
        "phases": {},
    }
    total_start = time.monotonic()

    # Phase 1: Unit tests
    logger.info("=" * 60)
    logger.info("PHASE 1: Unit Tests")
    logger.info("=" * 60)
    unit_results = run_pytest_suite(
        os.path.join(BACKEND_DIR, "tests"),
        "Unit Tests",
    )
    all_results["phases"]["unit_tests"] = unit_results

    if not args.quick:
        # Phase 2: Integration tests
        logger.info("=" * 60)
        logger.info("PHASE 2: Integration Tests")
        logger.info("=" * 60)
        integration_results = run_pytest_suite(
            os.path.join(PROJECT_ROOT, "testing", "test_integration_api.py"),
            "Integration API Tests",
        )
        all_results["phases"]["integration_api"] = integration_results

        integration_mongo = run_pytest_suite(
            os.path.join(PROJECT_ROOT, "testing", "test_integration_mongodb.py"),
            "Integration MongoDB Tests",
        )
        all_results["phases"]["integration_mongodb"] = integration_mongo

        # Phase 3: Detector edge cases
        logger.info("=" * 60)
        logger.info("PHASE 3: Detector Edge Case Tests")
        logger.info("=" * 60)
        edge_case_results = run_pytest_suite(
            os.path.join(PROJECT_ROOT, "testing", "test_detector_edge_cases.py"),
            "Detector Edge Cases",
        )
        all_results["phases"]["detector_edge_cases"] = edge_case_results

        # Phase 4: Scoring profile tests
        logger.info("=" * 60)
        logger.info("PHASE 4: Scoring Profile Tests")
        logger.info("=" * 60)
        profile_results = run_pytest_suite(
            os.path.join(PROJECT_ROOT, "testing", "test_scoring_profiles.py"),
            "Scoring Profiles",
        )
        all_results["phases"]["scoring_profiles"] = profile_results

    # Phase 5: Historical replay
    if not args.skip_replay:
        logger.info("=" * 60)
        logger.info("PHASE 5: Historical Replay Validation")
        logger.info("=" * 60)
        replay_results = await run_historical_replay()
        all_results["phases"]["historical_replay"] = replay_results

    # Compute totals
    total_duration = round(time.monotonic() - total_start, 2)
    total_passed = sum(
        p.get("passed", 0)
        for p in all_results["phases"].values()
        if isinstance(p, dict) and "passed" in p
    )
    total_failed = sum(
        p.get("failed", 0)
        for p in all_results["phases"].values()
        if isinstance(p, dict) and "failed" in p
    )
    total_errors = sum(
        p.get("errors", 0)
        for p in all_results["phases"].values()
        if isinstance(p, dict) and "errors" in p
    )

    all_results["summary"] = {
        "total_duration_seconds": total_duration,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "total_errors": total_errors,
        "overall_status": "PASS" if total_failed == 0 and total_errors == 0 else "FAIL",
    }

    # Generate combined report
    logger.info("=" * 60)
    logger.info("GENERATING REPORTS")
    logger.info("=" * 60)

    os.makedirs(REPORTS_DIR, exist_ok=True)

    # Save JSON report
    json_path = os.path.join(
        REPORTS_DIR,
        f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
    )
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, default=str)
    logger.info("JSON report saved: %s", json_path)

    # Generate Markdown report
    try:
        from testing.report_generator import ReportGenerator

        gen = ReportGenerator()

        report_data = {}
        if "unit_tests" in all_results["phases"]:
            report_data["test_results"] = all_results["phases"]["unit_tests"]
        if "historical_replay" in all_results["phases"]:
            replay = all_results["phases"]["historical_replay"]
            if "error" not in replay:
                report_data["batch_metrics"] = {
                    "total": replay.get("total_sequences", 0),
                    "wins": replay.get("wins", 0),
                    "losses": replay.get("losses", 0),
                    "neutral": replay.get("neutral", 0),
                    "unknown": replay.get("unknown", 0),
                    "no_trade": replay.get("no_trade_count", 0),
                    "win_rate": replay.get("win_rate", 0),
                    "precision_up": 0,
                    "precision_down": 0,
                    "no_trade_rate": 0,
                    "avg_confidence": 0,
                    "confidence_calibration": {},
                }

        md_report = gen.generate_full_report(report_data)
        md_path = os.path.join(
            REPORTS_DIR,
            f"full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        )
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_report)
        logger.info("Markdown report saved: %s", md_path)
    except Exception as exc:
        logger.warning("Could not generate Markdown report: %s", exc)

    # Console summary
    print()
    print("=" * 60)
    print("QUOTEX ALERT INTELLIGENCE - TEST RESULTS")
    print("ALERT-ONLY - No trade execution")
    print("=" * 60)
    print()

    for phase_name, phase_data in all_results["phases"].items():
        if isinstance(phase_data, dict):
            if "passed" in phase_data:
                status = "PASS" if phase_data.get("failed", 0) == 0 else "FAIL"
                print(
                    f"  {phase_data.get('label', phase_name):40s} "
                    f"{status:6s}  "
                    f"P:{phase_data.get('passed', 0)} "
                    f"F:{phase_data.get('failed', 0)} "
                    f"E:{phase_data.get('errors', 0)} "
                    f"({phase_data.get('duration_seconds', 0)}s)"
                )
            elif "win_rate" in phase_data:
                print(
                    f"  {'Historical Replay':40s} "
                    f"WR:{phase_data.get('win_rate', 0)}%  "
                    f"W:{phase_data.get('wins', 0)} "
                    f"L:{phase_data.get('losses', 0)} "
                    f"N:{phase_data.get('neutral', 0)}"
                )

    print()
    summary = all_results["summary"]
    print(f"  Overall: {summary['overall_status']}  ({summary['total_duration_seconds']}s)")
    print(f"  Reports: {REPORTS_DIR}")
    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Master Test Runner for Quotex Alert Intelligence (ALERT-ONLY)",
    )
    parser.add_argument(
        "--skip-replay",
        action="store_true",
        help="Skip the historical replay validation phase",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run only unit tests and replay (skip integration/edge/profile tests)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
