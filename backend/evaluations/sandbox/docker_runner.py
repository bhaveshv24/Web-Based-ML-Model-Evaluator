"""One hardened, short-lived Docker container per job (FR-016, SEC-005, SAD 5.1, D-02).

Run policy: no network, read-only root filesystem, non-root user 10001, all capabilities
dropped, no-new-privileges, Docker's default seccomp profile, memory/CPU/PID limits, a
noexec tmpfs for /tmp, CPU-time/file-size ulimits, and a hard wall-clock timeout enforced by
the worker. Only the job's own input directory (model + X, never the labels) is mounted, and
read-only. Predictions leave the container through its bounded stdout log, so no writable
host path is ever mounted.

After ``create`` the container's effective configuration is read back from the daemon and
compared with the policy; any mismatch means the model is not run (fail closed). On success,
failure, timeout or cancellation the container is killed and removed, which also kills every
process the model started (they live in the container's PID namespace).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from ..errors import ErrorCode, EvaluationError
from .base import (
    SANDBOX_INPUT_DIR,
    SandboxCancelled,
    SandboxPolicy,
    SandboxRequest,
    parse_output,
)

logger = logging.getLogger("evaluations.sandbox")

JOB_LABEL = "ml-evaluator.job"
ROLE_LABEL = "ml-evaluator.role"
RUNNER_EXIT_CODES = {
    3: ErrorCode.INVALID_INPUT,
    4: ErrorCode.MODEL_LOAD_FAILED,
    5: ErrorCode.MODEL_EXECUTION_FAILED,
    6: ErrorCode.INVALID_PREDICTIONS,
}
KILLED_BY_LIMIT_EXIT_CODES = {137, 152}  # SIGKILL (memory), SIGXCPU (CPU-time ulimit)
# Path INSIDE the container: its private, size-limited, noexec tmpfs (never the host /tmp).
CONTAINER_TMP = "/tmp"  # nosec B108
SAFE_ENVIRONMENT = {
    "HOME": CONTAINER_TMP,
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONUNBUFFERED": "1",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
}


def container_config(request: SandboxRequest, policy: SandboxPolicy) -> dict:
    """Keyword arguments for ``containers.create``. Pure, so the policy is unit-testable."""
    from docker.types import LogConfig, Ulimit

    cpu_seconds = int(request.timeout_seconds) + 5
    return {
        "image": policy.image,
        "command": request.command(),
        "user": policy.user,
        "network_mode": "none",
        "network_disabled": True,
        "read_only": True,
        "privileged": False,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "mem_limit": policy.memory_bytes,
        "memswap_limit": policy.memory_bytes,  # no swap on top of the memory limit
        "nano_cpus": policy.nano_cpus,
        "pids_limit": policy.pids_limit,
        "ipc_mode": "private",
        "init": True,
        "tmpfs": {CONTAINER_TMP: f"rw,noexec,nosuid,nodev,size={policy.tmpfs_bytes}"},
        "ulimits": [
            Ulimit(name="cpu", soft=cpu_seconds, hard=cpu_seconds),
            Ulimit(name="fsize", soft=policy.tmpfs_bytes, hard=policy.tmpfs_bytes),
            Ulimit(name="nofile", soft=policy.max_open_files, hard=policy.max_open_files),
            Ulimit(name="core", soft=0, hard=0),
        ],
        "volumes": {str(request.workspace.host_path): {"bind": SANDBOX_INPUT_DIR, "mode": "ro"}},
        "environment": dict(SAFE_ENVIRONMENT),
        "working_dir": CONTAINER_TMP,
        "hostname": "sandbox",
        "labels": {ROLE_LABEL: "sandbox", JOB_LABEL: request.job_id},
        "log_config": LogConfig(
            type="json-file",
            config={"max-size": str(policy.max_output_bytes), "max-file": "1"},
        ),
        "stdin_open": False,
        "tty": False,
        "auto_remove": False,  # removed explicitly after the logs are read
    }


def policy_violations(attrs: dict, request: SandboxRequest, policy: SandboxPolicy) -> list[str]:
    """Compare the daemon's view of a created container with the policy (IT-EXE-04)."""
    host = attrs.get("HostConfig") or {}
    config = attrs.get("Config") or {}
    problems = []
    expectations = {
        "network": host.get("NetworkMode") == "none" and config.get("NetworkDisabled") is True,
        "read_only_rootfs": host.get("ReadonlyRootfs") is True,
        "not_privileged": host.get("Privileged") is False,
        "caps_dropped": "ALL" in (host.get("CapDrop") or []) and not host.get("CapAdd"),
        "no_new_privileges": any(
            opt in ("no-new-privileges:true", "no-new-privileges")
            for opt in host.get("SecurityOpt") or []
        ),
        "non_root_user": config.get("User") == policy.user
        and policy.user.split(":")[0] not in ("", "0", "root"),
        "memory": host.get("Memory") == policy.memory_bytes
        and host.get("MemorySwap") == policy.memory_bytes,
        "cpu": host.get("NanoCpus") == policy.nano_cpus,
        "pids": host.get("PidsLimit") == policy.pids_limit,
        "no_host_namespaces": host.get("PidMode", "") in ("", "private")
        and host.get("IpcMode", "") in ("", "private")
        and host.get("UTSMode", "") in ("", "private"),
        "no_devices": not host.get("Devices"),
    }
    problems.extend(name for name, ok in expectations.items() if not ok)

    mounts = attrs.get("Mounts") or []
    input_only = (
        len(mounts) == 1
        and mounts[0].get("Destination") == SANDBOX_INPUT_DIR
        and mounts[0].get("RW") is False
        and str(mounts[0].get("Source", "")).rstrip("/")
        == str(request.workspace.host_path).rstrip("/")
    )
    if not input_only:
        problems.append("mounts")
    return problems


def _parse_created(value: str) -> datetime | None:
    """Docker reports e.g. '2026-10-28T06:55:00.123456789Z'; seconds precision is enough."""
    try:
        return datetime.fromisoformat(value[:19]).replace(tzinfo=UTC)
    except (TypeError, ValueError):
        return None


def _client_from_settings():
    import docker
    from django.conf import settings

    if settings.SANDBOX_DOCKER_URL:
        return docker.DockerClient(base_url=settings.SANDBOX_DOCKER_URL, timeout=30)
    return docker.from_env(timeout=30)


class DockerSandboxRunner:
    def __init__(
        self,
        client=None,
        policy: SandboxPolicy | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self.policy = policy or SandboxPolicy.from_settings()
        self._clock = clock
        self._sleep = sleep

    @staticmethod
    def _docker_errors() -> tuple[type[BaseException], ...]:
        try:
            import docker.errors
            import requests.exceptions
        except ImportError:  # pragma: no cover - the runtime extra is not installed
            return (ImportError,)
        return (docker.errors.DockerException, requests.exceptions.RequestException)

    def _get_client(self):
        if self._client is None:
            try:
                self._client = _client_from_settings()
            except Exception as exc:  # ImportError, DockerException, connection refused
                logger.error("docker client unavailable: %s", type(exc).__name__)
                raise EvaluationError(ErrorCode.SANDBOX_UNAVAILABLE) from exc
        return self._client

    def run(self, request: SandboxRequest) -> dict:
        client = self._get_client()
        container = None
        try:
            container = client.containers.create(**container_config(request, self.policy))
            container.reload()
            problems = policy_violations(container.attrs, request, self.policy)
            if problems:
                logger.error("job=%s sandbox policy mismatch: %s", request.job_id, problems)
                raise EvaluationError(ErrorCode.SANDBOX_POLICY_VIOLATION)
            container.start()
            self._wait(container, request)
            return self._collect(container, request)
        except (EvaluationError, SandboxCancelled):
            raise
        except self._docker_errors() as exc:
            logger.error("job=%s docker error: %s", request.job_id, type(exc).__name__)
            raise EvaluationError(ErrorCode.SANDBOX_UNAVAILABLE) from exc
        finally:
            if container is not None:
                self.destroy(container, request.job_id)

    def _wait(self, container, request: SandboxRequest) -> None:
        deadline = self._clock() + request.timeout_seconds
        while True:
            container.reload()
            if container.status in ("exited", "dead"):
                return
            if self._clock() >= deadline:
                logger.warning(
                    "job=%s exceeded %ss; killing", request.job_id, request.timeout_seconds
                )
                raise EvaluationError(
                    ErrorCode.TIMEOUT, f"Limit: {int(request.timeout_seconds)} seconds."
                )
            if request.cancel_check is not None and request.cancel_check():
                logger.info("job=%s cancelled while running; killing", request.job_id)
                raise SandboxCancelled()
            self._sleep(self.policy.poll_interval)

    def _collect(self, container, request: SandboxRequest) -> dict:
        state = container.attrs.get("State") or {}
        exit_code = state.get("ExitCode")
        if state.get("OOMKilled"):
            raise EvaluationError(ErrorCode.RESOURCE_EXHAUSTED, "Memory limit reached.")
        if exit_code in KILLED_BY_LIMIT_EXIT_CODES:
            raise EvaluationError(ErrorCode.RESOURCE_EXHAUSTED)
        if exit_code != 0:
            code = RUNNER_EXIT_CODES.get(exit_code, ErrorCode.MODEL_EXECUTION_FAILED)
            logger.info("job=%s sandbox exit code %s", request.job_id, exit_code)
            raise EvaluationError(code)
        raw = container.logs(stdout=True, stderr=False)
        return parse_output(raw, self.policy.max_output_bytes)

    def destroy(self, container, job_id: str) -> bool:
        """Kill and remove the container. Idempotent; failures are left for the reaper."""
        try:
            container.reload()
            if container.status not in ("exited", "dead", "created"):
                container.kill()
        except Exception as exc:  # already gone, or exited between reload and kill
            logger.debug("job=%s kill skipped: %s", job_id, type(exc).__name__)
        try:
            container.remove(force=True, v=True)
        except Exception as exc:
            if type(exc).__name__ == "NotFound":
                return True
            logger.error("job=%s container removal failed: %s", job_id, type(exc).__name__)
            return False
        logger.info("job=%s sandbox container removed", job_id)
        return True

    def remove_orphans(self, keep_job_ids: set[str], *, min_age_seconds: float = 0) -> int:
        """Remove sandbox containers whose job is no longer RUNNING (NFR-006).

        Containers younger than min_age_seconds are kept so an in-flight inspection (which
        has no RUNNING job row) is not killed mid-run.
        """
        client = self._get_client()
        now = datetime.now(UTC)
        removed = 0
        for container in client.containers.list(all=True, filters={"label": JOB_LABEL}):
            job_id = (container.labels or {}).get(JOB_LABEL, "")
            if job_id in keep_job_ids:
                continue
            created = _parse_created((container.attrs or {}).get("Created", ""))
            if created is not None and (now - created).total_seconds() < min_age_seconds:
                continue
            if self.destroy(container, job_id):
                removed += 1
        return removed
