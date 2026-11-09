# Sprint 2 results and verification

Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.


The scope is TSMP-1 through TSMP-16. The browser surface at `/results` signs in through the
existing API and reads completed evaluations. The full upload-to-evaluation browser wizard is
tracked separately under MLE-17.

## Task and evidence map

| Task | Implementation and verification |
|---|---|
| MLE-01 | `.github/workflows/ci.yml`, `docker-compose.yml`, lint, migration and 80% coverage gates. Compose now requires a configured Django signing key. |
| MLE-02 | `tests/test_auth_history_workspaces.py` covers registration, login, rotation, logout and throttling. |
| MLE-03 | The same suite covers owner-scoped history, filters and deletion of associated records and files. |
| MLE-04 | The same suite covers workspace creation, membership, evaluation visibility and role checks. |
| MLE-05 | `tests/test_ingestion.py` and `tests/test_ingestion_api.py` cover size, signature, UUID paths and checksums. |
| MLE-06 | The ingestion suites cover CSV limits, headers, missing data and target selection. |
| MLE-07 | The ingestion suites cover compatibility checks. The Redis suite covers model inspection dispatched to a worker. |
| MLE-08 | Foundation, authentication and ingestion regression suites run under the CI coverage gate. |
| MLE-09 | `tests/test_evaluation_jobs.py` covers API and state transitions. `tests/test_async_e2e.py` sends jobs through real Redis and Celery with a test runner. |
| MLE-10 | `tests/test_metric_engine.py` and `tests/test_metrics.py` cover task overrides, trusted scoring and scikit-learn parity. |
| MLE-11 | `tests/test_sandbox_policy.py` and `tests/test_sandbox_docker.py` cover the effective container policy, hostile models, label exclusion and cross-job isolation. |
| MLE-12 | The job and Docker suites cover timeout, process cleanup, sanitized errors, auditing and stale-job recovery. |
| MLE-13 | FR-022 and IT-REP-07, ST-REP-01/02. The browser displays classification cards, per-class scores, confusion matrix and selectable ROC curves. Regression displays metric cards, actual-versus-predicted and residual scatter, and a residual histogram. |
| MLE-14 | FR-023/024/027 and UT-REP-01..03, IT-REP-01/02. The API verifies ownership, size, uniqueness, completion, dataset checksum and task. The browser highlights metric winners. |
| MLE-15 | FR-025/026, IT-REP-03..06 and ST-SEC-09. API integration tests parse generated PDFs and validate JSON, report metadata and access control. |
| MLE-16 | M3 containment plus M4 API integration, report parsing and browser validation. See the verification record below. |

## Results and chart contracts

`GET /api/v1/evaluations/{id}/charts` returns `{id, task_type, charts}`. It returns 409 for
unfinished or failed runs and 404 for a foreign or missing evaluation. Each `charts` object has
a `type` matching `task_type`.

- **Classification** has `labels` and a square `confusion_matrix` with actual labels on rows and
  predicted labels on columns, in the same order. `roc` is either null or
  `{average, curves}`, where each class key maps to `{auc, fpr, tpr}`. The paired rate arrays
  are in plot order and are capped at 500 points per curve. The companion evaluation detail
  supplies `metrics_json.roc_auc_note` when ROC data is unavailable or partial.
- **Regression** has `predicted_vs_actual: {actual, predicted, sampled}`,
  `residuals: {predicted, residual}`, and `residual_histogram: {edges, counts}`.
  Scatter pairs share row order and sample up to 2,000 rows. Residual is actual minus predicted.
  Histogram counts cover all rows, with one more edge than count.

## Comparison and download contracts

All requests below require an access JWT.

| Request | Success |
|---|---|
| `POST /api/v1/comparisons` with `{"evaluation_ids": ["uuid", "uuid"]}` | 201 with comparison ID, ordered evaluations and `best_per_metric` |
| `GET /api/v1/comparisons/{id}` | 200 with the same shape |
| `GET /api/v1/evaluations/{id}/report.json` or `report.pdf` | 200 attachment |
| `GET /api/v1/comparisons/{id}/report.json` or `report.pdf` | 200 attachment |

A comparison requires 2–5 distinct, owned, successful evaluations with identical nonempty
dataset checksums and identical task types. A validation error returns 400. Missing or foreign
records return 404. Deleting a source evaluation invalidates the comparison and its downloads.
The winner map covers finite scalar metrics shared by all models and excludes the sample count.
MAE, MSE and RMSE are minimized. Other scored metrics are maximized. Exact ties select the first
evaluation in the submitted order.

JSON reports have `schema_version: 1`, `report_type`, `id`, `generated_at`, `owner` and an
ordered `evaluations` array. Comparison reports add `best_per_metric`. Each evaluation includes
its UUID, owner ID and email, task, status, duration in seconds, sandbox image, metrics and chart
data. The nested model supplies ID, filename, format, byte size and SHA-256. The dataset supplies
ID, filename, row count, column names, target column and SHA-256. Input metadata unavailable on
older records is null. Stored checksums and the target remain available independently of the
upload records. PDF downloads render the same metadata, per-model metrics and charts. Comparison
PDFs add a side-by-side table with best values marked.

## Reproduction

```sh
python -m pip install -e '.[dev,runtime]'
docker build -t ml-evaluator-sandbox:1.0 sandbox/
ruff check backend tests sandbox
python manage.py makemigrations --check --dry-run
REQUIRE_DOCKER_TESTS=1 REQUIRE_REDIS_TESTS=1 pytest --cov=backend --cov-fail-under=80
docker ps -aq --filter label=ml-evaluator.job
```

With Redis running, the last command should return an empty list after testing. For the browser
system check, sign in at `/results` with completed classification and regression evaluations.
Open each result, switch ROC class, compare three compatible runs, and download and open both
report formats. Select a mismatched run to verify the compare control explains why it is disabled.

## Local verification record

- The full suite passed **273 tests**, including the ten real-Docker containment tests and
  the Redis/Celery integration test. Backend coverage was **96.17%** against an 80% gate.
  Lint and Django migration checks passed, and zero labeled sandbox containers remained.
- Chromium signed in against Django with seeded completed results. It rendered both
  dashboard variants, switched ROC class, blocked a mixed selection, compared three
  models, downloaded and opened the comparison JSON and PDF, and signed out. The page
  also passed a 375-pixel viewport overflow check. Django integration tests opened
  single-evaluation PDF and JSON exports and checked foreign and anonymous requests.
- The initial full suite exposed an incompatible Celery/Kombu/Redis client combination.
  The test now uses a unique Redis namespace and cleans up its own keys. Docker probes
  verify blocked TCP and DNS, absence of a default route, and exposure of only the staged
  files when the host file-sharing driver allows directory listing.
- A fresh Compose stack on Docker Desktop passed registration, login, model and CSV
  upload, compatibility inspection, evaluation through a real sandbox, and JSON download.
  This exposed a root-owned media volume on the first run. The API image now initializes
  the media directory for UID 10002. The successful retry reused the built dependency layer
  and applied the same media ownership step with the current backend code.
- Invalid calendar dates in evaluation history filters now return 400. The regression case
  is in `tests/test_auth_history_workspaces.py`.
