# Project status - 14 October 2026

Historical execution context: dated results below are preserved, not current readiness claims. Current outcomes are in FINAL_SUBMISSION_CHECKLIST.md and SYSTEM_VALIDATION_REPORT.md.


Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.


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

The full React workflow, release security and performance validation, and final evidence remain
scheduled in Sprint 3. Sprint 2 results and the local verification record are tracked in
[SPRINT_2_EVIDENCE.md](SPRINT_2_EVIDENCE.md).


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

## TSMP-17 / TSMP-18 implementation update - 6 November 2026

- Extended the existing React Router app with model and CSV upload, target selection,
  compatibility reporting, task override, queued evaluation polling, result metrics/charts,
  private history, run comparison, report downloads, and role-gated workspace actions.
- Added the TSMP-18 role/action and input-security matrix at
  [TSMP_18_SECURITY_MATRIX.md](TSMP_18_SECURITY_MATRIX.md), plus tests for SQL-like compatibility
  IDs and target values.
- Verification: `npm run lint`, `npm run build`, `ruff check tests/test_ingestion_api.py`, and
  `manage.py check` pass; the focused auth, ingestion and reporting suites pass (89 tests, with
  one ReportLab deprecation warning). This host has no Docker CLI, so the full browser path through
  sandbox inspection/evaluation and its screenshots remain to be captured on a Docker-enabled
  machine. Record CI and browser evidence before closing the Jira tickets.
