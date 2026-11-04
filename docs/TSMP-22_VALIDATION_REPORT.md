# TSMP-22 (MLE-22) - Validation report

Web-Based ML Model Evaluator, Team 13. Prepared by Ayush M Shetty for TSMP-21 / TSMP-22 on
4 November 2026, branch `feature/TSMP-21-22-validation`.

Companion documents:
- [Repository audit](TSMP-21-22_REPOSITORY_AUDIT.md)
- [Test execution report](TSMP-21_TEST_EXECUTION_REPORT.md): every case with expected and
  actual result and Pass/Fail
- [Defect register](TSMP-21_DEFECT_REGISTER.md)
- [Requirements traceability matrix](TSMP-22_REQUIREMENTS_TRACEABILITY_MATRIX.md)

## 1. Requirement coverage summary

Status rule (from the RTM): **VERIFIED** means every SRS verification method for the requirement
passed. **PARTIAL** means at least one required method failed or was blocked. **NOT VERIFIED**
means none could be executed.

| Group | Total | Verified | Partial | Not verified | Not implemented |
|---|---|---|---|---|---|
| FR, High priority | 20 | 18 | 2 (FR-005, FR-014) | 0 | 0 |
| FR, Medium priority | 7 | 7 | 0 | 0 | 0 |
| SEC-001..010 | 10 | 9 | 1 (SEC-009) | 0 | 0 |
| NFR-001..011 | 11 | 7 | 2 (NFR-007, NFR-008) | 1 (NFR-004) | 1 (NFR-005, DEF-07) |
| **All** | **48** | **41 (85%)** | **5** | **1** | **1** |

Each of the 48 requirements has an architecture and design reference. 47 have real source
files: NFR-005 has none, because the React SPA does not exist. 46 have at least one executed
test: NFR-004 (operational review) and NFR-005 (USA-01) have none. Every missing link is marked
in the RTM.

**Requirements with insufficient system-level coverage:**
- FR-005 and FR-014 (both High). Their SRS verification method includes a system test that
  runs through the UI (ST-AUTH-02, ST-EXE-01). Those screens do not exist (DEF-07). The same
  behaviour passes end to end through the REST API (`SYS:ST-AUTH-01(API)`,
  `SYS:ST-EXE-01(API)`).
- FR-001, FR-006, FR-007 and FR-008..013 are verified by their SRS methods (functional,
  integration, unit, boundary). Their STP system tests through the UI (ST-AUTH-01/02,
  ST-ING-01) fail for the same reason.
- NFR-005: NOT IMPLEMENTED. No browser workflow exists to walk through (DEF-07).
- NFR-004: NOT VERIFIED. It needs an operating window to measure.

## 2. Test coverage summary

| Measure | Result |
|---|---|
| Automated regression (pytest, non-Docker) | **335 passed, 0 failed, 6 xfailed** (strict xfails documenting DEF-05/DEF-06) |
| Real-Docker containment suite (Linux Docker host) | **9 / 9 passed** |
| Backend line coverage | **96.37%** (gate 80%) |
| Lint / migration check | ruff clean; no missing migrations |
| Live system cases (Compose stack) | **15 / 15 passed** |
| Browser cases (Chrome, `/results`) | **7 / 7 passed** (after DEF-13 fix) |
| STP planned cases (80) | **75 passed, 4 failed, 1 blocked → 93.75%** (≥ 90% required) |

Per STP module: M1 14/16, M2 14/15, M3 14/15, M4 13/13, security 13/13, non-functional 7/8.
The PORT-01 result depends on the Linux CI `compose-smoke` job; see the test execution report.
All 4 failures and the 1 blocked case come from the missing React SPA (DEF-07).

## 3. System and browser validation

The deployed stack (API, Celery worker and beat, PostgreSQL 15, Redis 7, docker-socket-proxy,
per-job sandbox containers) was validated end to end through the REST API and in Chrome:

- **Upload → validate → run → results**: an iris random forest validated PASSED, was queued in
  63 ms (202), ran in the real sandbox and SUCCEEDED in about 1.1 s, with metrics and chart JSON
  retrievable.
- **Mismatch**: the iris model with the wine dataset FAILED, reporting expected 4 features and
  actual 13.
- **ONNX regression** SUCCEEDED with MAE, MSE, RMSE and R².
- **`/results` dashboard (FR-022, FR-024)**: classification cards, 3×3 confusion matrix and
  ROC curve with class switching; regression predicted-vs-actual, residual and histogram plots;
  a mixed classification/regression selection disables Compare with an explanation; a
  three-model comparison marks the best values; JSON and PDF downloads open. Screenshots:
  `docs/evidence/tsmp-21/screenshots/01..07`.

FR-022 and FR-024 are therefore **VERIFIED** in the browser (ST-REP-01..03 pass).

## 4. Security validation summary

| Area | Tests | Result |
|---|---|---|
| Password storage | ST-SEC-01 | PBKDF2-SHA256, salted, more than 100k iterations; no plaintext in the row |
| RBAC / privilege escalation | ST-SEC-02 (6 cases), STP 11.1 matrix | USER → 403 on every evaluator/admin function; evaluator → 403 on admin. Deviations DEF-05 (evaluator cannot open member evaluation detail; more restrictive than spec) and DEF-06 (ADMIN treated as superset; no data disclosed) |
| Tokens | ST-SEC-03, ST-SEC-04 | 15-minute lifetime; expired, tampered-role, `alg=none`, refresh-as-access, malformed and missing tokens → 401 |
| Injection | ST-SEC-05 (16 + 2 cases) | Filter, date, page and target-column injections → 400/404 with no SQL text and no data leak |
| Path traversal | ST-SEC-06 (4 names) | Stored as `models/<uuid>.pkl` inside the media root only |
| IDOR | ST-SEC-09 (16 endpoints) | 404 for every object of another user; no change to their data |
| Rate limiting | ST-SEC-10 (live), SEC-007 uploads | 6th failed login → 429; per-user upload limit → 429 (DEF-03 fixed) |
| Oversize upload | ST-SEC-11 (live, 200 MB) | 413 after 0.05 s with 6.4 MB read; memory stable (DEF-08 fixed) |
| Sandbox containment | IT-EXE-04, ST-SEC-07, ST-SEC-08, ST-EXE-02, cross-job (real Docker) | No network or DNS, non-root, read-only root, no labels or secrets visible, memory and PID exhaustion contained, timeout kills child processes, no cross-job visibility |
| Audit | ST-SEC-13 | Failed login and 403 rows with user/email, IP, event, time; admin actions and retention purges audited |
| Dependencies / static analysis / secrets | ST-SEC-12 | After DEF-01: pip-audit clean for project and sandbox dependencies; Bandit no medium or high findings; no secrets in Git history; `.env` ignored |
| Configuration | ST-SEC-12 review | CORS restrictive by default (no CORS headers sent). **No HTTPS/TLS configuration, and the development server is used (DEF-09, open)** |

No Critical security defect was found. Hostile-model containment held in every test.

## 5. Performance and reliability validation summary

Run on macOS 26.6.2 (Apple silicon) with Colima 0.10.3 (4 vCPU, 6 GiB Linux VM) and Docker
29.5.2. Compose stack with `WORKER_CONCURRENCY=3`.

| Test | Requirement | Target | Measured | Result |
|---|---|---|---|---|
| PERF-01 | NFR-001 | p95 ≤ 500 ms at 50 users, error rate < 1% | 7,377 requests in 5 min (24.6 req/s). p95 **120 ms** aggregate (history 28, status 25, charts 26, login 170). 0.53% errors, all 429 from the login throttle | PASS |
| PERF-02 | NFR-002 | ≤ 60 s | **1.26 s** for 10,000 × 50 with an 18.55 MB random forest | PASS |
| PERF-03 | NFR-011 | ≤ 20 s | **0.88 s** for 52,428,716 bytes (50.00 MiB), 457,242 rows | PASS |
| PERF-04 | NFR-003 | 5 jobs, results equal baseline | 5/5 SUCCEEDED and equal to single-run baseline; 3 running at once (3 worker slots); 3.5 s wall | PASS |
| REL-01 | NFR-006 | FAILED within 5 min; no orphan | Worker killed mid-job → FAILED (WORKER_LOST) **192 s** after the crash (207 s in an earlier run); 0 orphan containers | PASS |
| IT-EXE-05 (live) | FR-019 | killed at 120 s | TIMED_OUT at **120.57 s** (120.39 s earlier); container removed | PASS |

**Caveats.** All load ran on one laptop-class host, with Locust on the same machine. PERF-01
measured the Django development server that Compose currently uses (DEF-09), not a production
WSGI server. PERF-04 shows NFR-003's "at least 5 concurrently" is met by queueing over 3
configured worker slots, as the STP case specifies ("5 jobs with 3 workers"). Five truly
simultaneous jobs need `WORKER_CONCURRENCY=5` and enough host memory (1 GB per sandbox).

## 6. Usability and portability validation summary

- **USA-01 / NFR-005: not executed (blocked).** The STP needs five first-time users to complete
  upload → validate → run → view in the browser. Only the results part of that path exists in
  the UI (DEF-07), and no participants were available. Design check: SAD 8 plans 4 primary
  screens (Register, Login, New Evaluation, Dashboard). The current build cannot be measured
  against that plan.
- **Results UI heuristics (supplementary):** no horizontal overflow at the minimum 1280×720
  viewport. Errors appear as short human-readable notices (`#notice`, `aria-live`). Charts have
  ARIA labels. The browser console was clean after the favicon fix (DEF-13).
- **PORT-01 / NFR-008:** a fresh `docker compose down -v && up` on macOS (Colima) served the API
  in 8 s and passed every live case. Linux is covered by the CI `compose-smoke` job (see the test
  execution report for the run link). **Windows (Docker Desktop) was not tested. Firefox and
  Edge were not tested**; only Chrome was. NFR-008 is therefore PARTIAL.
- **Note for macOS developers:** the real-Docker test suite must run from a Linux container on
  the Docker host (`scripts/validation/run_docker_suite_linux.sh`), because the host's `/tmp`
  is not shared with the Docker VM.

## 7. Open defects and limitations

| ID | Severity | Summary | Owner / next step |
|---|---|---|---|
| DEF-07 | **High** | MLE-17 React SPA not implemented (UI-01..08; blocks NFR-005 and the UI system tests) | M2 + M4: deliver MLE-17, then rerun ST-AUTH-01/02, ST-ING-01, ST-EXE-01, USA-01 |
| DEF-05 | Medium | Evaluator cannot open member evaluation detail, charts or reports (STP 11.1, BR-05) | M1/M3/M4: agree the rule, then remove the strict xfails |
| DEF-09 | Medium | Development server and no HTTPS configuration in Compose (SEC-009) | Team: gunicorn behind a TLS proxy, plus Django HTTPS settings |
| DEF-12 | Medium | Evaluation deletion keeps uploads until retention (FR-006/NFR-010 wording) | Team decision |
| DEF-06 | Low | ADMIN treated as superset role versus STP 11.1 | Team decision: update the matrix or the code |
| DEF-10 | Low | No SonarQube quality gate (NFR-007) | Course infrastructure |

**Other limitations.**
- NFR-004 (availability) needs an operating window.
- OWASP ZAP baseline, Postman/Newman and `npm audit` (no frontend) from the STP toolset were
  not run. Their aims are covered by the pytest security matrix and the live system cases.
- `test-cases.xlsx` (STP 14) is replaced by the Markdown execution report.

## 8. Final validation conclusion

Against the STP release exit criteria (Part C, Section 5):

| Criterion | Required | Result | Met? |
|---|---|---|---|
| Test cases passing | ≥ 90% | 75 / 80 = **93.75%** of planned STP cases (PORT-01 counted with its CI evidence) | **Yes** |
| High-priority requirements | 100% Pass | **18 / 20** High FRs verified; FR-005 and FR-014 PARTIAL (UI system tests, DEF-07) | **No** |
| Open Critical/High defects | none | **1 open High (DEF-07)**; 0 Critical. DEF-01 and DEF-02 (High) are closed | **No** |
| Backend line coverage | ≥ 80% | 96.37% | Yes |
| SonarQube gate | passed | not configured (DEF-10) | No |
| ST-SEC-01..13 | all Pass or accepted risk | 13 / 13 Pass; DEF-09 is a documented configuration risk | Yes |
| Actual result and Pass/Fail recorded | every executed case | yes, every case | Yes |

**Conclusion.** The backend (M1-M4), the sandbox, and the security, performance, reliability
and retention behaviour are validated. Every security case passes, every measured performance
target is met with a wide margin, and the hostile-model containment suite passes on a real Linux
Docker host. **The release is not yet validated against the full MLE-21 exit criteria.** The
High-priority UI system tests and the usability walkthrough cannot pass until the MLE-17 React
workflow exists (DEF-07, the single open High defect). Once MLE-17 is delivered, the failed
cases (ST-AUTH-01, ST-AUTH-02, ST-ING-01, ST-EXE-01) and USA-01 must be re-executed. The open
Medium items (DEF-05, DEF-09, DEF-12) need team decisions before the final release.
