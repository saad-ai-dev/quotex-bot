"""Analytics service for the Quotex Alert Intelligence system.

ALERT-ONLY system -- analytics track prediction accuracy and signal
distribution. No financial P&L or trade metrics are computed.
"""

from typing import Any, Dict, List

from app.core.constants import Status, Outcome
from app.core.logging import get_logger
from app.db.mongo import get_collection
from app.db.repositories import alerts_repo, analytics_repo

logger = get_logger(__name__)

ALERTS_COLLECTION = "alerts"


class AnalyticsService:
    """Service for computing and retrieving alert analytics.

    ALERT-ONLY: All metrics relate to signal prediction accuracy,
    not trading performance or financial returns.
    """

    @staticmethod
    async def get_summary() -> Dict[str, Any]:
        """Compute an aggregated analytics summary across all alerts.

        Returns an AnalyticsSummary-compatible dict with:
        - Total counts (alerts, wins, losses, neutral, unknown)
        - Overall win rate
        - Per-market stats
        - Per-expiry stats
        - Confidence bucket stats
        - Last 50 alerts

        ALERT-ONLY: Win rate measures prediction accuracy, not profit.
        """
        collection = get_collection(ALERTS_COLLECTION)

        # --- Total counts by outcome ---
        count_pipeline = [
            {"$match": {"status": Status.EVALUATED}},
            {
                "$group": {
                    "_id": "$outcome",
                    "count": {"$sum": 1},
                }
            },
        ]
        outcome_counts: Dict[str, int] = {}
        async for doc in collection.aggregate(count_pipeline):
            outcome_counts[doc["_id"]] = doc["count"]

        total_wins = outcome_counts.get(Outcome.WIN, 0)
        total_losses = outcome_counts.get(Outcome.LOSS, 0)
        total_neutral = outcome_counts.get(Outcome.NEUTRAL, 0)
        total_unknown = outcome_counts.get(Outcome.UNKNOWN, 0)

        total_alerts = await alerts_repo.get_alerts_count()
        denominator = total_wins + total_losses
        win_rate = (total_wins / denominator * 100.0) if denominator > 0 else 0.0

        # --- Per-market stats ---
        market_pipeline = [
            {"$match": {"status": Status.EVALUATED}},
            {
                "$group": {
                    "_id": "$market_type",
                    "total": {"$sum": 1},
                    "wins": {
                        "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.WIN]}, 1, 0]}
                    },
                    "losses": {
                        "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.LOSS]}, 1, 0]}
                    },
                }
            },
        ]
        per_market_stats: Dict[str, Any] = {}
        async for doc in collection.aggregate(market_pipeline):
            market = doc["_id"]
            wins = doc["wins"]
            losses = doc["losses"]
            denom = wins + losses
            per_market_stats[market] = {
                "total": doc["total"],
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / denom * 100.0) if denom > 0 else 0.0, 2),
            }

        # --- Per-expiry stats ---
        expiry_pipeline = [
            {"$match": {"status": Status.EVALUATED}},
            {
                "$group": {
                    "_id": "$expiry_profile",
                    "total": {"$sum": 1},
                    "wins": {
                        "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.WIN]}, 1, 0]}
                    },
                    "losses": {
                        "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.LOSS]}, 1, 0]}
                    },
                }
            },
        ]
        per_expiry_stats: Dict[str, Any] = {}
        async for doc in collection.aggregate(expiry_pipeline):
            expiry = doc["_id"]
            wins = doc["wins"]
            losses = doc["losses"]
            denom = wins + losses
            per_expiry_stats[expiry] = {
                "total": doc["total"],
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / denom * 100.0) if denom > 0 else 0.0, 2),
            }

        # --- Confidence bucket stats (50-60, 60-70, 70-80, 80-90, 90-100) ---
        bucket_pipeline = [
            {"$match": {"status": Status.EVALUATED}},
            {
                "$bucket": {
                    "groupBy": "$confidence",
                    "boundaries": [50, 60, 70, 80, 90, 100.01],
                    "default": "other",
                    "output": {
                        "total": {"$sum": 1},
                        "wins": {
                            "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.WIN]}, 1, 0]}
                        },
                        "losses": {
                            "$sum": {"$cond": [{"$eq": ["$outcome", Outcome.LOSS]}, 1, 0]}
                        },
                    },
                }
            },
        ]
        confidence_bucket_stats: Dict[str, Any] = {}
        bucket_labels = {50: "50-60", 60: "60-70", 70: "70-80", 80: "80-90", 90: "90-100"}
        async for doc in collection.aggregate(bucket_pipeline):
            bucket_key = doc["_id"]
            label = bucket_labels.get(bucket_key, f"{bucket_key}")
            wins = doc["wins"]
            losses = doc["losses"]
            denom = wins + losses
            confidence_bucket_stats[label] = {
                "total": doc["total"],
                "wins": wins,
                "losses": losses,
                "win_rate": round((wins / denom * 100.0) if denom > 0 else 0.0, 2),
            }

        # --- Last 50 alerts ---
        last_50 = await alerts_repo.get_recent_alerts(limit=50)

        summary = {
            "total_alerts": total_alerts,
            "total_wins": total_wins,
            "total_losses": total_losses,
            "total_neutral": total_neutral,
            "total_unknown": total_unknown,
            "win_rate": round(win_rate, 2),
            "per_market_stats": per_market_stats,
            "per_expiry_stats": per_expiry_stats,
            "confidence_bucket_stats": confidence_bucket_stats,
            "last_50_alerts": last_50,
        }

        logger.info(
            f"Analytics summary computed: {total_alerts} total, "
            f"{total_wins}W/{total_losses}L, win_rate={win_rate:.1f}%"
        )
        return summary

    @staticmethod
    async def get_performance() -> List[Dict[str, Any]]:
        """Get performance breakdown aggregated by (market_type, expiry_profile).

        Returns a list of performance entry dicts, each containing:
        market_type, expiry_profile, total, wins, losses, win_rate.

        ALERT-ONLY: Win rate measures prediction accuracy only.
        """
        results = await analytics_repo.get_performance_by_market_and_expiry()
        logger.info(f"Performance data retrieved: {len(results)} groups")
        return results
