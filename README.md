# Web-Based ML Model Evaluator

Team 13's Software Engineering Level 3 mini-project: a secure browser-based application that evaluates already-trained tabular ML models against a CSV test dataset, presents trusted metrics and charts, compares models on the same dataset, and exports PDF/JSON reports.

## Project baseline

The approved Version 1 scope supports scikit-learn (`.pkl`, `.joblib`) and ONNX (`.onnx`) model artifacts, classification and regression CSV datasets, JWT authentication/RBAC, evaluation history, isolated Docker execution, model comparison, and report export. Model training, GPU inference, deep-learning frameworks, and image/video/NLP pipelines are out of scope.

The repository follows the approved four-module ownership model:

| Module | Functional area | Owner |
|---|---|---|
| M1 | Authentication and Workspace Management | Atharva Anand |
| M2 | Dataset Ingestion and Schema Pre-Validation | Atharva Rakesh Bidre |
| M3 | Sandboxed Model Execution and Metrics Engine | Ayush M Shetty |
| M4 | Model Benchmarking, Visual Analytics and Report Export | Bhavesh Velluru |

## Current increment

This foundation increment adds executable, dependency-light domain services for:

- model filename/size/signature validation;
- CSV header, duplicate-column, row-limit and missing-feature checks;
- task-type detection;
- trusted classification and regression metrics;
- comparison guards and best-per-metric selection;
- sanitized failure messages;
- a requirements-to-sprint Jira backlog and CI quality gate.

The domain services remain dependency-light, while the M1 increment now adds a Django REST API for secure JWT authentication, private evaluation history and evaluator workspaces. PostgreSQL and Redis are wired through Docker Compose; SQLite remains available for isolated tests and local development.

## M1 API

The versioned endpoints implemented for MLE-02 through MLE-04 are:

- `POST /api/v1/auth/register`, `/auth/login`, `/auth/token/refresh`, `/auth/logout`
- `GET /api/v1/evaluations` with `status`, `task_type`, `from`, `to` and `page` filters
- `GET` or `DELETE /api/v1/evaluations/{id}` with owner-only object access
- `GET` or `POST /api/v1/workspaces` for EVALUATOR/ADMIN accounts
- `POST /api/v1/workspaces/{id}/members` and `GET /api/v1/workspaces/{id}/evaluations`

Access JWTs expire after 15 minutes. Refresh JWTs expire after seven days, rotate on refresh and are blacklisted after rotation or logout. Login is limited to five attempts per minute for each IP/email combination.

## M2 API (MLE-5 to MLE-7)

- `POST /api/v1/models` - multipart `file`; `.pkl`/`.joblib`/`.onnx`, <= 100 MB, signature checked, stored as `<uuid><ext>` with SHA-256 (413 if oversize, 400 otherwise)
- `POST /api/v1/datasets` - multipart `file` (+ optional `target_column`); UTF-8 CSV <= 50 MB / 500k rows; returns columns, row count, suggested and selected target, SHA-256
- `GET` or `PATCH /api/v1/datasets/{id}` - PATCH `{"target_column": ...}` overrides the target and re-validates
- `POST /api/v1/compatibility-reports` - `{model_id, dataset_id}` -> PASSED/FAILED with per-check expected and actual values; `GET .../{id}` re-reads it

Model inspection is behind `ingestion.inspection.inspect_model`. Pickle/joblib are never loaded by the web process: with `SANDBOX_INSPECTION_ENABLED=1` the check is sent to the Celery worker, which reads `n_features_in_` / `feature_names_in_` inside the M3 sandbox (SAD 5.1 step 6). If inspection is disabled, the worker is unreachable, or the model cannot be inspected, the report fails closed (`MODEL_INSPECTION`).

## M3 API and evaluation engine (MLE-9 to MLE-12)

| Endpoint | Purpose | Responses |
|---|---|---|
| `POST /api/v1/evaluations` | `{model_id, dataset_id, task_type?, workspace_id?}`. Creates a job for a pair whose latest compatibility report is `PASSED` and still matches the dataset's current target (BR-01) | `202 {id, status: "QUEUED", status_url}`; 400 not validated / bad input; 404 not owned; 503 queue unavailable |
| `GET /api/v1/evaluations/{id}/status` | Polling (UI-03, every 2 s) | `200 {status, task_type, error_code, error_message, started_at, finished_at, duration_seconds}` |
| `GET /api/v1/evaluations/{id}` | Detail, including `metrics_json` and `charts_json` (FR-021) | 200; 404 |
| `GET /api/v1/evaluations/{id}/charts` | Chart data for M4 dashboards | 200; **409** until `SUCCEEDED`; 404 |

All endpoints are owner-only (another user's id returns 404). `DELETE /api/v1/evaluations/{id}` on a running job stops its sandbox.

**Lifecycle.** `QUEUED -> RUNNING -> SUCCEEDED | FAILED | TIMED_OUT`. Transitions are one-way, and terminal states never change (BR-04). Every change is a single conditional `UPDATE` (compare-and-set) in `evaluations/services.py`. A duplicate Celery delivery cannot claim a job twice, and a late or reaped worker cannot overwrite a newer state. `QUEUED -> FAILED` is used only when a job can never start (`QUEUE_UNAVAILABLE`, `QUEUE_EXPIRED`).

**Flow** (`evaluations/executor.py`): claim -> new per-job workspace -> split the CSV into features `X` and labels `y` -> detect the task -> run the model in the sandbox with a 120 s deadline -> validate predictions and compute metrics outside the sandbox -> remove the container and workspace -> publish the terminal state. Cleanup always happens before the terminal state is written.

**Task detection (FR-015).** The task is decided only from the trusted target column: text labels or integer-like, low-cardinality values mean classification; continuous numeric values mean regression. The user can override with `task_type`. Missing target values, a `REGRESSION` override on a non-numeric target, and more than `EVALUATION_MAX_CLASSES` (100) classes are rejected as `UNSUPPORTED_TASK` instead of guessed.

**Metrics (FR-017/018).** The metric set is fixed per task on the server and never taken from the model or the client:
- Classification: accuracy; precision, recall and F1 (macro, weighted and per class); confusion matrix; support; ROC-AUC (binary, or macro one-vs-rest) when valid probabilities exist, otherwise `null` with a note.
- Regression: MAE, MSE, RMSE, R².

Predictions are checked for length, scalar type and finite values before scoring. Malformed probabilities only drop ROC-AUC. A prediction set that shares no label with the target is rejected as a label-encoding error. The values are cross-checked against scikit-learn in `tests/test_metric_engine.py`.

**Failure categories** (`error_code`): `INVALID_INPUT`, `UNSUPPORTED_TASK`, `MODEL_LOAD_FAILED`, `MODEL_EXECUTION_FAILED`, `INVALID_PREDICTIONS`, `RESOURCE_EXHAUSTED`, `TIMEOUT`, `SANDBOX_UNAVAILABLE`, `SANDBOX_POLICY_VIOLATION`, `WORKER_LOST`, `QUEUE_UNAVAILABLE`, `QUEUE_EXPIRED`, `INTERNAL_ERROR`. Public messages are fixed server text (`evaluations/errors.py`): no tracebacks, paths or exception text (FR-020, SEC-010). Operators get the details in worker logs, tagged with the job id. Timeouts, resource-limit kills, policy violations and reaped jobs are written to `AuditLog` (SEC-006).

**Timeouts and recovery (FR-019, NFR-006).**
- The worker enforces `EVALUATION_TIMEOUT_SECONDS` (120) on the container's wall-clock time, then kills and removes the container. Every process the model started dies with it.
- Celery soft and hard task limits, plus a CPU-time ulimit inside the container, are backstops.
- `reap_stale_evaluations` runs every 60 s (Celery beat) and at worker start-up. It fails jobs left `RUNNING` longer than 120 s + 60 s grace (`WORKER_LOST`), so no job stays `RUNNING` for more than about 4 minutes. It also fails jobs queued for over an hour (`QUEUE_EXPIRED`) and removes orphaned sandbox containers and workspaces.

### Sandbox (FR-016, SEC-005, BR-06)

Each job runs in its own short-lived container started from the sandbox image (`sandbox/Dockerfile`, Python 3.11 with pinned scikit-learn 1.5.2, pandas, joblib and ONNX Runtime 1.19.2). The run policy (`evaluations/sandbox/docker_runner.py`):
- **Network:** `network=none`.
- **Filesystem:** read-only root; `/tmp` is a 64 MB `noexec` tmpfs.
- **Privileges:** user `10001:10001`, `cap_drop=ALL`, `no-new-privileges`, Docker's default seccomp profile.
- **Limits:** 1 GB memory with no swap, 1 CPU, 128 PIDs, CPU-time, file-size and open-file ulimits.
- **Environment:** only a fixed safe set of variables (no secrets).
- **Inputs:** the job's own directory, holding only `model.<ext>` and `X.csv`, is mounted read-only at `/input`. Labels are never written there.

After `create`, the daemon's view of the container is compared with this policy. Any difference means the model is not started (`SANDBOX_POLICY_VIOLATION`). Predictions come back on the container's size-capped stdout log, so no writable host path is ever mounted. The worker reaches Docker only through `docker-socket-proxy` (container API only) on an internal network. There is no fallback to unsandboxed execution: if Docker or the image is unavailable, jobs fail with `SANDBOX_UNAVAILABLE`.

Input files are copied from the media volume only if they are regular, non-symlinked files inside `MEDIA_ROOT/models` or `MEDIA_ROOT/datasets`, within the size limits, and match the SHA-256 recorded at upload.

**Trust boundary for pickle/joblib.** These formats run code when loaded, and no validation can make that safe. They are therefore loaded only inside the sandbox, and only predictions leave it. A hostile model can return wrong predictions for itself, but it cannot read the labels, compute its own metrics, reach the network, or touch other jobs or the host filesystem through the configured boundary.

**Known limitations.**
- A container is not a VM. A Linux kernel or Docker escape would bypass these controls. For stronger isolation, run the sandbox under gVisor (`runsc`) or a VM-based runtime, and keep the host patched.
- `docker-socket-proxy` allows the whole container API section (create, start, kill, remove, logs, inspect, and others) rather than the exact five calls listed in SAD 2.3. A compromised worker could still create containers, though not use images, volumes, networks, exec, or build.
- The job directory must be the same path in the worker and on the Docker host (`SANDBOX_HOST_WORK_DIR`). Docker Desktop on macOS and Windows reports bind-mount sources differently, and the policy check may then fail closed. The production target is a Linux Docker host.
- ONNX models must use opset 21 or lower (ONNX Runtime 1.19). Pickles must be compatible with scikit-learn 1.5.2. Mismatches fail as `MODEL_LOAD_FAILED`.
- ONNX probabilities are used only from ZipMap outputs, where class names are known. Otherwise ROC-AUC is omitted with a note.
- Compatibility inspection waits synchronously in the request for up to 60 s while the worker inspects the model.

### Run the asynchronous workflow locally (without Compose)

```bash
python3.11 -m venv .venv && . .venv/bin/activate
python -m pip install -e '.[dev,runtime]'
python manage.py migrate                       # SQLite by default
redis-server                                   # or: docker run -p 6379:6379 redis:7-alpine
docker build -t ml-evaluator-sandbox:1.0 sandbox/   # needs a Docker daemon
export SANDBOX_INSPECTION_ENABLED=1 SANDBOX_WORK_DIR=/tmp/ml-evaluator-jobs
PYTHONPATH=backend celery -A config worker --loglevel=INFO   # add --pool=threads on macOS
PYTHONPATH=backend celery -A config beat --loglevel=INFO     # reaper, every 60 s
python manage.py runserver
```

Both Celery processes and `runserver` need the same environment. Without Docker the stack still starts, but every job fails closed with `SANDBOX_UNAVAILABLE`. The macOS `--pool=threads` flag works around a known problem with Celery's default prefork pool on macOS; Linux and the Compose stack use the default pool.

Then: upload a model and a dataset, `POST /api/v1/compatibility-reports` until it returns `PASSED`, `POST /api/v1/evaluations`, and poll `/status` until it reaches a terminal state.

## Run the tests

```bash
python3 -m pip install -e '.[dev]'
ruff check backend tests sandbox
python manage.py makemigrations --check --dry-run
pytest --cov=backend --cov-fail-under=80
```

- **Without Docker:** two marked groups skip automatically when their service is missing. `redis` tests need a reachable Redis (`REDIS_URL`); `docker` tests need a Docker daemon and the sandbox image.
- **Hostile-model containment suite** (`tests/test_sandbox_docker.py`): network, identity, filesystem, environment, timeout plus child-process kill, memory and PID exhaustion, and cross-job visibility. Run it with:

  ```bash
  docker build -t ml-evaluator-sandbox:1.0 sandbox/
  REQUIRE_DOCKER_TESTS=1 pytest -m docker -v
  ```

  With `REQUIRE_DOCKER_TESTS=1`, missing Docker is a failure, not a skip. CI runs it that way in the `sandbox-tests` job, so a skipped local run never counts as security evidence.

## Run the API with Docker Compose

```bash
cp .env.example .env
# Replace both placeholder secrets in .env before starting the stack.
# Host directory for per-job sandbox inputs, owned by the worker's UID 10002 (Linux host):
sudo install -d -m 0711 -o 10002 -g 10002 /var/lib/ml-evaluator/jobs
docker compose --profile sandbox build sandbox   # builds ml-evaluator-sandbox:1.0
docker compose up --build
```

The Compose topology:
- `api -> PostgreSQL` for persistence, and `api -> Redis` to queue jobs.
- `worker` (Celery) runs evaluations and model inspection. It reaches Docker only through `docker-proxy`, on the internal `sandbox-control` network.
- `beat` runs the reaper every minute.

The API container never gets Docker access. Secrets are read from `.env`, which is ignored by Git and must never be committed. `api` applies migrations at start-up (`python manage.py migrate`).

## Planned runtime stack

- React + Vite + TypeScript + Tailwind + Recharts
- Django + Django REST Framework + SimpleJWT
- Celery + Redis
- PostgreSQL 15
- Docker Compose and a hardened per-job sandbox container
- ReportLab, GitHub Actions, SonarQube-compatible coverage, Postman/Newman

See [docs/JIRA_BACKLOG.md](docs/JIRA_BACKLOG.md) for the three Jira delivery sprints and the mapping back to the six two-week academic sprints in the approved SRS/SAD/STP.

## Security boundary

Pickle and joblib uploads are executable content. They must never be imported or unpickled by the web process. Compatibility inspection and prediction run only in the locked-down sandbox described by SEC-005; ground-truth labels and metric computation remain outside that container. See [Sandbox](#sandbox-fr-016-sec-005-br-06) for the enforced policy and its known limitations.

## Dependency security status

`pip-audit` on the development environment (28 October 2026) reports known advisories for **Django 5.1.15, Django REST Framework 3.15.2 and SimpleJWT 5.3.1**. These pins (`Django>=5.1,<5.2`, `djangorestframework>=3.15,<3.16`, `djangorestframework-simplejwt>=5.3,<5.4`) come from the M1 foundation and predate the M3 work. The fixes need framework upgrades (Django 5.2+, DRF 3.17+, SimpleJWT 5.5+), tracked under the dependency scan (ST-SEC-12, MLE-20) rather than in MLE-9 to MLE-12. No advisories are reported for Celery, Redis, the Docker SDK, scikit-learn, pandas, ONNX Runtime, onnx 1.23 or skl2onnx 1.20, or for the sandbox image's pinned `sandbox/requirements.txt` (`pip-audit -r sandbox/requirements.txt`). The only other finding is the virtual environment's own `setuptools`, which is not a project dependency. Bandit reports no findings for `backend/` and `sandbox/`; one documented `# nosec B108` marks the container-internal `/tmp` path.

