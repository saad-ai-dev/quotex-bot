#!/usr/bin/env python3
"""Poll the local backend for executed trades and append new results to a log.

This is a lightweight bridge for overnight observation. It does not make
strategy changes; it records evidence so the next iteration can use real
executed trades rather than alerts.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "runtime" / "executed_trade_monitor_state.json"
LOG_FILE = ROOT / "runtime" / "executed_trade_monitor.log"
BACKEND = "http://127.0.0.1:8000"
POLL_SECONDS = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_json(path: str) -> dict:
    with urlopen(f"{BACKEND}{path}", timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"seen": []}
    return json.loads(STATE_FILE.read_text())


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def append_log(message: str) -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as handle:
        handle.write(message.rstrip() + "\n")


def summarize_signal(signal: dict) -> str:
    features = signal.get("detected_features") or {}
    return (
        f"{signal.get('signal_id')} | {signal.get('asset_name')} | "
        f"{signal.get('prediction_direction')} | conf={signal.get('confidence')} | "
        f"expiry={signal.get('expiry_profile')} | outcome={signal.get('outcome')} | "
        f"executed_price={signal.get('executed_price')} | close={signal.get('close_price')} | "
        f"strategy={features.get('strategy_name')} | regime={features.get('regime')} | "
        f"trend={features.get('trend')} | trend_strength={features.get('trend_strength')} | "
        f"range_pos={features.get('recent_range_position')} | "
        f"consec_up={features.get('consecutive_up')} | consec_down={features.get('consecutive_down')}"
    )


def main() -> int:
    append_log(f"[{utc_now()}] monitor started")
    state = load_state()
    seen = set(state.get("seen", []))

    while True:
        try:
            payload = fetch_json("/api/signals/?limit=20&executed_only=1&directional_only=1")
            for signal in reversed(payload.get("signals", [])):
                signal_id = signal.get("signal_id")
                if not signal_id or signal_id in seen:
                    continue
                seen.add(signal_id)
                append_log(f"[{utc_now()}] executed_trade {summarize_signal(signal)}")

            summary = fetch_json("/api/analytics/summary")
            append_log(
                f"[{utc_now()}] summary total={summary.get('total')} "
                f"wins={summary.get('wins')} losses={summary.get('losses')} "
                f"pending={summary.get('pending')} win_rate={summary.get('win_rate')}"
            )
            save_state({"seen": sorted(seen)})
        except URLError as exc:
            append_log(f"[{utc_now()}] backend_unreachable error={exc}")
        except Exception as exc:  # pragma: no cover
            append_log(f"[{utc_now()}] monitor_error error={exc}")

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        append_log(f"[{utc_now()}] monitor stopped")
        sys.exit(130)
