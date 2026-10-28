"""Test doubles for the sandbox boundary (NFR-009: testable without Docker).

Nothing here is used by production code. TrustedSubprocessRunner runs sandbox/runner.py as
a plain subprocess for end-to-end tests with trusted fixture models only; it is NOT an
isolation boundary.
"""

from __future__ import annotations

import csv
import io
import subprocess
import sys
from pathlib import Path

from evaluations.errors import ErrorCode, EvaluationError
from evaluations.sandbox import parse_output

RUNNER = Path(__file__).resolve().parents[1] / "sandbox" / "runner.py"


def read_features(workspace) -> tuple[list[str], list[list[str]]]:
    rows = list(csv.reader(io.StringIO((workspace.path / "X.csv").read_text())))
    return rows[0], rows[1:]


class FakeRunner:
    """Records each request and returns predictions computed by ``predict(header, rows)``."""

    def __init__(self, predict=None, *, error: Exception | None = None, before=None):
        self.predict = predict
        self.error = error
        self.before = before
        self.requests = []
        self.seen_files: list[list[str]] = []
        self.seen_headers: list[list[str]] = []

    def run(self, request):
        self.requests.append(request)
        self.seen_files.append(sorted(p.name for p in request.workspace.path.iterdir()))
        if self.before is not None:
            self.before(request)
        if self.error is not None:
            raise self.error
        header, rows = read_features(request.workspace)
        self.seen_headers.append(header)
        return self.predict(header, rows)


class TrustedSubprocessRunner:
    """Runs the real in-container runner script as a subprocess (trusted fixtures only)."""

    def run(self, request):
        command = [arg.replace("/input", str(request.workspace.path)) for arg in request.command()]
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(RUNNER), *command],
                capture_output=True,
                timeout=request.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise EvaluationError(ErrorCode.TIMEOUT) from exc
        if completed.returncode != 0:
            raise EvaluationError(ErrorCode.MODEL_EXECUTION_FAILED)
        return parse_output(completed.stdout, 64 * 1024 * 1024)


# ----------------------------------------------------------------------- fake Docker daemon
class NotFound(Exception):
    pass


class FakeContainer:
    def __init__(self, client, kwargs):
        self.client = client
        self.kwargs = kwargs
        self.id = f"c{len(client.created)}"
        self.labels = kwargs.get("labels", {})
        self.status = "created"
        self.killed = False
        self.removed = False
        self.started = False
        self.reloads_until_exit = client.reloads_until_exit
        self.attrs = client.daemon_view(kwargs)
        self.attrs["Created"] = client.created_at
        self.attrs["State"] = {"ExitCode": 0, "OOMKilled": False}

    def reload(self):
        if self.removed:
            raise NotFound("gone")
        if self.status == "running":
            if self.reloads_until_exit is not None:
                self.reloads_until_exit -= 1
                if self.reloads_until_exit <= 0:
                    self.status = "exited"
                    self.attrs["State"] = {
                        "ExitCode": self.client.exit_code,
                        "OOMKilled": self.client.oom,
                    }

    def start(self):
        self.started = True
        self.status = "running"

    def kill(self):
        if self.status != "running":
            raise RuntimeError("409 not running")
        self.killed = True
        self.status = "exited"

    def remove(self, force=False, v=False):
        if self.client.remove_error is not None:
            raise self.client.remove_error
        self.removed = True
        self.client.containers.live.discard(self)

    def logs(self, stdout=True, stderr=False):
        return self.client.logs


class FakeContainers:
    def __init__(self, client):
        self.client = client
        self.live: set[FakeContainer] = set()

    def create(self, **kwargs):
        if self.client.create_error is not None:
            raise self.client.create_error
        container = FakeContainer(self.client, kwargs)
        self.client.created.append(container)
        self.live.add(container)
        return container

    def list(self, all=False, filters=None):
        return list(self.live)


class FakeDockerClient:
    """Simulates the daemon closely enough to test policy, timeout and cleanup logic."""

    def __init__(
        self,
        *,
        logs: bytes = b"",
        exit_code: int = 0,
        oom: bool = False,
        reloads_until_exit: int | None = 1,
        tamper=None,
        create_error: Exception | None = None,
        remove_error: Exception | None = None,
        created_at: str = "2020-01-01T00:00:00.000000000Z",
    ):
        self.logs = logs
        self.exit_code = exit_code
        self.oom = oom
        self.reloads_until_exit = reloads_until_exit
        self.tamper = tamper
        self.create_error = create_error
        self.remove_error = remove_error
        self.created_at = created_at
        self.created: list[FakeContainer] = []
        self.containers = FakeContainers(self)

    def daemon_view(self, kwargs) -> dict:
        """What `docker inspect` would report for these create() arguments."""
        mounts = [
            {"Source": source, "Destination": spec["bind"], "RW": spec["mode"] != "ro"}
            for source, spec in kwargs.get("volumes", {}).items()
        ]
        attrs = {
            "Config": {
                "User": kwargs.get("user", ""),
                "NetworkDisabled": kwargs.get("network_disabled", False),
            },
            "HostConfig": {
                "NetworkMode": kwargs.get("network_mode", "default"),
                "ReadonlyRootfs": kwargs.get("read_only", False),
                "Privileged": kwargs.get("privileged", False),
                "CapDrop": kwargs.get("cap_drop"),
                "CapAdd": kwargs.get("cap_add"),
                "SecurityOpt": kwargs.get("security_opt"),
                "Memory": kwargs.get("mem_limit", 0),
                "MemorySwap": kwargs.get("memswap_limit", 0),
                "NanoCpus": kwargs.get("nano_cpus", 0),
                "PidsLimit": kwargs.get("pids_limit"),
                "PidMode": kwargs.get("pid_mode", ""),
                "IpcMode": kwargs.get("ipc_mode", "private"),
                "UTSMode": "",
                "Devices": kwargs.get("devices"),
            },
            "Mounts": mounts,
        }
        if self.tamper is not None:
            self.tamper(attrs)
        return attrs
