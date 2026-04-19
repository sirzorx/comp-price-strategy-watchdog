#!/usr/bin/env python3
"""Validate the latest heartbeat artifact inside a GitHub watchdog repo."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate comp-price-strategy heartbeat freshness")
    parser.add_argument("--heartbeat-path", required=True, help="Path to the synced heartbeat JSON file")
    parser.add_argument("--timezone", default="America/Chicago", help="Local timezone to evaluate deadlines in")
    parser.add_argument("--now-local", help="Override current local time for testing")
    return parser.parse_args()


def _result(*, now_local: datetime, ok: bool, message: str, failure_type: str | None = None, **extra: Any) -> dict[str, Any]:
    payload = {
        "ok": ok,
        "checked_at": now_local.isoformat(),
        "failure_type": failure_type,
        "message": message,
    }
    payload.update(extra)
    return payload


def _load_heartbeat(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, f"heartbeat file missing: {path}"
    except json.JSONDecodeError as exc:
        return None, f"heartbeat file is not valid JSON: {exc}"
    except OSError as exc:
        return None, f"heartbeat file could not be read: {exc}"


def evaluate_heartbeat(
    *,
    heartbeat: dict[str, Any],
    now_local: datetime,
    timezone_name: str,
) -> dict[str, Any]:
    timezone = ZoneInfo(timezone_name)
    generated_at_raw = heartbeat.get("generated_at")
    if not generated_at_raw:
        return _result(
            now_local=now_local,
            ok=False,
            failure_type="heartbeat_missing_timestamp",
            message="heartbeat is missing generated_at",
        )

    try:
        generated_at = datetime.fromisoformat(generated_at_raw).astimezone(timezone)
    except ValueError as exc:
        return _result(
            now_local=now_local,
            ok=False,
            failure_type="heartbeat_bad_timestamp",
            message=f"heartbeat generated_at is invalid: {exc}",
        )

    watchdog = heartbeat.get("watchdog") or {}
    max_age_minutes = int(watchdog.get("max_heartbeat_age_minutes", 75))
    age_minutes = round((now_local - generated_at).total_seconds() / 60, 1)
    daily_status = heartbeat.get("daily_status") or {}
    completion_deadline_raw = watchdog.get("daily_completion_deadline_local") or {"hour": 11, "minute": 35}
    deadline = now_local.replace(
        hour=int(completion_deadline_raw.get("hour", 11)),
        minute=int(completion_deadline_raw.get("minute", 35)),
        second=0,
        microsecond=0,
    )

    result = _result(
        now_local=now_local,
        ok=True,
        failure_type=None,
        message="heartbeat is fresh",
        heartbeat_generated_at=generated_at.isoformat(),
        heartbeat_age_minutes=age_minutes,
        max_heartbeat_age_minutes=max_age_minutes,
        collector_state=heartbeat.get("collector_state"),
        daily_run_active=bool(heartbeat.get("daily_run_active")),
        daily_status=daily_status.get("status"),
        daily_status_local_date=daily_status.get("local_date"),
        completion_deadline_local=deadline.isoformat(),
    )

    if age_minutes > max_age_minutes:
        result["ok"] = False
        result["failure_type"] = "heartbeat_stale"
        result["message"] = "heartbeat is stale; laptop or network may be down"
        return result

    if now_local >= deadline:
        if daily_status.get("local_date") != now_local.date().isoformat():
            result["ok"] = False
            result["failure_type"] = "daily_status_missing_for_today"
            result["message"] = "daily scrape status is missing for today"
            return result

        if daily_status.get("status") not in {"success", "review_needed"}:
            result["ok"] = False
            result["failure_type"] = "daily_scrape_incomplete"
            result["message"] = "daily scrape has not reached a terminal acceptable state by the deadline"
            return result

    return result


def main() -> int:
    args = parse_args()
    timezone = ZoneInfo(args.timezone)
    now_local = (
        datetime.fromisoformat(args.now_local).astimezone(timezone)
        if args.now_local
        else datetime.now(timezone)
    ).replace(microsecond=0)

    heartbeat_path = Path(args.heartbeat_path)
    heartbeat, error = _load_heartbeat(heartbeat_path)
    if error:
        result = _result(
            now_local=now_local,
            ok=False,
            failure_type="heartbeat_unreadable",
            message=error,
            heartbeat_path=str(heartbeat_path),
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    result = evaluate_heartbeat(
        heartbeat=heartbeat or {},
        now_local=now_local,
        timezone_name=args.timezone,
    )
    result["heartbeat_path"] = str(heartbeat_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
