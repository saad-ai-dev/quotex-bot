"""
Analytics Service - computes and caches aggregated performance metrics.
ALERT-ONLY monitoring dashboard - no trade execution.
"""

from datetime import datetime, timezone
from typing import Any, Dict

from app.core.logging import get_logger
from app.db.repositories import alerts_repo, analytics_repo

logger = get_logger(__name__)

SUMMARY_CACHE_KEY = "global_summary"


class AnalyticsService:
    """Provides aggregated analytics for the monitoring dashboard.

    ALERT-ONLY: All metrics measure prediction accuracy, not trading P&L.
    """

    @staticmethod
    async def get_summary() -> Dict[str, Any]:
        """Return the full analytics summary, using cache when available.

        Returns:
            Summary dict with overall stats and per-market/expiry breakdowns.
        """
        cached = await analytics_repo.get_cached_summary(SUMMARY_CACHE_KEY)
        if cached and "data" in cached:
            return cached["data"]

        # Cache miss - compute fresh
        return await AnalyticsService.compute_and_cache_summary()

    @staticmethod
    async def compute_and_cache_summary() -> Dict[str, Any]:
        """Compute a fresh analytics summary from the database and cache it.

        Returns:
            The computed summary dict.
        """
        logger.info("Computing analytics summary ...")

        total = await alerts_repo.get_alerts_count()
        evaluated = await alerts_repo.get_alerts_count({"status": "evaluated"})
        pending = await alerts_repo.get_alerts_count({"status": "pending"})
        wins = await alerts_repo.get_alerts_count({"outcome": "WIN"})
        losses = await alerts_repo.get_alerts_count({"outcome": "LOSS"})
        neutral = await alerts_repo.get_alerts_count({"outcome": "NEUTRAL"})
        unknown = await alerts_repo.get_alerts_count({"outcome": "UNKNOWN"})

        overall_win_rate = 0.0
        if (wins + losses) > 0:
            overall_win_rate = round((wins / (wins + losses)) * 100, 2)

        # Average confidence across all evaluated signals
        avg_confidence = await AnalyticsService._compute_avg_confidence()

        # Per market/expiry breakdown
        performance = await analytics_repo.get_performance_by_market_and_expiry()

        # Today stats
        today_stats = await alerts_repo.get_today_stats()

        now = datetime.now(timezone.utc)

        summary = {
            "total_signals": total,
            "total_evaluated": evaluated,
            "total_pending": pending,
            "total_wins": wins,
            "total_losses": losses,
            "total_neutral": neutral,
            "total_unknown": unknown,
            "overall_win_rate": overall_win_rate,
            "avg_confidence": avg_confidence,
            "performance_by_market_expiry": performance,
            "today_total": today_stats["total"],
            "today_wins": today_stats["wins"],
            "today_losses": today_stats["losses"],
            "today_win_rate": today_stats["win_rate"],
            "cache_updated_at": now.isoformat(),
        }

        await analytics_repo.update_cached_summary(SUMMARY_CACHE_KEY, summary)
        logger.info("Analytics summary cached (%d total signals)", total)
        return summary

    @staticmethod
    async def _compute_avg_confidence() -> float:
        """Compute average confidence across all evaluated signals via aggregation."""
        from app.db.mongo import get_collection

        col = get_collection("alerts")
        pipeline = [
            {"$match": {"status": "evaluated"}},
            {"$group": {"_id": None, "avg_conf": {"$avg": "$confidence"}}},
        ]
        result = None
        async for doc in col.aggregate(pipeline):
            result = doc
            break

        if result and result.get("avg_conf") is not None:
            return round(result["avg_conf"], 2)
        return 0.0

    @staticmethod
    async def get_performance_breakdown():
        """Return the per-market/expiry performance breakdown.

        Returns:
            List of performance entry dicts.
        """
        return await analytics_repo.get_performance_by_market_and_expiry()
