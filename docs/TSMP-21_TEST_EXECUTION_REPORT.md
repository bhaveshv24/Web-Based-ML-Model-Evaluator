# TSMP-21 (MLE-21) - Test execution report

Full regression, security, performance, reliability, usability, portability and retention
execution for the Web-Based ML Model Evaluator. Executed 4 November 2026 by Ayush M Shetty on
branch `feature/TSMP-21-22-validation`, based on `main` at `714c789`.

## 1. Summary

| Measure | Result |
|---|---|
| STP planned cases (Part C §9: 80 cases) | **75 PASS, 4 FAIL, 1 BLOCKED (not executed)** |
| Pass rate, all planned cases | **93.75%** (75 / 80; blocked counts as not passed) |
| Pass rate, executed cases | 94.9% (75 / 79) |
| Automated pytest regression | 335 passed, 0 failed, 6 strict xfail (DEF-05, DEF-06) |
| Real-Docker containment suite | 9 / 9 passed (Linux Docker host) |
| Live system cases on the Compose stack | 15 / 15 passed on the final code (§3.5) |
| Browser cases on `/results` | 7 / 7 passed after the DEF-13 fix (§3.6) |
| Backend line coverage | 96.37% (gate 80%) |
| Defects found | 13 (0 Critical, 3 High, 5 Medium, 5 Low). 7 closed with regression tests and retest; 6 open |
| Open High/Critical | **1 High open: DEF-07** (MLE-17 React SPA not implemented) |

**MLE-21 acceptance criteria:**

| Criterion | Result |
|---|---|
| ≥ 90% of all test cases pass | **Met** (93.75%) |
| 100% of High-priority requirements pass | **Not met**: FR-005 and FR-014 are PARTIAL. Their UI system tests fail because the screens do not exist (DEF-07) |
| Every executed test has an actual result and Pass/Fail | **Met** (tables below; raw JSON/JUnit in `docs/evidence/tsmp-21/`) |
| All High/Critical defects closed | **Not met**: DEF-07 (High) is open. It is outside TSMP-21's scope: the missing MLE-17 deliverable owned by M2 + M4 |

All 4 failures and the 1 blocked case have the same root cause, DEF-07. No failure was found in
the implemented backend, sandbox or `/results` UI that is still open at High or Critical
severity.

## 2. Test environment

| Item | Version / configuration |
|---|---|
| Host | macOS 26.6.2, Apple silicon (arm64) |
| Docker | Colima 0.10.3 VM (4 vCPU, 6 GiB, Linux 6.8.0-117-generic aarch64); Docker Engine 29.5.2; Docker Compose 5.6.1 |
| Python | 3.11.14 (host venv); 3.11.18 (Linux test container); `python:3.11-slim` images |
| Framework (after DEF-01) | Django 5.2.19, DRF 3.18.3, SimpleJWT 5.5.1, Celery 5.4.0, Kombu 5.6.2, redis-py 6.4.0, ReportLab 4.2.5 |
| ML / sandbox | scikit-learn 1.5.2, pandas 2.2.3, ONNX Runtime 1.19.2, onnx 1.23.2, skl2onnx 1.20.0; sandbox image `ml-evaluator-sandbox:1.0` |
| Services (Compose) | PostgreSQL 15-alpine, Redis 7-alpine, tecnativa/docker-socket-proxy 0.3.0, `WORKER_CONCURRENCY=3`, `EVALUATION_TIMEOUT_SECONDS=120` |
| Test tools | pytest 9.2.0, pytest-cov 7.1.0, pytest-django 4.14.0, ruff 0.17.3, pip-audit 2.10.1, Bandit 1.9.4, Locust 2.47.0, playwright-core 1.63.0 with Google Chrome (headless) |
| Local services for pytest | Redis 7 (Homebrew), SQLite file DB (`tests/conftest.py`) |

## 3. Execution results

Notation follows the RTM. `file::test` is a pytest test in `tests/`. `SYS:` is a case in
`scripts/validation/system_tests.py` run on the Compose stack. `UI:` is a case in
`scripts/validation/browser/results_dashboard.mjs`. `DOCKER:` is a case in
`tests/test_sandbox_docker.py` run on the Linux Docker host. Status is the final status after
any retest; first-run failures are noted in the Actual column.

### 3.1 M1 - Authentication and workspace management (16 cases: 14 pass, 2 fail)

| Test ID | Requirement | Test description | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|---|
| UT-AUTH-01 | FR-001 | Weak password rejected | Validation error, minimum 8 characters | `abc123` → 400 | PASS | `test_auth_history_workspaces.py::test_registration_rejects_weak_password_and_hashes_strong_password` |
| UT-AUTH-02 | FR-001 | Strong password accepted | Accepted | 201; letters+digits password accepted | PASS | same |
| IT-AUTH-01 | FR-001 | Register new email | 201; row created; hash ≠ plaintext | 201; email normalized; `password != plaintext`; `check_password` true | PASS | same; `SYS:ST-AUTH-01(API)` |
| IT-AUTH-02 | FR-001 | Duplicate email | 400/409; no second row; no account data | 400; 1 row; generic message | PASS | `::test_duplicate_email_is_rejected_without_account_details` |
| IT-AUTH-03 | FR-002 | Login valid | 200; access + refresh; role USER | 200; role claim; 15 min / 7 day lifetimes | PASS | `::test_login_issues_role_token_with_required_lifetimes` |
| IT-AUTH-04 | FR-002 | Wrong password | 401 generic | 401 generic; `LOGIN_FAILED` audited | PASS | `::test_wrong_password_is_generic_and_audited` |
| IT-AUTH-05 | FR-003 | Refresh rotation | 200; old refresh invalid | 200; reuse of old refresh → 401 (also live) | PASS | `::test_refresh_rotates_and_blacklists_old_token`; `SYS:ST-AUTH-01(API)` |
| IT-AUTH-06 | FR-003 | Logout revokes refresh | Second use 401 | 204 then 401 (also live) | PASS | `::test_logout_revokes_refresh_token`; `SYS:ST-AUTH-01(API)` |
| IT-AUTH-07 | FR-005 | History lists own only | 3 items, newest first, page ≤ 20 | Own items only, newest first, page size 20 | PASS | `::test_history_is_owned_newest_first_and_filterable`, `::test_history_page_size_is_at_most_twenty` |
| IT-AUTH-08 | FR-005 | Status filter | Only FAILED returned | Only matching status; invalid filter/date → 400 | PASS | same; `::test_history_date_filter_and_invalid_filter` |
| IT-AUTH-09 | FR-006 | Delete own | 204; row, artifacts, reports removed | 204; rows and files removed | PASS | `::test_deleting_own_evaluation_removes_rows_and_files` (see DEF-12 on uploads) |
| IT-AUTH-10 | FR-006 | Delete other's | 404; unchanged | 404; unchanged | PASS | `::test_non_owner_receives_404_for_detail_and_delete` |
| IT-AUTH-11 | FR-007 | Evaluator workspace | Evaluator sees student's evaluation | 200; only workspace evaluations listed | PASS | `::test_evaluator_can_create_workspace_add_member_and_view_only_its_evaluations` |
| IT-AUTH-12 | FR-004, FR-007 | USER manages workspace | 403 | 403; `AUTHORIZATION_DENIED` audited | PASS | `::test_user_cannot_manage_workspaces_and_denial_is_audited` |
| ST-AUTH-01 | FR-001..003 | Register, log in, log out, try history through the UI | Redirected to login after logout; no protected data | **Registration cannot be done in the browser: no UI-01 register screen exists.** Sign-in, sign-out and reload on `/results` behave correctly (0 protected nodes after sign-out). The full flow passes through the API | **FAIL** (DEF-07) | `UI:ST-AUTH-01(UI sign-in)`, `UI:ST-AUTH-01(UI sign-out)`, screenshots 01, 02, 07; `SYS:ST-AUTH-01(API)` |
| ST-AUTH-02 | FR-005..007 | History page: filter, delete | List, filter and delete behave as specified | **No history filter, delete or workspace UI exists.** `/results` lists completed runs only. Behaviour passes through the API (IT-AUTH-07..11) | **FAIL** (DEF-07) | screenshot 02 |

### 3.2 M2 - Dataset ingestion and schema pre-validation (15 cases: 14 pass, 1 fail)

| Test ID | Requirement | Test description | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|---|
| UT-ING-01 | FR-008 | Extension allow-list | pkl, joblib, onnx accepted; exe and pkl.exe rejected | Exactly as expected (`MODEL_TYPE` for both rejects) | PASS | `test_tsmp21_security.py::test_ut_ing_01_extension_allow_list_exact_stp_vector`; `test_ingestion.py::test_model_extension_allow_list` |
| UT-ING-02 | FR-009 | 50 MB boundary | 50 MB accepted; +1 byte rejected (413) | Accepted at limit; limit+1 → `DATASET_SIZE` (API 413) | PASS | `test_ingestion.py::test_size_boundary`; `test_ingestion_api.py::test_oversize_dataset_returns_413` |
| UT-ING-03 | FR-010 | Header-only CSV | Rejected: no data rows | Rejected | PASS | `test_ingestion.py::test_header_only_and_duplicates_are_reported` |
| UT-ING-04 | FR-010 | Duplicate column | Rejected naming `a` | Rejected naming the column | PASS | same |
| UT-ING-05 | FR-011 | Target suggestion | Suggest `species`; can override | Last column suggested; override works | PASS | `test_ingestion.py::test_valid_csv_summary_and_target_suggestion` |
| UT-ING-06 | FR-012 | Feature count mismatch | 'expected 4, got 3' | expected/actual reported | PASS | `test_ingestion.py::test_feature_count_mismatch_is_explicit` |
| UT-ING-07 | FR-010 | Missing feature values | Column `age` with count 2 | Column and count reported; missing target not counted | PASS | `test_ingestion.py::test_missing_feature_values_are_rejected_but_missing_target_is_not_counted` |
| IT-ING-01 | FR-008 | Upload valid model | 201; UUID name; sha256 and size | 201; `models/<uuid>.pkl`; checksum recorded (also live) | PASS | `test_ingestion_api.py::test_valid_model_is_stored_under_uuid_name_with_sha256`; `SYS:ST-ING-01(API)` |
| IT-ING-02 | FR-008 | ZIP renamed to .onnx | 400; nothing stored | 400; nothing stored (5 disguises) | PASS | `test_ingestion_api.py::test_disguised_content_is_rejected` |
| IT-ING-03 | FR-009 | Upload iris.csv | 201; 150 rows; columns | Live: rows=150, suggested `species` | PASS | `test_ingestion_api.py::test_csv_is_parsed_and_target_is_suggested`; `SYS:ST-ING-01(API)` |
| IT-ING-04 | FR-012 | Compatible pair | PASSED | Live: rf_iris.pkl + iris.csv PASSED (inspected in the sandbox) | PASS | `test_ingestion_api.py::test_compatible_model_and_dataset_pass`; `SYS:ST-ING-01(API)` |
| IT-ING-05 | FR-012, FR-013 | Incompatible pair | FAILED; each failed check with expected vs actual | Live: rf_iris + wine FAILED, `FEATURE_COUNT` expected 4, actual 13 | PASS | `::test_feature_count_mismatch_fails_with_expected_and_actual`; `SYS:ST-ING-01(API)` |
| IT-ING-06 | FR-011 | Target override | 200; persisted; excluded from features | 200; re-validated; unknown column 400 | PASS | `::test_target_can_be_overridden_after_upload_and_is_revalidated` |
| ST-ING-01 | FR-008..013 | Upload and validate in the UI | Progress; PASSED/FAILED summary | **No upload wizard (UI-02) exists.** The same flow passes through the API | **FAIL** (DEF-07) | `SYS:ST-ING-01(API)` |
| ST-ING-02 | FR-008, FR-009 | Unauthenticated upload | 401; no file written | Live: 401 / 401; media file count unchanged (4 → 4) | PASS | `SYS:ST-ING-02`; `test_ingestion_api.py::test_model_upload_requires_authentication_and_file` |

### 3.3 M3 - Sandboxed execution and metrics (15 cases: 14 pass, 1 fail)

| Test ID | Requirement | Test description | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|---|
| UT-EXE-01 | FR-015 | 200 distinct floats | REGRESSION | REGRESSION | PASS | `test_metric_engine.py::test_ut_exe_01_two_hundred_distinct_floats_is_regression` |
| UT-EXE-02 | FR-015 | Strings a,b,c | CLASSIFICATION; override honoured | As expected | PASS | `::test_ut_exe_02_string_labels_are_classification_and_override_is_honoured` |
| UT-EXE-03 | FR-017 | [0,1,1,0] vs [0,1,0,0] | acc 0.75; class-1 P 1.00, R 0.50, F1 0.667 | Exact match; scikit-learn parity | PASS | `::test_ut_exe_03_classification_vector_through_the_engine` |
| UT-EXE-04 | FR-018 | [3,5,7] vs [2,5,8] | MAE 0.667, MSE 0.667, RMSE 0.816, R² 0.75 | Exact match | PASS | `::test_ut_exe_04_regression_vector_through_the_engine` |
| UT-EXE-05 | FR-019 | SUCCEEDED → RUNNING | Error; status unchanged | Raises; unchanged | PASS | `test_evaluation_jobs.py::test_ut_exe_05_illegal_transition_raises_and_leaves_status_unchanged` |
| UT-EXE-06 | FR-017 | ROC-AUC with/without proba | AUC with proba; omitted with note | As expected | PASS | `test_metric_engine.py::test_ut_exe_06_roc_auc_reported_with_probabilities`, `::test_roc_is_omitted_with_a_note_when_undefined` |
| IT-EXE-01 | FR-014 | POST /evaluations | 202 < 1 s; QUEUED; enqueued | Live: 202 QUEUED in 63 ms | PASS | `::test_post_returns_202_queued_immediately_and_enqueues_once`; `SYS:ST-EXE-01(API)` |
| IT-EXE-02 | FR-016 | sklearn model end to end | SUCCEEDED; metrics; container removed | Real sandbox: as expected | PASS | `DOCKER:test_it_exe_02_scikit_learn_model_end_to_end` |
| IT-EXE-03 | FR-016 | ONNX regression | SUCCEEDED; MAE, MSE, RMSE, R² | Real sandbox and live: R² 0.9991, MAE 3.9203, MSE 23.1813, RMSE 4.8147 | PASS | `DOCKER:test_it_exe_03_onnx_regression_model_end_to_end`; `SYS:IT-EXE-03(live)` |
| IT-EXE-04 | FR-016 | Inspect container config | network none; RO rootfs; non-root; caps dropped; limits | Daemon's effective config matches the policy | PASS | `DOCKER:test_it_exe_04_daemon_applies_the_run_policy` |
| IT-EXE-05 | FR-019 | Never-returning model | Killed at 120 s; TIMED_OUT; container removed | Real sandbox (5 s deadline): killed with all children. Live with the deployed 120 s limit: TIMED_OUT at 120.568 s, container removed | PASS | `DOCKER:test_it_exe_05_timeout_kills_the_model_and_all_its_children`; `SYS:IT-EXE-05(live)` |
| IT-EXE-06 | FR-020 | Corrupt/truncated model | FAILED; no trace or path | Job path: sanitized `MODEL_LOAD_FAILED`, audited. Live: truncated pickle FAILED at inspection, no trace/path markers | PASS | `test_evaluation_jobs.py::test_failures_are_categorized_sanitized_audited_and_cleaned_up`; `SYS:IT-EXE-06(live)` |
| IT-EXE-07 | FR-021 | Results retrievable | metrics_json, charts_json equal stored | Live: `charts_json` equals `/charts`; metrics present | PASS | `::test_successful_evaluation_end_to_end_with_status_detail_and_charts`; `SYS:ST-EXE-01(API)` |
| ST-EXE-01 | FR-014..021 | Upload, validate, run, open dashboard (UI) | Metrics visible; within NFR-002 | **Upload and run cannot be done in the browser (no UI-02/UI-03).** API path: SUCCEEDED in 1.117 s; result opens in `/results` (ST-REP-01) | **FAIL** (DEF-07) | `SYS:ST-EXE-01(API)`; screenshot 03 |
| ST-EXE-02 | FR-016 | Hostile model reads host paths, opens sockets | No host data; no connection | No host paths, secrets or labels visible; only `X.csv` and `model.pkl`; TCP and DNS blocked | PASS | `DOCKER:test_st_exe_02_identity_filesystem_environment_and_labels`, `DOCKER:test_st_sec_07_no_network_from_the_sandbox` |

### 3.4 M4 - Benchmarking, visual analytics and reports (13 cases: 13 pass)

| Test ID | Requirement | Test description | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|---|
| UT-REP-01 | FR-024 | Best metric direction | best F1 0.91; best RMSE 3.2 | As expected | PASS | `test_comparison_security.py::test_best_per_metric_uses_direction` |
| UT-REP-02 | FR-027 | Different dataset guard | ComparisonError | Raised | PASS | `::test_comparison_rejects_mixed_datasets` |
| UT-REP-03 | FR-023 | Sizes 1, 2, 5, 6 | 1 and 6 rejected | As expected | PASS | `::test_comparison_rejects_invalid_size`; `test_benchmarking.py::test_comparison_limits_and_order` |
| IT-REP-01 | FR-023 | Compare 3 | Aligned table for 3 | Live: 201 (API-18 returns 201); 3 evaluations; best per metric | PASS | `test_benchmarking.py::test_comparison_limits_and_order`; `SYS:ST-REP-03(API)` |
| IT-REP-02 | FR-027 | Mixed task types | 400 with message | Live: 400 | PASS | `test_benchmarking.py::test_comparison_guards`; `SYS:ST-REP-03(API)` |
| IT-REP-03 | FR-025 | JSON export | Model, dataset, task, metrics | Appendix B fields present | PASS | `test_benchmarking.py::test_evaluation_exports` |
| IT-REP-04 | FR-026 | PDF for one evaluation | application/pdf; metrics and charts | Parsed with pypdf; content present | PASS | same |
| IT-REP-05 | FR-026 | PDF for comparison | All models; best marked | Live: 7-page PDF listing all three models | PASS | `::test_comparison_exports_and_deletion`; `SYS:ST-REP-03(API)` |
| IT-REP-06 | FR-026, SEC-008 | Another user's report | 404/403; no file | 404 (JSON and PDF, evaluation and comparison) | PASS | `::test_reports_are_owner_only`; `test_tsmp21_security.py::test_st_sec_09_*` |
| IT-REP-07 | FR-022 | Chart data shape (3 classes) | 3×3 matrix; ROC present | As expected (also live) | PASS | `::test_classification_chart_contract`; `SYS:ST-EXE-01(API)` |
| ST-REP-01 | FR-022 | Classification dashboard | Cards, confusion matrix, ROC render | 9 metric cards; 3×3 matrix; ROC curve; class switch changes the curve (AUC 1 → 0.97) | PASS | `UI:ST-REP-01`; screenshot 03 |
| ST-REP-02 | FR-022 | Regression dashboard | Predicted-vs-actual and residual plots | Predicted-vs-actual, residual plot and residual histogram (820 marks); MAE/MSE/RMSE/R² cards | PASS | `UI:ST-REP-02`; screenshot 04 |
| ST-REP-03 | FR-023..026 | Compare 3, download PDF and JSON | Best highlighted; files open | Mixed selection disables Compare with a message; 3-model table with 8 best cells; JSON (3 evaluations) and PDF (`%PDF-`) downloaded | PASS | `UI:ST-REP-03`; screenshots 05, 06; `docs/evidence/tsmp-21/browser-comparison-*.json/.pdf` |

### 3.5 Security tests ST-SEC-01..13 (13 cases: 13 pass)

| Test ID | Requirement | Test description | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|---|
| ST-SEC-01 | SEC-001 | Passwords hashed | Hasher prefix; no plaintext | `pbkdf2_sha256$<iterations>$<salt>$<hash>`, more than 100k iterations; plaintext absent; unique salts | PASS | `test_tsmp21_security.py::test_st_sec_01_password_is_stored_only_as_a_salted_pbkdf2_hash` |
| ST-SEC-02 | SEC-002, FR-004 | USER token on EVALUATOR and ADMIN endpoints | 403 for every call | 403 on all 5 (GET/POST /workspaces, POST members, GET workspace evaluations, PATCH /admin/users/{id}); EVALUATOR → 403 on admin; nothing changed; denials audited. **First run: the ADMIN endpoint did not exist (DEF-04); retest after fix PASS** | PASS | `::test_st_sec_02_user_token_gets_403_on_every_evaluator_and_admin_function`, `::test_st_sec_02_evaluator_token_cannot_reach_admin_functions` |
| ST-SEC-03 | SEC-003 | Token older than 15 min | 401 | Lifetime exactly 900 s; expired → 401; missing/malformed → 401 | PASS | `::test_st_sec_03_*` (2) |
| ST-SEC-04 | SEC-003 | Role claim altered, signature kept | 401 | 401 (also on the admin endpoint); `alg=none` → 401; refresh token as access → 401 | PASS | `::test_st_sec_04_*` (3) |
| ST-SEC-05 | SEC-004 | SQL injection in filters | 400 or empty; no leak; no SQL error | 400 for 4 payloads × status/task_type/from/to; page injection 404; target-column injection 400; no SQL text; row counts unchanged | PASS | `::test_st_sec_05_*` (17) |
| ST-SEC-06 | SEC-004 | `../../etc/x.pkl` | UUID name inside media root | 4 traversal names stored only as `media/models/<uuid>.pkl` | PASS | `::test_st_sec_06_*` (4) |
| ST-SEC-07 | SEC-005 | Outbound connection from sandbox | Fails; FAILED; audit | No route, TCP and DNS blocked; failure audit covered at job level | PASS | `DOCKER:test_st_sec_07_no_network_from_the_sandbox`; `test_evaluation_jobs.py::test_failures_are_categorized_sanitized_audited_and_cleaned_up` |
| ST-SEC-08 | SEC-005 | Memory and process exhaustion | Killed by limits; host and other jobs fine | 2 GiB allocation → `RESOURCE_EXHAUSTED`; fork bomb capped below 128 PIDs; next job runs | PASS | `DOCKER:test_st_sec_08_*` (2) |
| ST-SEC-09 | SEC-008, FR-004 | User A on user B's ids | 404 each; no data | 404 on 16 endpoints (evaluation detail/status/charts/reports/delete, model, dataset get/patch, compatibility get/create, evaluation create, comparison create/get/reports); B's data unchanged | PASS | `::test_st_sec_09_user_a_gets_404_for_every_object_of_user_b` |
| ST-SEC-10 | SEC-007 | 6 failed logins in a minute | 6th → 429 | Live: [401×5, 429] | PASS | `SYS:ST-SEC-10(live)`; `test_auth_history_workspaces.py::test_login_is_limited_to_five_attempts_per_ip_and_email` |
| ST-SEC-11 | SEC-004 | 200 MB upload | 413 early; memory stable | **First run: 413 after 0.55 s, but all 209.7 MB were read first (DEF-08).** Retest: 413 after 0.05 s with 5.9 MB sent; API memory 120.4 → 120.7 MiB; nothing stored | PASS (retest) | `SYS:ST-SEC-11`; `::test_st_sec_11_*` |
| ST-SEC-12 | SEC-009 | pip-audit, npm audit, Bandit, SonarQube | No critical findings; no secrets | **First run FAIL:** 19 advisory entries in Django/DRF/SimpleJWT/setuptools (DEF-01). Retest: project and sandbox dependencies clean; Bandit 0 medium/high (1 Low false positive); no secrets in Git history; `.env` ignored. npm audit not applicable (no frontend). SonarQube not configured (DEF-10, NFR-007) | PASS (retest) | `pip-audit-env.log`, `pip-audit-sandbox.log`, `bandit.log`; CI `security-scan` |
| ST-SEC-13 | SEC-006 | Failed login and a 403 | Audit rows with user, IP, event, time | `LOGIN_FAILED` (email, 203.0.113.7, time) and `AUTHORIZATION_DENIED` (user, 203.0.113.8, path, time) | PASS | `::test_st_sec_13_failed_login_and_403_are_audited_with_user_ip_event_and_time` |

### 3.6 Non-functional tests (8 cases: 7 pass, 1 blocked)

| Test ID | Requirement | Test description | Expected result | Actual result | Status | Evidence |
|---|---|---|---|---|---|---|
| PERF-01 | NFR-001 | Locust 50 users, 5 min, login/history/status/charts | p95 ≤ 500 ms; errors < 1% | 7,377 requests, 24.6 req/s. p95: aggregate **120 ms**, history 28, status 25, charts 26, login 170. Max 228 ms. Errors 39 (0.53%), all 429 from the login throttle | PASS | `perf01_stats.csv`, `perf01-report.html`, `perf01-console.log` |
| PERF-02 | NFR-002 | 10,000 × 50 CSV, ~20 MB model | ≤ 60 s | 18.55 MB random forest (33 trees), 4.09 MB CSV: SUCCEEDED in **1.264 s** | PASS | `SYS:PERF-02` |
| PERF-03 | NFR-011 | Validate 50 MB CSV | ≤ 20 s | 52,428,716 bytes (50.00 MiB), 457,242 rows: 201 in **0.88 s**. First attempt generated only 36 MiB (test-data error, discarded and rerun) | PASS | `SYS:PERF-03` |
| PERF-04 | NFR-003 | 5 jobs, 3 workers | All finish; equal to baseline | 5/5 SUCCEEDED; 5/5 metrics equal to single-run baseline; at most 3 running at once; 3.5 s wall; 0 containers left | PASS | `SYS:PERF-04` |
| REL-01 | NFR-006 | Kill worker mid-job, restart | FAILED within 5 min; no orphan | FAILED (`WORKER_LOST`) 192 s after the crash; 0 orphan containers | PASS | `SYS:REL-01` |
| USA-01 | NFR-005 | Five first-time users | ≤ 5 primary screens | **Not executed.** No browser workflow for upload/validate/run (DEF-07) and no participants | **BLOCKED** | - |
| PORT-01 | NFR-008 | Fresh `docker compose up` on two OSes | Reachable; smoke passes | macOS 26.6.2 arm64 (Colima): `down -v` + `up` → API in 8 s; 15/15 live cases pass. Ubuntu x86_64 (CI `compose-smoke`): API in 6 s; 3/3 smoke cases including a sandboxed evaluation | PASS | `port01-macos.log`, `port01-linux-ci-compose-smoke.json`, CI run 41863894224 |
| RET-01 | NFR-010 | Age artifacts to 31 days, run purge | Files and DB references removed | **First attempt impossible: no retention job (DEF-02).** After fix: aged files and rows removed (API 404), fresh upload kept | PASS (after fix) | `SYS:RET-01`; `test_tsmp21_retention.py` |

### 3.7 Live system cases (Compose stack, final code)

`scripts/validation/system_tests.py`, results in `system-results.json`, logs in
`system-tests-run1.log` and `system-tests-run2.log`.

| Case | Actual result | Status |
|---|---|---|
| ST-AUTH-01(API) | weak pw 400; login role USER; refresh 200; old refresh 401; logout 204; refresh after logout 401; anonymous history 401 | PASS |
| ST-ING-01(API) | rows 150, suggested `species`; iris PASSED; wine FAILED (FEATURE_COUNT 4 vs 13) | PASS |
| ST-ING-02 | 401 / 401; media files 4 → 4 | PASS |
| ST-EXE-01(API) | 202 QUEUED in 63 ms; SUCCEEDED in 1.117 s; accuracy 1.0; 3×3 matrix; ROC for 3 classes; image `ml-evaluator-sandbox:1.0` | PASS |
| IT-EXE-03(live) | REGRESSION SUCCEEDED; R² 0.9991, MAE 3.9203, MSE 23.1813, RMSE 4.8147 | PASS |
| IT-EXE-06(live) | Truncated pickle → compatibility FAILED (`MODEL_INSPECTION`); no trace/path markers | PASS |
| ST-REP-03(API) | comparison 201; JSON 200 with 3 evaluations; PDF 200 (7 pages); mixed-task 400 | PASS |
| ST-SEC-10(live) | [401, 401, 401, 401, 401, 429] | PASS |
| ST-SEC-11 | 413 after 0.05 s; 5.9 MB sent; memory 120.4 → 120.7 MiB; nothing stored | PASS |
| PERF-02 / PERF-03 / PERF-04 | see §3.6 | PASS |
| REL-01 | Hanging model RUNNING with 1 sandbox container; worker killed, restarted after 15 s; job → FAILED (`WORKER_LOST`, 'The evaluation worker stopped unexpectedly.') **192 s** after the crash; 0 orphan containers (earlier run on pre-final code: 207 s) | PASS |
| IT-EXE-05(live) | TIMED_OUT (`TIMEOUT`, 'The evaluation exceeded the execution time limit and was stopped. Limit: 120 seconds.') at **120.568 s**; 0 containers left (earlier run: 120.393 s) | PASS |
| RET-01 | Model and dataset aged to 31 days: files present → `purge_expired` → `models=1, datasets=1, reports=0, artifacts=0`; files removed; API 404/404; 0-day model kept (200) | PASS |

**Harness note.** In the first full run on the final code, REL-01, IT-EXE-05(live) and RET-01
failed with HTTP 429 `THROTTLED` on upload. The driver had reused one account for all cases and
exceeded the new per-user upload limit (30/min, DEF-03 fix). The product behaved as designed.
The driver was changed to use a fresh account per case, and the three cases were rerun
(`system-tests-run2.log`). Both runs are kept as evidence.

### 3.8 Supplementary cases added for MLE-18 / TSMP-21

| Case | Requirement | Actual result | Status | Evidence |
|---|---|---|---|---|
| STP 11.1 matrix: evaluation resources (5 paths) | SEC-008, FR-004 | anonymous 401; owner 200; other user 404 | PASS | `test_tsmp21_security.py::test_matrix_evaluation_resources_anonymous_401_owner_200_other_user_404` |
| STP 11.1: evaluator on member evaluation (5 paths) | BR-05 | 404, expected 200 | **FAIL** (strict xfail, DEF-05) | `::test_matrix_evaluator_can_open_workspace_member_evaluation` |
| STP 11.1: evaluator workspace list | FR-007 | 200 with the member's evaluation | PASS | `::test_matrix_evaluator_sees_workspace_member_evaluation_in_workspace_list` |
| STP 11.1: ADMIN on other users' evaluations | SEC-008 | 404 (no disclosure; matrix says 403) | PASS | `::test_matrix_admin_cannot_read_other_users_evaluations` |
| STP 11.1: ADMIN on /workspaces | FR-004 | 200, expected 403 | **FAIL** (strict xfail, DEF-06) | `::test_matrix_admin_gets_403_on_workspaces` |
| STP 11.1: anonymous on 6 protected collections; public register/login | SEC-003 | 401; register 201, login 200 | PASS | `::test_matrix_anonymous_gets_401_on_protected_collections`, `::test_matrix_public_endpoints_need_no_token` |
| API-23 deactivate/reactivate | BR-08 | Deactivation blocks login (401), access token (401) and refresh (401); account kept; audited; reactivation restores login | PASS | `::test_api_23_admin_deactivates_and_reactivates_a_user`, `::test_api_23_input_and_lookup_errors` |
| SEC-007 upload limit | SEC-007 | 3rd upload in a minute at `2/min` → 429 with `Retry-After`; other user unaffected; default `30/min` | PASS | `::test_sec_007_*` |
| RET-01 unit cases | NFR-010 | 31-day uploads, compatibility rows and reports purged; 29-day kept; RUNNING-job inputs kept until terminal; configurable; command, task and schedule | PASS | `test_tsmp21_retention.py` (5) |
| UI-LAYOUT-1280 | SRS 2.4 | 0 px horizontal overflow at 1280×720 | PASS | `UI:UI-LAYOUT-1280` |
| UI-CONSOLE | UI-01..06 | **First run: 1 error, 404 on `/favicon.ico` (DEF-13).** Retest after fix: 0 console errors | PASS (retest) | `UI:UI-CONSOLE` |

Strict-xfail cases are reported as FAIL here. They are not part of the 80 STP cases.

## 4. Non-functional tests

PERF-01 load profile: each of the 50 simulated users signs in with its own seeded account and
then runs history (weight 4), status (4), charts (2) and a re-login (1), waiting 1-3 s between
requests. The 50 accounts and their completed evaluations were seeded directly in the database
(`scripts/validation/perf/seed_load_users.py`), so no sandbox work ran during the measurement,
as NFR-001 excludes evaluation requests. The 39 throttled logins are the SEC-007 login limit of
5/min per IP and email. Random task choice occasionally made a user log in more than 5 times
within a minute. They count as errors in the 0.53% error rate.

## 5. CI runs

All four jobs passed on both pushes of branch `feature/TSMP-21-22-validation`. GitHub Actions
was reporting degraded performance, so both runs waited about 20 minutes in the queue.

| Run | Commit | core-tests | sandbox-tests | security-scan | compose-smoke |
|---|---|---|---|---|---|
| [41863340528](https://github.com/bhaveshv24/Web-Based-ML-Model-Evaluator/actions/runs/41863340528) | `e0b96b3` (code and tooling) | success | success | success | success |
| [41863894224](https://github.com/bhaveshv24/Web-Based-ML-Model-Evaluator/actions/runs/41863894224) | `bb0f254` (with docs and evidence) | success | success | success | success |

- `core-tests`: ruff, migration check, full suite with Redis, coverage gate.
- `sandbox-tests`: the real-Docker containment suite on Ubuntu, with the skip guard and the
  no-leftover-container check.
- `security-scan`: pip-audit (project and sandbox) and Bandit `-ll`. This is the ST-SEC-12
  retest in CI.
- `compose-smoke` (PORT-01, Linux): Ubuntu, Linux 7.0.0-1017-azure x86_64, Docker 28.0.4. The
  API was ready 6 s after `docker compose up -d --build`. `ST-AUTH-01(API)`, `ST-ING-01(API)` and
  `ST-EXE-01(API)` passed 3/3, including a real sandboxed evaluation (202 in 67 ms, SUCCEEDED in
  1.651 s). Artifact copy: `docs/evidence/tsmp-21/port01-linux-ci-compose-smoke.json`.

## 6. Reproduction

```sh
# 1. Automated regression (lint, migrations, unit/integration, coverage)
python -m pip install -e '.[dev,runtime]'
ruff check backend tests sandbox scripts
python manage.py makemigrations --check --dry-run
REQUIRE_REDIS_TESTS=1 pytest -m "not docker" --cov=backend --cov-fail-under=80

# 2. Real-Docker containment suite
docker build -t ml-evaluator-sandbox:1.0 sandbox/
REQUIRE_DOCKER_TESTS=1 pytest -m docker -v          # Linux Docker host
scripts/validation/run_docker_suite_linux.sh         # macOS: runs it from a Linux container

# 3. Security scans
pip install pip-audit bandit
pip-audit --skip-editable && pip-audit -r sandbox/requirements.txt
bandit -r backend sandbox -x '*/migrations/*' -ll

# 4. Live system, performance, reliability, retention (stack up: see README "Docker Compose")
docker compose up -d --build
python scripts/validation/system_tests.py            # writes docs/evidence/tsmp-21/system-results.json

# 5. PERF-01 load test
export LOAD_PASSWORD=<random>
docker compose exec -T -e LOAD_PASSWORD api python manage.py shell \
  < scripts/validation/perf/seed_load_users.py | grep @ > /tmp/accounts.txt
pip install locust
LOAD_ACCOUNTS=/tmp/accounts.txt locust -f scripts/validation/perf/locustfile.py --headless \
  -u 50 -r 5 -t 5m --host http://localhost:8000 --csv docs/evidence/tsmp-21/perf01

# 6. Browser checks (Google Chrome installed)
python scripts/validation/browser/seed_results.py --out /tmp/browser.env
cd scripts/validation/browser && npm install
set -a; . /tmp/browser.env; set +a; node results_dashboard.mjs
```

## 7. Evidence index (`docs/evidence/tsmp-21/`)

| File | Content |
|---|---|
| `pytest-core.log`, `junit-core.xml`, `coverage.xml` | Final regression run: 335 passed, 6 xfailed, 96.37% |
| `docker-suite-linux.log` | Containment suite, 9 passed, Linux 6.8 |
| `ruff.log`, `makemigrations.log` | Lint and migration checks |
| `pip-audit-env.log`, `pip-audit-sandbox.log`, `bandit.log` | ST-SEC-12 **first run** (before DEF-01), kept as evidence of the defect |
| `pip-audit-retest.log`, `bandit-retest-ll.log` | ST-SEC-12 retest after the DEF-01 fix |
| `system-results.json`, `system-tests-run1.log`, `system-tests-run2.log` | Live cases with actual result and status |
| `perf01_*.csv`, `perf01-report.html`, `perf01-console.log` | PERF-01 Locust output |
| `port01-macos.log`, `port01-linux-ci-compose-smoke.json` | PORT-01 on macOS (local) and Ubuntu (CI artifact) |
| `browser-results.json`, `screenshots/01..07-*.png`, `browser-comparison-*.{json,pdf}` | Browser cases and the downloaded comparison reports |

Screenshots are produced by the browser script against the live stack. No screenshot was edited
or produced by hand.

## 8. Known limitations of this execution

- One host. Load and functional runs share the machine, and Locust ran on the same host as the
  stack.
- Windows (Docker Desktop), Firefox and Edge were not tested (NFR-008 PARTIAL).
- The macOS Docker VM does not share the host `/tmp`. The containment suite was therefore run
  from a Linux container on the Docker host (`--pid=host` so IT-EXE-05 sees the host process
  table). CI runs it natively on Ubuntu.
- OWASP ZAP, Postman/Newman and SonarQube from the STP tool list were not run.
- USA-01 needs five human participants and the MLE-17 UI.
