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

- **Model inspection is unavailable until the M3 sandbox exists (MLE-11).** `ingestion.inspection.inspect_model()` returns `None` by design because pickle/joblib must never be loaded by the web process. Until it is connected, `POST /api/v1/compatibility-reports` fails closed with a `MODEL_INSPECTION` check, so no real report can reach `PASSED`. The passing-path tests inject a fake inspector. Closing this is part of MLE-11/MLE-16 and must be re-verified end to end once the sandbox is wired in.
- Model signature checks are structural (first bytes only): binary pickle header, joblib pickle or known compression header, and a protobuf walk of the ONNX ModelProto header. They reduce disguised uploads but are not proof a file loads; the sandbox performs the real inspection.
- CSV limits: 50 MB, 500,000 rows, 1,000 columns, 255-character column names. At most 20 row-level issues are reported per upload.
