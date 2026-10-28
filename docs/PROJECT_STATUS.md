# Project status - 14 October 2026

## Repository audit

At audit time the default branch contained only `Team13_SRS_SAD_STP.pdf`, with one commit, no README, no issues and no pull requests. The Jira project contains unrelated legacy conference-review work items, so the ML Model Evaluator backlog is being added with an `MLE` prefix and without deleting or rewriting the pre-existing records.

## Completed in the foundation and M1 increment

- reconciled the synopsis, short SRS and approved Team 13 SRS/SAD/STP;
- added the project README, ownership table and security boundary;
- translated the six approved two-week sprints into three Jira delivery sprints;
- implemented dependency-light validation, task detection, metrics, comparison and sanitization services;
- added automated tests tied to STP vectors and negative cases;
- added a GitHub Actions lint/coverage gate.
- added Docker Compose topology for Django, PostgreSQL and Redis with environment-only secrets;
- implemented registration, JWT login/rotation/logout, RBAC and login throttling;
- implemented owner-only, filterable evaluation history and cascading artifact/report deletion;
- implemented evaluator-only workspaces, membership and workspace evaluation views.

## Remaining release work

Celery jobs, the hardened execution sandbox, React UI, ReportLab export, full security/performance suites and final evidence remain scheduled in the Jira backlog. No unexecuted test is represented as passed.


## Known limitations (tracked)

- **Model inspection runs through the M3 sandbox (MLE-11).** `ingestion.inspection.inspect_model()` sends the check to the Celery worker when `SANDBOX_INSPECTION_ENABLED=1`. The worker loads the model only inside the hardened container. When inspection is disabled or unavailable, `POST /api/v1/compatibility-reports` still fails closed with `MODEL_INSPECTION`. The end-to-end path through a real Redis broker and worker is covered by `tests/test_async_e2e.py`.
- Model signature checks are structural (first bytes only): binary pickle header, joblib pickle or known compression header, and a protobuf walk of the ONNX ModelProto header. They reduce disguised uploads but are not proof a file loads; the sandbox performs the real inspection.
- CSV limits: 50 MB, 500,000 rows, 1,000 columns, 255-character column names. At most 20 row-level issues are reported per upload.


## M3 increment - MLE-9 to MLE-12 (28 October 2026)

Implemented on branch `TSMP-9-12-sandboxed-evaluation`; see the README section "M3 API and evaluation engine" and [docs/M3_TRACEABILITY.md](M3_TRACEABILITY.md).

- Asynchronous evaluation lifecycle with Celery + Redis, compare-and-set state machine, 202/QUEUED submission, status and chart endpoints.
- Task detection with override and explicit rejection of unsupported targets; trusted metric engine with ROC-AUC, prediction validation and scikit-learn cross-checks.
- Hardened per-job Docker sandbox with post-create policy verification, read-only inputs (X and model only) and docker-socket-proxy access.
- 120 s enforced timeout with container kill/removal, idempotent cleanup, reaper for crashed workers, sanitized error catalog and audit events.

Evidence status: the containment suite `tests/test_sandbox_docker.py` needs a Docker host. It was **not executed on the development machine (no Docker)**. It runs in the CI job `sandbox-tests` with `REQUIRE_DOCKER_TESTS=1`, and this increment is not complete until that job passes.
