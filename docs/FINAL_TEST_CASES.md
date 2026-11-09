# Updated Test Case Document

Current task allocation: [Team ownership](TEAM_OWNERSHIP.md). Primary owners are Anand (01-04, 19-20), Bidre (05-08, 17-18), Ayush (09-12, 21-22), Bhavesh (13-16, 23-24). Module support and historical authorship remain distinct.


Team 13 | 9 November 2026 | Final verification on main

The source-file hashes are recorded in [source-manifest.json](evidence/final/source-manifest.json). Raw outputs identify the actual environments and execution times.

## Baseline and execution rules

The following 80 cases retain the IDs and expected results of approved STP Section 9.
The final source manifest, full JUnit, live-system JSON and browser JSON identify executed
checks. The earlier detailed execution report preserves original test data and procedures.
A PASS below cites the applicable automated rerun or executed historical method. Platform
and participant requirements remain explicit partial/blocked outcomes.

| Case ID | Requirement | Procedure / test data | Expected result | Final actual result | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| UT-AUTH-01 | FR-001 | Weak password rejected | Validation error, minimum 8 characters | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-AUTH-02 | FR-001 | Strong password accepted | Accepted | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| IT-AUTH-01 | FR-001 | Register new email | 201; row created; hash ≠ plaintext | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-02 | FR-001 | Duplicate email | 400/409; no second row; no account data | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-03 | FR-002 | Login valid | 200; access + refresh; role USER | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-04 | FR-002 | Wrong password | 401 generic | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-05 | FR-003 | Refresh rotation | 200; old refresh invalid | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-06 | FR-003 | Logout revokes refresh | Second use 401 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-07 | FR-005 | History lists own only | 3 items, newest first, page ≤ 20 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-08 | FR-005 | Status filter | Only FAILED returned | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-09 | FR-006 | Delete own | 204; row, artifacts, reports removed | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-10 | FR-006 | Delete other's | 404; unchanged | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-11 | FR-007 | Evaluator workspace | Evaluator sees student's evaluation | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-AUTH-12 | FR-004, FR-007 | USER manages workspace | 403 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-AUTH-01 | FR-001..003 | Register, log in, log out, try history through the UI | Redirected to login after logout; no protected data | Final React workflow passed registration, history/filter/delete, upload/compatibility and real sandbox evaluation as applicable. | PASS | evidence/final/browser/results.json |
| ST-AUTH-02 | FR-005..007 | History page: filter, delete | List, filter and delete behave as specified | Final React workflow passed registration, history/filter/delete, upload/compatibility and real sandbox evaluation as applicable. | PASS | evidence/final/browser/results.json |
| UT-ING-01 | FR-008 | Extension allow-list | pkl, joblib, onnx accepted; exe and pkl.exe rejected | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-ING-02 | FR-009 | 50 MB boundary | 50 MB accepted; +1 byte rejected (413) | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-ING-03 | FR-010 | Header-only CSV | Rejected: no data rows | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-ING-04 | FR-010 | Duplicate column | Rejected naming a | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-ING-05 | FR-011 | Target suggestion | Suggest species; can override | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-ING-06 | FR-012 | Feature count mismatch | 'expected 4, got 3' | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-ING-07 | FR-010 | Missing feature values | Column age with count 2 | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| IT-ING-01 | FR-008 | Upload valid model | 201; UUID name; sha256 and size | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-ING-02 | FR-008 | ZIP renamed to .onnx | 400; nothing stored | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-ING-03 | FR-009 | Upload iris.csv | 201; 150 rows; columns | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-ING-04 | FR-012 | Compatible pair | PASSED | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-ING-05 | FR-012, FR-013 | Incompatible pair | FAILED; each failed check with expected vs actual | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-ING-06 | FR-011 | Target override | 200; persisted; excluded from features | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-ING-01 | FR-008..013 | Upload and validate in the UI | Progress; PASSED/FAILED summary | Final React workflow passed registration, history/filter/delete, upload/compatibility and real sandbox evaluation as applicable. | PASS | evidence/final/browser/results.json |
| ST-ING-02 | FR-008, FR-009 | Unauthenticated upload | 401; no file written | models=401, datasets=401, media files 4 -> 4 | PASS | evidence/final/system-results.json |
| UT-EXE-01 | FR-015 | 200 distinct floats | REGRESSION | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-EXE-02 | FR-015 | Strings a,b,c | CLASSIFICATION; override honoured | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-EXE-03 | FR-017 | [0,1,1,0] vs [0,1,0,0] | acc 0.75; class-1 P 1.00, R 0.50, F1 0.667 | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-EXE-04 | FR-018 | [3,5,7] vs [2,5,8] | MAE 0.667, MSE 0.667, RMSE 0.816, R² 0.75 | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-EXE-05 | FR-019 | SUCCEEDED → RUNNING | Error; status unchanged | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-EXE-06 | FR-017 | ROC-AUC with/without proba | AUC with proba; omitted with note | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| IT-EXE-01 | FR-014 | POST /evaluations | 202 < 1 s; QUEUED; enqueued | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-EXE-02 | FR-016 | sklearn model end to end | SUCCEEDED; metrics; container removed | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-EXE-03 | FR-016 | ONNX regression | SUCCEEDED; MAE, MSE, RMSE, R² | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-EXE-04 | FR-016 | Inspect container config | network none; RO rootfs; non-root; caps dropped; limits | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-EXE-05 | FR-019 | Never-returning model | Killed at 120 s; TIMED_OUT; container removed | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-EXE-06 | FR-020 | Corrupt/truncated model | FAILED; no trace or path | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-EXE-07 | FR-021 | Results retrievable | metrics_json, charts_json equal stored | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-EXE-01 | FR-014..021 | Upload, validate, run, open dashboard (UI) | Metrics visible; within NFR-002 | Final React workflow passed registration, history/filter/delete, upload/compatibility and real sandbox evaluation as applicable. | PASS | evidence/final/browser/results.json |
| ST-EXE-02 | FR-016 | Hostile model reads host paths, opens sockets | No host data; no connection | No host paths, secrets or labels visible; only X.csv and model.pkl; TCP and DNS blocked | PASS | DOCKER:test_st_exe_02_identity_filesystem_environment_and_labels, DOCKER:test_st_sec_07_no_network_from_the_sandbox |
| UT-REP-01 | FR-024 | Best metric direction | best F1 0.91; best RMSE 3.2 | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-REP-02 | FR-027 | Different dataset guard | ComparisonError | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| UT-REP-03 | FR-023 | Sizes 1, 2, 5, 6 | 1 and 6 rejected | Applicable service/unit regressions passed in final suite. | PASS | evidence/final/unit-junit.xml; evidence/final/junit.xml |
| IT-REP-01 | FR-023 | Compare 3 | Aligned table for 3 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-REP-02 | FR-027 | Mixed task types | 400 with message | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-REP-03 | FR-025 | JSON export | Model, dataset, task, metrics | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-REP-04 | FR-026 | PDF for one evaluation | application/pdf; metrics and charts | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-REP-05 | FR-026 | PDF for comparison | All models; best marked | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-REP-06 | FR-026, SEC-008 | Another user's report | 404/403; no file | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| IT-REP-07 | FR-022 | Chart data shape (3 classes) | 3×3 matrix; ROC present | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-REP-01 | FR-022 | Classification dashboard | Cards, confusion matrix, ROC render | Chart/report API regressions and browser comparison/export checks passed. | PASS | evidence/final/browser/results.json; evidence/final/junit.xml |
| ST-REP-02 | FR-022 | Regression dashboard | Predicted-vs-actual and residual plots | Chart/report API regressions and browser comparison/export checks passed. | PASS | evidence/final/browser/results.json; evidence/final/junit.xml |
| ST-REP-03 | FR-023..026 | Compare 3, download PDF and JSON | Best highlighted; files open | Chart/report API regressions and browser comparison/export checks passed. | PASS | evidence/final/browser/results.json; evidence/final/junit.xml |
| ST-SEC-01 | SEC-001 | Passwords hashed | Hasher prefix; no plaintext | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-02 | SEC-002, FR-004 | USER token on EVALUATOR and ADMIN endpoints | 403 for every call | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-03 | SEC-003 | Token older than 15 min | 401 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-04 | SEC-003 | Role claim altered, signature kept | 401 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-05 | SEC-004 | SQL injection in filters | 400 or empty; no leak; no SQL error | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-06 | SEC-004 | ../../etc/x.pkl | UUID name inside media root | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-07 | SEC-005 | Outbound connection from sandbox | Fails; FAILED; audit | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-08 | SEC-005 | Memory and process exhaustion | Killed by limits; host and other jobs fine | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-09 | SEC-008, FR-004 | User A on user B's ids | 404 each; no data | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-10 | SEC-007 | 6 failed logins in a minute | 6th → 429 | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-11 | SEC-004 | 200 MB upload | 413 early; memory stable | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| ST-SEC-12 | SEC-009 | pip-audit, npm audit, Bandit, SonarQube | No critical findings; no secrets | Project/sandbox audits and static checks pass; SonarQube gate OK with zero blocker/critical findings. | PASS | FINAL_SUBMISSION_CHECKLIST.md |
| ST-SEC-13 | SEC-006 | Failed login and a 403 | Audit rows with user, IP, event, time | Applicable API, security or real-Docker regression passed in final full suite. | PASS | evidence/final/junit.xml |
| PERF-01 | NFR-001 | Locust 50 users, 5 min, login/history/status/charts | p95 ≤ 500 ms; errors < 1% | 50 users for five minutes; 7,575 requests, zero failures; aggregate p95 140 ms and all routes <=180 ms. | PASS | evidence/final/performance-summary.json |
| PERF-02 | NFR-002 | 10,000 × 50 CSV, ~20 MB model | ≤ 60 s | model 18.55 MB (33 trees), CSV 4.09 MB; status=SUCCEEDED; duration=1.414 s | PASS | evidence/final/system-results.json |
| PERF-03 | NFR-011 | Validate 50 MB CSV | ≤ 20 s | 52428716 bytes (50.00 MiB), HTTP 201, rows=457242, elapsed=1.61 s | PASS | evidence/final/system-results.json |
| PERF-04 | NFR-003 | 5 jobs, 3 workers | All finish; equal to baseline | 5 concurrent jobs in 2.7 s wall; statuses=['SUCCEEDED']; equal to baseline=5/5; max jobs running at once=5; no containers left=True | PASS | evidence/final/system-results.json |
| REL-01 | NFR-006 | Kill worker mid-job, restart | FAILED within 5 min; no orphan | RUNNING with 1 sandbox container(s); worker killed; restarted after 15 s; job -> FAILED (WORKER_LOST: 'The evaluation worker stopped unexpectedly.') 193 s after the crash; orphan containers at end=0 (checked up to 193 s after crash) | PASS | evidence/final/system-results.json |
| USA-01 | NFR-005 | Five first-time users | ≤ 5 primary screens | Five first-time participant sessions still required. | BLOCKED | TSMP-21_USABILITY_PROTOCOL.md |
| PORT-01 | NFR-008 | Fresh docker compose up on two OSes | Reachable; smoke passes | macOS Compose and prior Linux CI smoke available; Windows deployment and current non-Chrome browser checks remain. | PARTIAL | SYSTEM_VALIDATION_REPORT.md |
| RET-01 | NFR-010 | Age artifacts to 31 days, run purge | Files and DB references removed | files before=('1', '1'); purge output 'models=1, datasets=1, reports=0, artifacts=0'; files after (old model, old dataset, young model)=('0', '0', '1'); API lookups=(404, 404, 200) | PASS | evidence/final/system-results.json |

## Added regression scenarios

`tests/test_final_workflows.py` covers registration races, admin list/audit authorization, logout ownership, shared-input deletion and rollback. `tests/test_tsmp21_security.py` adds workspace membership revocation and read-only evaluator access. Browser scenarios add responsive layout, admin/evaluator controls, exports and invalid inputs. `frontend/tests/session.test.mjs` covers refresh concurrency, sign-out races and expiry. The full suite contains the passing cases recorded in final/junit.xml.

Final planned-case disposition is 78 PASS, 1 PARTIAL (PORT-01) and 1 BLOCKED (USA-01). The two remaining cases need actual platform/participant evidence.
