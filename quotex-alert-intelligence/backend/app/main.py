from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import APIKeyMiddleware
from app.db import mongo
from app.db.indexes import create_indexes
from app.db.repositories import alerts_repo, analytics_repo

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()


async def evaluate_pending_alerts() -> None:
    """Scheduled job: find pending alerts past their close time and mark them for evaluation."""
    try:
        pending = await alerts_repo.get_pending_alerts()
        if pending:
            logger.info(f"Found {len(pending)} pending alerts ready for evaluation")
        for alert in pending:
            # Placeholder: in production, compare actual price vs predicted direction
            # For now, mark as UNKNOWN so downstream can evaluate
            from app.core.constants import Outcome

            await alerts_repo.update_alert_outcome(
                signal_id=alert["signal_id"],
                outcome=Outcome.UNKNOWN,
            )
    except Exception as e:
        logger.error(f"Error in evaluate_pending_alerts job: {e}")


async def refresh_analytics_cache() -> None:
    """Scheduled job: refresh the cached analytics summary."""
    try:
        from app.core.constants import Status, Outcome

        total = await alerts_repo.get_alerts_count()
        evaluated = await alerts_repo.get_alerts_count({"status": Status.EVALUATED})
        wins = await alerts_repo.get_alerts_count({"outcome": Outcome.WIN})
        losses = await alerts_repo.get_alerts_count({"outcome": Outcome.LOSS})

        win_rate = 0.0
        if (wins + losses) > 0:
            win_rate = round((wins / (wins + losses)) * 100, 2)

        performance = await analytics_repo.get_performance_by_market_and_expiry()

        summary = {
            "total_alerts": total,
            "evaluated_alerts": evaluated,
            "pending_alerts": total - evaluated,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "performance_by_group": performance,
        }
        await analytics_repo.update_cached_summary(summary)
    except Exception as e:
        logger.error(f"Error in refresh_analytics_cache job: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown logic."""
    # Startup
    logger.info("Starting Quotex Alert Intelligence API")
    await mongo.connect()
    await create_indexes()

    # Schedule periodic jobs
    scheduler.add_job(
        evaluate_pending_alerts,
        "interval",
        seconds=settings.EVALUATION_CHECK_INTERVAL_SECONDS,
        id="evaluate_pending",
        replace_existing=True,
    )
    scheduler.add_job(
        refresh_analytics_cache,
        "interval",
        seconds=60,
        id="refresh_analytics",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("APScheduler started with evaluation and analytics jobs")

    yield

    # Shutdown
    logger.info("Shutting down Quotex Alert Intelligence API")
    scheduler.shutdown(wait=False)
    await mongo.close_connection()


app = FastAPI(
    title="Quotex Alert Intelligence API",
    description="ALERT-ONLY system for Quotex chart analysis. No trade execution.",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(APIKeyMiddleware)

# Import and include routers
from app.api.routers import health, settings as settings_router, signals, history, analytics, websocket

app.include_router(health.router, tags=["Health"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])
app.include_router(signals.router, prefix="/api/signals", tags=["Signals"])
app.include_router(history.router, prefix="/api/history", tags=["History"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
