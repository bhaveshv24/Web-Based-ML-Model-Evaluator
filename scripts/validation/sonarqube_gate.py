"""Configure an isolated SonarQube project or save its actual quality-gate result.

Use only with a fresh local/CI SonarQube instance. Credentials are written to private
files outside the repository. The gate enforces the STP's zero blocker/critical criterion;
backend line coverage is measured and enforced separately by pytest/coverage.py.
"""

import argparse
import base64
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

PROJECT = "team13-ml-evaluator"


def request(base, path, auth, data=None):
    payload = None if data is None else urllib.parse.urlencode(data).encode()
    headers = {"Authorization": "Basic " + base64.b64encode(":".join(auth).encode()).decode()}
    req = urllib.request.Request(base + path, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        for key, value in (data or {}).items():
            if "password" in key.lower():
                detail = detail.replace(str(value), "[redacted]")
        raise RuntimeError(f"{path}: HTTP {exc.code}: {detail}") from None
    return json.loads(raw) if raw else {}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["setup", "report"])
    parser.add_argument("--url", default="http://localhost:9000")
    parser.add_argument("--scanner-url", default="http://localhost:9000")
    parser.add_argument("--credentials", required=True)
    parser.add_argument("--env-file")
    parser.add_argument("--out")
    args = parser.parse_args()
    credentials = Path(args.credentials)
    if args.mode == "setup":
        if not args.env_file:
            parser.error("setup requires --env-file")
        for attempt in range(90):
            try:
                status = request(args.url, "/api/system/status", ("admin", "admin"))
                if status["status"] == "UP":
                    break
            except (OSError, urllib.error.URLError):
                pass
            if attempt == 89:
                raise RuntimeError("SonarQube did not become ready within three minutes")
            time.sleep(2)
        password = secrets.token_urlsafe(32) + "Aa1!"
        request(args.url, "/api/users/change_password", ("admin", "admin"), {
            "login": "admin", "previousPassword": "admin", "password": password,
        })
        auth = ("admin", password)
        request(args.url, "/api/projects/create", auth, {"project": PROJECT, "name": PROJECT})
        gate = request(args.url, "/api/qualitygates/create", auth, {
            "name": "Team13 Critical Findings",
        })
        for metric in ("blocker_violations", "critical_violations"):
            request(args.url, "/api/qualitygates/create_condition", auth, {
                "gateName": gate["name"], "metric": metric, "op": "GT", "error": "0",
            })
        request(args.url, "/api/qualitygates/select", auth, {
            "gateName": "Team13 Critical Findings", "projectKey": PROJECT,
        })
        token = request(args.url, "/api/user_tokens/generate", auth, {
            "name": "team13-verification",
        })["token"]
        # Create private files before writing credentials, including on shared CI hosts.
        for path, content in (
            (credentials, json.dumps({"password": password})),
            (Path(args.env_file), f"SONAR_TOKEN={token}\nSONAR_HOST_URL={args.scanner_url}\n"),
        ):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, "w") as handle:
                handle.write(content)
        return 0
    if not args.out:
        parser.error("report requires --out")
    auth = ("admin", json.loads(credentials.read_text())["password"])
    report = request(args.url, "/api/qualitygates/project_status?projectKey=" + PROJECT, auth)
    measures = request(args.url, "/api/measures/component?component=" + PROJECT +
                       "&metricKeys=blocker_violations,critical_violations,coverage", auth)
    output = {"gate": report, "measures": measures}
    Path(args.out).write_text(json.dumps(output, indent=2) + "\n")
    print("SonarQube quality gate", report["projectStatus"]["status"])
    return 0 if report["projectStatus"]["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
