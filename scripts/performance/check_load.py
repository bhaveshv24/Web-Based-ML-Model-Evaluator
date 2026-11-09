"""Fail PERF-01 when measured aggregate latency or error rate misses its target."""

import csv
import json
import sys


def main(path):
    with open(path, newline="") as handle:
        rows = list(csv.DictReader(handle))
    overall = next(row for row in rows if row["Name"] == "Aggregated")
    total = int(overall["Request Count"])
    failed = int(overall["Failure Count"])
    p95_ms = float(overall["95%"])
    passed = total > 0 and failed / total < 0.01 and p95_ms <= 500
    print(json.dumps({
        "case": "PERF-01", "requests": total, "failures": failed,
        "error_rate": round(failed / total, 4) if total else None,
        "p95_ms": p95_ms, "passed": passed,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
