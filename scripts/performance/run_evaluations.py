"""PERF-02/04: real 10k x 50, 20 MiB sandbox run and five isolated jobs."""

import io
import json
import os
import sys
import time

import joblib
import numpy as np
import pandas as pd
import requests
from sklearn.dummy import DummyClassifier

BASE = os.environ.get("PERF_BASE_URL", "http://localhost:5173") + "/api/v1"
PASSWORD = os.environ["PERF_PASSWORD"]
SESSION = requests.Session()


def post(path, **kwargs):
    response = SESSION.post(BASE + path, timeout=120, **kwargs)
    response.raise_for_status()
    return response.json()


def wait(job_id):
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        response = SESSION.get(BASE + f"/evaluations/{job_id}/status", timeout=15)
        response.raise_for_status()
        body = response.json()
        if body["status"] in ("SUCCEEDED", "FAILED", "TIMED_OUT"):
            if body["status"] != "SUCCEEDED":
                raise AssertionError(f"{job_id}: {body}")
            detail = SESSION.get(BASE + f"/evaluations/{job_id}", timeout=15)
            detail.raise_for_status()
            return body, detail.json()
        time.sleep(0.25)
    raise TimeoutError(f"job {job_id} did not finish")


def main():
    token = post("/auth/login", json={
        "email": "perf-0@example.test", "password": PASSWORD,
    })["access"]
    SESSION.headers["Authorization"] = f"Bearer {token}"

    columns = [f"feature_{i}" for i in range(50)]
    frame = pd.DataFrame(np.zeros((10_000, 50), dtype=np.float32), columns=columns)
    model = DummyClassifier(strategy="most_frequent").fit(frame.iloc[:3], [0, 0, 1])
    model.padding_ = np.random.default_rng(1).integers(0, 256, 20 * 1024**2, dtype=np.uint8)
    payload = io.BytesIO()
    joblib.dump(model, payload, compress=0)
    model_bytes = payload.getvalue()
    assert 20 * 1024**2 <= len(model_bytes) < 21 * 1024**2
    model_id = post("/models", files={
        "file": ("reference.joblib", model_bytes, "application/octet-stream"),
    })["id"]

    datasets = []
    for index, positive_fraction in enumerate((0.1, 0.3, 0.5, 0.7, 0.9)):
        labels = np.array([1] * int(10_000 * positive_fraction) + [0] *
                          (10_000 - int(10_000 * positive_fraction)))
        csv_bytes = frame.assign(target=labels).to_csv(index=False).encode()
        dataset_id = post("/datasets", files={
            "file": (f"reference-{index}.csv", csv_bytes, "text/csv"),
        })["id"]
        report = post("/compatibility-reports", json={
            "model_id": model_id, "dataset_id": dataset_id,
        })
        assert report["result"] == "PASSED", report
        datasets.append((dataset_id, 1 - positive_fraction))

    baselines = []
    for dataset_id, expected in datasets:
        job = post("/evaluations", json={"model_id": model_id, "dataset_id": dataset_id})
        status, detail = wait(job["id"])
        accuracy = detail["metrics_json"]["accuracy"]
        assert abs(accuracy - expected) < 1e-9
        baselines.append((accuracy, status["duration_seconds"]))

    jobs = [post("/evaluations", json={"model_id": model_id, "dataset_id": dataset_id})
            for dataset_id, _ in datasets]
    concurrent_ids = {job["id"] for job in jobs}
    max_running = 0
    overlap_deadline = time.monotonic() + 30
    while time.monotonic() < overlap_deadline:
        response = SESSION.get(BASE + "/evaluations?status=RUNNING", timeout=15)
        response.raise_for_status()
        running = {row["id"] for row in response.json()["results"]}
        max_running = max(max_running, len(running & concurrent_ids))
        if max_running == 5:
            break
        time.sleep(0.05)
    results = [wait(job["id"]) for job in jobs]
    accuracies = [detail["metrics_json"]["accuracy"] for _, detail in results]
    assert accuracies == [value for value, _ in baselines]
    durations = [status["duration_seconds"] for status, _ in results]
    passed = max([seconds for _, seconds in baselines] + durations) <= 60 and max_running == 5
    print(json.dumps({
        "cases": ["PERF-02", "PERF-04"], "rows": 10000, "features": 50,
        "model_bytes": len(model_bytes), "baseline_durations_seconds": [
            seconds for _, seconds in baselines],
        "concurrent_durations_seconds": durations,
        "max_simultaneously_running": max_running,
        "accuracies": accuracies, "matched_single_run_baselines": True,
        "passed": passed,
    }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
