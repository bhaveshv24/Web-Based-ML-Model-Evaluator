# TSMP-21 / TSMP-22 - Repository and requirements audit

Audit date: 4 November 2026. Auditor: Ayush M Shetty (TSMP-21 / TSMP-22).
Baseline: `origin/main` at `714c789` (Merge PR #30, TSMP-13-16). The audit was done before any
change on branch `feature/TSMP-21-22-validation`.

## Sources read

- `README.md`, `docs/JIRA_BACKLOG.md`, `docs/PROJECT_STATUS.md`, `docs/M3_TRACEABILITY.md`,
  `docs/SPRINT_2_EVIDENCE.md`
- `Team13_SRS.pdf` (8 pages) and `Team13_SRS_SAD_STP.pdf` (36 pages: Part A SRS, Part B SAD,
  Part C STP with 80 planned test cases and the RTM)
- All of `backend/`, `sandbox/`, `tests/`, `.github/workflows/ci.yml`, `Dockerfile`,
  `docker-compose.yml`, `.env.example`
- Git history and pull requests #25 to #30. No branch, pull request or code exists for
  MLE-17 to MLE-24 apart from this work.

## Repository structure

| Path | Content | Module |
|---|---|---|
| `backend/accounts/` | User model (UUID, email, role), JWT login/refresh/logout, `IsEvaluator`, login throttle, `AuditLog` | M1 |
| `backend/workspaces/` | Workspace, membership, evaluator-only views | M1 |
| `backend/evaluations/views.py` (history part) | Owned, paginated, filtered history; delete | M1 |
| `backend/ingestion/` | Model/dataset upload, CSV validation, target override, compatibility reports, sandboxed inspection hook | M2 |
| `backend/evaluations/` | Job API, Celery tasks, state machine, executor, reaper, Docker sandbox runner, metrics engine, task detection, error catalog, audit | M3 |
| `backend/benchmarking/` | Comparison guard and winners, JSON/PDF reports, static `/results` dashboard (HTML/JS/CSS) | M4 |
| `sandbox/` | Sandbox image (Python 3.11, scikit-learn 1.5.2, ONNX Runtime 1.19.2) and `runner.py` | M3 |
| `tests/` | 15 pytest modules, 264 tests at baseline | all |
| `.github/workflows/ci.yml` | `core-tests` (ruff, migrations check, pytest with 80% coverage gate, Redis) and `sandbox-tests` (real Docker containment suite) | MLE-1 |
| `docker-compose.yml` | api, worker, beat, docker-proxy, sandbox (build only), PostgreSQL 15, Redis 7 | MLE-1 |

There is no `frontend/` directory. The SAD source layout (`frontend/src/...`) and stack (React,
Vite, Tailwind, Recharts) are not present.

## Baseline test run (unchanged `main`)

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check backend tests sandbox` | All checks passed |
| Migrations | `python manage.py makemigrations --check --dry-run` | No changes detected |
| Test suite + coverage | `REQUIRE_REDIS_TESTS=1 pytest --cov=backend --cov-fail-under=80` | **264 passed, 9 skipped** (Docker), coverage **96.17%** |
| Docker containment suite | `scripts/validation/run_docker_suite_linux.sh` (Linux container on the Docker host) | **9 passed** |

Log: `docs/evidence/tsmp-21/pytest-core.log` (baseline run). On macOS the Docker suite cannot
run directly, because the host's `/tmp` is not shared with the Docker VM (8 of 9 cases fail with
sandbox exit code 3, input missing). This is the documented macOS bind-mount limitation, not a
product defect. The suite was therefore run from a Linux container on the Docker host.

## Delivered functionality by Jira story

| Story | Status | Evidence |
|---|---|---|
| MLE-1 Repository, CI, Compose | Complete | CI jobs, Compose topology, env-only secrets |
| MLE-2 Register/login/refresh/logout | Complete | `accounts/`, `test_auth_history_workspaces.py` |
| MLE-3 History and deletion | Complete. Deleting an evaluation keeps its uploaded model and dataset (see DEF-12) | `evaluations/views.py` |
| MLE-4 Evaluator workspaces | Complete for list views. The evaluator cannot open a member's evaluation detail or reports (DEF-05) | `workspaces/` |
| MLE-5 Model upload validation | Complete | `ingestion/validators.py`, `views.py` |
| MLE-6 CSV ingestion and target | Complete | same |
| MLE-7 Compatibility report | Complete; inspection runs in the sandbox | `ingestion/compatibility.py`, `inspection.py` |
| MLE-8 Sprint 1 evidence | Complete (automated) | CI |
| MLE-9 to MLE-12 (M3) | Complete | `evaluations/`, `sandbox/`, Docker suite |
| MLE-13 Dashboards | Complete as a static JS page at `/results` (not React/Recharts) | `benchmarking/dashboard/` |
| MLE-14 Comparison guard | Complete | `benchmarking/comparison.py` |
| MLE-15 JSON/PDF export | Complete | `benchmarking/reports.py`, `pdf.py` |
| MLE-16 Sprint 2 evidence | Complete | `docs/SPRINT_2_EVIDENCE.md` |
| **MLE-17** End-to-end React workflow | **Not implemented.** Only `/results` (sign-in, completed runs, dashboards, compare, downloads, sign-out) exists. No browser screens for registration, upload wizard, run status, history filter/delete, workspaces or admin console | - |
| **MLE-18** Authorization and input-security matrix | **Partial.** Login throttle, RBAC for workspaces, IDOR 404s and input validation exist. Missing: upload rate limit (SEC-007), admin endpoint API-23 (needed for the ADMIN column), and an executed matrix | - |
| **MLE-19** Performance, concurrency, reliability | **Partial.** Reaper and concurrency design exist with unit tests. No Locust or timing harness, and no recorded PERF results | - |
| **MLE-20** Portability, retention, quality gate | **Partial.** Coverage gate exists. No retention job (`purge_expired` in SAD 2.1 is absent), no SonarQube, no dependency scan in CI. Pinned framework versions have published advisories (README) | - |
| MLE-23 / MLE-24 | Not started (out of scope for TSMP-21/22) | - |

## Missing functionality at baseline

1. **NFR-010 retention**: no scheduled purge; RET-01 cannot run.
2. **SEC-007 second clause**: no per-user upload rate limit.
3. **API-23 / UC-12 / BR-08**: no admin activate/deactivate endpoint and no admin console. The
   ADMIN-only column of STP 11.1 and ST-SEC-02's ADMIN half cannot be tested.
4. **MLE-17 React SPA (UI-01..UI-08)**: no registration, upload, run status, history-management,
   workspace or admin screens. NFR-005 (≤5 primary screens) cannot be validated in a browser.
5. **SEC-009**: framework versions with known advisories (Django 5.1.15 is past end of
   support); no HTTPS settings or TLS termination in Compose; the API runs Django's development
   server.
6. **NFR-007**: no SonarQube quality gate.
7. **STP tooling**: no Locust, OWASP ZAP, Postman/Newman or Playwright assets.

## Existing test coverage mapped to STP IDs (baseline)

| STP group | Planned | Automated at baseline | Notes |
|---|---|---|---|
| M1 UT/IT-AUTH (14) + ST-AUTH (2) | 16 | 14 UT/IT covered | ST-AUTH-01/02 need the UI |
| M2 UT/IT-ING (13) + ST-ING (2) | 15 | 13 UT/IT + ST-ING-02 covered | ST-ING-01 needs the UI |
| M3 UT/IT-EXE (13) + ST-EXE (2) | 15 | 14 covered (IT-EXE-02..05, ST-EXE-02 need real Docker) | ST-EXE-01 needs the UI |
| M4 UT/IT-REP (10) + ST-REP (3) | 13 | 10 covered | ST-REP-01..03 were run once manually in Sprint 2 |
| ST-SEC-01..13 | 13 | Partly: 01, 02 (USER half), 07, 08, 09 (evaluations only), 10 | 03, 04, 05, 06, 11 (real size), 12, 13 (IP check) had no test |
| PERF/REL/USA/PORT/RET | 8 | REL-01 at unit level only | No load, timing, portability or retention test |

## Known defects at baseline

Recorded with root cause, fix and retest in [TSMP-21_DEFECT_REGISTER.md](TSMP-21_DEFECT_REGISTER.md).

## Dependencies and blockers for TSMP-21 and TSMP-22

| Blocker | Effect | Owner |
|---|---|---|
| MLE-17 React SPA not delivered | ST-AUTH-01/02, ST-ING-01 and ST-EXE-01 cannot run as specified (through the UI). USA-01 cannot run. NFR-005 cannot be validated | M2 + M4 (backlog) |
| USA-01 needs five first-time users | Needs people and the MLE-17 UI; a single tester cannot run it | Team |
| PORT-01 second and third OS | Only macOS (Colima) is available locally. Linux is covered by the new CI `compose-smoke` job. Windows was not tested | Team |
| NFR-004 availability (operational review) | Needs a defined demonstration/operating window; cannot be measured in a test session | Team |
| SonarQube | No server or project key configured | Team / course infrastructure |
