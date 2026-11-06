"""PORT-01 (NFR-008) portability check: one command per operating system.

Runs the same checks on Linux, macOS and Windows (standard library only, no shell syntax), and
writes one JSON file with the host description and a PASS/FAIL per check. Use it to produce
PORT-01 evidence on a machine the team has not tested yet, for example Windows with Docker
Desktop.

    python scripts/validation/portability_check.py                 # preflight only, changes nothing
    python scripts/validation/portability_check.py --up --smoke   # start stack, run smoke cases
    python scripts/validation/portability_check.py --fresh --up --smoke   # PORT-01 "fresh install"

--fresh runs `docker compose down -v` first, which DELETES the local database and uploads.
--smoke needs the dev extras (`pip install -e .[dev]`) because it reuses system_tests.py.
Secrets are never printed or written: only whether they are set and not placeholders.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE_CASES = "ST-AUTH-01(API),ST-ING-01(API),ST-EXE-01(API)"
PLACEHOLDER_PREFIX = "replace-with-"
SECRET_KEYS = ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD")
COMPOSE = os.environ.get("COMPOSE", "docker compose").split()


class Report:
    def __init__(self):
        self.results: list[dict] = []

    def record(self, check: str, ok: bool, actual: str, *, required: bool = True) -> bool:
        status = "PASS" if ok else ("FAIL" if required else "WARN")
        self.results.append({"check": check, "status": status, "actual": actual})
        print(f"{status:4} {check}: {actual}", flush=True)
        return ok

    @property
    def passed(self) -> bool:
        return all(r["status"] != "FAIL" for r in self.results)


def run(args: list[str], timeout: int = 900) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def http_status(url: str) -> int | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 (local URL)
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, OSError):
        return None


def env_values(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def host_description() -> dict:
    return {
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "executed_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def preflight(report: Report, base_url: str) -> None:
    docker = shutil.which("docker")
    if not report.record("docker CLI on PATH", docker is not None, docker or "not found"):
        return
    client = run(["docker", "version", "--format", "{{.Client.Version}}"], timeout=60)
    report.record(
        "docker client", client.returncode == 0, client.stdout.strip() or client.stderr.strip()
    )
    server = run(
        ["docker", "version", "--format", "{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}"],
        timeout=60,
    )
    report.record(
        "docker daemon reachable",
        server.returncode == 0,
        server.stdout.strip() or server.stderr.strip()[:200],
    )
    compose = run([*COMPOSE, "version", "--short"], timeout=60)
    report.record(
        "docker compose v2", compose.returncode == 0, compose.stdout.strip() or "not available"
    )

    env_file = ROOT / ".env"
    if report.record(".env present", env_file.exists(), str(env_file.relative_to(ROOT))):
        values = env_values(env_file)
        for key in SECRET_KEYS:
            value = values.get(key, "")
            report.record(
                f"{key} set and not a placeholder",
                bool(value) and not value.startswith(PLACEHOLDER_PREFIX),
                "set"
                if value and not value.startswith(PLACEHOLDER_PREFIX)
                else "missing or still the .env.example placeholder",
            )
        work_dir = values.get("SANDBOX_HOST_WORK_DIR", "")
        exists = bool(work_dir) and Path(work_dir).is_dir()
        report.record(
            "SANDBOX_HOST_WORK_DIR exists on the Docker host",
            exists,
            f"{work_dir or 'unset'} ({'found' if exists else 'not found from this shell'})",
            required=False,
        )
    config = run([*COMPOSE, "config", "--quiet"], timeout=120)
    report.record(
        "compose file valid", config.returncode == 0, config.stderr.strip()[:200] or "valid"
    )

    image = run(
        [
            "docker",
            "image",
            "inspect",
            "--format",
            "{{.Os}}/{{.Architecture}}",
            os.environ.get("SANDBOX_IMAGE", "ml-evaluator-sandbox:1.0"),
        ],
        timeout=60,
    )
    report.record(
        "sandbox image built",
        image.returncode == 0,
        image.stdout.strip() or "not built yet (--up builds it)",
        required=False,
    )

    port = int(base_url.rsplit(":", 1)[-1].split("/")[0]) if base_url.count(":") == 2 else 80
    with socket.socket() as probe:
        in_use = probe.connect_ex(("127.0.0.1", port)) == 0
    ours = in_use and http_status(f"{base_url}/api/v1/evaluations") == 401
    report.record(
        f"port {port} free or served by this API",
        not in_use or ours,
        "free" if not in_use else ("served by this API" if ours else "used by another program"),
    )


def bring_up(report: Report, base_url: str, fresh: bool, timeout: int) -> None:
    if fresh:
        down = run([*COMPOSE, "down", "-v"])
        report.record(
            "docker compose down -v (fresh install)",
            down.returncode == 0,
            down.stderr.strip().splitlines()[-1] if down.stderr.strip() else "done",
        )
    build = run([*COMPOSE, "--profile", "sandbox", "build", "sandbox"], timeout=1800)
    report.record(
        "sandbox image build",
        build.returncode == 0,
        "built" if build.returncode == 0 else build.stderr.strip()[-300:],
    )
    building = time.monotonic()
    up = run([*COMPOSE, "up", "-d", "--build"], timeout=1800)
    if not report.record(
        "docker compose up -d --build",
        up.returncode == 0,
        f"returned after {time.monotonic() - building:.0f} s (includes image builds)"
        if up.returncode == 0
        else up.stderr.strip()[-300:],
    ):
        return
    # Readiness is timed from the moment the containers were started, not from the build.
    started = time.monotonic()
    ready_at = None
    while time.monotonic() - started < timeout:
        if http_status(f"{base_url}/api/v1/evaluations") == 401:
            ready_at = time.monotonic() - started
            break
        time.sleep(2)
    report.record(
        "API reachable (anonymous request answered 401)",
        ready_at is not None,
        f"{ready_at:.0f} s after compose up returned"
        if ready_at is not None
        else f"not within {timeout} s",
    )
    report.record(
        "/results served",
        http_status(f"{base_url}/results") == 200,
        f"HTTP {http_status(f'{base_url}/results')}",
    )


def smoke(report: Report, base_url: str) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "smoke.json"
        proc = run(
            [
                sys.executable,
                str(ROOT / "scripts/validation/system_tests.py"),
                "--base-url",
                base_url,
                "--only",
                SMOKE_CASES,
                "--out",
                str(out),
            ],
            timeout=1800,
        )
        cases = json.loads(out.read_text())["results"] if out.exists() else []
    for case in cases:
        report.record(f"smoke {case['id']}", case["status"] == "PASS", case["actual"][:200])
    if not cases:
        report.record("smoke cases ran", False, (proc.stderr or proc.stdout).strip()[-300:])
    return cases


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--up", action="store_true", help="build and start the Compose stack")
    parser.add_argument(
        "--fresh", action="store_true", help="docker compose down -v first (deletes data)"
    )
    parser.add_argument("--smoke", action="store_true", help="run the PORT-01 smoke cases")
    parser.add_argument("--timeout", type=int, default=180, help="seconds to wait for the API")
    parser.add_argument(
        "--out", help="JSON result file (default: port01-<os>.json in the current directory)"
    )
    args = parser.parse_args()

    report = Report()
    host = host_description()
    print(f"PORT-01 on {host['platform']} ({host['machine']}), Python {host['python']}", flush=True)
    preflight(report, args.base_url)
    if args.up and report.passed:
        bring_up(report, args.base_url, args.fresh, args.timeout)
    smoke_cases = smoke(report, args.base_url) if args.smoke and report.passed else []

    out = Path(args.out or f"port01-{host['os'].lower()}.json")
    out.write_text(
        json.dumps(
            {
                "host": host,
                "mode": {"up": args.up, "fresh": args.fresh, "smoke": args.smoke},
                "status": "PASS" if report.passed else "FAIL",
                "checks": report.results,
                "smoke_results": smoke_cases,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"{'PASS' if report.passed else 'FAIL'}: {out}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
