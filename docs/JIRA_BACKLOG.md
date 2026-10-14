# Jira delivery backlog

The approved Team 13 document defines six two-week academic sprints. The Jira request is for three sprints, so each Jira delivery sprint below groups two consecutive academic sprints. This preserves the approved 12-week plan while keeping the board at three sprints.

## Team ownership

- M1 - Atharva Anand: Authentication and Workspace Management
- M2 - Atharva Rakesh Bidre: Dataset Ingestion and Schema Pre-Validation
- M3 - Ayush M Shetty: Sandboxed Model Execution and Metrics Engine
- M4 - Bhavesh Velluru: Benchmarking, Visual Analytics and Report Export

## Sprint 1 - Foundation, Authentication and Safe Ingestion

Academic weeks 1-4 (approved Sprints 1-2). Goal: establish a tested repository and let a user authenticate, upload artifacts, choose a target and receive a pre-validation report.

| Key | Story / task | Owner | Requirement IDs | Acceptance criteria |
|---|---|---|---|---|
| MLE-1 | Repository, CI and Docker Compose foundation | All / Atharva Anand | NFR-007..009, SEC-009 | Push/PR CI runs lint and tests; coverage gate is >=80%; secrets are environment-only; Compose topology is documented. |
| MLE-2 | Register, login, refresh and logout | Atharva Anand | FR-001..004, SEC-001..003, SEC-007 | Strong-password registration works; duplicate email is rejected; 15-minute access and rotating 7-day refresh tokens are issued; logout revokes refresh. |
| MLE-3 | Evaluation history and deletion | Atharva Anand | FR-005..006, SEC-008 | History is owned, paginated and filterable; deletion cascades to artifacts/reports; non-owner receives 404. |
| MLE-4 | Evaluator workspaces | Atharva Anand | FR-007 | Evaluator can create a workspace, add a member and view only workspace evaluations; USER receives 403. |
| MLE-5 | Model upload validation | Atharva Rakesh Bidre | FR-008, SEC-004 | Only pkl/joblib/onnx <=100 MB with matching signature is stored under a UUID name with SHA-256. |
| MLE-6 | CSV ingestion and target selection | Atharva Rakesh Bidre | FR-009..011 | CSV <=50 MB/500k rows is parsed; duplicate/empty headers and missing features are rejected; target is suggested and can be overridden. |
| MLE-7 | Model-dataset compatibility report | Atharva Rakesh Bidre | FR-012..013, BR-01, BR-06..07 | Safe inspection reports PASSED/FAILED with each expected and actual value; target never enters features. |
| MLE-8 | Sprint 1 automated evidence | M1 + M2 | UT/IT/ST-AUTH, UT/IT/ST-ING | Planned unit/integration cases run in CI; system scripts and actual result fields are prepared. |

## Sprint 2 - Sandboxed Evaluation, Metrics and Model Comparison

Academic weeks 5-8 (approved Sprints 3-4). Goal: execute validated models in a locked-down asynchronous worker and turn stored results into trustworthy dashboards, comparisons and exports.

| Key | Story / task | Owner | Requirement IDs | Acceptance criteria |
|---|---|---|---|---|
| MLE-9 | Asynchronous evaluation lifecycle | Ayush M Shetty | FR-014, FR-019, FR-021 | POST returns 202/QUEUED; legal status transitions persist; successful metrics/charts are retrievable. |
| MLE-10 | Task detection and trusted metric engine | Ayush M Shetty | FR-015, FR-017..018 | Classification/regression detection can be overridden; STP hand-computed metric vectors pass exactly. |
| MLE-11 | Hardened per-job sandbox | Ayush M Shetty | FR-016, SEC-005, BR-06 | No network/root/capabilities; read-only root; CPU/memory/PID/time limits; only X/model mounted; labels stay outside. |
| MLE-12 | Timeout, cleanup and sanitized failure handling | Ayush M Shetty | FR-019..020, NFR-006, SEC-006, SEC-010 | 120 s jobs are killed and removed; no job remains RUNNING >5 min; error contains no path/trace; audit event exists. |
| MLE-13 | Results dashboards and chart contracts | Bhavesh Velluru | FR-022 | Classification and regression dashboards render required cards/plots from documented chart JSON. |
| MLE-14 | Comparison guard and best-value highlighting | Bhavesh Velluru | FR-023..024, FR-027, BR-02 | Only 2-5 SUCCEEDED results with identical dataset checksum/task compare; correct direction selects each winner. |
| MLE-15 | JSON and PDF report export | Bhavesh Velluru | FR-025..026, Appendix B | Evaluation/comparison exports include owner, IDs, checksums, task, metrics, charts, status, duration and sandbox tag; unauthorized export fails. |
| MLE-16 | Sprint 2 security and integration evidence | M3 + M4 | IT/ST-EXE, UT/IT/ST-REP, ST-SEC-07..09 | Real sandbox policy and hostile fixtures pass; dashboards and both exports open; comparison negative tests pass. |

## Sprint 3 - Integration, Hardening, Validation and Release

Academic weeks 9-12 (approved Sprints 5-6). Goal: integrate all modules, prove the measurable NFR/security targets, close defects, and package reproducible final evidence.

| Key | Story / task | Owner | Requirement IDs | Acceptance criteria |
|---|---|---|---|---|
| MLE-17 | End-to-end React workflow | M2 + M4 | UI-01..08, NFR-005 | Register -> Login -> New Evaluation -> Dashboard uses <=5 primary screens; history, compare, workspace/admin views follow API auth. |
| MLE-18 | Authorization and input-security matrix | M1 + M2 | SEC-001..004, SEC-007..010 | Token, RBAC, IDOR, injection, traversal, upload-size and rate-limit cases execute with expected 401/403/404/413/429 results. |
| MLE-19 | Performance, concurrency and reliability validation | M3 + M4 | NFR-001..006, NFR-011 | 95p API <=500 ms at 50 users; reference evaluation <=60 s; 50 MB validation <=20 s; five jobs isolate; crash cleanup passes. |
| MLE-20 | Portability, retention and quality gate | All | NFR-007..010 | Compose starts on two OSes; 31-day artifacts purge; backend coverage >=80%; no blocker/critical static-analysis finding. |
| MLE-21 | Full regression, security and usability execution | All | ST-SEC-01..13, PERF/REL/USA/PORT/RET | 100% High requirements pass; >=90% all cases pass; Actual Result and Pass/Fail are recorded; High/Critical defects are closed. |
| MLE-22 | Traceability and validation report | All | FR-001..027, SEC-001..010, NFR-001..011 | Requirement -> architecture -> design -> code -> unit/integration -> system links are complete; defects include root cause/fix/retest. |
| MLE-23 | Final report, maintenance plan and demo evidence | All | Course submission guide | Numbered/captioned screenshots, Git/Jira/PR/CI/security evidence, final consolidated report, maintenance plan and 15-minute demo deck are complete. |
| MLE-24 | Risk register and sprint retrospectives | All | Project governance | Risks, mitigations, owners and review dates are current; each delivery sprint records completed work, carry-over, impediments and agreed improvements. |

## Definition of done for every Jira story

1. Requirement IDs and acceptance criteria are present.
2. Implementation is pushed on a branch and linked to the Jira key.
3. At least one teammate reviews the pull request.
4. Unit/integration tests pass in CI; relevant negative/security test is included.
5. Documentation and traceability are updated.
6. The owner can explain the implementation and evidence.

