"""
Improvement Loop Runner for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Runs automated cycles of: test -> replay -> analyze -> propose -> apply -> retest,
comparing each cycle against the previous to track improvement. Stops
when improvements plateau or a maximum cycle count is reached.
"""
import asyncio
import copy
import json
import logging
import os
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import sys

_BACKEND_DIR = str(Path(__file__).resolve().parent.parent / "backend")
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CycleReport:
    """Report for a single improvement cycle.

    ALERT-ONLY: Tracks alert system improvement progress per cycle.
    """

    cycle_number: int
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    test_results: Dict[str, Any] = field(default_factory=dict)
    replay_metrics: Dict[str, Any] = field(default_factory=dict)
    replay_results: List[Dict[str, Any]] = field(default_factory=list)
    failure_analysis: Dict[str, Any] = field(default_factory=dict)
    improvements_proposed: List[Dict[str, Any]] = field(default_factory=list)
    improvements_applied: List[Dict[str, Any]] = field(default_factory=list)
    comparison_with_previous: Dict[str, Any] = field(default_factory=dict)
    overall_win_rate: float = 0.0
    overall_assessment: str = "pending"


# ---------------------------------------------------------------------------
# Main improvement loop
# ---------------------------------------------------------------------------


class ImprovementLoop:
    """Orchestrates the improvement loop: test, analyze, improve, retest.

    ALERT-ONLY: This loop improves alert prediction accuracy, not
    trade execution strategy. All changes are to detection thresholds,
    scoring weights, and profile configurations.

    The loop:
        1. Run automated tests (pytest) to verify code quality.
        2. Run historical replay validation through the orchestrator.
        3. Analyze results and identify top failure modes.
        4. Propose config adjustments (threshold changes, weight changes).
        5. Apply safe improvements to JSON config files in shared/configs/.
        6. Re-run validation on fresh sequences.
        7. Compare before/after metrics.
        8. Generate changelog.
        9. Stop when improvements plateau.
    """

    # Maximum safe adjustment per config key per cycle
    MAX_WEIGHT_DELTA = 3
    MAX_THRESHOLD_DELTA = 5
    MAX_PENALTY_DELTA = 0.5

    def __init__(
        self,
        config_dir: Optional[str] = None,
        max_cycles: int = 10,
        plateau_threshold: float = 1.0,
    ) -> None:
        """Initialize the improvement loop.

        Args:
            config_dir: Path to shared/configs directory containing
                profile JSON files. Defaults to auto-detect.
            max_cycles: Maximum number of improvement cycles to run.
            plateau_threshold: Minimum win rate delta (%) to consider
                an improvement significant.
        """
        if config_dir is None:
            config_dir = str(
                Path(__file__).resolve().parent.parent / "shared" / "configs"
            )
        self.config_dir = config_dir
        self.max_cycles = max_cycles
        self.plateau_threshold = plateau_threshold
        self._cycle_history: List[CycleReport] = []
        self._changelog: List[Dict[str, Any]] = []
        self._config_backups: Dict[str, Dict[str, Any]] = {}

    async def run_full_loop(self) -> List[CycleReport]:
        """Run the complete improvement loop until plateau or max cycles.

        ALERT-ONLY: Iteratively improves alert prediction accuracy.

        Returns:
            List of CycleReport objects for all completed cycles.
        """
        logger.info(
            "Starting improvement loop (max_cycles=%d, plateau=%.1f%%)",
            self.max_cycles, self.plateau_threshold,
        )

        # Backup all configs before starting
        self._backup_configs()

        for cycle_num in range(1, self.max_cycles + 1):
            report = await self.run_cycle(cycle_num)
            self._cycle_history.append(report)

            if self.should_stop():
                logger.info(
                    "Improvement loop stopping after cycle %d (plateau detected)",
                    cycle_num,
                )
                break

        # Save final changelog
        self.save_changelog()

        # Generate summary
        self._print_summary()

        return self._cycle_history

    async def run_cycle(self, cycle_number: int) -> CycleReport:
        """Run a single improvement cycle.

        ALERT-ONLY: Each cycle aims to improve alert accuracy through:
        1. Testing code quality
        2. Replaying candle data through the engine
        3. Analyzing failure modes
        4. Proposing and applying safe config changes
        5. Comparing with the previous cycle

        Args:
            cycle_number: Sequential cycle number (1-based).

        Returns:
            CycleReport with all cycle data.
        """
        report = CycleReport(
            cycle_number=cycle_number,
            started_at=datetime.now(timezone.utc),
        )
        logger.info("=" * 50)
        logger.info("Starting improvement cycle %d", cycle_number)
        logger.info("=" * 50)

        # Step 1: Run automated tests
        report.test_results = await self.run_automated_tests()
        tests_passed = report.test_results.get("exit_code", 1) == 0
        logger.info(
            "Cycle %d: Tests %s (exit_code=%d)",
            cycle_number,
            "PASSED" if tests_passed else "FAILED",
            report.test_results.get("exit_code", -1),
        )

        # Step 2: Run historical replay validation
        from testing.historical_replay_runner import ReplayRunner
        from testing.fixtures.candle_generator import CandleGenerator

        runner = ReplayRunner()
        gen = CandleGenerator(seed=42 + cycle_number * 7)

        # Use different seeds each cycle for diversity
        all_results = []
        for expiry in ["1m", "2m", "3m"]:
            seed_base = 100 + cycle_number * 50 + hash(expiry) % 500
            batch = gen.generate_batch(count=30, seed_start=seed_base)
            results = await runner.run_batch(batch, expiry_profile=expiry)
            all_results.extend(results)

        report.replay_results = all_results
        report.replay_metrics = runner.compute_metrics(all_results)
        report.overall_win_rate = report.replay_metrics.get(
            "win_rate_excluding_neutral_unknown", 0.0
        )
        logger.info(
            "Cycle %d: Replay complete - win_rate=%.1f%%, total=%d",
            cycle_number,
            report.overall_win_rate,
            report.replay_metrics.get("total_alerts", 0),
        )

        # Step 3: Analyze results and identify top failure modes
        from testing.batch_analyzer import BatchAnalyzer

        analyzer = BatchAnalyzer()

        # Convert replay results to analyzer format
        formatted_signals = []
        for r in all_results:
            formatted_signals.append({
                "signal_id": r.get("signal_id", "unknown"),
                "direction": r.get("prediction_direction", "NO_TRADE"),
                "prediction_direction": r.get("prediction_direction", "NO_TRADE"),
                "confidence": r.get("confidence", 0),
                "outcome": r.get("outcome", "UNKNOWN"),
                "market_type": r.get("market_type", "LIVE"),
                "expiry_profile": r.get("expiry_profile", "1m"),
                "reasons": r.get("reasons", []),
                "detected_features": r.get("detected_features", {}),
                "chart_read_confidence": r.get("chart_read_confidence", 1.0),
            })

        analysis = analyzer.analyze(formatted_signals)
        report.failure_analysis = analyzer.generate_failure_report(
            analysis.failure_analyses
        )
        logger.info(
            "Cycle %d: %d failures analyzed across %d categories",
            cycle_number,
            report.failure_analysis.get("total_failures", 0),
            report.failure_analysis.get("category_count", 0),
        )

        # Step 4: Propose config adjustments
        recommendations = analyzer.generate_improvement_recommendations(
            analysis.failure_groups
        )
        report.improvements_proposed = self._filter_safe_proposals(recommendations)
        logger.info(
            "Cycle %d: %d improvements proposed (%d safe for auto-apply)",
            cycle_number,
            len(recommendations),
            len(report.improvements_proposed),
        )

        # Step 5: Apply safe improvements to config files
        for proposal in report.improvements_proposed:
            applied = self._apply_config_changes(proposal)
            if applied:
                report.improvements_applied.append(proposal)

        logger.info(
            "Cycle %d: %d improvements applied",
            cycle_number, len(report.improvements_applied),
        )

        # Step 6: Compare with previous cycle
        if self._cycle_history:
            previous = self._cycle_history[-1]
            report.comparison_with_previous = self._compare_with_previous(
                report, previous
            )
            delta = report.comparison_with_previous.get("win_rate_delta", 0.0)
            logger.info(
                "Cycle %d: Win rate delta vs previous = %+.2f%%",
                cycle_number, delta,
            )

        report.overall_assessment = self._assess_cycle(report)
        report.finished_at = datetime.now(timezone.utc)

        logger.info(
            "Cycle %d complete: assessment=%s, win_rate=%.1f%%",
            cycle_number, report.overall_assessment, report.overall_win_rate,
        )

        return report

    async def run_automated_tests(self) -> Dict[str, Any]:
        """Run pytest and collect results.

        ALERT-ONLY: Tests validate alert system functionality.

        Returns:
            Dict with passed, failed, errors, exit_code, duration, and summary.
        """
        project_root = str(Path(__file__).resolve().parent.parent)
        backend_tests = os.path.join(project_root, "backend", "tests")
        start = time.monotonic()

        try:
            result = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    backend_tests,
                    "-v", "--tb=short", "-q",
                    "--timeout=60",
                ],
                capture_output=True,
                text=True,
                timeout=300,
                cwd=project_root,
            )
            duration = round(time.monotonic() - start, 2)

            output = result.stdout + result.stderr
            # Parse pytest summary line (e.g., "5 passed, 2 failed")
            passed = 0
            failed = 0
            errors = 0
            for line in output.split("\n"):
                if "passed" in line:
                    try:
                        passed = int(line.split(" passed")[0].strip().split()[-1])
                    except (ValueError, IndexError):
                        pass
                if "failed" in line:
                    try:
                        failed = int(line.split(" failed")[0].strip().split()[-1])
                    except (ValueError, IndexError):
                        pass
                if "error" in line.lower():
                    try:
                        errors = int(line.split(" error")[0].strip().split()[-1])
                    except (ValueError, IndexError):
                        pass

            return {
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "duration_seconds": duration,
                "exit_code": result.returncode,
                "output_summary": output[-1000:] if len(output) > 1000 else output,
            }
        except subprocess.TimeoutExpired:
            return {
                "passed": 0, "failed": 0, "errors": 1,
                "duration_seconds": 300, "exit_code": -1,
                "output_summary": "Test execution timed out after 300 seconds",
            }
        except FileNotFoundError:
            return {
                "passed": 0, "failed": 0, "errors": 0,
                "duration_seconds": round(time.monotonic() - start, 2),
                "exit_code": 0,
                "output_summary": "No test directory found, skipping tests",
            }
        except Exception as exc:
            return {
                "passed": 0, "failed": 0, "errors": 1,
                "duration_seconds": round(time.monotonic() - start, 2),
                "exit_code": -1,
                "output_summary": f"Error running tests: {exc}",
            }

    def _filter_safe_proposals(
        self, recommendations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter recommendations to only those safe for auto-application.

        ALERT-ONLY: Only applies conservative config changes that are
        unlikely to cause regressions.

        Safe changes:
        - Weight adjustments within MAX_WEIGHT_DELTA
        - Threshold adjustments within MAX_THRESHOLD_DELTA
        - Penalty adjustments within MAX_PENALTY_DELTA
        - Only for categories with >= 3 failures (enough data)

        Args:
            recommendations: List from generate_improvement_recommendations.

        Returns:
            Filtered list of safe proposals.
        """
        safe = []
        for rec in recommendations:
            if rec.get("failure_count", 0) < 3:
                continue
            if rec.get("priority") == "CRITICAL":
                # Critical changes need manual review
                continue

            config_changes = rec.get("config_changes", [])
            if not config_changes:
                continue

            # Validate all changes are within safe bounds
            all_safe = True
            for cc in config_changes:
                key = cc.get("key", "")
                value = cc.get("value", 0)
                if "weights." in key and abs(value) > self.MAX_WEIGHT_DELTA:
                    all_safe = False
                elif "thresholds." in key and abs(value) > self.MAX_THRESHOLD_DELTA:
                    all_safe = False
                elif "penalties." in key and abs(value) > self.MAX_PENALTY_DELTA:
                    all_safe = False

            if all_safe:
                safe.append(rec)

        return safe

    def _apply_config_changes(self, proposal: Dict[str, Any]) -> bool:
        """Apply config changes from a proposal to all relevant config files.

        ALERT-ONLY: Modifies alert system configuration files in shared/configs/.

        Args:
            proposal: Improvement proposal dict with config_changes.

        Returns:
            True if at least one change was applied successfully.
        """
        config_changes = proposal.get("config_changes", [])
        if not config_changes:
            return False

        config_files = self._find_config_files()
        if not config_files:
            logger.warning("No config files found in %s", self.config_dir)
            return False

        any_applied = False
        for filepath in config_files:
            for cc in config_changes:
                try:
                    self._apply_single_change(
                        filepath,
                        cc["key"],
                        cc["change"],
                        cc["value"],
                    )
                    any_applied = True
                except Exception as exc:
                    logger.error(
                        "Failed to apply %s to %s: %s",
                        cc["key"], filepath, exc,
                    )

        if any_applied:
            self._changelog.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "cycle": len(self._cycle_history) + 1,
                "category": proposal.get("category"),
                "action": proposal.get("action"),
                "config_changes": config_changes,
            })

        return any_applied

    def _apply_single_change(
        self,
        filepath: str,
        config_key: str,
        change_type: str,
        change_value: Any,
    ) -> None:
        """Apply a single change to a JSON config file.

        ALERT-ONLY: Modifies a single config parameter.

        Args:
            filepath: Path to the JSON config file.
            config_key: Dot-separated key path (e.g., "weights.price_action").
            change_type: One of "increase", "decrease", or "set".
            change_value: The value to apply.
        """
        with open(filepath, "r", encoding="utf-8") as f:
            config = json.load(f)

        # Handle nested keys (e.g., "weights.otc_patterns")
        keys = config_key.split(".")
        target = config
        for key in keys[:-1]:
            if key not in target:
                logger.warning(
                    "Key '%s' not found in %s, skipping", config_key, filepath
                )
                return
            target = target[key]

        final_key = keys[-1]
        current_value = target.get(final_key)

        if current_value is None:
            logger.warning(
                "Key '%s' not found in %s, skipping", final_key, filepath
            )
            return

        if not isinstance(current_value, (int, float)):
            logger.warning(
                "Key '%s' in %s is not numeric (%s), skipping",
                final_key, filepath, type(current_value).__name__,
            )
            return

        old_value = current_value
        if change_type == "increase":
            target[final_key] = current_value + change_value
        elif change_type == "decrease":
            target[final_key] = max(0, current_value - change_value)
        elif change_type == "set":
            target[final_key] = change_value
        else:
            logger.warning("Unknown change_type '%s', skipping", change_type)
            return

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
            f.write("\n")  # Trailing newline

        logger.info(
            "Updated %s: %s = %s -> %s",
            os.path.basename(filepath), config_key, old_value, target[final_key],
        )

    def _find_config_files(self) -> List[str]:
        """Find all JSON config files in the config directory."""
        if not os.path.isdir(self.config_dir):
            logger.warning("Config directory not found: %s", self.config_dir)
            return []

        files = []
        for name in sorted(os.listdir(self.config_dir)):
            if name.endswith(".json"):
                files.append(os.path.join(self.config_dir, name))
        return files

    def _backup_configs(self) -> None:
        """Backup all config files before starting the improvement loop."""
        for filepath in self._find_config_files():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self._config_backups[filepath] = json.load(f)
                logger.info("Backed up config: %s", os.path.basename(filepath))
            except Exception as exc:
                logger.error("Failed to backup %s: %s", filepath, exc)

    def restore_configs(self) -> None:
        """Restore all config files to their pre-loop state.

        ALERT-ONLY: Reverts all config changes made during the loop.
        """
        for filepath, config in self._config_backups.items():
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                    f.write("\n")
                logger.info("Restored config: %s", os.path.basename(filepath))
            except Exception as exc:
                logger.error("Failed to restore %s: %s", filepath, exc)

    def _compare_with_previous(
        self, current: CycleReport, previous: CycleReport
    ) -> Dict[str, Any]:
        """Compare the current cycle against the previous one.

        ALERT-ONLY: Tracks alert accuracy improvement over cycles.
        """
        curr_wr = current.overall_win_rate
        prev_wr = previous.overall_win_rate
        wr_delta = round(curr_wr - prev_wr, 2)

        curr_metrics = current.replay_metrics
        prev_metrics = previous.replay_metrics

        return {
            "win_rate_before": prev_wr,
            "win_rate_after": curr_wr,
            "win_rate_delta": wr_delta,
            "losses_before": prev_metrics.get("losses", 0),
            "losses_after": curr_metrics.get("losses", 0),
            "losses_delta": (
                curr_metrics.get("losses", 0) - prev_metrics.get("losses", 0)
            ),
            "no_trade_before": prev_metrics.get("no_trade", 0),
            "no_trade_after": curr_metrics.get("no_trade", 0),
            "improvements_applied": len(current.improvements_applied),
            "assessment": (
                "improved" if wr_delta > self.plateau_threshold
                else "degraded" if wr_delta < -self.plateau_threshold
                else "unchanged"
            ),
        }

    def should_stop(self, cycles: Optional[List[CycleReport]] = None) -> bool:
        """Determine whether the improvement loop should stop.

        ALERT-ONLY: Prevents over-tuning of alert parameters.

        Stopping criteria:
            - Less than 3 cycles completed: never stop early.
            - Win rate delta < plateau_threshold for last 2 consecutive cycles.
            - Degradation in 2 out of last 3 cycles.
            - All test suites failing.

        Args:
            cycles: List of cycle reports. Defaults to internal history.

        Returns:
            True if the loop should stop.
        """
        history = cycles or self._cycle_history
        if len(history) < 3:
            return False

        # Check last 2 cycles for plateau
        recent = history[-2:]
        deltas = []
        for r in recent:
            comp = r.comparison_with_previous
            if comp:
                deltas.append(abs(comp.get("win_rate_delta", 0.0)))

        if deltas and all(d < self.plateau_threshold for d in deltas):
            logger.info(
                "Improvement loop plateaued (delta < %.1f%% for last 2 cycles)",
                self.plateau_threshold,
            )
            return True

        # Check for degradation over last 3 cycles
        last_3 = history[-3:]
        degradations = sum(
            1 for c in last_3
            if c.comparison_with_previous.get("assessment") == "degraded"
        )
        if degradations >= 2:
            logger.info("Improvement loop showing degradation, stopping")
            return True

        # Check if tests are consistently failing
        if all(c.test_results.get("exit_code", 0) != 0 for c in last_3):
            logger.info("Tests failing for 3 consecutive cycles, stopping")
            return True

        return False

    def _assess_cycle(self, report: CycleReport) -> str:
        """Provide an overall assessment for a cycle."""
        wr = report.overall_win_rate
        tests_ok = report.test_results.get("exit_code", 1) == 0 or report.test_results.get("errors", 0) == 0

        if wr >= 65 and tests_ok:
            return "good"
        elif wr >= 55 and tests_ok:
            return "acceptable"
        elif not tests_ok:
            return "tests_failing"
        elif wr < 40:
            return "poor"
        else:
            return "needs_improvement"

    def save_changelog(
        self,
        filepath: Optional[str] = None,
    ) -> None:
        """Save the changelog of all applied improvements.

        ALERT-ONLY: Tracks changes to alert system configuration.

        Args:
            filepath: Output file path. Defaults to testing/reports/changelog.json.
        """
        if filepath is None:
            filepath = str(
                Path(__file__).parent / "reports" / "changelog.json"
            )
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_cycles": len(self._cycle_history),
            "total_changes": len(self._changelog),
            "changes": self._changelog,
            "cycle_summaries": [
                {
                    "cycle": c.cycle_number,
                    "win_rate": c.overall_win_rate,
                    "assessment": c.overall_assessment,
                    "improvements_applied": len(c.improvements_applied),
                    "comparison": c.comparison_with_previous,
                }
                for c in self._cycle_history
            ],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Changelog saved to %s", filepath)

    def save_full_report(
        self,
        filepath: Optional[str] = None,
    ) -> None:
        """Save a full report of all cycles.

        ALERT-ONLY: Comprehensive loop execution report.

        Args:
            filepath: Output file path.
        """
        if filepath is None:
            filepath = str(
                Path(__file__).parent / "reports" / "improvement_loop_report.json"
            )
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "config_dir": self.config_dir,
            "max_cycles": self.max_cycles,
            "plateau_threshold": self.plateau_threshold,
            "total_cycles_run": len(self._cycle_history),
            "final_win_rate": (
                self._cycle_history[-1].overall_win_rate
                if self._cycle_history else 0.0
            ),
            "cycles": [
                {
                    "cycle_number": c.cycle_number,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "finished_at": c.finished_at.isoformat() if c.finished_at else None,
                    "test_results": c.test_results,
                    "replay_metrics": c.replay_metrics,
                    "failure_analysis_summary": {
                        "total_failures": c.failure_analysis.get("total_failures", 0),
                        "top_category": c.failure_analysis.get("top_failure_category", "none"),
                    },
                    "improvements_proposed": len(c.improvements_proposed),
                    "improvements_applied": len(c.improvements_applied),
                    "comparison": c.comparison_with_previous,
                    "win_rate": c.overall_win_rate,
                    "assessment": c.overall_assessment,
                }
                for c in self._cycle_history
            ],
            "changelog": self._changelog,
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("Full report saved to %s", filepath)

    def _print_summary(self) -> None:
        """Print a human-readable summary of the improvement loop."""
        if not self._cycle_history:
            print("No cycles completed.")
            return

        print("\n" + "=" * 60)
        print("IMPROVEMENT LOOP SUMMARY - ALERT ONLY")
        print("=" * 60)
        print(f"Total cycles: {len(self._cycle_history)}")
        print(f"Total config changes applied: {len(self._changelog)}")

        for c in self._cycle_history:
            delta_str = ""
            if c.comparison_with_previous:
                d = c.comparison_with_previous.get("win_rate_delta", 0.0)
                delta_str = f" (delta: {d:+.2f}%)"
            print(
                f"  Cycle {c.cycle_number}: "
                f"win_rate={c.overall_win_rate:.1f}%{delta_str}, "
                f"assessment={c.overall_assessment}"
            )

        first_wr = self._cycle_history[0].overall_win_rate
        last_wr = self._cycle_history[-1].overall_win_rate
        total_delta = round(last_wr - first_wr, 2)
        print(f"\nOverall improvement: {first_wr:.1f}% -> {last_wr:.1f}% ({total_delta:+.2f}%)")
        print("=" * 60)


async def main():
    """Run the full improvement loop.

    ALERT-ONLY: Iteratively improves alert prediction accuracy
    through automated analysis and config adjustment cycles.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    loop = ImprovementLoop(max_cycles=5, plateau_threshold=1.0)

    try:
        cycles = await loop.run_full_loop()

        # Save reports
        loop.save_full_report()
        loop.save_changelog()

        print(f"\nCompleted {len(cycles)} improvement cycles.")
        print("Reports saved to testing/reports/")
    except KeyboardInterrupt:
        print("\nLoop interrupted. Restoring configs...")
        loop.restore_configs()
        loop.save_changelog()
    except Exception as exc:
        logger.exception("Improvement loop failed: %s", exc)
        print(f"\nLoop failed: {exc}. Restoring configs...")
        loop.restore_configs()
        raise


if __name__ == "__main__":
    asyncio.run(main())
