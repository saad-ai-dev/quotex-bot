"""
Stress testing for the Quotex Alert Intelligence system.
ALERT-ONLY - No trade execution.

Tests system behavior under high load: rapid signal ingestion,
WebSocket connection storms, long-running sessions, and memory
stability monitoring.
"""

import asyncio
import logging
import os
import resource
import statistics
import time
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class StressTest:
    """Stress tests for the alert intelligence backend.

    ALERT-ONLY: All stress tests exercise the alert ingestion,
    querying, and broadcasting pipeline. No trades are placed.
    """

    async def test_rapid_ingestion(
        self,
        backend_url: str = "http://localhost:8000",
        count: int = 100,
    ) -> Dict[str, Any]:
        """Send many signals rapidly and measure throughput.

        ALERT-ONLY: Tests alert ingestion throughput under load.

        Args:
            backend_url: Base URL of the backend API.
            count: Number of signals to send.

        Returns:
            Dict with total_sent, total_success, total_failed,
            duration_seconds, throughput_per_second, and latency metrics.
        """
        url = f"{backend_url.rstrip('/')}/api/signals"
        responses: List[Dict[str, Any]] = []
        latencies: List[float] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            start = time.monotonic()

            tasks = []
            for i in range(count):
                payload = {
                    "asset": f"STRESS_{i}/USD",
                    "market_type": "LIVE" if i % 2 == 0 else "OTC",
                    "expiry_profile": ["1m", "2m", "3m"][i % 3],
                    "direction": "UP" if i % 2 == 0 else "DOWN",
                    "confidence": 50.0 + (i % 50),
                }
                tasks.append(self._send_signal(client, url, payload, latencies))

            results = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.monotonic() - start

        successes = sum(1 for r in results if r is True)
        failures = sum(1 for r in results if r is not True)

        latency_metrics = self.measure_latency(latencies)

        return {
            "test": "rapid_ingestion",
            "total_sent": count,
            "total_success": successes,
            "total_failed": failures,
            "duration_seconds": round(duration, 3),
            "throughput_per_second": round(count / duration, 2) if duration > 0 else 0,
            "latency": latency_metrics,
        }

    async def _send_signal(
        self,
        client: httpx.AsyncClient,
        url: str,
        payload: Dict[str, Any],
        latencies: List[float],
    ) -> bool:
        """Send a single signal and track latency."""
        start = time.monotonic()
        try:
            resp = await client.post(url, json=payload)
            elapsed = (time.monotonic() - start) * 1000  # ms
            latencies.append(elapsed)
            return resp.status_code == 201
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            latencies.append(elapsed)
            logger.error("Signal send failed: %s", exc)
            return False

    async def test_ws_connection_storm(
        self,
        backend_url: str = "http://localhost:8000",
        count: int = 20,
    ) -> Dict[str, Any]:
        """Open many WebSocket connections simultaneously.

        ALERT-ONLY: Tests the alert broadcasting system under connection load.

        Args:
            backend_url: Base URL (will be converted to ws://).
            count: Number of simultaneous WebSocket connections.

        Returns:
            Dict with total_attempted, total_connected, total_failed,
            and duration.
        """
        ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url.rstrip('/')}/ws/alerts"

        connected = 0
        failed = 0
        start = time.monotonic()

        try:
            import websockets
        except ImportError:
            return {
                "test": "ws_connection_storm",
                "error": "websockets library not installed",
                "total_attempted": count,
                "total_connected": 0,
                "total_failed": count,
            }

        connections = []
        for i in range(count):
            try:
                ws = await asyncio.wait_for(
                    websockets.connect(ws_url),
                    timeout=10.0,
                )
                connections.append(ws)
                connected += 1
            except Exception as exc:
                logger.warning("WS connection %d failed: %s", i, exc)
                failed += 1

        duration = time.monotonic() - start

        # Clean up
        for ws in connections:
            try:
                await ws.close()
            except Exception:
                pass

        return {
            "test": "ws_connection_storm",
            "total_attempted": count,
            "total_connected": connected,
            "total_failed": failed,
            "duration_seconds": round(duration, 3),
            "connections_per_second": round(connected / duration, 2) if duration > 0 else 0,
        }

    async def test_long_running_session(
        self,
        backend_url: str = "http://localhost:8000",
        duration_minutes: int = 30,
    ) -> Dict[str, Any]:
        """Run a continuous signal flow for an extended period.

        ALERT-ONLY: Tests system stability during sustained alert generation.

        Args:
            backend_url: Base URL of the backend API.
            duration_minutes: How long to run in minutes.

        Returns:
            Dict with signals_sent, signals_succeeded, errors, duration,
            and throughput statistics.
        """
        url = f"{backend_url.rstrip('/')}/api/signals"
        end_time = time.monotonic() + (duration_minutes * 60)
        signals_sent = 0
        signals_ok = 0
        errors = 0
        latencies: List[float] = []
        interval = 1.0  # 1 signal per second

        async with httpx.AsyncClient(timeout=30.0) as client:
            start = time.monotonic()
            while time.monotonic() < end_time:
                payload = {
                    "asset": f"LONG_{signals_sent}/USD",
                    "market_type": "LIVE",
                    "expiry_profile": "1m",
                    "direction": "UP" if signals_sent % 2 == 0 else "DOWN",
                    "confidence": 60.0 + (signals_sent % 30),
                }

                req_start = time.monotonic()
                try:
                    resp = await client.post(url, json=payload)
                    elapsed = (time.monotonic() - req_start) * 1000
                    latencies.append(elapsed)
                    signals_sent += 1
                    if resp.status_code == 201:
                        signals_ok += 1
                    else:
                        errors += 1
                except Exception as exc:
                    elapsed = (time.monotonic() - req_start) * 1000
                    latencies.append(elapsed)
                    signals_sent += 1
                    errors += 1
                    logger.warning("Long-running signal error: %s", exc)

                await asyncio.sleep(interval)

            total_duration = time.monotonic() - start

        return {
            "test": "long_running_session",
            "duration_minutes": duration_minutes,
            "actual_duration_seconds": round(total_duration, 2),
            "signals_sent": signals_sent,
            "signals_succeeded": signals_ok,
            "errors": errors,
            "error_rate": round((errors / signals_sent) * 100, 2) if signals_sent > 0 else 0,
            "latency": self.measure_latency(latencies),
        }

    async def test_memory_stability(
        self,
        backend_url: str = "http://localhost:8000",
        iterations: int = 1000,
    ) -> Dict[str, Any]:
        """Send many requests and monitor memory usage for leaks.

        ALERT-ONLY: Tests that the alert system does not leak memory.

        Args:
            backend_url: Base URL of the backend API.
            iterations: Number of requests to send.

        Returns:
            Dict with memory snapshots, potential leak detection, and latency.
        """
        url = f"{backend_url.rstrip('/')}/api/signals"
        latencies: List[float] = []
        memory_snapshots: List[Dict[str, Any]] = []

        # Take initial memory snapshot
        memory_snapshots.append(self._get_memory_snapshot(0))

        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(iterations):
                payload = {
                    "asset": f"MEM_{i}/USD",
                    "market_type": "LIVE",
                    "expiry_profile": "1m",
                    "direction": "UP",
                    "confidence": 70.0,
                }

                start = time.monotonic()
                try:
                    await client.post(url, json=payload)
                except Exception:
                    pass
                latencies.append((time.monotonic() - start) * 1000)

                # Snapshot every 100 iterations
                if (i + 1) % 100 == 0:
                    memory_snapshots.append(self._get_memory_snapshot(i + 1))

        # Final snapshot
        memory_snapshots.append(self._get_memory_snapshot(iterations))

        # Analyze memory trend
        initial_rss = memory_snapshots[0]["rss_mb"]
        final_rss = memory_snapshots[-1]["rss_mb"]
        growth_mb = round(final_rss - initial_rss, 2)
        growth_pct = round((growth_mb / initial_rss) * 100, 2) if initial_rss > 0 else 0

        # Flag potential leak if growth > 50% of initial
        potential_leak = growth_pct > 50

        return {
            "test": "memory_stability",
            "iterations": iterations,
            "initial_rss_mb": initial_rss,
            "final_rss_mb": final_rss,
            "growth_mb": growth_mb,
            "growth_pct": growth_pct,
            "potential_leak": potential_leak,
            "memory_snapshots": memory_snapshots,
            "latency": self.measure_latency(latencies),
        }

    def _get_memory_snapshot(self, iteration: int) -> Dict[str, Any]:
        """Take a memory usage snapshot of the current process."""
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            # maxrss is in kilobytes on Linux
            rss_mb = round(usage.ru_maxrss / 1024, 2)
        except Exception:
            rss_mb = 0.0

        return {
            "iteration": iteration,
            "rss_mb": rss_mb,
            "timestamp": time.time(),
        }

    def measure_latency(self, responses: List[float]) -> Dict[str, float]:
        """Compute latency statistics from a list of response times (in ms).

        ALERT-ONLY: Measures alert system response latency.

        Args:
            responses: List of latency values in milliseconds.

        Returns:
            Dict with min, max, avg, p95, p99 latency values.
        """
        if not responses:
            return {
                "min_ms": 0.0,
                "max_ms": 0.0,
                "avg_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "count": 0,
            }

        sorted_resp = sorted(responses)
        n = len(sorted_resp)

        p95_idx = min(int(n * 0.95), n - 1)
        p99_idx = min(int(n * 0.99), n - 1)

        return {
            "min_ms": round(sorted_resp[0], 2),
            "max_ms": round(sorted_resp[-1], 2),
            "avg_ms": round(statistics.mean(sorted_resp), 2),
            "p95_ms": round(sorted_resp[p95_idx], 2),
            "p99_ms": round(sorted_resp[p99_idx], 2),
            "count": n,
        }
