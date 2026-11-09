"""PERF-03 / NFR-011: time validation of an exactly 50 MiB, valid CSV."""

import json
import platform
import sys
import time

from ingestion.validators import DATASET_LIMIT_BYTES, validate_csv_bytes


def main() -> int:
    header = (",".join(f"feature_{i}" for i in range(50)) + ",target\n").encode()
    row = (",".join(["123456789"] * 50) + ",1\n").encode()
    count, padding = divmod(DATASET_LIMIT_BYTES - len(header) - len(row), len(row))
    # Padding lives in a final target cell, so the CSV stays valid and under the field limit.
    final_row = row[:-1] + b" " * padding + b"\n"
    content = header + row * count + final_row
    assert len(content) == DATASET_LIMIT_BYTES

    started = time.perf_counter()
    summary, issues = validate_csv_bytes(content)
    elapsed = time.perf_counter() - started
    result = {
        "case": "PERF-03", "bytes": len(content), "rows": summary.rows if summary else None,
        "seconds": round(elapsed, 3), "limit_seconds": 20,
        "passed": not issues and elapsed <= 20,
        "python": platform.python_version(), "platform": platform.platform(),
        "issues": [issue.code for issue in issues],
    }
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
