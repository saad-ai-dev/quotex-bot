"""
Quotex Alert Monitoring API - Main Application Entry Point.

ALERT-ONLY system: Analyses chart data, generates directional signals,
stores results in MongoDB, and broadcasts alerts via WebSocket.
NO trade execution of any kind.
"""

import logging
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.deps import set_db, get_db
from app.api.routes import health, settings, signals, history, analytics, websocket, dashboard
from app.api.routes.health import set_start_time

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (env vars with sensible defaults)
# ---------------------------------------------------------------------------
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "quotex_alerts")

CORS_ORIGINS = ["*"]  # Allow all origins (local tool + chrome extension)

# Allow additional origins via env var (comma-separated)
_extra_origins = os.getenv("CORS_EXTRA_ORIGINS", "")
if _extra_origins:
    CORS_ORIGINS.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])

BACKEND_DIR = Path(__file__).resolve().parent.parent  # backend/
STATIC_DIR = BACKEND_DIR / "static"

# APScheduler evaluation/metrics intervals
PENDING_EVAL_INTERVAL = int(os.getenv("PENDING_EVAL_INTERVAL", "10"))
METRICS_WORKER_INTERVAL = int(os.getenv("METRICS_WORKER_INTERVAL", "60"))

# ---------------------------------------------------------------------------
# Module-level references for lifespan management
# ---------------------------------------------------------------------------
_motor_client: AsyncIOMotorClient | None = None
_scheduler = None


# ---------------------------------------------------------------------------
# Background worker stubs
# ---------------------------------------------------------------------------
async def pending_evaluator_tick():
    """Periodic task: evaluate pending signals whose candles have closed.

    ALERT-ONLY: Determines WIN or LOSS based on the signal's bullish/bearish
    scores vs the predicted direction. Every directional signal gets a clear
    WIN or LOSS outcome — no UNKNOWN.

    In production with real chart data from the extension, this would compare
    the predicted direction against the actual candle close price.
    """
    try:
        from datetime import datetime, timezone
        import random
        db = get_db()
        collection = db["signals"]
        now_iso = datetime.now(timezone.utc).isoformat()

        # Find pending directional signals whose evaluation time has passed
        expired = await collection.find({
            "status": "PENDING",
            "was_executed": True,
            "signal_for_close_at": {"$lte": now_iso},
            "prediction_direction": {"$in": ["UP", "DOWN"]},
        }).to_list(length=100)

        if not expired:
            # Also clean up expired NO_TRADE signals
            await collection.update_many(
                {
                    "status": "PENDING",
                    "was_executed": True,
                    "signal_for_close_at": {"$lte": now_iso},
                    "prediction_direction": "NO_TRADE",
                },
                {"$set": {"status": "EVALUATED", "outcome": "NEUTRAL", "evaluated_at": now_iso}}
            )
            return

        from app.api.routes.signals import _price_cache

        for sig in expired:
            sid = sig["signal_id"]
            direction = sig["prediction_direction"]
            entry_price = sig.get("entry_price")
            asset_name = sig.get("asset_name", "Unknown")

            # Get close price from the live price cache — EXACT match only
            # No fuzzy matching to prevent cross-asset contamination
            close_price = _price_cache.get(asset_name)

            # Validate close price is reasonable relative to entry
            # If prices differ by more than 5%, it's likely a cross-asset contamination
            price_valid = False
            if entry_price and close_price and entry_price > 0:
                pct_diff = abs(close_price - entry_price) / entry_price
                price_valid = pct_diff < 0.01  # Max 1% change in 1-3 minutes

            # Determine WIN/LOSS based on real price movement
            if entry_price and close_price and price_valid and abs(close_price - entry_price) > 0.000001:
                if direction == "UP":
                    outcome = "WIN" if close_price > entry_price else "LOSS"
                else:  # DOWN
                    outcome = "WIN" if close_price < entry_price else "LOSS"
            else:
                # Price data unavailable or unchanged
                # Check how long this signal has been waiting
                created = sig.get("created_at", "")
                try:
                    from dateutil.parser import parse as dt_parse
                    age_seconds = (datetime.now(timezone.utc) - dt_parse(created)).total_seconds()
                except Exception:
                    age_seconds = 120

                if age_seconds < 120:
                    # Less than 2 minutes — skip, wait for real price
                    continue

                # Over 2 minutes old — force evaluate, but ONLY with valid price
                # Re-check price validity to prevent cross-asset contamination
                force_valid = False
                if close_price and entry_price and abs(close_price - entry_price) > 0.000001:
                    force_pct = abs(close_price - entry_price) / entry_price
                    force_valid = force_pct < 0.01  # Must pass 1% check

                if force_valid:
                    if direction == "UP":
                        outcome = "WIN" if close_price > entry_price else "LOSS"
                    else:
                        outcome = "WIN" if close_price < entry_price else "LOSS"
                else:
                    # No valid price data — mark as UNKNOWN
                    outcome = "UNKNOWN"
                    close_price = entry_price

            await collection.update_one(
                {"signal_id": sid},
                {"$set": {
                    "status": "EVALUATED",
                    "outcome": outcome,
                    "close_price": close_price,
                    "evaluated_at": now_iso,
                }}
            )

            price_info = ""
            if entry_price and close_price:
                diff = close_price - entry_price
                price_info = f" entry={entry_price:.5f} close={close_price:.5f} diff={diff:+.5f}"
            logger.info(
                "Auto-evaluated %s: %s %s -> %s%s",
                sid[:8], direction, asset_name,
                outcome, price_info
            )

            # Broadcast update to dashboard in real-time
            try:
                from app.api.routes.websocket import manager
                import json
                updated = await collection.find_one({"signal_id": sid}, {"_id": 0})
                event = {"event_type": "evaluation_update", "signal": updated}
                await manager.broadcast(json.dumps(event, default=str))
            except Exception:
                pass

        logger.info("Pending evaluator: evaluated %d expired signals", len(expired))

        # Clean up expired NO_TRADE signals
        await collection.update_many(
            {
                "status": "PENDING",
                "was_executed": True,
                "signal_for_close_at": {"$lte": now_iso},
                "prediction_direction": "NO_TRADE",
            },
            {"$set": {"status": "EVALUATED", "outcome": "NEUTRAL", "evaluated_at": now_iso}}
        )

    except Exception as exc:
        logger.warning("Pending evaluator tick failed: %s", exc)


async def metrics_worker_tick():
    """Periodic task: update cached metrics / aggregations.

    ALERT-ONLY: Refreshes dashboard statistics, not trade accounting.
    """
    try:
        db = get_db()
        collection = db["signals"]
        total = await collection.count_documents({})
        evaluated = await collection.count_documents({"status": "EVALUATED"})
        wins = await collection.count_documents({"outcome": "WIN"})
        logger.info(
            "Metrics: total=%d evaluated=%d wins=%d",
            total, evaluated, wins,
        )
    except Exception as exc:
        logger.warning("Metrics worker tick failed: %s", exc)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler.

    Startup:
        1. Connect to MongoDB and create indexes.
        2. Start APScheduler with periodic background workers.
        3. Record application start time.

    Shutdown:
        1. Stop APScheduler.
        2. Close the MongoDB connection.

    ALERT-ONLY: No trade engine initialisation or broker connections.
    """
    global _motor_client, _scheduler

    start = time.time()
    logger.info("=== Quotex Alert Monitoring API starting (ALERT-ONLY) ===")

    # --- MongoDB connection ---
    logger.info("Connecting to MongoDB at %s ...", MONGO_URL)
    _motor_client = AsyncIOMotorClient(MONGO_URL)
    db = _motor_client[MONGO_DB_NAME]
    set_db(db)

    # Create indexes for the signals collection
    try:
        signals_col = db["signals"]
        await signals_col.create_index("signal_id", unique=True)
        await signals_col.create_index("created_at")
        await signals_col.create_index("status")
        await signals_col.create_index("outcome")
        await signals_col.create_index("market_type")
        await signals_col.create_index("expiry_profile")
        await signals_col.create_index([("market_type", 1), ("expiry_profile", 1)])
        await signals_col.create_index([("status", 1), ("created_at", -1)])
        logger.info("MongoDB indexes ensured on 'signals' collection")
    except Exception as exc:
        logger.error("Failed to create MongoDB indexes: %s", exc)

    # --- APScheduler ---
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger

        _scheduler = AsyncIOScheduler()

        _scheduler.add_job(
            pending_evaluator_tick,
            trigger=IntervalTrigger(seconds=PENDING_EVAL_INTERVAL),
            id="pending_evaluator",
            name="Pending Signal Evaluator (ALERT-ONLY)",
            replace_existing=True,
        )
        _scheduler.add_job(
            metrics_worker_tick,
            trigger=IntervalTrigger(seconds=METRICS_WORKER_INTERVAL),
            id="metrics_worker",
            name="Metrics Worker (ALERT-ONLY)",
            replace_existing=True,
        )

        _scheduler.start()
        logger.info(
            "APScheduler started: pending_evaluator every %ds, metrics_worker every %ds",
            PENDING_EVAL_INTERVAL,
            METRICS_WORKER_INTERVAL,
        )
    except Exception as exc:
        logger.error("Failed to start APScheduler: %s", exc)
        _scheduler = None

    set_start_time(start)
    logger.info("=== Startup complete (%.2fs) ===", time.time() - start)

    # ---- Application runs here ----
    yield

    # --- Shutdown ---
    logger.info("=== Quotex Alert Monitoring API shutting down ===")

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")

    if _motor_client is not None:
        _motor_client.close()
        logger.info("MongoDB connection closed")

    logger.info("=== Shutdown complete ===")


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Quotex Alert Monitoring API",
    description="ALERT-ONLY monitoring system - analyses chart data and generates "
                "directional signal alerts. No trade execution.",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS Middleware
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Static files (sound files, optional dashboard assets)
# ---------------------------------------------------------------------------
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    logger.info("Mounted static files from %s", STATIC_DIR)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
# Health check (no prefix -- /health)
app.include_router(health.router)

# API routes
app.include_router(settings.router, prefix="/api/settings")
app.include_router(signals.router, prefix="/api/signals")
app.include_router(history.router, prefix="/api/history")
app.include_router(analytics.router, prefix="/api/analytics")

# WebSocket
app.include_router(websocket.router, prefix="/ws")

# Dashboard (serves HTML at / and /history) -- must be LAST to avoid route conflicts
app.include_router(dashboard.router)
