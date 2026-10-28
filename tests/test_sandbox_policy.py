"""MLE-11 / MLE-12: sandbox run policy, timeout, kill and cleanup (IT-EXE-04, IT-EXE-05).

These run without Docker against a simulated daemon (NFR-009). The same behaviour is
exercised against a real daemon in tests/test_sandbox_docker.py (CI job sandbox-tests).
"""

import json
import os
from pathlib import Path

import docker.errors
import pytest
from evaluations.errors import ErrorCode, EvaluationError
from evaluations.sandbox import SandboxCancelled, SandboxPolicy, SandboxRequest, parse_output
from evaluations.sandbox.base import RESULT_MARKER
from evaluations.sandbox.docker_runner import (
    JOB_LABEL,
    DockerSandboxRunner,
    container_config,
    policy_violations,
)
from evaluations.sandbox.workspace import (
    JobWorkspace,
    read_trusted,
    remove_stale_workspaces,
)
from sandbox_doubles import FakeDockerClient

POLICY = SandboxPolicy(
    image="ml-evaluator-sandbox:test",
    user="10001:10001",
    memory_bytes=1024**3,
    nano_cpus=1_000_000_000,
    pids_limit=128,
    tmpfs_bytes=64 * 1024**2,
    max_output_bytes=1024 * 1024,
    poll_interval=0,
)


@pytest.fixture(autouse=True)
def work_dir(settings, tmp_path):
    settings.SANDBOX_WORK_DIR = tmp_path / "jobs"
    settings.SANDBOX_HOST_WORK_DIR = tmp_path / "host-view"
    return tmp_path / "jobs"


def result_line(payload: dict) -> bytes:
    return RESULT_MARKER + json.dumps(payload).encode() + b"\n"


def make_request(workspace, **extra):
    values = {
        "job_id": "job-1",
        "mode": "predict",
        "workspace": workspace,
        "model_filename": "model.pkl",
        "timeout_seconds": 120,
    }
    values.update(extra)
    return SandboxRequest(**values)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += 1.0


def runner_for(client, clock=None):
    clock = clock or Clock()
    return DockerSandboxRunner(client, POLICY, clock=clock, sleep=clock.sleep)


# ------------------------------------------------------------------ IT-EXE-04: run policy
def test_container_config_matches_the_approved_policy():
    workspace = JobWorkspace.create("job-1")
    config = container_config(make_request(workspace), POLICY)
    assert config["network_mode"] == "none" and config["network_disabled"] is True
    assert config["read_only"] is True and config["privileged"] is False
    assert config["user"] == "10001:10001"
    assert config["cap_drop"] == ["ALL"] and "cap_add" not in config
    assert config["security_opt"] == ["no-new-privileges:true"]
    assert config["mem_limit"] == config["memswap_limit"] == 1024**3
    assert config["nano_cpus"] == 1_000_000_000 and config["pids_limit"] == 128
    assert config["tmpfs"] == {"/tmp": f"rw,noexec,nosuid,nodev,size={64 * 1024**2}"}
    assert config["auto_remove"] is False
    # Only the job's own directory is mounted, read-only, at /input.
    assert config["volumes"] == {str(workspace.host_path): {"bind": "/input", "mode": "ro"}}
    # No host environment (secrets, credentials) is passed through.
    assert not {k for k in config["environment"] if "SECRET" in k or "PASSWORD" in k}
    assert "DJANGO_SECRET_KEY" not in config["environment"]
    assert config["labels"][JOB_LABEL] == "job-1"
    ulimits = {u["Name"]: (u["Soft"], u["Hard"]) for u in config["ulimits"]}
    assert ulimits["cpu"] == (125, 125) and ulimits["core"] == (0, 0)
    assert config["command"] == ["predict", "/input/model.pkl", "/input/X.csv"]
    for forbidden in ("privileged", "pid_mode", "devices", "cap_add"):
        assert config.get(forbidden) in (None, False)


def test_inspect_mode_only_passes_the_model():
    workspace = JobWorkspace.create("inspect-1")
    request = make_request(workspace, mode="inspect", model_filename="model.onnx")
    assert container_config(request, POLICY)["command"] == ["inspect", "/input/model.onnx"]


def test_compliant_container_has_no_policy_violations():
    workspace = JobWorkspace.create("job-1")
    request = make_request(workspace)
    attrs = FakeDockerClient().daemon_view(container_config(request, POLICY))
    assert policy_violations(attrs, request, POLICY) == []


@pytest.mark.parametrize(
    ("tamper", "violation"),
    [
        (lambda a: a["HostConfig"].update(NetworkMode="bridge"), "network"),
        (lambda a: a["HostConfig"].update(ReadonlyRootfs=False), "read_only_rootfs"),
        (lambda a: a["HostConfig"].update(Privileged=True), "not_privileged"),
        (lambda a: a["HostConfig"].update(CapAdd=["SYS_ADMIN"]), "caps_dropped"),
        (lambda a: a["HostConfig"].update(SecurityOpt=[]), "no_new_privileges"),
        (lambda a: a["Config"].update(User="0:0"), "non_root_user"),
        (lambda a: a["HostConfig"].update(Memory=0), "memory"),
        (lambda a: a["HostConfig"].update(NanoCpus=0), "cpu"),
        (lambda a: a["HostConfig"].update(PidsLimit=None), "pids"),
        (lambda a: a["HostConfig"].update(PidMode="host"), "no_host_namespaces"),
        (lambda a: a["HostConfig"].update(Devices=[{"PathOnHost": "/dev/kmsg"}]), "no_devices"),
        (lambda a: a["Mounts"][0].update(RW=True), "mounts"),
        (
            lambda a: a["Mounts"].append(
                {"Source": "/var/run/docker.sock", "Destination": "/sock", "RW": False}
            ),
            "mounts",
        ),
    ],
)
def test_policy_mismatch_fails_closed_and_never_starts_the_model(tamper, violation):
    workspace = JobWorkspace.create("job-1")
    request = make_request(workspace)
    client = FakeDockerClient(tamper=tamper, logs=result_line({"predictions": [1]}))
    assert violation in policy_violations(
        client.daemon_view(container_config(request, POLICY)), request, POLICY
    )
    with pytest.raises(EvaluationError) as raised:
        runner_for(client).run(request)
    assert raised.value.code == ErrorCode.SANDBOX_POLICY_VIOLATION
    container = client.created[0]
    assert not container.started
    assert container.removed


# ------------------------------------------------------------- execution and termination
def test_successful_run_returns_payload_and_removes_container():
    workspace = JobWorkspace.create("job-1")
    client = FakeDockerClient(logs=b"model chatter\n" + result_line({"predictions": [1, 0]}))
    payload = runner_for(client).run(make_request(workspace))
    assert payload == {"predictions": [1, 0]}
    assert client.created[0].removed
    assert not client.containers.live


def test_timeout_kills_and_removes_the_container():
    """IT-EXE-05: a never-returning model is killed at the deadline and removed."""
    workspace = JobWorkspace.create("job-1")
    client = FakeDockerClient(reloads_until_exit=None)  # never exits on its own
    clock = Clock()
    with pytest.raises(EvaluationError) as raised:
        runner_for(client, clock).run(make_request(workspace, timeout_seconds=120))
    assert raised.value.code == ErrorCode.TIMEOUT
    assert clock.now >= 120
    container = client.created[0]
    assert container.killed and container.removed
    assert not client.containers.live


def test_cancellation_kills_and_removes_the_container():
    workspace = JobWorkspace.create("job-1")
    client = FakeDockerClient(reloads_until_exit=None)
    calls = iter([False, False, True])
    with pytest.raises(SandboxCancelled):
        runner_for(client).run(make_request(workspace, cancel_check=lambda: next(calls)))
    assert client.created[0].killed and client.created[0].removed


@pytest.mark.parametrize(
    ("exit_code", "oom", "expected"),
    [
        (0, True, ErrorCode.RESOURCE_EXHAUSTED),
        (137, False, ErrorCode.RESOURCE_EXHAUSTED),
        (152, False, ErrorCode.RESOURCE_EXHAUSTED),
        (3, False, ErrorCode.INVALID_INPUT),
        (4, False, ErrorCode.MODEL_LOAD_FAILED),
        (5, False, ErrorCode.MODEL_EXECUTION_FAILED),
        (6, False, ErrorCode.INVALID_PREDICTIONS),
        (1, False, ErrorCode.MODEL_EXECUTION_FAILED),
    ],
)
def test_exit_states_map_to_failure_categories(exit_code, oom, expected):
    workspace = JobWorkspace.create("job-1")
    client = FakeDockerClient(exit_code=exit_code, oom=oom)
    with pytest.raises(EvaluationError) as raised:
        runner_for(client).run(make_request(workspace))
    assert raised.value.code == expected
    assert client.created[0].removed


def test_docker_errors_fail_closed_as_sandbox_unavailable():
    workspace = JobWorkspace.create("job-1")
    client = FakeDockerClient(create_error=docker.errors.ImageNotFound("missing image"))
    with pytest.raises(EvaluationError) as raised:
        runner_for(client).run(make_request(workspace))
    assert raised.value.code == ErrorCode.SANDBOX_UNAVAILABLE


def test_unreachable_docker_daemon_fails_closed(monkeypatch):
    def refuse():
        raise docker.errors.DockerException("connection refused /var/run/docker.sock")

    monkeypatch.setattr("evaluations.sandbox.docker_runner._client_from_settings", refuse)
    workspace = JobWorkspace.create("job-1")
    with pytest.raises(EvaluationError) as raised:
        DockerSandboxRunner(policy=POLICY).run(make_request(workspace))
    assert raised.value.code == ErrorCode.SANDBOX_UNAVAILABLE
    assert "docker.sock" not in raised.value.public_message


def test_failed_removal_is_reported_and_left_for_the_reaper():
    workspace = JobWorkspace.create("job-1")
    client = FakeDockerClient(
        logs=result_line({"predictions": [1]}), remove_error=RuntimeError("busy")
    )
    runner = runner_for(client)
    assert runner.run(make_request(workspace)) == {"predictions": [1]}
    assert runner.destroy(client.created[0], "job-1") is False


def test_remove_orphans_keeps_running_jobs_and_young_containers():
    client = FakeDockerClient()
    runner = runner_for(client)
    for job in ("running-job", "finished-job"):
        client.containers.create(labels={JOB_LABEL: job}, volumes={})
    assert runner.remove_orphans({"running-job"}, min_age_seconds=60) == 1
    assert [c.labels[JOB_LABEL] for c in client.containers.live] == ["running-job"]

    young = FakeDockerClient(created_at="2999-01-01T00:00:00Z")
    young.containers.create(labels={JOB_LABEL: "inspect-x"}, volumes={})
    assert runner_for(young).remove_orphans(set(), min_age_seconds=60) == 0


# ------------------------------------------------------------------------ output parsing
def test_parse_output_uses_only_the_last_framed_line():
    raw = result_line({"predictions": ["forged"]}) + b"noise\n" + result_line({"predictions": [2]})
    assert parse_output(raw, 1024) == {"predictions": [2]}


@pytest.mark.parametrize(
    "raw",
    [
        b"no marker at all",
        RESULT_MARKER + b"{not json",
        RESULT_MARKER + b"[1, 2]",
        RESULT_MARKER + b"[" * 100000,
    ],
)
def test_parse_output_rejects_malformed_results(raw):
    with pytest.raises(EvaluationError) as raised:
        parse_output(raw, 10**7)
    assert raised.value.code == ErrorCode.INVALID_PREDICTIONS


def test_parse_output_rejects_oversized_output():
    with pytest.raises(EvaluationError):
        parse_output(b"x" * 2048, 1024)


# ---------------------------------------------------------------------- job workspaces
def test_each_job_gets_a_distinct_private_workspace(work_dir):
    first, second = JobWorkspace.create("job-1"), JobWorkspace.create("job-1")
    assert first.path != second.path
    assert first.path.parent == second.path.parent == work_dir
    assert oct(first.path.stat().st_mode & 0o777) == oct(0o711)
    assert first.host_path.name == first.path.name


def test_staging_copies_verifies_checksum_and_rejects_unknown_names(tmp_path):
    media = tmp_path / "media" / "models"
    media.mkdir(parents=True)
    source = media / "m.pkl"
    source.write_bytes(b"\x80\x04model")
    import hashlib

    digest = hashlib.sha256(b"\x80\x04model").hexdigest()
    workspace = JobWorkspace.create("job-1")
    staged = workspace.stage_copy(
        source, "model.pkl", allowed_root=media, max_bytes=100, sha256=digest
    )
    assert staged.read_bytes() == b"\x80\x04model"
    assert oct(staged.stat().st_mode & 0o777) == oct(0o644)
    with pytest.raises(ValueError):
        workspace.write_bytes("../escape.csv", b"x")
    with pytest.raises(FileExistsError):  # never overwrites an existing staged file
        workspace.write_bytes("model.pkl", b"x")

    other = JobWorkspace.create("job-2")
    with pytest.raises(EvaluationError, match="INVALID_INPUT"):
        other.stage_copy(source, "model.pkl", allowed_root=media, max_bytes=100, sha256="0" * 64)


def test_staging_rejects_traversal_symlinks_and_oversize(tmp_path):
    media = tmp_path / "media" / "models"
    media.mkdir(parents=True)
    secret = tmp_path / "settings.py"
    secret.write_text("SECRET_KEY = 'x'")
    link = media / "link.pkl"
    link.symlink_to(secret)
    big = media / "big.pkl"
    big.write_bytes(b"x" * 101)
    workspace = JobWorkspace.create("job-1")

    for source in (media / ".." / ".." / "settings.py", link, media / "missing.pkl", big):
        with pytest.raises(EvaluationError) as raised:
            workspace.stage_copy(source, "model.pkl", allowed_root=media, max_bytes=100, sha256="")
        assert raised.value.code == ErrorCode.INVALID_INPUT
        assert str(tmp_path) not in raised.value.public_message
    # A symlink inside the root that points inside the root is still refused (O_NOFOLLOW).
    inner = media / "inner.pkl"
    inner.write_bytes(b"ok")
    (media / "alias.pkl").symlink_to(inner)
    with pytest.raises(EvaluationError):
        read_trusted(media / "alias.pkl", allowed_root=media, max_bytes=10, sha256="")


def test_cleanup_is_idempotent_and_refuses_swapped_symlinks(work_dir, tmp_path):
    workspace = JobWorkspace.create("job-1")
    workspace.write_bytes("X.csv", b"a\n1\n")
    assert workspace.cleanup() is True
    assert not workspace.path.exists()
    assert workspace.cleanup() is True  # second call is a no-op

    victim = tmp_path / "victim"
    victim.mkdir()
    (victim / "keep.txt").write_text("keep")
    swapped = JobWorkspace.create("job-2")
    os.rmdir(swapped.path)
    swapped.path.symlink_to(victim)
    assert swapped.cleanup() is False
    assert (victim / "keep.txt").exists()


def test_stale_workspaces_are_removed_but_active_jobs_are_kept(work_dir):
    active = JobWorkspace.create("active-job")
    stale = JobWorkspace.create("crashed-job")
    removed = remove_stale_workspaces({"active-job"}, older_than_seconds=0, now=10**12)
    assert removed == 1
    assert active.path.exists() and not stale.path.exists()
    assert remove_stale_workspaces(set(), older_than_seconds=10**9, now=0) == 0
    assert Path(work_dir).exists()
