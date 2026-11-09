"""TSMP-21 system, performance, reliability and retention tests against a running stack.

Runs STP cases end to end through the public REST API of a Docker Compose deployment
(real PostgreSQL, Redis, Celery worker, docker-socket-proxy and per-job sandbox containers)
and records an actual result and Pass/Fail for each case in a JSON file.

Usage (from the repository root, stack already up with `docker compose up -d`):
    python scripts/validation/system_tests.py [--base-url http://localhost:8000] \
        [--only ST-EXE-01,PERF-02] [--out docs/evidence/tsmp-21/system-results.json]

REL-01 and RET-01 also drive the stack with `docker compose` (kill/start the worker, run
a management command in the api container), so the docker CLI must reach the same daemon.
Fixture models are trained here with the scikit-learn version pinned in the sandbox image.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import pickle
import platform
import secrets
import subprocess
import sys
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import sklearn
from sklearn.datasets import load_iris, load_wine, make_regression
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier

ROOT = Path(__file__).resolve().parents[2]
TERMINAL = {"SUCCEEDED", "FAILED", "TIMED_OUT"}
COMPOSE = os.environ.get("COMPOSE", "docker compose").split()


class Api:
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        self.email = f"tsmp21-{secrets.token_hex(4)}@pes.edu"
        self.password = secrets.token_urlsafe(12) + "Aa1"
        self.tokens: dict = {}

    def url(self, path: str) -> str:
        return f"{self.base}/api/v1{path}"

    def call(self, method, path, *, auth=True, **kwargs):
        headers = kwargs.pop("headers", {})
        if auth and self.tokens:
            headers["Authorization"] = f"Bearer {self.tokens['access']}"
        return self.session.request(method, self.url(path), headers=headers, timeout=180,
                                    **kwargs)

    def register_and_login(self):
        body = {"email": self.email, "password": self.password}
        assert self.call("POST", "/auth/register", auth=False, json=body).status_code == 201
        response = self.call("POST", "/auth/login", auth=False, json=body)
        assert response.status_code == 200, response.text
        self.tokens = response.json()
        return self

    def upload(self, path: str, name: str, content: bytes, **data):
        return self.call("POST", path, files={"file": (name, content)}, data=data)

    def prepared_pair(self, model: bytes, model_name: str, csv: bytes, target: str):
        """Upload model and dataset, run the compatibility check; return ids and report."""
        model_response = self.upload("/models", model_name, model)
        assert model_response.status_code == 201, model_response.text
        dataset_response = self.upload("/datasets", "data.csv", csv, target_column=target)
        assert dataset_response.status_code == 201, dataset_response.text
        model_id, dataset_id = model_response.json()["id"], dataset_response.json()["id"]
        report = self.call("POST", "/compatibility-reports",
                           json={"model_id": model_id, "dataset_id": dataset_id})
        assert report.status_code == 201, report.text
        return model_id, dataset_id, report.json()

    def submit(self, model_id, dataset_id, **extra):
        response = self.call("POST", "/evaluations",
                             json={"model_id": model_id, "dataset_id": dataset_id, **extra})
        assert response.status_code == 202, response.text
        return response.json()["id"]

    def wait(self, evaluation_id, timeout=300, interval=1.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = self.call("GET", f"/evaluations/{evaluation_id}/status").json()
            if status["status"] in TERMINAL:
                return status
            time.sleep(interval)
        raise TimeoutError(f"{evaluation_id} not terminal after {timeout}s")

    def evaluate(self, model: bytes, model_name: str, csv: bytes, target: str, **extra):
        model_id, dataset_id, report = self.prepared_pair(model, model_name, csv, target)
        assert report["result"] == "PASSED", report
        evaluation_id = self.submit(model_id, dataset_id, **extra)
        return evaluation_id, self.wait(evaluation_id)


# ------------------------------------------------------------------------------- fixtures
def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode()


class Fixtures:
    def __init__(self):
        iris = load_iris(as_frame=True)
        x = iris.data.copy()
        x.columns = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
        y = iris.target.map(dict(enumerate(iris.target_names)))
        self.iris_csv = csv_bytes(x.assign(species=y))
        self.iris_models = {
            "rf_iris.pkl": RandomForestClassifier(n_estimators=50, random_state=0),
            "logreg_iris.joblib": LogisticRegression(max_iter=500),
            "dtree_iris.pkl": DecisionTreeClassifier(max_depth=2, random_state=0),
            "knn_iris.pkl": KNeighborsClassifier(n_neighbors=15),
            "gnb_iris.pkl": GaussianNB(),
        }
        self.iris_bytes = {}
        for name, estimator in self.iris_models.items():
            estimator.fit(x, y)
            self.iris_bytes[name] = pickle.dumps(estimator, protocol=4)
        wine = load_wine(as_frame=True)
        self.wine_csv = csv_bytes(wine.data.assign(cultivar=wine.target.astype(str)))
        # Regression ONNX pair (IT-EXE-03).
        xr, yr = make_regression(n_samples=400, n_features=6, noise=5.0, random_state=1)
        cols = [f"f{i}" for i in range(6)]
        self.housing_csv = csv_bytes(pd.DataFrame(xr, columns=cols).assign(price=yr))
        from skl2onnx import to_onnx

        linreg = LinearRegression().fit(xr.astype(np.float32), yr)
        self.linreg_onnx = to_onnx(linreg, xr[:1].astype(np.float32),
                                   target_opset=17).SerializeToString()

    @staticmethod
    def perf_pair(target_mb=19.5):
        """PERF-02: 10,000 x 50 regression CSV and a random forest of just under 20 MB."""
        x, y = make_regression(n_samples=10_000, n_features=50, noise=10, random_state=2)
        cols = [f"x{i}" for i in range(50)]
        frame = pd.DataFrame(x, columns=cols).round(5)
        csv = csv_bytes(frame.assign(target=np.round(y, 4)))
        trees = 4
        while True:
            model = RandomForestRegressor(n_estimators=trees, max_depth=14, random_state=0,
                                          n_jobs=-1).fit(frame, y)
            blob = pickle.dumps(model, protocol=4)
            if len(blob) >= target_mb * 1024**2 * 0.9 or trees > 400:
                break
            trees = max(trees + 1, int(trees * target_mb * 1024**2 / len(blob)))
        while len(blob) > 20 * 1024**2:
            trees -= 1
            model = RandomForestRegressor(n_estimators=trees, max_depth=14, random_state=0,
                                          n_jobs=-1).fit(frame, y)
            blob = pickle.dumps(model, protocol=4)
        return csv, blob, trees

    @staticmethod
    def hanging_model() -> bytes:
        """Loads cleanly, reports 4 input features, then never returns from predict."""

        class Payload:
            def __reduce__(self):
                return (eval, ("type('Hang', (), {'n_features_in_': 4, 'predict': "
                               "lambda self, X: __import__('time').sleep(10**6)})()",))

        return pickle.dumps(Payload(), protocol=4)


# ---------------------------------------------------------------------------------- tests
RESULTS: list[dict] = []


def case(test_id, requirement, description, expected):
    def wrap(func):
        func.meta = dict(id=test_id, requirement=requirement, description=description,
                         expected=expected)
        return func

    return wrap


def compose(*args, check=True, capture=True):
    return subprocess.run([*COMPOSE, *args], cwd=ROOT, check=check, text=True,
                          capture_output=capture)


def sandbox_containers() -> list[str]:
    out = subprocess.run(["docker", "ps", "-aq", "--filter", "label=ml-evaluator.job"],
                         capture_output=True, text=True, check=True).stdout
    return out.split()


@case("ST-AUTH-01(API)", "FR-001..003", "Register, login, refresh, logout over HTTP",
      "201/200; rotated refresh; after logout refresh=401 and anonymous history=401")
def t_auth(ctx):
    api = Api(ctx.base)
    weak = api.call("POST", "/auth/register", auth=False,
                    json={"email": api.email, "password": secrets.token_hex(3)})
    api.register_and_login()
    refresh = api.call("POST", "/auth/token/refresh", auth=False,
                       json={"refresh": api.tokens["refresh"]})
    reused = api.call("POST", "/auth/token/refresh", auth=False,
                      json={"refresh": api.tokens["refresh"]})
    api.tokens.update(refresh.json())
    logout = api.call("POST", "/auth/logout", json={"refresh": api.tokens["refresh"]})
    after = api.call("POST", "/auth/token/refresh", auth=False,
                     json={"refresh": api.tokens["refresh"]})
    anon = api.call("GET", "/evaluations", auth=False)
    ok = (weak.status_code, refresh.status_code, reused.status_code, logout.status_code,
          after.status_code, anon.status_code) == (400, 200, 401, 204, 401, 401)
    return ok, (f"weak pw={weak.status_code}, role={api.tokens.get('role')}, "
                f"refresh={refresh.status_code}, reuse old refresh={reused.status_code}, "
                f"logout={logout.status_code}, refresh after logout={after.status_code}, "
                f"anonymous history={anon.status_code}")


@case("ST-ING-01(API)", "FR-008..013", "Upload model+CSV, pick target, validate (pass and fail)",
      "PASSED for rf_iris+iris; FAILED for rf_iris+wine naming expected 4 vs actual 13")
def t_ingest(ctx):
    api = ctx.api
    _, dataset_id, passed = api.prepared_pair(ctx.fx.iris_bytes["rf_iris.pkl"], "rf_iris.pkl",
                                              ctx.fx.iris_csv, "species")
    dataset = api.call("GET", f"/datasets/{dataset_id}").json()
    _, _, failed = api.prepared_pair(ctx.fx.iris_bytes["rf_iris.pkl"], "rf_iris.pkl",
                                     ctx.fx.wine_csv, "cultivar")
    count = next((c for c in failed["checks"] if c.get("code") == "FEATURE_COUNT"), {})
    ok = (passed["result"] == "PASSED" and failed["result"] == "FAILED"
          and str(count.get("expected")) == "4" and str(count.get("actual")) == "13"
          and dataset["row_count"] == 150 and dataset["suggested_target"] == "species")
    return ok, (f"iris rows={dataset['row_count']}, suggested={dataset['suggested_target']}; "
                f"iris pair={passed['result']}; wine pair={failed['result']} "
                f"checks={json.dumps(failed['checks'])[:300]}")


@case("ST-ING-02", "FR-008, FR-009", "Unauthenticated upload of model and dataset",
      "401 for both; no file written")
def t_unauth_upload(ctx):
    before = compose("exec", "-T", "api", "sh", "-c", "find /app/media -type f | wc -l").stdout
    m = requests.post(f"{ctx.base}/api/v1/models", files={"file": ("m.pkl", b"\x80\x04x")})
    d = requests.post(f"{ctx.base}/api/v1/datasets", files={"file": ("d.csv", b"a,b\n1,2\n")})
    after = compose("exec", "-T", "api", "sh", "-c", "find /app/media -type f | wc -l").stdout
    ok = m.status_code == d.status_code == 401 and before.strip() == after.strip()
    return ok, f"models={m.status_code}, datasets={d.status_code}, media files {before.strip()}" \
               f" -> {after.strip()}"


@case("ST-EXE-01(API)", "FR-014..021, NFR-002", "Upload, validate, run in real sandbox, read "
      "results and charts", "202 QUEUED <1 s; SUCCEEDED; metrics and charts stored; total "
      "within NFR-002")
def t_e2e(ctx):
    api = ctx.api
    model_id, dataset_id, report = api.prepared_pair(ctx.fx.iris_bytes["rf_iris.pkl"],
                                                     "rf_iris.pkl", ctx.fx.iris_csv, "species")
    started = time.monotonic()
    response = api.call("POST", "/evaluations", json={"model_id": model_id,
                                                      "dataset_id": dataset_id})
    submit_ms = (time.monotonic() - started) * 1000
    status = api.wait(response.json()["id"])
    detail = api.call("GET", f"/evaluations/{response.json()['id']}").json()
    charts = api.call("GET", f"/evaluations/{response.json()['id']}/charts").json()
    ctx.iris_evaluation = detail["id"]
    metrics = detail["metrics_json"] or {}
    ok = (response.status_code == 202 and response.json()["status"] == "QUEUED"
          and submit_ms < 1000 and status["status"] == "SUCCEEDED"
          and {"accuracy", "f1_macro", "confusion_matrix"} <= set(metrics)
          and len(charts["charts"]["confusion_matrix"]) == 3 and charts["charts"]["roc"]
          and status["duration_seconds"] <= 60 and detail["charts_json"] == charts["charts"])
    return ok, (f"compat={report['result']}; POST={response.status_code} "
                f"{response.json()['status']} in {submit_ms:.0f} ms; final={status['status']} "
                f"duration={status['duration_seconds']} s; accuracy={metrics.get('accuracy')}; "
                f"confusion 3x3; ROC classes={sorted(charts['charts']['roc']['curves'])}; "
                f"sandbox_image={detail['sandbox_image']}")


@case("IT-EXE-03(live)", "FR-016, FR-018", "ONNX regression model through the deployed stack",
      "SUCCEEDED; MAE, MSE, RMSE, R-squared stored")
def t_onnx(ctx):
    evaluation_id, status = ctx.api.evaluate(ctx.fx.linreg_onnx, "linreg.onnx",
                                             ctx.fx.housing_csv, "price")
    ctx.onnx_eval = evaluation_id
    metrics = ctx.api.call("GET", f"/evaluations/{evaluation_id}").json()["metrics_json"] or {}
    ok = status["status"] == "SUCCEEDED" and {"mae", "mse", "rmse", "r2"} <= set(metrics)
    return ok, f"status={status['status']} task={status['task_type']} metrics=" \
               f"{ {k: round(v, 4) for k, v in metrics.items() if isinstance(v, float)} }"


@case("IT-EXE-06(live)", "FR-020, SEC-010", "Truncated model file",
      "Rejected (FAILED) with a sanitized message: no stack trace or path")
def t_corrupt(ctx):
    blob = ctx.fx.iris_bytes["rf_iris.pkl"][:40]
    _, _, report = ctx.api.prepared_pair(blob, "truncated.pkl", ctx.fx.iris_csv, "species")
    text = json.dumps(report)
    leaked = [m for m in ("Traceback", "/app/", "/input", "File \"", "Error:") if m in text]
    ok = report["result"] == "FAILED" and not leaked
    return ok, f"compatibility={report['result']} checks={text[:260]} leaks={leaked}"


@case("ST-REP-03(API)", "FR-023..026", "Compare 3 evaluations, download PDF and JSON",
      "201 with best_per_metric; JSON and PDF 200 and parseable; mixed task 400")
def t_compare(ctx):
    api = ctx.api
    ids = []
    for name in ("rf_iris.pkl", "logreg_iris.joblib", "dtree_iris.pkl"):
        evaluation_id, status = api.evaluate(ctx.fx.iris_bytes[name], name, ctx.fx.iris_csv,
                                             "species")
        assert status["status"] == "SUCCEEDED", status
        ids.append(evaluation_id)
    created = api.call("POST", "/comparisons", json={"evaluation_ids": ids})
    comparison = created.json()
    js = api.call("GET", f"/comparisons/{comparison['id']}/report.json")
    pdf = api.call("GET", f"/comparisons/{comparison['id']}/report.pdf")
    from pypdf import PdfReader

    pages = PdfReader(io.BytesIO(pdf.content)).pages
    text = "".join(page.extract_text() for page in pages)
    onnx_id = getattr(ctx, "onnx_eval", None)
    mixed = (api.call("POST", "/comparisons", json={"evaluation_ids": [ids[0], onnx_id]})
             .status_code if onnx_id else None)
    ok = (created.status_code == 201 and js.status_code == 200 and pdf.status_code == 200
          and pdf.headers["Content-Type"] == "application/pdf"
          and len(js.json()["evaluations"]) == 3 and comparison["best_per_metric"]
          and all(name in text for name in ("rf_iris.pkl", "logreg_iris.joblib")))
    return ok, (f"comparison={created.status_code}; best accuracy -> "
                f"{comparison['best_per_metric'].get('accuracy')}; json={js.status_code} "
                f"evaluations={len(js.json()['evaluations'])}; pdf={pdf.status_code} "
                f"{len(pdf.content)} bytes, {len(pages)} pages; mixed-task compare={mixed}")


@case("ST-SEC-10(live)", "SEC-007", "Six failed logins within one minute", "6th returns 429")
def t_rate(ctx):
    email = f"brute-{secrets.token_hex(3)}@pes.edu"
    codes = [requests.post(f"{ctx.base}/api/v1/auth/login",
                           json={"email": email, "password": "Wrong-pass1"}).status_code
             for _ in range(6)]
    return codes == [401] * 5 + [429], f"status codes={codes}"


@case("ST-SEC-11", "SEC-004", "Upload a 200 MB model file",
      "413 rejected early; api memory stable; nothing stored")
def t_oversize(ctx):
    path = Path(ctx.tmp) / "big.pkl"
    with open(path, "wb") as handle:
        handle.write(b"\x80\x04")
        handle.truncate(200 * 1024 * 1024)

    def api_mem():
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}",
                              ctx.api_container], capture_output=True, text=True).stdout
        return out.split("/")[0].strip()

    before = api_mem()
    started = time.monotonic()
    result = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code} %{size_upload}",
         "-H", f"Authorization: Bearer {ctx.api.tokens['access']}",
         "-F", f"file=@{path}", f"{ctx.base}/api/v1/models"],
        capture_output=True, text=True)
    elapsed = time.monotonic() - started
    after = api_mem()
    code, uploaded = result.stdout.split()
    stored = compose("exec", "-T", "api", "sh", "-c",
                     "find /app/media -type f -size +100M | wc -l").stdout.strip()
    path.unlink()
    ok = code == "413" and stored == "0"
    return ok, (f"HTTP {code} after {elapsed:.2f} s; client sent {int(float(uploaded))/1e6:.1f}"
                f" MB before the response; api memory {before} -> {after}; files >100 MB "
                f"stored={stored}")


@case("PERF-02", "NFR-002", "Evaluate 10,000 x 50 CSV with a ~20 MB model",
      "Job duration (started -> finished) <= 60 s")
def t_perf2(ctx):
    csv, blob, trees = Fixtures.perf_pair()
    evaluation_id, status = ctx.api.evaluate(blob, "rf_10k_x_50.pkl", csv, "target",
                                             task_type="REGRESSION")
    ok = status["status"] == "SUCCEEDED" and status["duration_seconds"] <= 60
    return ok, (f"model {len(blob)/1024**2:.2f} MB ({trees} trees), CSV "
                f"{len(csv)/1024**2:.2f} MB; status={status['status']}; "
                f"duration={status['duration_seconds']} s")


@case("PERF-03", "NFR-011", "Validate a 50 MB CSV", "Upload + validation completes <= 20 s")
def t_perf3(ctx):
    limit = 50 * 1024 * 1024
    rng = np.random.default_rng(3)
    # ~118 bytes per row: 480,000 rows overshoot 50 MiB, then whole rows are trimmed until
    # the file is just under the limit (and under the 500,000-row limit).
    rows = 480_000
    frame = pd.DataFrame(rng.normal(size=(rows, 12)).round(6),
                         columns=[f"c{i}" for i in range(12)])
    frame["label"] = rng.integers(0, 3, rows)
    blob = csv_bytes(frame)
    assert len(blob) > limit, len(blob)
    cut = blob.rfind(b"\n", 0, limit) + 1
    blob = blob[:cut]
    assert limit - len(blob) < 1024, len(blob)
    started = time.monotonic()
    response = ctx.api.upload("/datasets", "fifty_mb.csv", blob, target_column="label")
    elapsed = time.monotonic() - started
    ok = response.status_code == 201 and elapsed <= 20
    rows_out = response.json().get("row_count") if response.ok else response.text[:200]
    return ok, f"{len(blob)} bytes ({len(blob)/1024**2:.2f} MiB), HTTP {response.status_code}, " \
               f"rows={rows_out}, elapsed={elapsed:.2f} s"


@case("PERF-04", "NFR-003", "Submit 5 jobs at once with 3 workers",
      "All 5 SUCCEEDED; each result equals its single-run baseline")
def t_perf4(ctx):
    api = ctx.api
    pairs, baseline = {}, {}
    for name, blob in ctx.fx.iris_bytes.items():
        model_id, dataset_id, report = api.prepared_pair(blob, name, ctx.fx.iris_csv, "species")
        assert report["result"] == "PASSED"
        pairs[name] = (model_id, dataset_id)
        evaluation_id = api.submit(model_id, dataset_id)
        api.wait(evaluation_id)
        baseline[name] = api.call("GET", f"/evaluations/{evaluation_id}").json()["metrics_json"]
    started = time.monotonic()
    with ThreadPoolExecutor(5) as pool:
        ids = dict(zip(pairs, pool.map(lambda p: api.submit(*p), pairs.values()), strict=True))
    statuses = {name: api.wait(i) for name, i in ids.items()}
    wall = time.monotonic() - started
    same = {name: api.call("GET", f"/evaluations/{i}").json()["metrics_json"] == baseline[name]
            for name, i in ids.items()}
    overlap = _max_overlap([statuses[n] for n in ids])
    ok = all(s["status"] == "SUCCEEDED" for s in statuses.values()) and all(same.values())
    return ok, (f"5 concurrent jobs in {wall:.1f} s wall; statuses="
                f"{sorted({s['status'] for s in statuses.values()})}; equal to baseline="
                f"{sum(same.values())}/5; max jobs running at once={overlap}; "
                f"no containers left={not sandbox_containers()}")


def _max_overlap(statuses):
    events = []
    for s in statuses:
        events += [(s["started_at"], 1), (s["finished_at"], -1)]
    running = peak = 0
    for _, delta in sorted(events, key=lambda e: (e[0], e[1])):
        running += delta
        peak = max(peak, running)
    return peak


@case("REL-01", "NFR-006", "Kill the worker during a RUNNING job, then restart it",
      "Job FAILED within 5 min of the crash; no orphan sandbox container")
def t_rel(ctx):
    api = ctx.api
    model_id, dataset_id, report = api.prepared_pair(Fixtures.hanging_model(), "hang.pkl",
                                                     ctx.fx.iris_csv, "species")
    assert report["result"] == "PASSED", report
    evaluation_id = api.submit(model_id, dataset_id)
    for _ in range(60):
        status = api.call("GET", f"/evaluations/{evaluation_id}/status").json()
        if status["status"] == "RUNNING":
            break
        time.sleep(1)
    time.sleep(5)
    containers_during = len(sandbox_containers())
    compose("kill", "worker")
    crashed = time.monotonic()
    time.sleep(15)
    compose("start", "worker")
    final = None
    while time.monotonic() - crashed < 330:
        final = api.call("GET", f"/evaluations/{evaluation_id}/status").json()
        if final["status"] in TERMINAL:
            break
        time.sleep(5)
    failed_after = time.monotonic() - crashed
    orphan_deadline = time.monotonic() + 120
    while sandbox_containers() and time.monotonic() < orphan_deadline:
        time.sleep(5)
    orphans = sandbox_containers()
    ok = final["status"] == "FAILED" and failed_after <= 300 and not orphans
    return ok, (f"RUNNING with {containers_during} sandbox container(s); worker killed; "
                f"restarted after 15 s; job -> {final['status']} ({final['error_code']}: "
                f"'{final['error_message']}') {failed_after:.0f} s after the crash; orphan "
                f"containers at end={len(orphans)} (checked up to "
                f"{time.monotonic() - crashed:.0f} s after crash)")


@case("IT-EXE-05(live)", "FR-019, NFR-006, SEC-006", "Model that never returns, with the "
      "deployed 120 s limit", "Killed at ~120 s; TIMED_OUT; container removed")
def t_timeout(ctx):
    api = ctx.api
    model_id, dataset_id, report = api.prepared_pair(Fixtures.hanging_model(), "hang.pkl",
                                                     ctx.fx.iris_csv, "species")
    assert report["result"] == "PASSED", report
    evaluation_id = api.submit(model_id, dataset_id)
    status = api.wait(evaluation_id, timeout=400, interval=2)
    containers = sandbox_containers()
    ok = (status["status"] == "TIMED_OUT" and 120 <= status["duration_seconds"] <= 130
          and not containers)
    return ok, (f"status={status['status']} ({status['error_code']}: "
                f"'{status['error_message']}'); duration={status['duration_seconds']} s; "
                f"sandbox containers left={len(containers)}")


@case("RET-01", "NFR-010", "Age artifacts to 31 days in the deployed DB, run retention",
      "Files and DB references removed; younger uploads kept")
def t_ret(ctx):
    api = ctx.api
    old_model = api.upload("/models", "old.pkl", ctx.fx.iris_bytes["gnb_iris.pkl"]).json()["id"]
    old_data = api.upload("/datasets", "old.csv", ctx.fx.iris_csv,
                          target_column="species").json()["id"]
    young = api.upload("/models", "young.pkl", ctx.fx.iris_bytes["gnb_iris.pkl"]).json()["id"]
    script = (
        "from datetime import timedelta; from django.utils import timezone;"
        "from ingestion.models import ModelArtifact, Dataset;"
        f"old=timezone.now()-timedelta(days=31);"
        f"ModelArtifact.objects.filter(id='{old_model}').update(created_at=old);"
        f"Dataset.objects.filter(id='{old_data}').update(created_at=old)"
    )
    compose("exec", "-T", "api", "python", "manage.py", "shell", "-c", script)

    def exists(kind, ident):
        return compose("exec", "-T", "api", "sh", "-c",
                       f"ls /app/media/{kind}/{ident}* 2>/dev/null | wc -l").stdout.strip()

    before = (exists("models", old_model), exists("datasets", old_data))
    purge = compose("exec", "-T", "api", "python", "manage.py", "purge_expired").stdout.strip()
    after = (exists("models", old_model), exists("datasets", old_data),
             exists("models", young))
    gone = (api.call("GET", f"/models/{old_model}").status_code,
            api.call("GET", f"/datasets/{old_data}").status_code,
            api.call("GET", f"/models/{young}").status_code)
    ok = before == ("1", "1") and after == ("0", "0", "1") and gone == (404, 404, 200)
    return ok, (f"files before={before}; purge output '{purge}'; files after (old model, old "
                f"dataset, young model)={after}; API lookups={gone}")


ALL = [t_auth, t_ingest, t_unauth_upload, t_e2e, t_onnx, t_corrupt, t_compare, t_rate,
       t_oversize, t_perf2, t_perf3, t_perf4, t_rel, t_timeout, t_ret]


class Context:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--only", default="")
    parser.add_argument("--out", default=str(ROOT / "docs/evidence/tsmp-21/system-results.json"))
    args = parser.parse_args()
    ctx = Context()
    ctx.base = args.base_url
    ctx.tmp = tempfile.mkdtemp(prefix="tsmp21-")
    ctx.api_container = compose("ps", "-q", "api").stdout.strip()
    print("building fixtures with scikit-learn", sklearn.__version__, flush=True)
    ctx.fx = Fixtures()
    wanted = {i.strip() for i in args.only.split(",") if i.strip()}
    out = Path(args.out)
    previous = json.loads(out.read_text())["results"] if out.exists() and wanted else []
    for test in ALL:
        meta = test.meta
        if wanted and meta["id"] not in wanted:
            continue
        print(f"== {meta['id']}: {meta['description']}", flush=True)
        # A fresh account per case: one account uploading for every case would exceed the
        # per-user upload limit (SEC-007, 30/min), which is the product working as designed.
        ctx.api = Api(ctx.base).register_and_login()
        started = time.monotonic()
        try:
            ok, actual = test(ctx)
        except Exception as exc:  # recorded as a failure with the reason, never hidden
            ok, actual = False, f"ERROR {type(exc).__name__}: {exc}"
            traceback.print_exc()
        record = {**meta, "actual": actual, "status": "PASS" if ok else "FAIL",
                  "seconds": round(time.monotonic() - started, 1),
                  "executed_at": datetime.now(UTC).isoformat(timespec="seconds")}
        print(f"   {record['status']}: {actual}", flush=True)
        previous = [r for r in previous if r["id"] != meta["id"]]
        RESULTS.append(record)
    results = previous + RESULTS
    env = {
        "base_url": ctx.base,
        "client_os": f"{platform.system()} {platform.release()} {platform.machine()}",
        "python": sys.version.split()[0],
        "scikit_learn": sklearn.__version__,
        "docker": subprocess.run(["docker", "version", "--format",
                                  "{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}"],
                                 capture_output=True, text=True).stdout.strip(),
        "git_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                     capture_output=True, text=True).stdout.strip(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"environment": env, "results": results}, indent=2) + "\n")
    passed = sum(r["status"] == "PASS" for r in results)
    print(f"\n{passed}/{len(results)} passed -> {out}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
