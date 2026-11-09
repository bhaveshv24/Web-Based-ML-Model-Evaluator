"""NFR-004 availability probe for the defined demonstration/operating window.

NFR-004: "The deployed system shall be available at least 99% of the defined
demonstration/operating window, excluding planned maintenance." SRS method: operational review.

This probe produces the measurement for that review. Run it for the whole agreed window
against the deployed stack. Every sample is kept, so the review can audit the result:

    python scripts/validation/availability_probe.py --duration 2h --interval 15 \
        --out docs/evidence/tsmp-21/nfr004-<date>.json \
        [--maintenance 2026-11-20T10:00:00+00:00/2026-11-20T10:15:00+00:00]

A sample is UP only when the dashboard shell answers 200 and the API answers an anonymous
request with 401 (the API, database and authentication stack are serving), both within
--request-timeout seconds. Samples inside a declared maintenance window are excluded.
Standard library only, so it runs on any OS with Python 3.11.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

TARGET = 0.99
CHECKS = (("/results", 200), ("/api/v1/evaluations", 401))


def parse_duration(text: str) -> float:
    units = {"s": 1, "m": 60, "h": 3600}
    return float(text[:-1]) * units[text[-1]] if text[-1] in units else float(text)


def parse_window(text: str) -> tuple[datetime, datetime]:
    start, end = (datetime.fromisoformat(part) for part in text.split("/"))
    if start.tzinfo is None or end.tzinfo is None or end <= start:
        raise argparse.ArgumentTypeError("use START/END in ISO 8601 with a UTC offset")
    return start, end


def probe(base: str, path: str, timeout: float) -> tuple[int | None, float]:
    started = time.monotonic()
    try:
        with urllib.request.urlopen(base + path, timeout=timeout) as response:  # noqa: S310
            code = response.status
    except urllib.error.HTTPError as error:
        code = error.code
    except (urllib.error.URLError, OSError):
        code = None
    return code, round((time.monotonic() - started) * 1000, 1)


def summarize(samples: list[dict]) -> dict:
    counted = [s for s in samples if not s["maintenance"]]
    up = sum(s["up"] for s in counted)
    availability = up / len(counted) if counted else None
    return {
        "samples_total": len(samples),
        "samples_in_maintenance": len(samples) - len(counted),
        "samples_counted": len(counted),
        "samples_up": up,
        "availability": None if availability is None else round(availability, 5),
        "target": TARGET,
        "meets_target": None if availability is None else availability >= TARGET,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--duration", default="1h", help="e.g. 90m, 2h, 3600 (seconds)")
    parser.add_argument("--interval", type=float, default=15.0, help="seconds between samples")
    parser.add_argument("--request-timeout", type=float, default=5.0)
    parser.add_argument("--maintenance", type=parse_window, action="append", default=[])
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    started_at = datetime.now(UTC)
    deadline = time.monotonic() + parse_duration(args.duration)
    samples: list[dict] = []
    while time.monotonic() < deadline:
        now = datetime.now(UTC)
        results = {path: probe(base, path, args.request_timeout) for path, _ in CHECKS}
        up = all(results[path][0] == expected for path, expected in CHECKS)
        in_maintenance = any(start <= now < end for start, end in args.maintenance)
        samples.append(
            {
                "at": now.isoformat(timespec="seconds"),
                "up": up,
                "maintenance": in_maintenance,
                "checks": {
                    path: {"status": code, "ms": ms} for path, (code, ms) in results.items()
                },
            }
        )
        if not up:
            print(f"{now:%H:%M:%S} DOWN {results}", flush=True)
        time.sleep(max(0.0, args.interval - (datetime.now(UTC) - now).total_seconds()))

    summary = summarize(samples)
    Path(args.out).write_text(
        json.dumps(
            {
                "requirement": "NFR-004",
                "base_url": base,
                "window": {
                    "start": started_at.isoformat(timespec="seconds"),
                    "end": datetime.now(UTC).isoformat(timespec="seconds"),
                    "interval_seconds": args.interval,
                    "maintenance": [[s.isoformat(), e.isoformat()] for s, e in args.maintenance],
                },
                "summary": summary,
                "samples": samples,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary))
    return 0 if summary["meets_target"] else 1


if __name__ == "__main__":
    sys.exit(main())
