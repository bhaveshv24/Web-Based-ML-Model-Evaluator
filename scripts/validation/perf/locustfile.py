"""PERF-01 (NFR-001): 95% of non-evaluation API requests within 500 ms at 50 users.

Mix: login, history, job status and chart data (the NFR-001 list), per seeded account.
    locust -f scripts/validation/perf/locustfile.py --headless -u 50 -r 5 -t 5m \
        --host http://localhost:8000 --csv docs/evidence/tsmp-21/perf01
Needs LOAD_PASSWORD and LOAD_ACCOUNTS (a file of "<email> <evaluation id>" lines written by
seed_load_users.py). Each simulated user owns one account, so the 5/min login throttle
(keyed by IP and email) is never shared between users.
"""
import itertools
import os
import threading

from locust import HttpUser, between, task

PASSWORD = os.environ["LOAD_PASSWORD"]
with open(os.environ["LOAD_ACCOUNTS"]) as handle:
    ACCOUNTS = [line.split() for line in handle if line.strip()]
_next = itertools.count()
_lock = threading.Lock()


class Researcher(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        with _lock:
            self.email, self.evaluation = ACCOUNTS[next(_next) % len(ACCOUNTS)]
        self.login()

    def login(self):
        response = self.client.post("/api/v1/auth/login",
                                    json={"email": self.email, "password": PASSWORD},
                                    name="POST /auth/login")
        if response.ok:
            self.client.headers["Authorization"] = f"Bearer {response.json()['access']}"

    @task(1)
    def relogin(self):
        self.login()

    @task(4)
    def history(self):
        self.client.get("/api/v1/evaluations?status=SUCCEEDED", name="GET /evaluations")

    @task(4)
    def status(self):
        self.client.get(f"/api/v1/evaluations/{self.evaluation}/status",
                        name="GET /evaluations/{id}/status")

    @task(2)
    def charts(self):
        self.client.get(f"/api/v1/evaluations/{self.evaluation}/charts",
                        name="GET /evaluations/{id}/charts")
