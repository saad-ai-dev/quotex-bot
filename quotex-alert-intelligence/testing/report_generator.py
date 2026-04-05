"""
Report generation for the Quotex Alert Intelligence testing framework.
ALERT-ONLY - No trade execution.

Generates human-readable reports in Markdown and machine-readable
exports in JSON/CSV. Covers test summaries, validation metrics,
failure analysis, improvement plans, and before/after comparisons.
"""

import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates comprehensive reports for the alert testing framework.

    ALERT-ONLY: All reports measure alert prediction accuracy and
    system reliability, not trade profitability.
    """

    def generate_test_summary(self, pytest_results: Dict[str, Any]) -> str:
        """Generate a Markdown summary of pytest results.

        ALERT-ONLY: Summarizes alert system unit/integration test results.

        Args:
            pytest_results: Dict with passed, failed, errors, duration_seconds.

        Returns:
            Markdown-formatted string.
        """
        passed = pytest_results.get("passed", 0)
        failed = pytest_results.get("failed", 0)
        errors = pytest_results.get("errors", 0)
        duration = pytest_results.get("duration_seconds", 0)
        exit_code = pytest_results.get("exit_code", -1)

        total = passed + failed + errors
        pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0
        status = "PASS" if failed == 0 and errors == 0 else "FAIL"

        lines = [
            "# Test Summary Report",
            "",
            f"**Status:** {status}",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Results",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total tests | {total} |",
            f"| Passed | {passed} |",
            f"| Failed | {failed} |",
            f"| Errors | {errors} |",
            f"| Pass rate | {pass_rate}% |",
            f"| Duration | {duration}s |",
            f"| Exit code | {exit_code} |",
            "",
        ]

        if pytest_results.get("output_summary"):
            lines.extend([
                "## Output (last 500 chars)",
                "",
                "```",
                pytest_results["output_summary"],
                "```",
                "",
            ])

        lines.append("*ALERT-ONLY system - No trade execution*")
        return "\n".join(lines)

    def generate_validation_summary(self, batch_metrics: Dict[str, Any]) -> str:
        """Generate a Markdown summary of batch validation metrics.

        ALERT-ONLY: Summarizes alert prediction accuracy.

        Args:
            batch_metrics: Dict from BatchAnalyzer.compute_metrics.

        Returns:
            Markdown-formatted string.
        """
        lines = [
            "# Validation Summary Report",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Overall Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Total signals | {batch_metrics.get('total', 0)} |",
            f"| Wins | {batch_metrics.get('wins', 0)} |",
            f"| Losses | {batch_metrics.get('losses', 0)} |",
            f"| Neutral | {batch_metrics.get('neutral', 0)} |",
            f"| Unknown | {batch_metrics.get('unknown', 0)} |",
            f"| No-trade | {batch_metrics.get('no_trade', 0)} |",
            f"| **Win rate** | **{batch_metrics.get('win_rate', 0)}%** |",
            f"| Precision (UP) | {batch_metrics.get('precision_up', 0)}% |",
            f"| Precision (DOWN) | {batch_metrics.get('precision_down', 0)}% |",
            f"| No-trade rate | {batch_metrics.get('no_trade_rate', 0)}% |",
            f"| Avg confidence | {batch_metrics.get('avg_confidence', 0)} |",
            "",
        ]

        # Confidence calibration
        calibration = batch_metrics.get("confidence_calibration", {})
        if calibration:
            lines.extend([
                "## Confidence Calibration",
                "",
                "| Confidence Bucket | Actual Win Rate |",
                "|-------------------|-----------------|",
            ])
            for bucket, wr in sorted(calibration.items()):
                lines.append(f"| {bucket} | {wr}% |")
            lines.append("")

        lines.append("*ALERT-ONLY system - No trade execution*")
        return "\n".join(lines)

    def generate_failure_analysis(self, failures: Dict[str, Any]) -> str:
        """Generate a Markdown failure analysis report.

        ALERT-ONLY: Analyzes why alerts were incorrect.

        Args:
            failures: Dict from BatchAnalyzer.generate_failure_report.

        Returns:
            Markdown-formatted string.
        """
        lines = [
            "# Failure Analysis Report",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Total failures:** {failures.get('total_failures', 0)}",
            f"**Categories identified:** {failures.get('category_count', 0)}",
            f"**Top failure category:** {failures.get('top_failure_category', 'N/A')}",
            "",
            "## Failure Categories",
            "",
            "| Category | Count | Avg Confidence | Markets | Expiries |",
            "|----------|-------|---------------|---------|----------|",
        ]

        categories = failures.get("categories", {})
        for cat, info in sorted(categories.items(), key=lambda x: -x[1].get("count", 0)):
            lines.append(
                f"| {cat} | {info['count']} | "
                f"{info.get('avg_confidence', 0)} | "
                f"{', '.join(info.get('market_types', []))} | "
                f"{', '.join(info.get('expiry_profiles', []))} |"
            )

        lines.append("")

        # Individual failure details
        details = failures.get("details", [])
        if details:
            lines.extend([
                "## Individual Failures",
                "",
            ])
            for d in details[:20]:  # Limit to 20 for readability
                lines.extend([
                    f"### {d.get('signal_id', 'N/A')}",
                    f"- **Category:** {d.get('category', 'N/A')}",
                    f"- **Direction:** {d.get('direction', 'N/A')}",
                    f"- **Confidence:** {d.get('confidence', 'N/A')}",
                    f"- **Explanation:** {d.get('explanation', 'N/A')}",
                    "",
                ])

        lines.append("*ALERT-ONLY system - No trade execution*")
        return "\n".join(lines)

    def generate_improvement_plan(
        self, recommendations: List[Dict[str, Any]]
    ) -> str:
        """Generate a Markdown improvement plan from recommendations.

        ALERT-ONLY: Plan targets alert accuracy improvements.

        Args:
            recommendations: List from BatchAnalyzer.generate_improvement_recommendations.

        Returns:
            Markdown-formatted string.
        """
        lines = [
            "# Improvement Plan",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Recommendations:** {len(recommendations)}",
            "",
        ]

        # Group by priority
        by_priority = {"CRITICAL": [], "HIGH": [], "MEDIUM": [], "LOW": []}
        for rec in recommendations:
            priority = rec.get("priority", "MEDIUM")
            by_priority.setdefault(priority, []).append(rec)

        for priority in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            items = by_priority.get(priority, [])
            if not items:
                continue

            lines.extend([
                f"## {priority} Priority",
                "",
            ])

            for rec in items:
                lines.extend([
                    f"### {rec.get('action', 'N/A')}",
                    f"- **Category:** {rec.get('category', 'N/A')}",
                    f"- **Failure count:** {rec.get('failure_count', 0)}",
                    f"- **Details:** {rec.get('details', 'N/A')}",
                    f"- **Affected markets:** {', '.join(rec.get('affected_markets', []))}",
                    f"- **Affected expiries:** {', '.join(rec.get('affected_expiries', []))}",
                    f"- **Avg confidence of failures:** {rec.get('avg_confidence', 0)}",
                    "",
                ])

        lines.append("*ALERT-ONLY system - No trade execution*")
        return "\n".join(lines)

    def generate_comparison_report(
        self, before: Dict[str, Any], after: Dict[str, Any]
    ) -> str:
        """Generate a Markdown before/after comparison report.

        ALERT-ONLY: Compares alert accuracy before and after changes.

        Args:
            before: Comparison dict with 'before', 'after', 'delta' per metric.
            after: Same structure (or the overall comparison dict).

        Returns:
            Markdown-formatted string.
        """
        # Handle case where 'before' is the full comparison dict
        if "overall" in before:
            comparison = before
        else:
            comparison = after

        lines = [
            "# Before/After Comparison Report",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            f"**Overall:** {comparison.get('overall', 'N/A')}",
            "",
            "## Metric Comparison",
            "",
            "| Metric | Before | After | Delta | Assessment |",
            "|--------|--------|-------|-------|------------|",
        ]

        for metric, data in comparison.items():
            if metric == "overall" or not isinstance(data, dict):
                continue
            lines.append(
                f"| {metric} | {data.get('before', 'N/A')} | "
                f"{data.get('after', 'N/A')} | "
                f"{data.get('delta', 'N/A')} | "
                f"{data.get('assessment', 'N/A')} |"
            )

        lines.extend(["", "*ALERT-ONLY system - No trade execution*"])
        return "\n".join(lines)

    def export_json(self, data: Any, filepath: str) -> None:
        """Export data to a JSON file.

        ALERT-ONLY: Exports alert analysis data for further processing.

        Args:
            data: Any JSON-serializable data.
            filepath: Output file path.
        """
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info("JSON exported to %s", filepath)

    def export_csv(self, signals: List[Dict[str, Any]], filepath: str) -> None:
        """Export signal data to a CSV file.

        ALERT-ONLY: Exports alert records for spreadsheet analysis.

        Args:
            signals: List of signal dicts.
            filepath: Output file path.
        """
        if not signals:
            logger.warning("No signals to export")
            return

        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

        # Determine columns from first signal, with preferred order
        preferred_order = [
            "signal_id", "market_type", "expiry_profile", "direction",
            "confidence", "outcome", "bullish_score", "bearish_score",
            "parse_mode", "chart_read_confidence", "created_at",
        ]

        all_keys = set()
        for s in signals:
            all_keys.update(s.keys())

        # Order: preferred first, then remaining alphabetically
        columns = [k for k in preferred_order if k in all_keys]
        remaining = sorted(all_keys - set(columns))
        columns.extend(remaining)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            for sig in signals:
                # Flatten nested dicts for CSV
                row = {}
                for key in columns:
                    val = sig.get(key)
                    if isinstance(val, (dict, list)):
                        row[key] = json.dumps(val, default=str)
                    else:
                        row[key] = val
                writer.writerow(row)

        logger.info("CSV exported to %s (%d rows)", filepath, len(signals))

    def generate_full_report(self, all_data: Dict[str, Any]) -> str:
        """Generate a comprehensive full report combining all sections.

        ALERT-ONLY: Complete system validation report.

        Args:
            all_data: Dict with optional keys:
                - test_results: pytest results dict
                - batch_metrics: validation metrics dict
                - failure_report: failure analysis dict
                - recommendations: improvement recommendations list
                - comparison: before/after comparison dict

        Returns:
            Markdown-formatted string combining all sections.
        """
        sections = []

        sections.append("# Quotex Alert Intelligence - Full Validation Report")
        sections.append("")
        sections.append(f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        sections.append("**System type:** ALERT-ONLY (No trade execution)")
        sections.append("")
        sections.append("---")
        sections.append("")

        # Test summary
        if "test_results" in all_data:
            sections.append(self.generate_test_summary(all_data["test_results"]))
            sections.append("")
            sections.append("---")
            sections.append("")

        # Validation summary
        if "batch_metrics" in all_data:
            sections.append(self.generate_validation_summary(all_data["batch_metrics"]))
            sections.append("")
            sections.append("---")
            sections.append("")

        # Failure analysis
        if "failure_report" in all_data:
            sections.append(self.generate_failure_analysis(all_data["failure_report"]))
            sections.append("")
            sections.append("---")
            sections.append("")

        # Improvement plan
        if "recommendations" in all_data:
            sections.append(self.generate_improvement_plan(all_data["recommendations"]))
            sections.append("")
            sections.append("---")
            sections.append("")

        # Comparison report
        if "comparison" in all_data:
            sections.append(
                self.generate_comparison_report(all_data["comparison"], all_data["comparison"])
            )
            sections.append("")

        sections.append("---")
        sections.append("")
        sections.append("*This report was auto-generated by the Quotex Alert Intelligence testing framework.*")
        sections.append("*ALERT-ONLY system - No trade execution.*")

        return "\n".join(sections)
