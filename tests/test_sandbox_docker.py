"""Real-container containment suite (IT-EXE-02, IT-EXE-04, IT-EXE-05, ST-EXE-02, ST-SEC-07/08).

Hostile-model fixtures run inside the real sandbox image through DockerSandboxRunner.
Requires a Docker daemon and the image (docker build -t ml-evaluator-sandbox:1.0 sandbox/).
Skipped when unavailable, except in CI where REQUIRE_DOCKER_TESTS=1 turns that into a
failure so the suite can never silently stop running.
"""

import json
import os
import pickle
import subprocess
import tempfile
import time
from pathlib import Path

import pytest
from evaluations.errors import ErrorCode, EvaluationError
from evaluations.sandbox import SandboxPolicy, SandboxRequest
from evaluations.sandbox.docker_runner import (
    JOB_LABEL,
    DockerSandboxRunner,
    container_config,
    policy_violations,
)
from evaluations.sandbox.workspace import JobWorkspace

pytestmark = pytest.mark.docker
REQUIRED = os.environ.get("REQUIRE_DOCKER_TESTS") == "1"


def require(module: str):
    """importorskip, except that CI (REQUIRE_DOCKER_TESTS=1) must never skip this suite."""
    if REQUIRED:
        return __import__(module, fromlist=["_"])
    return pytest.importorskip(module)


docker = require("docker")

IMAGE = os.environ.get("SANDBOX_IMAGE", "ml-evaluator-sandbox:1.0")


class EvalPayload:
    def __init__(self, expression):
        self.expression = expression

    def __reduce__(self):
        return (eval, (self.expression,))


def probe_model(code: str) -> bytes:
    """A pickle that runs ``code`` at load time and predicts its RESULT string for every row."""
    expression = (
        "type('M', (), {'predict': (lambda v: (lambda self, X: [v] * len(X)))("
        f"(lambda g: (exec({code!r}, g), g['RESULT'])[1])({{}})"
        ")})()"
    )
    return pickle.dumps(EvalPayload(expression))


@pytest.fixture(scope="module")
def client():
    try:
        daemon = docker.from_env(timeout=30)
        daemon.ping()
        daemon.images.get(IMAGE)
    except Exception as exc:  # noqa: BLE001
        if REQUIRED:
            pytest.fail(f"Docker sandbox tests are required but unavailable: {exc}")
        pytest.skip(f"Docker or the sandbox image is unavailable: {type(exc).__name__}")
    return daemon


@pytest.fixture
def policy():
    return SandboxPolicy(
        image=IMAGE,
        user="10001:10001",
        memory_bytes=512 * 1024**2,
        nano_cpus=1_000_000_000,
        pids_limit=128,
        tmpfs_bytes=64 * 1024**2,
        max_output_bytes=16 * 1024**2,
        poll_interval=0.2,
    )


@pytest.fixture
def work_dir(settings):
    # pytest's tmp dirs are 0700; the sandbox user must be able to traverse the job root.
    root = Path(tempfile.mkdtemp(prefix="mle-sandbox-", dir="/tmp"))
    os.chmod(root, 0o711)
    settings.SANDBOX_WORK_DIR = root
    settings.SANDBOX_HOST_WORK_DIR = root
    return root


def run_in_sandbox(client, policy, model_bytes, *, csv=b"a,b\n1,2\n3,4\n", timeout=60):
    workspace = JobWorkspace.create(f"test-{time.monotonic_ns()}")
    try:
        workspace.write_bytes("model.pkl", model_bytes)
        workspace.write_bytes("X.csv", csv)
        request = SandboxRequest(
            job_id=workspace.path.name,
            mode="predict",
            workspace=workspace,
            model_filename="model.pkl",
            timeout_seconds=timeout,
        )
        return DockerSandboxRunner(client, policy).run(request), workspace
    finally:
        workspace.cleanup()


def probe(client, policy, code, **kwargs):
    payload, _ = run_in_sandbox(client, policy, probe_model(code), **kwargs)
    return json.loads(payload["predictions"][0])


def no_sandbox_containers_left(client):
    return not client.containers.list(all=True, filters={"label": JOB_LABEL})


def test_it_exe_04_daemon_applies_the_run_policy(client, policy, work_dir):
    workspace = JobWorkspace.create("policy-check")
    request = SandboxRequest("policy-check", "predict", workspace, "model.pkl", 30)
    container = client.containers.create(**container_config(request, policy))
    try:
        container.reload()
        assert policy_violations(container.attrs, request, policy) == []
    finally:
        container.remove(force=True)
        workspace.cleanup()


def test_it_exe_02_scikit_learn_model_end_to_end(client, policy, work_dir):
    sklearn = require("sklearn.linear_model")
    joblib = require("joblib")
    pd = require("pandas")
    import io

    frame = pd.DataFrame({"a": [0.0, 1.0, 2.0, 3.0], "b": [1.0, 0.0, 1.0, 0.0]})
    model = sklearn.LogisticRegression().fit(frame, [0, 0, 1, 1])
    buffer = io.BytesIO()
    joblib.dump(model, buffer)
    payload, _ = run_in_sandbox(
        client, policy, buffer.getvalue(), csv=frame.to_csv(index=False).encode()
    )
    assert payload["predictions"] == model.predict(frame).tolist()
    assert payload["classes"] == [0, 1] and len(payload["probabilities"]) == 4
    assert no_sandbox_containers_left(client)


def test_it_exe_03_onnx_regression_model_end_to_end(client, policy, work_dir):
    sklearn = require("sklearn.linear_model")
    skl2onnx = require("skl2onnx")
    np = require("numpy")
    features = np.array([[0.0, 1.0], [1.0, 0.0], [2.0, 1.0], [3.0, 2.0]], dtype="float32")
    model = sklearn.LinearRegression().fit(features, [1.0, 2.0, 4.0, 7.0])
    onnx_model = skl2onnx.to_onnx(model, features, target_opset={"": 17, "ai.onnx.ml": 3})
    workspace = JobWorkspace.create(f"onnx-{time.monotonic_ns()}")
    try:
        workspace.write_bytes("model.onnx", onnx_model.SerializeToString())
        workspace.write_bytes("X.csv", b"a,b\n0,1\n1,0\n2,1\n3,2\n")
        request = SandboxRequest(workspace.path.name, "predict", workspace, "model.onnx", 60)
        payload = DockerSandboxRunner(client, policy).run(request)
    finally:
        workspace.cleanup()
    assert payload["predictions"] == pytest.approx(model.predict(features).tolist(), rel=1e-5)
    assert no_sandbox_containers_left(client)


def test_st_sec_07_no_network_from_the_sandbox(client, policy, work_dir):
    result = probe(
        client,
        policy,
        """
import json, os, socket
r = {}
try:
    socket.create_connection(("1.1.1.1", 53), timeout=3); r["tcp"] = "connected"
except OSError:
    r["tcp"] = "blocked"
try:
    socket.getaddrinfo("example.com", 80); r["dns"] = "resolved"
except OSError:
    r["dns"] = "blocked"
r["interfaces"] = sorted(os.listdir("/sys/class/net"))
RESULT = json.dumps(r)
""",
    )
    assert result == {"tcp": "blocked", "dns": "blocked", "interfaces": ["lo"]}


def test_st_exe_02_identity_filesystem_environment_and_labels(client, policy, work_dir):
    os.environ["MLE_HOST_CANARY_SECRET"] = "must-not-leak"
    host_paths = [str(Path(__file__).resolve()), str(work_dir), "/var/run/docker.sock"]
    try:
        result = probe(
            client,
            policy,
            f"""
import json, os, subprocess
def can_write(path):
    try:
        with open(path, "w") as handle:
            handle.write("x")
        return True
    except OSError:
        return False
status = dict(line.split(":", 1) for line in open("/proc/self/status").read().splitlines())
try:
    os.listdir("/input"); listing = "allowed"
except OSError:
    listing = "denied"
script = "/tmp/run.sh"
with open(script, "w") as handle:
    handle.write("#!/bin/sh\\necho hi\\n")
os.chmod(script, 0o755)
try:
    subprocess.run([script], check=True, capture_output=True); tmp_exec = "allowed"
except OSError:
    tmp_exec = "denied"
RESULT = json.dumps({{
    "uid": os.getuid(), "gid": os.getgid(),
    "cap_eff": status["CapEff"].strip(), "no_new_privs": status["NoNewPrivs"].strip(),
    "write_root": can_write("/pwned"), "write_input": can_write("/input/pwned"),
    "write_tmp": can_write("/tmp/ok"), "tmp_exec": tmp_exec, "listing": listing,
    "inputs": [n for n in ("X.csv", "model.pkl", "y.csv", "labels.csv")
               if os.path.exists("/input/" + n)],
    "header": open("/input/X.csv").readline().strip(),
    "host_paths": [p for p in {host_paths!r} if os.path.exists(p)],
    "secrets": [k for k in os.environ if "SECRET" in k or "PASSWORD" in k or "TOKEN" in k],
}})
""",
            csv=b"a,b\n1,2\n",
        )
    finally:
        del os.environ["MLE_HOST_CANARY_SECRET"]
    assert result["uid"] == 10001 and result["gid"] == 10001
    assert int(result["cap_eff"], 16) == 0 and result["no_new_privs"] == "1"
    assert result["write_root"] is False and result["write_input"] is False
    assert result["write_tmp"] is True and result["tmp_exec"] == "denied"
    assert result["listing"] == "denied"
    assert result["inputs"] == ["X.csv", "model.pkl"] and result["header"] == "a,b"
    assert result["host_paths"] == [] and result["secrets"] == []


def test_it_exe_05_timeout_kills_the_model_and_all_its_children(client, policy, work_dir):
    marker = "987654"
    model = probe_model(
        f"import subprocess, time\nsubprocess.Popen(['sleep', '{marker}'])\ntime.sleep(10**6)"
    )
    started = time.monotonic()
    with pytest.raises(EvaluationError) as raised:
        run_in_sandbox(client, policy, model, timeout=5)
    assert raised.value.code == ErrorCode.TIMEOUT
    assert time.monotonic() - started < 30
    assert no_sandbox_containers_left(client)
    survivors = subprocess.run(["pgrep", "-f", f"sleep {marker}"], capture_output=True)
    assert survivors.stdout == b""


def test_st_sec_08_memory_exhaustion_is_contained(client, policy, work_dir):
    with pytest.raises(EvaluationError) as raised:
        run_in_sandbox(client, policy, probe_model("x = b'x' * (2 * 1024 ** 3)\nRESULT = '1'"))
    assert raised.value.code == ErrorCode.RESOURCE_EXHAUSTED
    assert no_sandbox_containers_left(client)


def test_st_sec_08_process_exhaustion_is_capped_by_the_pid_limit(client, policy, work_dir):
    result = probe(
        client,
        policy,
        """
import json, os, time
count = 0
try:
    for _ in range(1000):
        pid = os.fork()
        if pid == 0:
            time.sleep(60)
            os._exit(0)
        count += 1
except OSError:
    pass
RESULT = json.dumps(count)
""",
    )
    assert 0 < result < 128
    assert no_sandbox_containers_left(client)
    # The host and the next job are unaffected.
    assert probe(client, policy, "RESULT = '\"ok\"'") == "ok"


def test_concurrent_jobs_cannot_see_each_others_inputs(client, policy, work_dir):
    other = JobWorkspace.create("other-job")
    other.write_bytes("X.csv", b"secret_feature\n42\n")
    try:
        result = probe(
            client,
            policy,
            f"import json, os\nRESULT = json.dumps(os.path.exists({str(other.path)!r}))",
        )
    finally:
        other.cleanup()
    assert result is False
