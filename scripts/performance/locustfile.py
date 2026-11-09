"""PERF-01: 50 users, five minutes, login/history/status through the deployed frontend."""

import itertools
import os
import time

from locust import HttpUser, between, task

account_numbers = itertools.count()


class EvaluatorUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        number = next(account_numbers)
        if number >= 50:
            raise RuntimeError("PERF-01 seeds exactly 50 users")
        self.email = f"perf-{number}@example.test"
        self.password = os.environ["PERF_PASSWORD"]
        self.token = ""
        self.last_login = 0.0
        self.login()
        with self.client.get("/api/v1/evaluations?status=SUCCEEDED", headers=self.headers,
                             name="history", catch_response=True) as response:
            if response.status_code != 200 or not response.json().get("results"):
                response.failure("seeded history missing")
                self.evaluation_id = None
            else:
                self.evaluation_id = response.json()["results"][0]["id"]

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def login(self):
        with self.client.post("/api/v1/auth/login", json={
            "email": self.email, "password": self.password,
        }, name="login", catch_response=True) as response:
            if response.status_code != 200 or "access" not in response.json():
                response.failure(f"login returned {response.status_code}")
            else:
                self.token = response.json()["access"]
                self.last_login = time.monotonic()

    @task(2)
    def history(self):
        self.client.get("/api/v1/evaluations", headers=self.headers, name="history")

    @task(2)
    def status(self):
        if self.evaluation_id:
            self.client.get(f"/api/v1/evaluations/{self.evaluation_id}/status",
                            headers=self.headers, name="status")

    @task(1)
    def charts(self):
        if self.evaluation_id:
            self.client.get(f"/api/v1/evaluations/{self.evaluation_id}/charts",
                            headers=self.headers, name="charts")

    @task(1)
    def refresh_login(self):
        # Keep each IP/email below the API's 5/min login throttle.
        if time.monotonic() - self.last_login >= 16:
            self.login()
        else:
            self.history()
