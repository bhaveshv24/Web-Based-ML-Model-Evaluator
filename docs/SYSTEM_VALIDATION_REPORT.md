# System Validation Report

Team 13 | 9 November 2026 | Final verification on main

The source-file hashes are recorded in [source-manifest.json](evidence/final/source-manifest.json). Raw outputs identify the actual environments and execution times.

## Automated execution summary

| Scope | Result | Evidence |
| --- | --- | --- |
| Full regression, API, Redis/Celery and real Docker | 416 passed; zero failures/errors/skips/xfails | final/junit.xml; final/pytest.log |
| Dedicated unit/service subset | 121 passed | final/unit-junit.xml |
| Live Compose system checks | 15 / 15 passed | final/system-results.json |
| React browser workflow | 11 / 11 passed in installed Chrome | final/browser/results.json |
| Client session race/expiry tests | 3 / 3 passed | frontend/tests/session.test.mjs |
| Backend line / branch coverage | 97.36% / 92.67% | final/coverage.xml |
| HTTPS configuration | Certificate-verified 401 for protected API; HSTS present | final/https.json |

## Deployment and complete data flow

The local macOS Docker Desktop stack ran Nginx/React, Gunicorn/Django, PostgreSQL 15,
Redis 7, Celery/beat, the restricted Docker proxy and real inference containers. The React
browser tests exercised registration/login, model/CSV upload, compatibility inspection,
queued evaluation through completion, charts/ROC selection, comparison, JSON/PDF downloads,
history filters/deletion, invalid inputs, responsive layout, logout, evaluator workspace
creation/membership, and admin account activation/deactivation/audit access. No browser
page errors were recorded in the passing run.

## Live system outcomes

| Case | Actual result | Outcome |
| --- | --- | --- |
| ST-AUTH-01(API) | weak pw=400, role=USER, refresh=200, reuse old refresh=401, logout=204, refresh after logout=401, anonymous history=401 | PASS |
| ST-ING-01(API) | iris rows=150, suggested=species; iris pair=PASSED; wine pair=FAILED checks=[{"code": "TARGET_EXCLUDED", "status": "PASSED", "message": "Target column is excluded from the feature set", "expected": "'cultivar' not in features", "actual": ["alcohol", "malic_acid", "ash", "alcalinity_of_ash", "magnesium", "total_phenols", "flavanoids", "nonflavanoid_phenols", "proanthocyanins | PASS |
| ST-ING-02 | models=401, datasets=401, media files 4 -> 4 | PASS |
| ST-EXE-01(API) | compat=PASSED; POST=202 QUEUED in 38 ms; final=SUCCEEDED duration=1.186 s; accuracy=1.0; confusion 3x3; ROC classes=['setosa', 'versicolor', 'virginica']; sandbox_image=ml-evaluator-sandbox:1.0 | PASS |
| IT-EXE-03(live) | status=SUCCEEDED task=REGRESSION metrics={'r2': 0.9991, 'mae': 3.9203, 'mse': 23.1813, 'rmse': 4.8147} | PASS |
| IT-EXE-06(live) | compatibility=FAILED checks={"id": "514238e2-fab5-4171-8fad-33a3f5afd425", "model_id": "25c80465-eaf2-4cdd-8718-aca64e6353e5", "dataset_id": "63e702a4-53b2-48a5-8f57-8b20573ff5d7", "result": "FAILED", "checks": [{"code": "TARGET_EXCLUDED", "status": "PASSED", "message": "Target column is leaks=[] | PASS |
| ST-REP-03(API) | comparison=201; best accuracy -> ab4f95ca-f7b5-4a5e-b6c6-25c88ed3cba0; json=200 evaluations=3; pdf=200 11868 bytes, 7 pages; mixed-task compare=404 | PASS |
| ST-SEC-10(live) | status codes=[401, 401, 401, 401, 401, 429] | PASS |
| ST-SEC-11 | HTTP 413 after 0.66 s; client sent 2.3 MB before the response; api memory 234.8MiB -> 252.3MiB; files >100 MB stored=0 | PASS |
| PERF-02 | model 18.55 MB (33 trees), CSV 4.09 MB; status=SUCCEEDED; duration=1.414 s | PASS |
| PERF-03 | 52428716 bytes (50.00 MiB), HTTP 201, rows=457242, elapsed=1.61 s | PASS |
| PERF-04 | 5 concurrent jobs in 2.7 s wall; statuses=['SUCCEEDED']; equal to baseline=5/5; max jobs running at once=5; no containers left=True | PASS |
| REL-01 | RUNNING with 1 sandbox container(s); worker killed; restarted after 15 s; job -> FAILED (WORKER_LOST: 'The evaluation worker stopped unexpectedly.') 193 s after the crash; orphan containers at end=0 (checked up to 193 s after crash) | PASS |
| IT-EXE-05(live) | status=TIMED_OUT (TIMEOUT: 'The evaluation exceeded the execution time limit and was stopped. Limit: 120 seconds.'); duration=121.052 s; sandbox containers left=0 | PASS |
| RET-01 | files before=('1', '1'); purge output 'models=1, datasets=1, reports=0, artifacts=0'; files after (old model, old dataset, young model)=('0', '0', '1'); API lookups=(404, 404, 200) | PASS |

## Corrected defects and design decisions

Workspace-member results are now readable by the authorized evaluator and access ends when
membership ends. Deletion remains owner-only and preserves shared inputs until their last
reference is removed. Physical removal follows database commit, with rollback tested.
Duplicate registration races return validation errors. Logout rejects another account's
refresh token. Concurrent client requests share token refresh, stale refresh cannot restore
a signed-out session, and invalid uploads clear prior validation. Comparison additionally
checks the selected target. Admin and history/workspace controls are present in React.

The existing ADMIN hierarchy is retained as a documented deviation from the original STP
matrix, with no blanket access to other users' records. The HTTPS override was exercised
with a locally trusted Caddy certificate; public hostname/DNS issuance remains deployment
configuration. See FINAL_SRS_SAD_STP_UPDATE.md.

## Performance, quality and availability

The final 50-user steady-state run handled 7,575 requests with zero failures. Aggregate
p95 was 140 ms; per-route p95 was login 180 ms, charts 26 ms, status 25 ms and history 24 ms.
The five-minute local availability window recorded 30/30 successful samples (100%).
This is a bounded rehearsal measurement, not a long-term availability claim. SonarQube's
actual final gate is OK with zero blocker/critical findings across backend, sandbox and
frontend source. Reference evaluation and five-job isolation also passed; see their JSON log.


Exact final performance, availability and SonarQube results are recorded in their JSON
files under `evidence/final` and summarized in FINAL_SUBMISSION_CHECKLIST.md. The initial
availability attempt coincided with SonarQube exhausting the local Docker memory budget;
that failed measurement is retained as `availability-resource-contention.json`. It is not
counted as a passing operational window. The isolated final window is reported separately.

## Acceptance and outstanding evidence

All automated test results above pass. The original USA-01 calls for five first-time
participants; no participant study is fabricated by these browser checks. Full NFR-008
still needs the actual Windows Docker installation and current Firefox/Edge evidence.
The required historical sprint videos and individual viva explanations must be supplied by
the team. Record acceptance/sign-off after reviewing these items and the current quality
results. A closed issue alone does not establish that its evidence exists.
