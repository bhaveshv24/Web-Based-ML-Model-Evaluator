# TSMP-21 defect register

Severity and lifecycle follow STP Part C, Section 12. Critical: security breach, sandbox
escape, data loss or system unusable. High: major feature fails with no workaround. Medium:
feature partly fails, workaround exists. Low: cosmetic or minor.
Lifecycle: Open → In Progress → Fixed → Retest → Closed.

Branch for every fix: `feature/TSMP-21-22-validation`. Retest commands are in
[TSMP-21_TEST_EXECUTION_REPORT.md](TSMP-21_TEST_EXECUTION_REPORT.md#reproduction).

## Summary

| ID | Severity | Priority | Requirement | Test | Title | Status |
|---|---|---|---|---|---|---|
| DEF-01 | High | P1 | SEC-009 | ST-SEC-12 | Framework versions with published advisories; Django 5.1 past end of support | **Closed** |
| DEF-02 | High | P1 | NFR-010 | RET-01 | No retention purge for uploads and reports | **Closed** |
| DEF-03 | Medium | P2 | SEC-007 | ST-SEC-10 (extended) | Uploads not rate limited per user | **Closed** |
| DEF-04 | Medium | P2 | SEC-002, FR-004, BR-08 (UC-12, API-23) | ST-SEC-02 | No admin activate/deactivate endpoint | **Closed** |
| DEF-05 | Medium | P2 | SEC-008, BR-05, FR-007 | STP 11.1 matrix | Evaluator cannot open a workspace member's evaluation, charts or reports | **Open** |
| DEF-06 | Low | P3 | FR-004, SEC-002 | STP 11.1 matrix | ADMIN gets evaluator/user functions where the matrix expects 403 | **Open** (team decision) |
| DEF-07 | High | P1 | UI-01..UI-08, NFR-005; system tests for FR-001..007, FR-008..013, FR-014..021 | ST-AUTH-01/02, ST-ING-01, ST-EXE-01, USA-01 | MLE-17 React single-page application not implemented | **Open** (blocker, outside TSMP-21 scope) |
| DEF-08 | Low | P3 | SEC-004 | ST-SEC-11 | Oversize upload is read in full before the 413 | **Closed** |
| DEF-09 | Medium | P2 | SEC-009, NFR-008 | ST-SEC-12 (configuration review) | Compose serves the API with Django's development server, without TLS or HTTPS settings | **Open** |
| DEF-10 | Low | P3 | NFR-007 | CI quality gate | SonarQube quality gate not configured | **Open** |
| DEF-11 | Low | P4 | NFR-008 (installation docs) | PORT-01 | `.env.example` points to a document that does not exist | **Closed** |
| DEF-12 | Medium | P2 | FR-006, NFR-010 | IT-AUTH-09 (extended) | Deleting an evaluation keeps its uploaded model and dataset until retention | **Open** (team decision) |
| DEF-13 | Low | P4 | UI-05 (UI quality) | UI-CONSOLE | `/results` declares no icon, so the browser logs a 404 for `/favicon.ico` | **Closed** |

13 defects: 0 Critical, 3 High, 5 Medium, 5 Low. 7 closed, 6 open.
**High: 3 found, 2 closed, 1 open (DEF-07).**

## Details

### DEF-01 - Framework versions with published advisories (High, Closed)

- **Found by:** ST-SEC-12. `pip-audit --skip-editable` on the project environment reported 19
  advisory entries in 4 packages: Django 5.1.15 (9), djangorestframework 3.15.2 (5),
  djangorestframework-simplejwt 5.3.1 (2) and setuptools 80.9.0 (3). Evidence:
  `docs/evidence/tsmp-21/pip-audit-env.log`.
- **Impact:** reachable without authentication. These include DRF memory amplification through
  the Content-Type charset (CVE-2026-114136), quadratic `Accept` header parsing
  (CVE-2026-114138) and a `DATA_UPLOAD_MAX_MEMORY_SIZE` bypass for JSON bodies
  (PYSEC-2026-3827), all on the public `/auth/login` and `/auth/register`. SimpleJWT
  CVE-2024-22513 lets disabled accounts keep access, which matters for BR-08. Django 5.1 is past
  end of support and no longer receives security fixes.
- **Root cause:** the M1 foundation pinned `Django<5.2`, `djangorestframework<3.16` and
  `djangorestframework-simplejwt<5.4`. The README listed the upgrade as pending under ST-SEC-12.
- **Fix:** `pyproject.toml` floors raised to `Django>=5.2.17,<5.3` (5.2 LTS),
  `djangorestframework>=3.18.2,<3.19` and `djangorestframework-simplejwt>=5.5.1,<5.6`.
  Installed: Django 5.2.19, DRF 3.18.3, SimpleJWT 5.5.1. No code change was needed. The
  `token_blacklist` app gains two upstream migrations (0012, 0013), applied by `migrate`.
  A CI `security-scan` job now runs pip-audit and Bandit on every push.
- **Retest:** project and sandbox scans report no known vulnerabilities for project
  dependencies. The only remaining entries are for `setuptools` in the local virtual
  environment, which is a build tool and not a project dependency (CI upgrades it before
  scanning). Full suite at the time of the fix: 326 passed, 6 xfailed (the final regression run is 335 passed,
  6 xfailed). All API contracts are unchanged.
  Status: **Retest Pass → Closed.**

### DEF-02 - No retention purge (High, Closed)

- **Found by:** audit and RET-01. SAD 2.1 lists a `purge_expired` Celery task. No code
  existed, so NFR-010 was not implemented and RET-01 could not run.
- **Root cause:** MLE-20 not delivered.
- **Fix:** `backend/ingestion/retention.py`, `backend/ingestion/tasks.py` (task
  `ingestion.purge_expired`), management command `purge_expired`, hourly beat entry
  `purge-expired-uploads` and setting `RETENTION_DAYS` (default 30). Models and datasets older
  than the retention period are deleted with their files and compatibility reports, along with
  stored reports and artifacts of expired evaluations. Evaluation history keeps its checksums
  and metrics; its model/dataset links become null. Inputs of QUEUED or RUNNING jobs are kept
  until the job ends. Each purge writes a `RETENTION_PURGE` audit row.
- **Regression tests:** `tests/test_tsmp21_retention.py` (5 tests).
- **Retest:** RET-01 on the Compose stack: uploads aged to 31 days are removed (files and DB
  rows, API returns 404) and a fresh upload is kept. Status: **Retest Pass → Closed.**

### DEF-03 - No per-user upload rate limit (Medium, Closed)

- **Found by:** audit against SEC-007 ("uploads shall be rate limited per user").
- **Root cause:** only the login throttle was implemented.
- **Fix:** `accounts.throttles.UploadRateThrottle` (scope `upload`, keyed by user) on
  `POST /models` and `POST /datasets`. Default `30/min`, configurable with `UPLOAD_RATE_LIMIT`.
  Over the limit returns 429 with `Retry-After`.
- **Regression tests:** `test_sec_007_uploads_are_rate_limited_per_user`,
  `test_sec_007_default_upload_rate_is_configured`. Status: **Closed.**

### DEF-04 - No admin activate/deactivate endpoint (Medium, Closed)

- **Found by:** ST-SEC-02. The ADMIN column of STP 11.1 and API-23 (`PATCH
  /admin/users/{id}`) could not be tested because the endpoint did not exist. UC-12 and BR-08
  had no implementation.
- **Fix:** `accounts.permissions.IsAdmin` (denials audited) and `accounts.views.AdminUserView`
  at `PATCH /api/v1/admin/users/{id}` with body `{"is_active": bool}`. Deactivation blacklists
  every outstanding refresh token. SimpleJWT rejects access tokens of inactive users and Django
  rejects their login. Users are never deleted, so their audit history is kept (BR-08). An admin
  cannot deactivate their own account. Activation and deactivation are audited
  (`USER_ACTIVATED` / `USER_DEACTIVATED`).
- **Regression tests:** `test_api_23_admin_deactivates_and_reactivates_a_user`,
  `test_api_23_input_and_lookup_errors`, and the `/admin/users/{id}` cases of
  `test_st_sec_02_*`. Status: **Closed.**
- **Not covered:** the UI-08 admin console and the audit-log viewer (part of DEF-07).

### DEF-05 - Evaluator cannot open member evaluations (Medium, Open)

- **Found by:** STP 11.1 matrix. Row `/evaluations/{id}, charts, reports`, column EVALUATOR,
  expects "Own + workspace members". BR-05 says an EVALUATOR of the containing workspace may
  view an evaluation and its reports.
- **Actual:** `GET /evaluations/{id}`, `/status`, `/charts`, `/report.json` and `/report.pdf` of a
  workspace member's evaluation return **404** to the workspace's evaluator. The evaluator can
  list those evaluations with their metrics through `GET /workspaces/{id}/evaluations`, so FR-007
  itself works.
- **Root cause:** `OwnedEvaluationMixin` (M3/M4 views) filters on `owner=request.user` only.
- **Workaround:** use the workspace evaluation list (metrics included).
- **Tracking:** strict xfail `test_matrix_evaluator_can_open_workspace_member_evaluation[*]`
  (5 cases). It fails as XPASS once fixed.
- **Not fixed here:** the change widens object-level access in three teammates' modules (M1
  workspaces, M3 evaluation views, M4 reports). It needs the owners' review of the exact rule,
  for example whether it applies only while the user remains a member.

### DEF-06 - ADMIN treated as a superset role (Low, Open, needs a team decision)

- **Found by:** STP 11.1 matrix. ADMIN is expected to get 403 on `/workspaces`,
  `/comparisons` and `/evaluations/{id}`.
- **Actual:** `IsEvaluator` deliberately admits ADMIN, so ADMIN can manage workspaces (200). ADMIN
  can also use comparisons and its own evaluations as a normal user. Other users' evaluations
  return 404 rather than 403. No data of other users is disclosed.
- **Decision needed:** update STP 11.1 to match the implemented "ADMIN ⊇ EVALUATOR ⊇ USER"
  model, or restrict ADMIN in code. Tracked by strict xfail
  `test_matrix_admin_gets_403_on_workspaces`.

### DEF-07 - MLE-17 React SPA not implemented (High, Open, blocker)

- **Found by:** audit; ST-AUTH-01, ST-AUTH-02, ST-ING-01, ST-EXE-01 and USA-01.
- **Actual:** the only browser surface is `/results` (sign-in, completed runs, dashboards,
  comparison, downloads, sign-out). There is no browser UI for registration (UI-01 register),
  the upload wizard (UI-02), run status (UI-03), history filter and delete (UI-04), workspaces
  (UI-07) or the admin console (UI-08). A first-time user cannot complete
  upload → validate → run → view in a browser, so NFR-005 cannot be satisfied or measured.
- **Root cause:** MLE-17 (owners M2 + M4 per `docs/JIRA_BACKLOG.md`) has not started. No branch,
  pull request or `frontend/` directory exists.
- **Workaround:** the complete workflow works through the REST API (ST-*(API) cases pass).
- **Why not fixed in TSMP-21:** building the SPA is the MLE-17 story owned by other members, not
  a defect fix. The task rules also forbid rebuilding or replacing teammates' work. This is the
  main release blocker.

### DEF-08 - Oversize upload read in full before 413 (Low, Closed)

- **Found by:** ST-SEC-11 first run. A 200 MB upload returned 413 with stable server memory, but
  only after the client had sent all 209.7 MB. Django had spooled the body to a temporary file
  before the view's size check ran. STP expects "413 rejected early".
- **Fix:** `ingestion.views._reject_oversize_body` returns 413 from the declared
  `Content-Length` (limit + 1 MiB multipart allowance) before the body is parsed, for both
  upload endpoints. Missing or understated lengths still hit the existing per-file checks.
- **Regression tests:** `test_st_sec_11_oversize_body_is_rejected_from_content_length_before_parsing`
  (models and datasets; asserts the parser is never called) and
  `test_st_sec_11_body_at_the_limit_is_still_parsed_normally`.
- **Retest (live):** 413 after 0.05 s with 5.9 MB sent, compared with 0.55 s and 209.7 MB before.
  API memory 120.4 → 120.7 MiB; no file over 100 MB stored. Source: `ST-SEC-11` in
  `docs/evidence/tsmp-21/system-results.json` (executed 2026-11-04T15:55:52Z on the final code).
  Status: **Retest Pass → Closed.**

### DEF-09 - Development server and no HTTPS configuration in Compose (Medium, Open)

- **Found by:** ST-SEC-12 configuration review (SEC-009: "production traffic shall use HTTPS and
  a restrictive CORS policy").
- **Actual:** `docker-compose.yml` runs `python manage.py runserver`. There is no TLS-terminating
  proxy, and `SECURE_SSL_REDIRECT`, HSTS and `SECURE_PROXY_SSL_HEADER` are not set. CORS is
  restrictive by default: no CORS middleware is installed, so no `Access-Control-Allow-Origin`
  header is sent and browsers block cross-origin calls. Cookies are marked secure when
  `DEBUG=0`.
- **Recommendation:** run gunicorn behind an HTTPS reverse proxy (STP staging environment) and
  enable the Django HTTPS settings through the environment. This is a deployment change that
  affects every module's runtime, so it was not made unilaterally.

### DEF-10 - No SonarQube quality gate (Low, Open)

- NFR-007 requires a SonarQube gate with no blocker or critical issues. No SonarQube project is
  configured. Partial substitutes now run in CI: ruff, an 80% coverage gate (actual 96%), and
  Bandit with no medium or high findings. The coverage XML is already uploaded and can be used
  by SonarQube.

### DEF-11 - Broken documentation pointer (Low, Closed)

- `.env.example` referred to `docs/EVALUATION_ENGINE.md`, which does not exist. It now points to
  the README section. The new `RETENTION_DAYS` and `UPLOAD_RATE_LIMIT` settings are documented
  there.

### DEF-12 - Evaluation deletion keeps uploads (Medium, Open, needs a team decision)

- FR-006: "delete their own evaluation record together with its stored artifacts and reports".
  NFR-010: uploads are deleted after 30 days "unless the evaluation is deleted earlier".
- **Actual:** `DELETE /evaluations/{id}` removes the evaluation, its `EvaluationArtifact` and
  `Report` rows and their files (IT-AUTH-09 passes). The uploaded model and dataset remain,
  because `Evaluation.model_artifact` and `Evaluation.dataset` are `SET_NULL` and one upload can
  serve several evaluations. There is no API to delete an upload, so it remains until the
  30-day purge (DEF-02 fix).
- **Decision needed:** delete uploads that no other evaluation references when an evaluation is
  deleted, or add `DELETE /models/{id}` and `/datasets/{id}`.

### DEF-13 - Console 404 for the favicon on `/results` (Low, Closed)

- **Found by:** the UI-CONSOLE browser check. Chrome logged "Failed to load resource: 404",
  because the page declares no icon and the browser falls back to `/favicon.ico`.
- **Fix:** `backend/benchmarking/dashboard/favicon.svg`, served by the existing
  `dashboard_asset` view at `/results/favicon.svg` (same-origin, so the page CSP applies) and
  referenced from `index.html`.
- **Regression test:** `test_tsmp21_security.py::test_results_page_declares_an_icon_that_is_served_with_the_page_csp`.
- **Retest:** UI-CONSOLE in `browser-results.json`. Status: **Closed.**
